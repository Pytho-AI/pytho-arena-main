import { createHash } from "node:crypto";
import { createServer } from "node:http";
import { pathToFileURL } from "node:url";

export const FRAME_SERVER_BIND_HOST = "127.0.0.1";
export const FRAME_SERVER_PORT = 46_000;
export const FRAME_SERVER_MAX_MESSAGE_BYTES = 8 * 1024 * 1024;

const websocketGuid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";
const assetIds = new Set([
  "mq_1l_usa",
  "uav_orion",
  "quadcopter_surrogate",
  "nasams_fcs",
  "range_watch_tower",
  "cargo_ship_liberty",
]);
const entityClasses = new Set(["fixed-wing", "multirotor", "sensor", "ground-vehicle", "ship", "effect"]);
const entityStatuses = new Set(["active", "neutralized", "penetrated", "complete", "offline"]);
const utf8Decoder = new TextDecoder("utf-8", { fatal: true });

function websocketFrame(opcode, payload) {
  const body = Buffer.isBuffer(payload) ? payload : Buffer.from(payload, "utf8");
  if (body.length < 126) return Buffer.concat([Buffer.from([0x80 | opcode, body.length]), body]);
  if (body.length <= 0xffff) {
    const header = Buffer.allocUnsafe(4);
    header[0] = 0x80 | opcode;
    header[1] = 126;
    header.writeUInt16BE(body.length, 2);
    return Buffer.concat([header, body]);
  }
  const header = Buffer.allocUnsafe(10);
  header[0] = 0x80 | opcode;
  header[1] = 127;
  header.writeBigUInt64BE(BigInt(body.length), 2);
  return Buffer.concat([header, body]);
}

function isPosition(position) {
  return position
    && typeof position === "object"
    && Number.isFinite(position.east)
    && Number.isFinite(position.up)
    && Number.isFinite(position.north);
}

function isAttitude(attitude) {
  return attitude
    && typeof attitude === "object"
    && Number.isFinite(attitude.heading)
    && Number.isFinite(attitude.pitch)
    && Number.isFinite(attitude.roll);
}

function validateFramePayload(payload) {
  if (!Buffer.isBuffer(payload) || payload.length > FRAME_SERVER_MAX_MESSAGE_BYTES) {
    throw new RangeError(`frame-v1 payload exceeds ${FRAME_SERVER_MAX_MESSAGE_BYTES} bytes`);
  }
  const parsed = JSON.parse(utf8Decoder.decode(payload));
  if (
    !parsed
    || typeof parsed !== "object"
    || parsed.schemaVersion !== 1
    || parsed.type !== "frame"
    || typeof parsed.runId !== "string"
    || parsed.runId.length === 0
    || !Number.isSafeInteger(parsed.sequence)
    || parsed.sequence < 0
    || !Number.isFinite(parsed.simTimeSec)
    || parsed.simTimeSec < 0
    || parsed.coordinateFrame !== "ENU"
    || !Array.isArray(parsed.entities)
    || parsed.entities.length > 2_000
    || (parsed.tracks !== undefined && !Array.isArray(parsed.tracks))
    || (parsed.events !== undefined && !Array.isArray(parsed.events))
  ) {
    throw new Error("payload does not match the frame-v1 envelope");
  }
  const ids = new Set();
  for (const entity of parsed.entities) {
    if (
      !entity
      || typeof entity !== "object"
      || typeof entity.id !== "string"
      || entity.id.length === 0
      || ids.has(entity.id)
      || !entityClasses.has(entity.entityClass)
      || !assetIds.has(entity.assetId)
      || !isPosition(entity.positionM)
      || (entity.attitudeDeg !== undefined && !isAttitude(entity.attitudeDeg))
      || !entityStatuses.has(entity.status)
      || (entity.visible !== undefined && typeof entity.visible !== "boolean")
    ) {
      throw new Error("frame-v1 entity is invalid or uses an unknown assetId");
    }
    ids.add(entity.id);
  }
  for (const track of parsed.tracks ?? []) {
    if (
      !track
      || typeof track !== "object"
      || typeof track.id !== "string"
      || track.id.length === 0
      || !isPosition(track.positionM)
      || !Number.isFinite(track.confidence)
      || track.confidence < 0
      || track.confidence > 1
    ) {
      throw new Error("frame-v1 track is invalid");
    }
  }
  if ((parsed.events ?? []).some((event) => !event || typeof event !== "object" || Array.isArray(event))) {
    throw new Error("frame-v1 event is invalid");
  }
}

function closeWithPolicyError(socket) {
  const code = Buffer.allocUnsafe(2);
  code.writeUInt16BE(1008);
  socket.end(websocketFrame(0x8, code));
}

