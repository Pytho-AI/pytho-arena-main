#include "pythoFrameWs.h"

#include <daScript/daScript.h>

#include <EASTL/string.h>

#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <poll.h>
#include <sys/socket.h>
#include <unistd.h>

#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <mutex>

namespace pytho_frame_ws
{
namespace
{
constexpr uint16_t endpoint_port = 46000;
constexpr unsigned max_message_bytes = 8 * 1024 * 1024;
constexpr auto reconnect_delay = std::chrono::seconds(1);
constexpr char handshake_request[] =
  "GET / HTTP/1.1\r\n"
  "Host: 127.0.0.1:46000\r\n"
  "Upgrade: websocket\r\n"
  "Connection: Upgrade\r\n"
  "Sec-WebSocket-Version: 13\r\n"
  "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
  "\r\n";
constexpr char expected_accept[] = "Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=";

enum class Phase
{
  disconnected,
  connecting,
  handshake,
  open
};

int socket_fd = -1;
Phase phase = Phase::disconnected;
std::chrono::steady_clock::time_point next_connect_at{};
eastl::string receive_buffer;
eastl::string transmit_buffer;
eastl::string fragmented_message;
uint8_t fragmented_opcode = 0;
uint32_t mask_seed = 0x50595448U;
std::atomic<bool> connected{false};
std::mutex queue_mutex;
eastl::string pending_message;

void disconnect()
{
  if (socket_fd >= 0)
    close(socket_fd);
  socket_fd = -1;
  phase = Phase::disconnected;
  connected = false;
  next_connect_at = std::chrono::steady_clock::now() + reconnect_delay;
  receive_buffer.clear();
  transmit_buffer.clear();
  fragmented_message.clear();
  fragmented_opcode = 0;
}

void flush_transmit()
{
  while (socket_fd >= 0 && !transmit_buffer.empty())
  {
    const ssize_t sent = send(socket_fd, transmit_buffer.data(), transmit_buffer.size(), 0);
    if (sent > 0)
    {
      transmit_buffer.erase(0, static_cast<size_t>(sent));
      continue;
    }
    if (sent < 0 && (errno == EAGAIN || errno == EWOULDBLOCK))
      return;
    disconnect();
    return;
  }
}

void queue_client_frame(uint8_t opcode, const char *payload, size_t payload_size)
{
  if (payload_size > 125 || phase != Phase::open)
    return;

  char header[8];
  size_t header_size = 0;
  header[header_size++] = static_cast<char>(0x80U | opcode);
  header[header_size++] = static_cast<char>(0x80U | payload_size);
  mask_seed = mask_seed * 1664525U + 1013904223U;
  const uint8_t mask[4] = {
    static_cast<uint8_t>(mask_seed >> 24), static_cast<uint8_t>(mask_seed >> 16),
    static_cast<uint8_t>(mask_seed >> 8), static_cast<uint8_t>(mask_seed)};
  for (uint8_t byte : mask)
    header[header_size++] = static_cast<char>(byte);
  transmit_buffer.append(header, header_size);
  for (size_t i = 0; i < payload_size; ++i)
    transmit_buffer.push_back(static_cast<char>(static_cast<uint8_t>(payload[i]) ^ mask[i & 3]));
}

void publish_text(eastl::string &&message)
{
  if (message.empty() || message.size() > max_message_bytes)
    return;
  std::lock_guard<std::mutex> lock(queue_mutex);
  pending_message = eastl::move(message);
}

bool parse_one_frame()
{
  if (receive_buffer.size() < 2)
    return false;

  const auto *bytes = reinterpret_cast<const uint8_t *>(receive_buffer.data());
  const bool final_frame = (bytes[0] & 0x80U) != 0;
  const uint8_t opcode = bytes[0] & 0x0fU;
  const bool masked = (bytes[1] & 0x80U) != 0;
  uint64_t payload_size = bytes[1] & 0x7fU;
  size_t offset = 2;

  if (payload_size == 126)
  {
    if (receive_buffer.size() < offset + 2)
      return false;
    payload_size = (static_cast<uint64_t>(bytes[offset]) << 8) | bytes[offset + 1];
    offset += 2;
  }
  else if (payload_size == 127)
  {
    if (receive_buffer.size() < offset + 8)
      return false;
    payload_size = 0;
    for (unsigned i = 0; i < 8; ++i)
      payload_size = (payload_size << 8) | bytes[offset + i];
    offset += 8;
  }

  if (payload_size > max_message_bytes || payload_size + fragmented_message.size() > max_message_bytes)
  {
    disconnect();
    return false;
  }

  uint8_t mask[4]{};
  if (masked)
  {
    if (receive_buffer.size() < offset + 4)
      return false;
    std::memcpy(mask, bytes + offset, sizeof(mask));
    offset += 4;
  }
  if (payload_size > receive_buffer.size() - offset)
    return false;

  eastl::string payload(receive_buffer.data() + offset, static_cast<size_t>(payload_size));
  if (masked)
    for (size_t i = 0; i < payload.size(); ++i)
      payload[i] = static_cast<char>(static_cast<uint8_t>(payload[i]) ^ mask[i & 3]);
  receive_buffer.erase(0, offset + static_cast<size_t>(payload_size));

  if (opcode == 0x8)
  {
    disconnect();
    return false;
  }
  if (opcode == 0x9)
  {
    queue_client_frame(0xA, payload.data(), payload.size());
    return true;
  }
  if (opcode == 0xA)
    return true;
  if (opcode == 0x1)
  {
    if (final_frame)
      publish_text(eastl::move(payload));
    else
    {
      fragmented_opcode = opcode;
      fragmented_message = eastl::move(payload);
    }
    return true;
  }
  if (opcode == 0x0 && fragmented_opcode == 0x1)
  {
    fragmented_message.append(payload);
    if (final_frame)
    {
      publish_text(eastl::move(fragmented_message));
      fragmented_message.clear();
      fragmented_opcode = 0;
    }
  }
  return true;
}

void receive_available()
{
  char buffer[64 * 1024];
  while (socket_fd >= 0)
  {
    const ssize_t received = recv(socket_fd, buffer, sizeof(buffer), 0);
    if (received > 0)
    {
      if (receive_buffer.size() + static_cast<size_t>(received) > max_message_bytes + 64 * 1024)
      {
        disconnect();
        return;
      }
      receive_buffer.append(buffer, static_cast<size_t>(received));
      continue;
    }
    if (received == 0)
    {
      disconnect();
      return;
    }
    if (errno == EAGAIN || errno == EWOULDBLOCK)
      break;
    disconnect();
    return;
  }
}

void poll_connect()
{
  pollfd descriptor{socket_fd, POLLOUT, 0};
  const int result = ::poll(&descriptor, 1, 0);
  if (result <= 0)
    return;
  int error = 0;
  socklen_t error_size = sizeof(error);
  if (getsockopt(socket_fd, SOL_SOCKET, SO_ERROR, &error, &error_size) != 0 || error != 0)
  {
    disconnect();
    return;
  }
  phase = Phase::handshake;
  transmit_buffer.assign(handshake_request, sizeof(handshake_request) - 1);
}

void poll_handshake()
{
  flush_transmit();
  if (phase != Phase::handshake)
    return;
  receive_available();
  if (phase != Phase::handshake)
    return;
  const auto header_end = receive_buffer.find("\r\n\r\n");
  if (header_end == eastl::string::npos)
    return;
  const eastl::string response = receive_buffer.substr(0, header_end + 4);
  receive_buffer.erase(0, header_end + 4);
  if (response.find("HTTP/1.1 101") == eastl::string::npos || response.find(expected_accept) == eastl::string::npos)
  {
    disconnect();
    return;
  }
  phase = Phase::open;
  connected = true;
}
} // namespace

bool start()
{
  if (phase != Phase::disconnected)
    return true;
  if (std::chrono::steady_clock::now() < next_connect_at)
    return true;

  socket_fd = socket(AF_INET, SOCK_STREAM, 0);
  if (socket_fd < 0)
  {
    next_connect_at = std::chrono::steady_clock::now() + reconnect_delay;
    return false;
  }
#if defined(SO_NOSIGPIPE)
  const int no_sigpipe = 1;
  if (setsockopt(socket_fd, SOL_SOCKET, SO_NOSIGPIPE, &no_sigpipe, sizeof(no_sigpipe)) != 0)
  {
    disconnect();
    return false;
  }
#endif
  const int flags = fcntl(socket_fd, F_GETFL, 0);
  if (flags < 0 || fcntl(socket_fd, F_SETFL, flags | O_NONBLOCK) != 0)
  {
    disconnect();
    return false;
  }

  sockaddr_in address{};
  address.sin_family = AF_INET;
  address.sin_port = htons(endpoint_port);
  address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
  const int result = connect(socket_fd, reinterpret_cast<sockaddr *>(&address), sizeof(address));
  if (result == 0)
  {
    phase = Phase::handshake;
    transmit_buffer.assign(handshake_request, sizeof(handshake_request) - 1);
  }
  else if (errno == EINPROGRESS)
    phase = Phase::connecting;
  else
    disconnect();
  return true;
}

void poll()
{
  if (phase == Phase::connecting)
    poll_connect();
  if (phase == Phase::handshake)
    poll_handshake();
  if (phase != Phase::open)
    return;
  flush_transmit();
  receive_available();
  while (phase == Phase::open && parse_one_frame())
  {}
}

bool is_connected() { return connected; }

char *take_message(das::Context *context, das::LineInfoArg *at)
{
  eastl::string message;
  {
    std::lock_guard<std::mutex> lock(queue_mutex);
    if (pending_message.empty())
      return nullptr;
    message = eastl::move(pending_message);
    pending_message.clear();
  }
  return context->allocateString(message.c_str(), message.size(), at);
}

void reset()
{
  disconnect();
  next_connect_at = {};
  std::lock_guard<std::mutex> lock(queue_mutex);
  pending_message.clear();
}
} // namespace pytho_frame_ws

