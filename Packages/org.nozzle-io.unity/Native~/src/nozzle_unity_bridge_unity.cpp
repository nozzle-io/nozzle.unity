#include "nozzle_unity_environment.hpp"

#include "IUnityGraphics.h"
#include "IUnityInterface.h"

namespace {

IUnityInterfaces *unity_interfaces = nullptr;
IUnityGraphics *unity_graphics = nullptr;
int32_t graphics_device_available = 0;

void UNITY_INTERFACE_API on_graphics_device_event(UnityGfxDeviceEventType event_type) {
    switch(event_type) {
        case kUnityGfxDeviceEventInitialize:
            graphics_device_available = 1;
            break;
        case kUnityGfxDeviceEventShutdown:
            graphics_device_available = 0;
            nozzle_unity_cancel_all_operations("operation canceled by Unity graphics device shutdown");
            break;
        default:
            break;
    }
}

void UNITY_INTERFACE_API on_render_event(int event_id) {
    nozzle_unity_process_render_event(event_id);
}

} // namespace

extern "C" {

UNITY_INTERFACE_EXPORT void UNITY_INTERFACE_API UnityPluginLoad(IUnityInterfaces *interfaces) {
    unity_interfaces = interfaces;
    unity_graphics = unity_interfaces != nullptr ? unity_interfaces->Get<IUnityGraphics>() : nullptr;
    if(unity_graphics != nullptr) {
        unity_graphics->RegisterDeviceEventCallback(on_graphics_device_event);
        on_graphics_device_event(kUnityGfxDeviceEventInitialize);
    }
}

UNITY_INTERFACE_EXPORT void UNITY_INTERFACE_API UnityPluginUnload() {
    if(unity_graphics != nullptr) {
        unity_graphics->UnregisterDeviceEventCallback(on_graphics_device_event);
    }
    graphics_device_available = 0;
    nozzle_unity_cancel_all_operations("operation canceled by Unity plugin unload");
    unity_graphics = nullptr;
    unity_interfaces = nullptr;
}

} // extern "C"

int32_t nozzle_unity_environment_has_unity_headers() {
    return 1;
}

int32_t nozzle_unity_environment_has_graphics_device() {
    return graphics_device_available;
}

nozzle_unity_render_event_func nozzle_unity_environment_render_event_func() {
    return on_render_event;
}

const char *nozzle_unity_environment_status_message() {
    return "nozzle_unity Unity-header bridge loaded: Unity lifecycle callbacks are compiled, but nozzle runtime sender/receiver/discovery implementation is still not complete.";
}
