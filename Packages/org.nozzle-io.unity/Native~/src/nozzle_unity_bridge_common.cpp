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
#include <new>
#include <vector>

struct nozzle_unity_sender_t {
#if defined(NOZZLE_UNITY_WITH_NOZZLE_CORE)
    NozzleSender *sender = nullptr;
#endif
};

struct nozzle_unity_receiver_t {
#if defined(NOZZLE_UNITY_WITH_NOZZLE_CORE)
    NozzleReceiver *receiver = nullptr;
#endif
};

struct nozzle_unity_frame_t {
#if defined(NOZZLE_UNITY_WITH_NOZZLE_CORE)
    NozzleFrame *frame = nullptr;
#endif
};

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

struct operation_execution {
    nozzle_unity_operation_id_t operation_id = 0;
    uint64_t managed_generation = 0;
    int32_t kind = (int32_t)nozzle_unity_operation_kind_unknown;
    nozzle_unity_sender_t *sender = nullptr;
    nozzle_unity_receiver_t *receiver = nullptr;
    void *native_texture = nullptr;
    uint32_t width = 0;
    uint32_t height = 0;
    int32_t texture_format = 0;
    uint64_t timeout_ms = 0;
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

char *duplicate_c_string(const char *source) {
    if(source == nullptr) {
        return nullptr;
    }
    const size_t length = strlen(source);
    char *copy = new(std::nothrow) char[length + 1];
    if(copy == nullptr) {
        return nullptr;
    }
    memcpy(copy, source, length + 1);
    return copy;
}

int32_t unsupported_runtime_status() {
    return (int32_t)nozzle_unity_status_unsupported;
}

int32_t bridge_runtime_available() {
#if defined(NOZZLE_UNITY_WITH_NOZZLE_CORE)
    return nozzle_unity_environment_has_unity_headers() != 0
        && nozzle_unity_environment_has_graphics_device() != 0
        && nozzle_unity_environment_runtime_backend_available() != 0
        && nozzle_unity_environment_render_event_func() != nullptr
        && nozzle_unity_environment_native_device() != nullptr;
#else
    return 0;
#endif
}

int32_t normalize_nozzle_status(int32_t error_code) {
#if defined(NOZZLE_UNITY_WITH_NOZZLE_CORE)
    if(error_code == (int32_t)NOZZLE_OK) {
        return (int32_t)nozzle_unity_status_ok;
    }
    if(error_code == (int32_t)NOZZLE_ERROR_INVALID_ARGUMENT) {
        return (int32_t)nozzle_unity_status_invalid_argument;
    }
    if(error_code == (int32_t)NOZZLE_ERROR_UNSUPPORTED_BACKEND
        || error_code == (int32_t)NOZZLE_ERROR_UNSUPPORTED_FORMAT) {
        return (int32_t)nozzle_unity_status_unsupported;
    }
    if(error_code == (int32_t)NOZZLE_ERROR_TIMEOUT) {
        return (int32_t)nozzle_unity_status_busy;
    }
#else
    (void)error_code;
#endif
    return (int32_t)nozzle_unity_status_unknown;
}

void format_nozzle_status(char *destination, size_t capacity, const char *operation, int32_t error_code) {
    if(destination == nullptr || capacity == 0) {
        return;
    }
    const char *operation_name = operation != nullptr ? operation : "nozzle operation";
    const int written = snprintf(destination, capacity, "%s returned nozzle error %d", operation_name, error_code);
    if(written < 0) {
        destination[0] = '\0';
        return;
    }
    destination[capacity - 1] = '\0';
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
    std::vector<operation_execution> operations_to_process;
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
                operation_execution execution{};
                execution.operation_id = operation->operation_id;
                execution.managed_generation = operation->managed_generation;
                execution.kind = operation->kind;
                execution.sender = operation->sender;
                execution.receiver = operation->receiver;
                execution.native_texture = operation->native_texture;
                execution.width = operation->width;
                execution.height = operation->height;
                execution.texture_format = operation->texture_format;
                execution.timeout_ms = operation->timeout_ms;
                operations_to_process.push_back(execution);
            } else if(operation->state == (int32_t)nozzle_unity_operation_state_queued) {
                kept_operation_ids.push_back(operation_id);
            }
        }
        pending_operation_ids.swap(kept_operation_ids);
    }

    for(operation_execution &execution : operations_to_process) {
        int32_t final_state = (int32_t)nozzle_unity_operation_state_failed;
        int32_t final_result = (int32_t)nozzle_unity_status_unsupported;
        uint64_t frame_index = 0;
        uint32_t completed_width = execution.width;
        uint32_t completed_height = execution.height;
        int32_t completed_format = execution.texture_format;
        char message[NOZZLE_UNITY_STATUS_MESSAGE_CAPACITY]{};

#if defined(NOZZLE_UNITY_WITH_NOZZLE_CORE)
        if(!bridge_runtime_available()) {
            write_status_message(
                message,
                sizeof(message),
                "Unity runtime backend is unavailable for this graphics device"
            );
        } else if(execution.kind == (int32_t)nozzle_unity_operation_kind_sender_publish_native_texture) {
            if(execution.sender == nullptr || execution.sender->sender == nullptr) {
                final_result = (int32_t)nozzle_unity_status_invalid_argument;
                write_status_message(message, sizeof(message), "sender publish operation has no native sender handle");
            } else {
                NozzleErrorCode error_code = nozzle_sender_publish_native_texture(
                    execution.sender->sender,
                    execution.native_texture,
                    execution.width,
                    execution.height,
                    (NozzleTextureFormat)execution.texture_format
                );
                final_result = normalize_nozzle_status((int32_t)error_code);
                if(error_code == NOZZLE_OK) {
                    final_state = (int32_t)nozzle_unity_operation_state_completed;
                    write_status_message(message, sizeof(message), "sender native texture published on Unity render thread");
                } else {
                    format_nozzle_status(message, sizeof(message), "nozzle_sender_publish_native_texture", (int32_t)error_code);
                }
            }
        } else if(execution.kind == (int32_t)nozzle_unity_operation_kind_receiver_acquire_and_copy_native_texture) {
            if(execution.receiver == nullptr || execution.receiver->receiver == nullptr) {
                final_result = (int32_t)nozzle_unity_status_invalid_argument;
                write_status_message(message, sizeof(message), "receiver operation has no native receiver handle");
            } else {
                NozzleAcquireDesc acquire_desc{};
                acquire_desc.timeout_ms = 0;
                NozzleFrame *frame = nullptr;
                NozzleErrorCode error_code = nozzle_receiver_acquire_frame(
                    execution.receiver->receiver,
                    &acquire_desc,
                    &frame
                );
                if(error_code != NOZZLE_OK) {
                    final_result = normalize_nozzle_status((int32_t)error_code);
                    format_nozzle_status(message, sizeof(message), "nozzle_receiver_acquire_frame", (int32_t)error_code);
                } else if(frame == nullptr) {
                    final_result = (int32_t)nozzle_unity_status_unknown;
                    write_status_message(message, sizeof(message), "nozzle_receiver_acquire_frame returned null frame");
                } else {
                    NozzleFrameInfo frame_info{};
                    NozzleErrorCode info_error = nozzle_frame_get_info(frame, &frame_info);
                    if(info_error == NOZZLE_OK) {
                        frame_index = frame_info.frame_index;
                        completed_width = frame_info.width;
                        completed_height = frame_info.height;
                        completed_format = (int32_t)frame_info.format;
                    }

                    NozzleErrorCode copy_error = nozzle_frame_copy_to_native_texture(
                        frame,
                        execution.native_texture,
                        execution.width,
                        execution.height,
                        (NozzleTextureFormat)execution.texture_format
                    );
                    nozzle_frame_release(frame);

                    if(info_error != NOZZLE_OK) {
                        final_result = normalize_nozzle_status((int32_t)info_error);
                        format_nozzle_status(message, sizeof(message), "nozzle_frame_get_info", (int32_t)info_error);
                    } else if(copy_error != NOZZLE_OK) {
                        final_result = normalize_nozzle_status((int32_t)copy_error);
                        format_nozzle_status(message, sizeof(message), "nozzle_frame_copy_to_native_texture", (int32_t)copy_error);
                    } else {
                        final_state = (int32_t)nozzle_unity_operation_state_completed;
                        final_result = (int32_t)nozzle_unity_status_ok;
                        write_status_message(message, sizeof(message), "receiver frame copied to Unity native texture on render thread");
                    }
                }
            }
        } else {
            write_status_message(message, sizeof(message), "unknown render-thread operation kind");
        }
#else
        write_status_message(message, sizeof(message), "nozzle core is not linked into this nozzle_unity bridge");
#endif

        std::lock_guard<std::mutex> lock(queue_mutex);
        queued_operation *operation = find_operation_record(execution.operation_id);
        if(operation == nullptr) {
            continue;
        }
        operation->frame_index = frame_index;
        operation->width = completed_width;
        operation->height = completed_height;
        operation->texture_format = completed_format;
        complete_operation(
            *operation,
            operation->cancel_requested && final_state != (int32_t)nozzle_unity_operation_state_completed
                ? (int32_t)nozzle_unity_operation_state_canceled
                : final_state,
            final_result,
            operation->cancel_requested && final_state != (int32_t)nozzle_unity_operation_state_completed
                ? "render-thread operation finished after cancel request"
                : message
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
    out_support->runtime_supported = (uint32_t)bridge_runtime_available();
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
    if(out_sender == nullptr) {
        return (int32_t)nozzle_unity_status_invalid_argument;
    }
    *out_sender = nullptr;
    if(desc == nullptr || desc->name == nullptr) {
        return (int32_t)nozzle_unity_status_invalid_argument;
    }
#if defined(NOZZLE_UNITY_WITH_NOZZLE_CORE)
    if(!bridge_runtime_available()) {
        return unsupported_runtime_status();
    }

    NozzleSenderDesc sender_desc{};
    sender_desc.name = desc->name;
    sender_desc.application_name = desc->application_name;
    sender_desc.ring_buffer_size = desc->ring_buffer_size;
    sender_desc.allow_format_fallback = 1;
    sender_desc.fallback_flags = NOZZLE_FALLBACK_SAFE_DEFAULTS;
    sender_desc.fallback_flags_valid = 1;

    NozzleNativeDevice native_device{};
    native_device.backend = (NozzleBackendType)nozzle_unity_environment_backend();
    native_device.device = nozzle_unity_environment_native_device();
    native_device.context = nullptr;
    if(native_device.backend == NOZZLE_BACKEND_UNKNOWN || native_device.device == nullptr) {
        return unsupported_runtime_status();
    }

    NozzleSender *sender = nullptr;
    NozzleErrorCode error_code = nozzle_sender_create_with_native_device(
        &sender_desc,
        &native_device,
        &sender
    );
    if(error_code != NOZZLE_OK) {
        return normalize_nozzle_status((int32_t)error_code);
    }

    nozzle_unity_sender_t *bridge_sender = new(std::nothrow) nozzle_unity_sender_t();
    if(bridge_sender == nullptr) {
        nozzle_sender_destroy(sender);
        return (int32_t)nozzle_unity_status_unknown;
    }
    bridge_sender->sender = sender;
    *out_sender = bridge_sender;
    return (int32_t)nozzle_unity_status_ok;
#else
    return unsupported_runtime_status();
#endif
}

NOZZLE_UNITY_API void nozzle_unity_sender_destroy(nozzle_unity_sender_t *sender) {
#if defined(NOZZLE_UNITY_WITH_NOZZLE_CORE)
    if(sender != nullptr && sender->sender != nullptr) {
        nozzle_sender_destroy(sender->sender);
        sender->sender = nullptr;
    }
#endif
    delete sender;
}

NOZZLE_UNITY_API int32_t nozzle_unity_sender_publish_native_texture(
    nozzle_unity_sender_t *sender,
    void *native_texture,
    uint32_t width,
    uint32_t height,
    int32_t texture_format
) {
#if defined(NOZZLE_UNITY_WITH_NOZZLE_CORE)
    if(sender == nullptr || sender->sender == nullptr || native_texture == nullptr) {
        return (int32_t)nozzle_unity_status_invalid_argument;
    }
    if(!bridge_runtime_available()) {
        return unsupported_runtime_status();
    }
    NozzleErrorCode error_code = nozzle_sender_publish_native_texture(
        sender->sender,
        native_texture,
        width,
        height,
        (NozzleTextureFormat)texture_format
    );
    return normalize_nozzle_status((int32_t)error_code);
#else
    (void)sender;
    (void)native_texture;
    (void)width;
    (void)height;
    (void)texture_format;
    return unsupported_runtime_status();
#endif
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
    if(out_receiver == nullptr) {
        return (int32_t)nozzle_unity_status_invalid_argument;
    }
    *out_receiver = nullptr;
    if(desc == nullptr || desc->name == nullptr) {
        return (int32_t)nozzle_unity_status_invalid_argument;
    }
#if defined(NOZZLE_UNITY_WITH_NOZZLE_CORE)
    if(!bridge_runtime_available()) {
        return unsupported_runtime_status();
    }

    NozzleReceiverDesc receiver_desc{};
    receiver_desc.name = desc->name;
    receiver_desc.application_name = desc->application_name;
    receiver_desc.receive_mode = (NozzleReceiveMode)desc->receive_mode;

    NozzleReceiver *receiver = nullptr;
    NozzleErrorCode error_code = nozzle_receiver_create(&receiver_desc, &receiver);
    if(error_code != NOZZLE_OK) {
        return normalize_nozzle_status((int32_t)error_code);
    }

    nozzle_unity_receiver_t *bridge_receiver = new(std::nothrow) nozzle_unity_receiver_t();
    if(bridge_receiver == nullptr) {
        nozzle_receiver_destroy(receiver);
        return (int32_t)nozzle_unity_status_unknown;
    }
    bridge_receiver->receiver = receiver;
    *out_receiver = bridge_receiver;
    return (int32_t)nozzle_unity_status_ok;
#else
    return unsupported_runtime_status();
#endif
}

NOZZLE_UNITY_API void nozzle_unity_receiver_destroy(nozzle_unity_receiver_t *receiver) {
#if defined(NOZZLE_UNITY_WITH_NOZZLE_CORE)
    if(receiver != nullptr && receiver->receiver != nullptr) {
        nozzle_receiver_destroy(receiver->receiver);
        receiver->receiver = nullptr;
    }
#endif
    delete receiver;
}

NOZZLE_UNITY_API int32_t nozzle_unity_receiver_acquire_frame(
    nozzle_unity_receiver_t *receiver,
    const nozzle_unity_acquire_desc *desc,
    nozzle_unity_frame_t **out_frame
) {
    if(out_frame == nullptr) {
        return (int32_t)nozzle_unity_status_invalid_argument;
    }
    *out_frame = nullptr;
#if defined(NOZZLE_UNITY_WITH_NOZZLE_CORE)
    if(receiver == nullptr || receiver->receiver == nullptr || desc == nullptr) {
        return (int32_t)nozzle_unity_status_invalid_argument;
    }
    NozzleAcquireDesc acquire_desc{};
    acquire_desc.timeout_ms = desc->timeout_ms;
    NozzleFrame *frame = nullptr;
    NozzleErrorCode error_code = nozzle_receiver_acquire_frame(receiver->receiver, &acquire_desc, &frame);
    if(error_code != NOZZLE_OK) {
        return normalize_nozzle_status((int32_t)error_code);
    }
    nozzle_unity_frame_t *bridge_frame = new(std::nothrow) nozzle_unity_frame_t();
    if(bridge_frame == nullptr) {
        nozzle_frame_release(frame);
        return (int32_t)nozzle_unity_status_unknown;
    }
    bridge_frame->frame = frame;
    *out_frame = bridge_frame;
    return (int32_t)nozzle_unity_status_ok;
#else
    (void)receiver;
    (void)desc;
    return unsupported_runtime_status();
#endif
}

NOZZLE_UNITY_API void nozzle_unity_frame_release(nozzle_unity_frame_t *frame) {
#if defined(NOZZLE_UNITY_WITH_NOZZLE_CORE)
    if(frame != nullptr && frame->frame != nullptr) {
        nozzle_frame_release(frame->frame);
        frame->frame = nullptr;
    }
#endif
    delete frame;
}

NOZZLE_UNITY_API int32_t nozzle_unity_frame_get_info(
    nozzle_unity_frame_t *frame,
    nozzle_unity_frame_info *out_info
) {
    if(out_info == nullptr) {
        return (int32_t)nozzle_unity_status_invalid_argument;
    }
    memset(out_info, 0, sizeof(nozzle_unity_frame_info));
#if defined(NOZZLE_UNITY_WITH_NOZZLE_CORE)
    if(frame == nullptr || frame->frame == nullptr) {
        return (int32_t)nozzle_unity_status_invalid_argument;
    }
    NozzleFrameInfo frame_info{};
    NozzleErrorCode error_code = nozzle_frame_get_info(frame->frame, &frame_info);
    if(error_code != NOZZLE_OK) {
        return normalize_nozzle_status((int32_t)error_code);
    }
    out_info->frame_index = frame_info.frame_index;
    out_info->timestamp_ns = frame_info.timestamp_ns;
    out_info->width = frame_info.width;
    out_info->height = frame_info.height;
    out_info->texture_format = (int32_t)frame_info.format;
    out_info->semantic_format = (int32_t)frame_info.semantic_format;
    out_info->transfer_mode = (int32_t)frame_info.transfer_mode;
    out_info->sync_mode = (int32_t)frame_info.sync_mode;
    out_info->dropped_frame_count = frame_info.dropped_frame_count;
    return (int32_t)nozzle_unity_status_ok;
#else
    (void)frame;
    return unsupported_runtime_status();
#endif
}

NOZZLE_UNITY_API int32_t nozzle_unity_frame_copy_to_native_texture(
    nozzle_unity_frame_t *frame,
    void *native_texture,
    uint32_t width,
    uint32_t height,
    int32_t texture_format
) {
#if defined(NOZZLE_UNITY_WITH_NOZZLE_CORE)
    if(frame == nullptr || frame->frame == nullptr || native_texture == nullptr) {
        return (int32_t)nozzle_unity_status_invalid_argument;
    }
    NozzleErrorCode error_code = nozzle_frame_copy_to_native_texture(
        frame->frame,
        native_texture,
        width,
        height,
        (NozzleTextureFormat)texture_format
    );
    return normalize_nozzle_status((int32_t)error_code);
#else
    (void)frame;
    (void)native_texture;
    (void)width;
    (void)height;
    (void)texture_format;
    return unsupported_runtime_status();
#endif
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
#if defined(NOZZLE_UNITY_WITH_NOZZLE_CORE)
    if(!bridge_runtime_available()) {
        return unsupported_runtime_status();
    }

    NozzleSenderInfoArray core_array{};
    NozzleErrorCode error_code = nozzle_enumerate_senders(&core_array);
    if(error_code != NOZZLE_OK) {
        return normalize_nozzle_status((int32_t)error_code);
    }
    if(core_array.count == 0) {
        nozzle_free_sender_info_array(&core_array);
        return (int32_t)nozzle_unity_status_ok;
    }

    const uint32_t core_count = core_array.count;
    nozzle_unity_sender_info *items = new(std::nothrow) nozzle_unity_sender_info[core_count]{};
    if(items == nullptr) {
        nozzle_free_sender_info_array(&core_array);
        return (int32_t)nozzle_unity_status_unknown;
    }

    for(uint32_t index = 0; index < core_count; index += 1) {
        items[index].name = duplicate_c_string(core_array.items[index].name);
        items[index].application_name = duplicate_c_string(core_array.items[index].application_name);
        items[index].id = duplicate_c_string(core_array.items[index].id);
        items[index].backend = (int32_t)core_array.items[index].backend;
        if((core_array.items[index].name != nullptr && items[index].name == nullptr)
            || (core_array.items[index].application_name != nullptr && items[index].application_name == nullptr)
            || (core_array.items[index].id != nullptr && items[index].id == nullptr)) {
            out_array->items = items;
            out_array->count = index + 1;
            nozzle_unity_discovery_free_sender_info_array(out_array);
            nozzle_free_sender_info_array(&core_array);
            clear_sender_info_array(out_array);
            return (int32_t)nozzle_unity_status_unknown;
        }
    }

    nozzle_free_sender_info_array(&core_array);
    out_array->items = items;
    out_array->count = core_count;
    return (int32_t)nozzle_unity_status_ok;
#else
    return unsupported_runtime_status();
#endif
}

NOZZLE_UNITY_API void nozzle_unity_discovery_free_sender_info_array(
    nozzle_unity_sender_info_array *array
) {
    if(array == nullptr || array->items == nullptr) {
        clear_sender_info_array(array);
        return;
    }
    for(uint32_t index = 0; index < array->count; index += 1) {
        delete[] array->items[index].name;
        delete[] array->items[index].application_name;
        delete[] array->items[index].id;
    }
    delete[] array->items;
    clear_sender_info_array(array);
}

} // extern "C"
