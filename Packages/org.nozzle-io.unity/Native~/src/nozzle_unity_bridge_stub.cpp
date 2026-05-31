#include "nozzle_unity_environment.hpp"

int32_t nozzle_unity_environment_has_unity_headers() {
    return 0;
}

int32_t nozzle_unity_environment_has_graphics_device() {
    return 0;
}

nozzle_unity_render_event_func nozzle_unity_environment_render_event_func() {
    return nullptr;
}

const char *nozzle_unity_environment_status_message() {
    return "nozzle_unity CI stub loaded: built without Unity Native Plugin API headers; runtime sender/receiver/discovery support is intentionally disabled.";
}
