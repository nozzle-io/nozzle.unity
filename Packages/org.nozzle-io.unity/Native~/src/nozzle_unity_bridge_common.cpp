#include "nozzle_unity/nozzle_unity_bridge.h"

#include "nozzle_unity_environment.hpp"

#if defined(NOZZLE_UNITY_WITH_NOZZLE_CORE)
    #include "nozzle/nozzle_c.h"
#endif

#include <stddef.h>
#include <stdio.h>
#include <string.h>

#include <deque>
#include <mutex>
#include <vector>

namespace {

struct queued_operation {
    nozzle_unity_operation_id_t operation_id = 0;
    uint64_t managed_generation = 0;
    int32_t kind = (int32_t)nozzle_unity_operation_kind_unknown;
    int32_t state = (int32_t)nozzle_unity_operation_state_unknown;
    int32_t result = (int32_t)nozzle_unity_status_unknown;
    nozzle_unity_sender_t *sender = nullptr;
    nozzle_unity_receiver_t *receiver = nullptr;
    void *native_texture = nullptr;
    uint32_t width = 0;
    uint32_t height = 0;
    int32_t texture_format = 0;
    uint64_t timeout_ms = 0;
    uint64_t frame_index = 0;
    bool cancel_requested = false;
    char status_message[NOZZLE_UNITY_STATUS_MESSAGE_CAPACITY]{};
};

std::mutex queue_mutex;
std::deque<nozzle_unity_operation_id_t> pending_operation_ids;
std::vector<queued_operation> operation_records;
nozzle_unity_operation_id_t next_operation_id = 1;
uint64_t total_queued_operations = 0;
uint64_t total_running_operations = 0;
uint64_t total_completed_operations = 0;
uint64_t total_failed_operations = 0;
uint64_t total_canceled_operations = 0;
nozzle_unity_operation_id_t last_operation_id = 0;
int32_t last_operation_result = (int32_t)nozzle_unity_status_ok;
char last_queue_message[NOZZLE_UNITY_STATUS_MESSAGE_CAPACITY] = "nozzle_unity queue has not processed operations";

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

uint32_t direct_nozzle_c_abi_available() {
#if defined(NOZZLE_UNITY_WITH_NOZZLE_CORE)
    NozzleSenderDesc desc{};
    uint32_t fallback_flags{0};
    const NozzleErrorCode error_code = nozzle_resolve_fallback_flags(&desc, &fallback_flags);
    return error_code == NOZZLE_OK ? 1u : 0u;
#else
    return 0u;
#endif
}

void remember_queue_status(const char *message, int32_t result, nozzle_unity_operation_id_t operation_id) {
    write_status_message(last_queue_message, sizeof(last_queue_message), message);
    last_operation_result = result;
    last_operation_id = operation_id;
}

void complete_operation(queued_operation &operation, int32_t state, int32_t result, const char *message) {
    const int32_t previous_state = operation.state;
    operation.state = state;
    operation.result = result;
    write_status_message(operation.status_message, sizeof(operation.status_message), message);
    remember_queue_status(message, result, operation.operation_id);
    if(previous_state == (int32_t)nozzle_unity_operation_state_running && total_running_operations > 0) {
        total_running_operations -= 1;
    }
    if(state == (int32_t)nozzle_unity_operation_state_completed) {
        total_completed_operations += 1;
    } else if(state == (int32_t)nozzle_unity_operation_state_canceled) {
        total_canceled_operations += 1;
    } else {
        total_failed_operations += 1;
    }
}

void copy_operation_status(const queued_operation &operation, nozzle_unity_operation_status *out_status) {
    memset(out_status, 0, sizeof(nozzle_unity_operation_status));
    out_status->operation_id = operation.operation_id;
    out_status->managed_generation = operation.managed_generation;
    out_status->kind = operation.kind;
    out_status->state = operation.state;
    out_status->result = operation.result;
    out_status->frame_index = operation.frame_index;
    out_status->width = operation.width;
    out_status->height = operation.height;
    out_status->texture_format = operation.texture_format;
    write_status_message(
        out_status->status_message,
        NOZZLE_UNITY_STATUS_MESSAGE_CAPACITY,
        operation.status_message
    );
}

queued_operation *find_operation_record(nozzle_unity_operation_id_t operation_id) {
    for(queued_operation &operation : operation_records) {
        if(operation.operation_id == operation_id) {
            return &operation;
        }
    }
    return nullptr;
}

const queued_operation *find_operation_record_const(nozzle_unity_operation_id_t operation_id) {
    for(const queued_operation &operation : operation_records) {
        if(operation.operation_id == operation_id) {
            return &operation;
        }
    }
    return nullptr;
}

bool operation_matches_handle(const queued_operation &operation, nozzle_unity_sender_t *sender, nozzle_unity_receiver_t *receiver) {
    const bool sender_matches = sender != nullptr && operation.sender == sender;
    const bool receiver_matches = receiver != nullptr && operation.receiver == receiver;
    return sender_matches || receiver_matches;
}

int32_t enqueue_operation(queued_operation operation, nozzle_unity_operation_id_t *out_operation_id) {
    if(out_operation_id == nullptr) {
        return (int32_t)nozzle_unity_status_invalid_argument;
    }
    if(operation.native_texture == nullptr || operation.width == 0 || operation.height == 0) {
        *out_operation_id = 0;
        return (int32_t)nozzle_unity_status_invalid_argument;
    }

    std::lock_guard<std::mutex> lock(queue_mutex);
    operation.operation_id = next_operation_id;
    next_operation_id += 1;
    if(next_operation_id == 0) {
        next_operation_id = 1;
    }
    operation.state = (int32_t)nozzle_unity_operation_state_queued;
    operation.result = (int32_t)nozzle_unity_status_unknown;
    write_status_message(
        operation.status_message,
        sizeof(operation.status_message),
        "queued for Unity render-thread event processing"
    );
    operation_records.push_back(operation);
    pending_operation_ids.push_back(operation.operation_id);
    total_queued_operations += 1;
    last_operation_id = operation.operation_id;
    *out_operation_id = operation.operation_id;
    return (int32_t)nozzle_unity_status_ok;
}

int32_t cancel_matching_operations(nozzle_unity_sender_t *sender, nozzle_unity_receiver_t *receiver) {
    std::lock_guard<std::mutex> lock(queue_mutex);
    for(queued_operation &operation : operation_records) {
        if(!operation_matches_handle(operation, sender, receiver)) {
            continue;
        }
        if(operation.state == (int32_t)nozzle_unity_operation_state_queued) {
            complete_operation(
                operation,
                (int32_t)nozzle_unity_operation_state_canceled,
                (int32_t)nozzle_unity_status_unsupported,
                "operation canceled before render-thread execution"
            );
        } else if(operation.state == (int32_t)nozzle_unity_operation_state_running) {
            operation.cancel_requested = true;
            write_status_message(
                operation.status_message,
                sizeof(operation.status_message),
                "cancel requested while render-thread operation is running"
            );
            remember_queue_status(
                "cancel requested while render-thread operation is running",
                (int32_t)nozzle_unity_status_busy,
                operation.operation_id
            );
        }
    }
    return (int32_t)nozzle_unity_status_ok;
}

} // namespace