namespace bind_dascript
{
class PythoFrameWsModule final : public das::Module
{
public:
  PythoFrameWsModule() : das::Module("PythoFrameWs")
  {
    das::ModuleLibrary lib(this);
    das::addExtern<DAS_BIND_FUN(pytho_frame_ws::start)>(*this, lib, "pytho_ws_start", das::SideEffects::modifyExternal,
      "pytho_frame_ws::start");
    das::addExtern<DAS_BIND_FUN(pytho_frame_ws::poll)>(*this, lib, "pytho_ws_poll", das::SideEffects::modifyExternal,
      "pytho_frame_ws::poll");
    das::addExtern<DAS_BIND_FUN(pytho_frame_ws::is_connected)>(*this, lib, "pytho_ws_is_connected",
      das::SideEffects::accessExternal, "pytho_frame_ws::is_connected");
    das::addExtern<DAS_BIND_FUN(pytho_frame_ws::take_message)>(*this, lib, "pytho_ws_take_message",
      das::SideEffects::modifyExternal, "pytho_frame_ws::take_message");
    das::addExtern<DAS_BIND_FUN(pytho_frame_ws::reset)>(*this, lib, "pytho_ws_reset", das::SideEffects::modifyExternal,
      "pytho_frame_ws::reset");
    verifyAotReady();
  }

  das::ModuleAotType aotRequire(das::TextWriter &writer) const override
  {
    writer << "#include \"pythoFrameWs.h\"\n";
    return das::ModuleAotType::cpp;
  }
};
} // namespace bind_dascript

REGISTER_MODULE_IN_NAMESPACE(PythoFrameWsModule, bind_dascript)
