#include "nozzle_unity/nozzle_unity_bridge.h"

#include "nozzle_unity_environment.hpp"

#include <stddef.h>
#include <stdio.h>
#include <string.h>

namespace {

void write_status_message(char *destination, size_t capacity, const char *message) {
    if(destination == nullptr || capacity == 0) {
        return;
    }

    if(message == nullptr) {
        message = "nozzle_unity bridge status is unavailable";
    }

    const int written = snprintf(destination, capacity, "%s", message);
    if(written < 0) {
        destination[0] = '\0';
        return;
    }

    destination[capacity - 1] = '\0';
}

void clear_sender_info_array(nozzle_unity_sender_info_array *array) {
    if(array == nullptr) {
        return;
    }
    array->items = nullptr;
    array->count = 0;
}

int32_t unsupported_runtime_status() {
    return (int32_t)nozzle_unity_status_unsupported;
}

} // namespace

extern "C" {

NOZZLE_UNITY_API int32_t nozzle_unity_get_support(nozzle_unity_support_info *out_support) {
    if(out_support == nullptr) {
        return (int32_t)nozzle_unity_status_invalid_argument;
    }

    memset(out_support, 0, sizeof(nozzle_unity_support_info));
    out_support->abi_version = NOZZLE_UNITY_ABI_VERSION;
    out_support->bridge_binary_loaded = 1;
    out_support->runtime_supported = 0;
    out_support->unity_headers_compiled = (uint32_t)nozzle_unity_environment_has_unity_headers();
    out_support->unity_graphics_device_available = (uint32_t)nozzle_unity_environment_has_graphics_device();
    out_support->render_thread_events_available = nozzle_unity_environment_render_event_func() != nullptr ? 1u : 0u;
    out_support->direct_nozzle_c_abi_available = 0;
    write_status_message(
        out_support->status_message,
        NOZZLE_UNITY_STATUS_MESSAGE_CAPACITY,
        nozzle_unity_environment_status_message()
    );

    return (int32_t)nozzle_unity_status_ok;
}

NOZZLE_UNITY_API const char *nozzle_unity_get_version(void) {
    return "0.1.0-bridge-abi.1";
}

NOZZLE_UNITY_API nozzle_unity_render_event_func nozzle_unity_get_render_event_func(void) {
    return nozzle_unity_environment_render_event_func();
}

NOZZLE_UNITY_API int32_t nozzle_unity_sender_create(
    const nozzle_unity_sender_desc *desc,
    nozzle_unity_sender_t **out_sender
) {
    (void)desc;
    if(out_sender == nullptr) {
        return (int32_t)nozzle_unity_status_invalid_argument;
    }
    *out_sender = nullptr;
    return unsupported_runtime_status();
}

NOZZLE_UNITY_API void nozzle_unity_sender_destroy(nozzle_unity_sender_t *sender) {
    (void)sender;
}

NOZZLE_UNITY_API int32_t nozzle_unity_sender_publish_native_texture(
    nozzle_unity_sender_t *sender,
    void *native_texture,
    uint32_t width,
    uint32_t height,
    int32_t texture_format
) {
    (void)sender;
    (void)native_texture;
    (void)width;
    (void)height;
    (void)texture_format;
    return unsupported_runtime_status();
}

NOZZLE_UNITY_API int32_t nozzle_unity_receiver_create(
    const nozzle_unity_receiver_desc *desc,
    nozzle_unity_receiver_t **out_receiver
) {
    (void)desc;
    if(out_receiver == nullptr) {
        return (int32_t)nozzle_unity_status_invalid_argument;
    }
    *out_receiver = nullptr;
    return unsupported_runtime_status();
}

NOZZLE_UNITY_API void nozzle_unity_receiver_destroy(nozzle_unity_receiver_t *receiver) {
    (void)receiver;
}

NOZZLE_UNITY_API int32_t nozzle_unity_receiver_acquire_frame(
    nozzle_unity_receiver_t *receiver,
    const nozzle_unity_acquire_desc *desc,
    nozzle_unity_frame_t **out_frame
) {
    (void)receiver;
    (void)desc;
    if(out_frame == nullptr) {
        return (int32_t)nozzle_unity_status_invalid_argument;
    }
    *out_frame = nullptr;
    return unsupported_runtime_status();
}

NOZZLE_UNITY_API void nozzle_unity_frame_release(nozzle_unity_frame_t *frame) {
    (void)frame;
}

NOZZLE_UNITY_API int32_t nozzle_unity_frame_get_info(
    nozzle_unity_frame_t *frame,
    nozzle_unity_frame_info *out_info
) {
    (void)frame;
    if(out_info == nullptr) {
        return (int32_t)nozzle_unity_status_invalid_argument;
    }
    memset(out_info, 0, sizeof(nozzle_unity_frame_info));
    return unsupported_runtime_status();
}

NOZZLE_UNITY_API int32_t nozzle_unity_frame_copy_to_native_texture(
    nozzle_unity_frame_t *frame,
    void *native_texture,
    uint32_t width,
    uint32_t height,
    int32_t texture_format
) {
    (void)frame;
    (void)native_texture;
    (void)width;
    (void)height;
    (void)texture_format;
    return unsupported_runtime_status();
}

NOZZLE_UNITY_API int32_t nozzle_unity_discovery_enumerate_senders(
    nozzle_unity_sender_info_array *out_array
) {
    if(out_array == nullptr) {
        return (int32_t)nozzle_unity_status_invalid_argument;
    }
    clear_sender_info_array(out_array);
    return unsupported_runtime_status();
}

NOZZLE_UNITY_API void nozzle_unity_discovery_free_sender_info_array(
    nozzle_unity_sender_info_array *array
) {
    clear_sender_info_array(array);
}

} // extern "C"