void nozzle_unity_process_render_event(int32_t event_id) {
    std::vector<nozzle_unity_operation_id_t> operation_ids_to_process;
    {
        std::lock_guard<std::mutex> lock(queue_mutex);
        std::deque<nozzle_unity_operation_id_t> kept_operation_ids;
        while(!pending_operation_ids.empty()) {
            const nozzle_unity_operation_id_t operation_id = pending_operation_ids.front();
            pending_operation_ids.pop_front();
            queued_operation *operation = find_operation_record(operation_id);
            if(operation == nullptr) {
                continue;
            }
            const bool sender_event = event_id == NOZZLE_UNITY_EVENT_SENDER_PUBLISH_NATIVE_TEXTURE
                && operation->kind == (int32_t)nozzle_unity_operation_kind_sender_publish_native_texture;
            const bool receiver_event = event_id == NOZZLE_UNITY_EVENT_RECEIVER_ACQUIRE_AND_COPY_NATIVE_TEXTURE
                && operation->kind == (int32_t)nozzle_unity_operation_kind_receiver_acquire_and_copy_native_texture;
            if((sender_event || receiver_event)
                && operation->state == (int32_t)nozzle_unity_operation_state_queued) {
                operation->state = (int32_t)nozzle_unity_operation_state_running;
                operation->result = (int32_t)nozzle_unity_status_busy;
                write_status_message(
                    operation->status_message,
                    sizeof(operation->status_message),
                    "render-thread operation is running"
                );
                total_running_operations += 1;
                operation_ids_to_process.push_back(operation_id);
            } else if(operation->state == (int32_t)nozzle_unity_operation_state_queued) {
                kept_operation_ids.push_back(operation_id);
            }
        }
        pending_operation_ids.swap(kept_operation_ids);
    }

    for(nozzle_unity_operation_id_t operation_id : operation_ids_to_process) {
        std::lock_guard<std::mutex> lock(queue_mutex);
        queued_operation *operation = find_operation_record(operation_id);
        if(operation == nullptr) {
            continue;
        }
        complete_operation(
            *operation,
            (int32_t)nozzle_unity_operation_state_failed,
            (int32_t)nozzle_unity_status_unsupported,
            operation->cancel_requested
                ? "render-thread operation finished after cancel request; backend native texture operation is not implemented yet"
                : "render-thread queue drained, but backend native texture operation is not implemented yet"
        );
    }
}


