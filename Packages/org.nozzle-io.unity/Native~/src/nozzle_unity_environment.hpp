#pragma once

#include "nozzle_unity/nozzle_unity_bridge.h"

#include <stdint.h>

int32_t nozzle_unity_environment_has_unity_headers();
int32_t nozzle_unity_environment_has_graphics_device();
nozzle_unity_render_event_func nozzle_unity_environment_render_event_func();
const char *nozzle_unity_environment_status_message();
