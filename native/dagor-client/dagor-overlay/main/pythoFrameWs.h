#pragma once

#include <daScript/daScript.h>

namespace pytho_frame_ws
{
bool start();
void poll();
bool is_connected();
char *take_message(das::Context *context, das::LineInfoArg *at);
void reset();
} // namespace pytho_frame_ws