void nozzle_unity_cancel_all_operations(const char *message) {
    std::lock_guard<std::mutex> lock(queue_mutex);
    for(queued_operation &operation : operation_records) {
        if(operation.state == (int32_t)nozzle_unity_operation_state_queued) {
            complete_operation(
                operation,
                (int32_t)nozzle_unity_operation_state_canceled,
                (int32_t)nozzle_unity_status_unsupported,
                message != nullptr ? message : "operation canceled by Unity graphics shutdown"
            );
        } else if(operation.state == (int32_t)nozzle_unity_operation_state_running) {
            operation.cancel_requested = true;
            write_status_message(
                operation.status_message,
                sizeof(operation.status_message),
                message != nullptr ? message : "cancel requested by Unity graphics shutdown"
            );
            remember_queue_status(
                message != nullptr ? message : "cancel requested by Unity graphics shutdown",
                (int32_t)nozzle_unity_status_busy,
                operation.operation_id
            );
        }
    }
}


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
    out_support->direct_nozzle_c_abi_available = direct_nozzle_c_abi_available();
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

NOZZLE_UNITY_API int32_t nozzle_unity_sender_enqueue_publish_native_texture(
    const nozzle_unity_sender_publish_native_texture_desc *desc,
    nozzle_unity_operation_id_t *out_operation_id
) {
    if(desc == nullptr || desc->sender == nullptr) {
        if(out_operation_id != nullptr) {
            *out_operation_id = 0;
        }
        return (int32_t)nozzle_unity_status_invalid_argument;
    }

    queued_operation operation{};
    operation.kind = (int32_t)nozzle_unity_operation_kind_sender_publish_native_texture;
    operation.sender = desc->sender;
    operation.native_texture = desc->native_texture;
    operation.width = desc->width;
    operation.height = desc->height;
    operation.texture_format = desc->texture_format;
    operation.managed_generation = desc->managed_generation;
    return enqueue_operation(operation, out_operation_id);
}

