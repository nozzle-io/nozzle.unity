#include "nozzle_unity_environment.hpp"

#include "IUnityGraphics.h"
#if defined(_WIN32)
    #include <d3d11.h>
    #include "IUnityGraphicsD3D11.h"
#endif
#include "IUnityInterface.h"

#include <stdio.h>

namespace {

IUnityInterfaces *unity_interfaces = nullptr;
IUnityGraphics *unity_graphics = nullptr;
int32_t graphics_device_available = 0;
int32_t runtime_backend_available = 0;
int32_t backend = 0;
void *native_device = nullptr;
UnityGfxRenderer renderer = kUnityGfxRendererNull;
char status_message[NOZZLE_UNITY_STATUS_MESSAGE_CAPACITY] = "nozzle_unity Unity-header bridge loaded before Unity graphics initialization";

#if defined(__APPLE__)
extern "C" void *nozzle_unity_environment_get_metal_device(IUnityInterfaces *unity_interfaces);
#endif

void write_status_message(const char *message) {
    if(message == nullptr) {
        message = "nozzle_unity Unity-header bridge status unavailable";
    }
    const int written = snprintf(status_message, sizeof(status_message), "%s", message);
    if(written < 0) {
        status_message[0] = '\0';
        return;
    }
    status_message[sizeof(status_message) - 1] = '\0';
}

void refresh_graphics_device_state() {
    runtime_backend_available = 0;
    backend = 0;
    native_device = nullptr;
    renderer = kUnityGfxRendererNull;

    if(unity_graphics == nullptr) {
        write_status_message("nozzle_unity Unity-header bridge loaded, but IUnityGraphics is unavailable");
        return;
    }

    renderer = unity_graphics->GetRenderer();
    switch(renderer) {
        case kUnityGfxRendererMetal: {
#if defined(__APPLE__)
            native_device = nozzle_unity_environment_get_metal_device(unity_interfaces);
            backend = 2;
            runtime_backend_available = native_device != nullptr ? 1 : 0;
            write_status_message(
                runtime_backend_available
                    ? "nozzle_unity Unity-header bridge ready for Metal runtime backend"
                    : "nozzle_unity Metal renderer detected, but IUnityGraphicsMetal device is unavailable"
            );
#else
            write_status_message("nozzle_unity Metal renderer is unsupported on this host build");
#endif
            break;
        }
        case kUnityGfxRendererD3D11: {
#if defined(_WIN32)
            IUnityGraphicsD3D11 *d3d11 = unity_interfaces != nullptr
                ? unity_interfaces->Get<IUnityGraphicsD3D11>()
                : nullptr;
            native_device = d3d11 != nullptr && d3d11->GetDevice != nullptr
                ? (void *)d3d11->GetDevice()
                : nullptr;
            backend = 1;
            runtime_backend_available = native_device != nullptr ? 1 : 0;
            write_status_message(
                runtime_backend_available
                    ? "nozzle_unity Unity-header bridge ready for D3D11 runtime backend"
                    : "nozzle_unity D3D11 renderer detected, but IUnityGraphicsD3D11 device is unavailable"
            );
#else
            write_status_message("nozzle_unity D3D11 renderer is unsupported on this host build");
#endif
            break;
        }
        case kUnityGfxRendererNull:
            write_status_message("nozzle_unity Unity graphics renderer is Null; runtime backend is unavailable");
            break;
        default:
            write_status_message("nozzle_unity Unity graphics renderer is unsupported; only Metal and D3D11 are targeted");
            break;
    }
}

void UNITY_INTERFACE_API on_graphics_device_event(UnityGfxDeviceEventType event_type) {
    switch(event_type) {
        case kUnityGfxDeviceEventInitialize:
            graphics_device_available = 1;
            refresh_graphics_device_state();
            break;
        case kUnityGfxDeviceEventShutdown:
            graphics_device_available = 0;
            runtime_backend_available = 0;
            backend = 0;
            native_device = nullptr;
            renderer = kUnityGfxRendererNull;
            write_status_message("nozzle_unity Unity graphics device shutdown; runtime backend unavailable");
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
    } else {
        write_status_message("nozzle_unity Unity-header bridge loaded, but IUnityGraphics is unavailable");
    }
}

UNITY_INTERFACE_EXPORT void UNITY_INTERFACE_API UnityPluginUnload() {
    if(unity_graphics != nullptr) {
        unity_graphics->UnregisterDeviceEventCallback(on_graphics_device_event);
    }
    graphics_device_available = 0;
    runtime_backend_available = 0;
    backend = 0;
    native_device = nullptr;
    renderer = kUnityGfxRendererNull;
    write_status_message("nozzle_unity Unity plugin unloaded; runtime backend unavailable");
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

int32_t nozzle_unity_environment_runtime_backend_available() {
    return runtime_backend_available;
}

int32_t nozzle_unity_environment_backend() {
    return backend;
}

void *nozzle_unity_environment_native_device() {
    return native_device;
}

nozzle_unity_render_event_func nozzle_unity_environment_render_event_func() {
    return on_render_event;
}

const char *nozzle_unity_environment_status_message() {
    return status_message;
}