function handleClientData(socket, incoming, onText) {
  socket.frameBuffer = Buffer.concat([socket.frameBuffer ?? Buffer.alloc(0), incoming]);
  while (socket.frameBuffer.length >= 2) {
    const first = socket.frameBuffer[0];
    const second = socket.frameBuffer[1];
    const masked = (second & 0x80) !== 0;
    const final = (first & 0x80) !== 0;
    let length = second & 0x7f;
    let offset = 2;
    if (length === 126) {
      if (socket.frameBuffer.length < 4) return;
      length = socket.frameBuffer.readUInt16BE(2);
      offset = 4;
    } else if (length === 127) {
      if (socket.frameBuffer.length < 10) return;
      const longLength = socket.frameBuffer.readBigUInt64BE(2);
      if (longLength > BigInt(Number.MAX_SAFE_INTEGER)) return socket.destroy();
      length = Number(longLength);
      offset = 10;
    }
    if (!masked || length > FRAME_SERVER_MAX_MESSAGE_BYTES) return closeWithPolicyError(socket);
    const maskBytes = masked ? 4 : 0;
    if (socket.frameBuffer.length < offset + maskBytes + length) return;
    const mask = masked ? socket.frameBuffer.subarray(offset, offset + 4) : undefined;
    offset += maskBytes;
    const payload = Buffer.from(socket.frameBuffer.subarray(offset, offset + length));
    socket.frameBuffer = socket.frameBuffer.subarray(offset + length);
    if (mask) for (let index = 0; index < payload.length; index += 1) payload[index] ^= mask[index % 4];
    const opcode = first & 0x0f;
    if (opcode === 0x8) {
      socket.end(websocketFrame(0x8, payload));
      return;
    }
    if (opcode === 0x9) socket.write(websocketFrame(0xA, payload));
    if (opcode === 0x1) {
      if (!final) return closeWithPolicyError(socket);
      onText(socket, payload);
    }
  }
}

export class LoopbackFrameServer {
  bindHost = FRAME_SERVER_BIND_HOST;
  port;
  #server;
  #clients = new Set();

  constructor({ port = FRAME_SERVER_PORT } = {}) {
    if (!Number.isSafeInteger(port) || port < 0 || port > 65_535) throw new RangeError("port must be between 0 and 65535");
    this.port = port;
    this.#server = createServer((_request, response) => {
      response.writeHead(426, { Connection: "close", "Content-Type": "text/plain" });
      response.end("WebSocket connection required\n");
    });
    this.#server.on("upgrade", (request, socket) => this.#upgrade(request, socket));
  }

  get ready() {
    return this.#clients.size > 0;
  }

  get listeningPort() {
    const address = this.#server.address();
    return typeof address === "object" && address ? address.port : undefined;
  }

  start() {
    if (this.#server.listening) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const onError = (error) => {
        this.#server.off("listening", onListening);
        reject(error);
      };
      const onListening = () => {
        this.#server.off("error", onError);
        resolve();
      };
      this.#server.once("error", onError);
      this.#server.once("listening", onListening);
      this.#server.listen(this.port, this.bindHost);
    });
  }

  send(payload) {
    if (typeof payload !== "string") throw new TypeError("WebSocket payload must be text");
    const bytes = Buffer.from(payload, "utf8");
    validateFramePayload(bytes);
    const frame = websocketFrame(0x1, bytes);
    for (const socket of this.#clients) socket.write(frame);
  }

  close() {
    for (const socket of this.#clients) socket.destroy();
    this.#clients.clear();
    if (!this.#server.listening) return Promise.resolve();
    return new Promise((resolve, reject) => {
      this.#server.close((error) => error ? reject(error) : resolve());
    });
  }

  #upgrade(request, socket) {
    const key = request.headers["sec-websocket-key"];
    if (
      request.headers.upgrade?.toLowerCase() !== "websocket"
      || typeof key !== "string"
      || request.socket.remoteAddress !== FRAME_SERVER_BIND_HOST
    ) {
      socket.destroy();
      return;
    }
    const accept = createHash("sha1").update(key + websocketGuid).digest("base64");
    socket.write([
      "HTTP/1.1 101 Switching Protocols",
      "Upgrade: websocket",
      "Connection: Upgrade",
      `Sec-WebSocket-Accept: ${accept}`,
      "\r\n",
    ].join("\r\n"));
    this.#clients.add(socket);
    socket.on("data", (data) => handleClientData(socket, data, (source, payload) => this.#relay(source, payload)));
    socket.on("close", () => this.#clients.delete(socket));
    socket.on("error", () => this.#clients.delete(socket));
  }

  #relay(source, payload) {
    try {
      validateFramePayload(payload);
    } catch {
      closeWithPolicyError(source);
      return;
    }
    const frame = websocketFrame(0x1, payload);
    for (const socket of this.#clients) {
      if (socket !== source) socket.write(frame);
    }
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const server = new LoopbackFrameServer();
  await server.start();
  process.stdout.write(`frame-v1 server listening on ws://${server.bindHost}:${server.listeningPort}/\n`);
  const stop = async () => {
    await server.close();
    process.exit(0);
  };
  process.once("SIGINT", stop);
  process.once("SIGTERM", stop);
}