NOZZLE_UNITY_API int32_t nozzle_unity_sender_cancel_operations(nozzle_unity_sender_t *sender) {
    if(sender == nullptr) {
        return (int32_t)nozzle_unity_status_ok;
    }
    return cancel_matching_operations(sender, nullptr);
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

NOZZLE_UNITY_API int32_t nozzle_unity_receiver_enqueue_acquire_and_copy_native_texture(
    const nozzle_unity_receiver_acquire_copy_native_texture_desc *desc,
    nozzle_unity_operation_id_t *out_operation_id
) {
    if(desc == nullptr || desc->receiver == nullptr) {
        if(out_operation_id != nullptr) {
            *out_operation_id = 0;
        }
        return (int32_t)nozzle_unity_status_invalid_argument;
    }

    queued_operation operation{};
    operation.kind = (int32_t)nozzle_unity_operation_kind_receiver_acquire_and_copy_native_texture;
    operation.receiver = desc->receiver;
    operation.native_texture = desc->native_texture;
    operation.width = desc->width;
    operation.height = desc->height;
    operation.texture_format = desc->texture_format;
    operation.timeout_ms = desc->timeout_ms;
    operation.managed_generation = desc->managed_generation;
    return enqueue_operation(operation, out_operation_id);
}

NOZZLE_UNITY_API int32_t nozzle_unity_receiver_cancel_operations(nozzle_unity_receiver_t *receiver) {
    if(receiver == nullptr) {
        return (int32_t)nozzle_unity_status_ok;
    }
    return cancel_matching_operations(nullptr, receiver);
}

NOZZLE_UNITY_API int32_t nozzle_unity_operation_get_status(
    nozzle_unity_operation_id_t operation_id,
    nozzle_unity_operation_status *out_status
) {
    if(operation_id == 0 || out_status == nullptr) {
        return (int32_t)nozzle_unity_status_invalid_argument;
    }

    std::lock_guard<std::mutex> lock(queue_mutex);
    const queued_operation *operation = find_operation_record_const(operation_id);
    if(operation != nullptr) {
        copy_operation_status(*operation, out_status);
        return (int32_t)nozzle_unity_status_ok;
    }

    memset(out_status, 0, sizeof(nozzle_unity_operation_status));
    out_status->operation_id = operation_id;
    out_status->state = (int32_t)nozzle_unity_operation_state_unknown;
    out_status->result = (int32_t)nozzle_unity_status_unknown;
    write_status_message(
        out_status->status_message,
        NOZZLE_UNITY_STATUS_MESSAGE_CAPACITY,
        "operation id is unknown or already released"
    );
    return (int32_t)nozzle_unity_status_unknown;
}

NOZZLE_UNITY_API int32_t nozzle_unity_operation_release(nozzle_unity_operation_id_t operation_id) {
    if(operation_id == 0) {
        return (int32_t)nozzle_unity_status_invalid_argument;
    }

    std::lock_guard<std::mutex> lock(queue_mutex);
    for(auto it = operation_records.begin(); it != operation_records.end(); ++it) {
        if(it->operation_id != operation_id) {
            continue;
        }
        if(it->state == (int32_t)nozzle_unity_operation_state_queued
            || it->state == (int32_t)nozzle_unity_operation_state_running) {
            return (int32_t)nozzle_unity_status_busy;
        }
        operation_records.erase(it);
        return (int32_t)nozzle_unity_status_ok;
    }
    return (int32_t)nozzle_unity_status_unknown;
}


NOZZLE_UNITY_API int32_t nozzle_unity_queue_get_diagnostics(nozzle_unity_queue_diagnostics *out_diagnostics) {
    if(out_diagnostics == nullptr) {
        return (int32_t)nozzle_unity_status_invalid_argument;
    }

    std::lock_guard<std::mutex> lock(queue_mutex);
    memset(out_diagnostics, 0, sizeof(nozzle_unity_queue_diagnostics));
    out_diagnostics->queued_operations = total_queued_operations;
    out_diagnostics->running_operations = total_running_operations;
    out_diagnostics->completed_operations = total_completed_operations;
    out_diagnostics->failed_operations = total_failed_operations;
    out_diagnostics->canceled_operations = total_canceled_operations;
    out_diagnostics->last_operation_id = last_operation_id;
    out_diagnostics->last_result = last_operation_result;
    write_status_message(
        out_diagnostics->status_message,
        NOZZLE_UNITY_STATUS_MESSAGE_CAPACITY,
        last_queue_message
    );
    return (int32_t)nozzle_unity_status_ok;
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
