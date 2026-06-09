#pragma once

#include <stdint.h>

#if defined(_WIN32)
    #if defined(NOZZLE_UNITY_EXPORTS)
        #define NOZZLE_UNITY_API __declspec(dllexport)
    #else
        #define NOZZLE_UNITY_API __declspec(dllimport)
    #endif
#else
    #define NOZZLE_UNITY_API __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

enum {
    NOZZLE_UNITY_ABI_VERSION = 1,
    NOZZLE_UNITY_STATUS_MESSAGE_CAPACITY = 256,
    NOZZLE_UNITY_EVENT_SENDER_PUBLISH_NATIVE_TEXTURE = 0x4E5A0001,
    NOZZLE_UNITY_EVENT_RECEIVER_ACQUIRE_AND_COPY_NATIVE_TEXTURE = 0x4E5A0002,
};

typedef enum nozzle_unity_status {
    nozzle_unity_status_ok = 0,
    nozzle_unity_status_unknown = 1,
    nozzle_unity_status_invalid_argument = 2,
    nozzle_unity_status_unsupported = 3,
    nozzle_unity_status_busy = 4,
} nozzle_unity_status;

typedef struct nozzle_unity_sender_t nozzle_unity_sender_t;
typedef struct nozzle_unity_receiver_t nozzle_unity_receiver_t;
typedef struct nozzle_unity_frame_t nozzle_unity_frame_t;
typedef uint64_t nozzle_unity_operation_id_t;

typedef enum nozzle_unity_operation_kind {
    nozzle_unity_operation_kind_unknown = 0,
    nozzle_unity_operation_kind_sender_publish_native_texture = 1,
    nozzle_unity_operation_kind_receiver_acquire_and_copy_native_texture = 2,
} nozzle_unity_operation_kind;

typedef enum nozzle_unity_operation_state {
    nozzle_unity_operation_state_unknown = 0,
    nozzle_unity_operation_state_queued = 1,
    nozzle_unity_operation_state_running = 2,
    nozzle_unity_operation_state_completed = 3,
    nozzle_unity_operation_state_failed = 4,
    nozzle_unity_operation_state_canceled = 5,
} nozzle_unity_operation_state;

typedef struct nozzle_unity_support_info {
    uint32_t abi_version;
    uint32_t bridge_binary_loaded;
    uint32_t runtime_supported;
    uint32_t unity_headers_compiled;
    uint32_t unity_graphics_device_available;
    uint32_t render_thread_events_available;
    uint32_t direct_nozzle_c_abi_available;
    char status_message[NOZZLE_UNITY_STATUS_MESSAGE_CAPACITY];
} nozzle_unity_support_info;

typedef struct nozzle_unity_sender_desc {
    const char *name;
    const char *application_name;
    uint32_t ring_buffer_size;
    int32_t texture_format;
} nozzle_unity_sender_desc;

typedef struct nozzle_unity_receiver_desc {
    const char *name;
    const char *application_name;
    int32_t receive_mode;
} nozzle_unity_receiver_desc;

typedef struct nozzle_unity_acquire_desc {
    uint64_t timeout_ms;
} nozzle_unity_acquire_desc;

typedef struct nozzle_unity_sender_info {
    const char *name;
    const char *application_name;
    const char *id;
    int32_t backend;
} nozzle_unity_sender_info;

typedef struct nozzle_unity_sender_info_array {
    nozzle_unity_sender_info *items;
    uint32_t count;
} nozzle_unity_sender_info_array;

typedef struct nozzle_unity_frame_info {
    uint64_t frame_index;
    uint64_t timestamp_ns;
    uint32_t width;
    uint32_t height;
    int32_t texture_format;
    int32_t semantic_format;
    int32_t transfer_mode;
    int32_t sync_mode;
    uint32_t dropped_frame_count;
} nozzle_unity_frame_info;

typedef struct nozzle_unity_sender_publish_native_texture_desc {
    nozzle_unity_sender_t *sender;
    void *native_texture;
    uint32_t width;
    uint32_t height;
    int32_t texture_format;
    uint64_t managed_generation;
} nozzle_unity_sender_publish_native_texture_desc;

typedef struct nozzle_unity_receiver_acquire_copy_native_texture_desc {
    nozzle_unity_receiver_t *receiver;
    void *native_texture;
    uint32_t width;
    uint32_t height;
    int32_t texture_format;
    uint64_t timeout_ms;
    uint64_t managed_generation;
} nozzle_unity_receiver_acquire_copy_native_texture_desc;

typedef struct nozzle_unity_operation_status {
    nozzle_unity_operation_id_t operation_id;
    uint64_t managed_generation;
    int32_t kind;
    int32_t state;
    int32_t result;
    uint64_t frame_index;
    uint32_t width;
    uint32_t height;
    int32_t texture_format;
    char status_message[NOZZLE_UNITY_STATUS_MESSAGE_CAPACITY];
} nozzle_unity_operation_status;

typedef struct nozzle_unity_queue_diagnostics {
    uint64_t queued_operations;
    uint64_t running_operations;
    uint64_t completed_operations;
    uint64_t failed_operations;
    uint64_t canceled_operations;
    nozzle_unity_operation_id_t last_operation_id;
    int32_t last_result;
    char status_message[NOZZLE_UNITY_STATUS_MESSAGE_CAPACITY];
} nozzle_unity_queue_diagnostics;

typedef void (*nozzle_unity_render_event_func)(int32_t event_id);

NOZZLE_UNITY_API int32_t nozzle_unity_get_support(nozzle_unity_support_info *out_support);
NOZZLE_UNITY_API const char *nozzle_unity_get_version(void);
NOZZLE_UNITY_API nozzle_unity_render_event_func nozzle_unity_get_render_event_func(void);

NOZZLE_UNITY_API int32_t nozzle_unity_sender_create(
    const nozzle_unity_sender_desc *desc,
    nozzle_unity_sender_t **out_sender
);
NOZZLE_UNITY_API void nozzle_unity_sender_destroy(nozzle_unity_sender_t *sender);
NOZZLE_UNITY_API int32_t nozzle_unity_sender_publish_native_texture(
    nozzle_unity_sender_t *sender,
    void *native_texture,
    uint32_t width,
    uint32_t height,
    int32_t texture_format
);
NOZZLE_UNITY_API int32_t nozzle_unity_sender_enqueue_publish_native_texture(
    const nozzle_unity_sender_publish_native_texture_desc *desc,
    nozzle_unity_operation_id_t *out_operation_id
);
NOZZLE_UNITY_API int32_t nozzle_unity_sender_cancel_operations(nozzle_unity_sender_t *sender);

NOZZLE_UNITY_API int32_t nozzle_unity_receiver_create(
    const nozzle_unity_receiver_desc *desc,
    nozzle_unity_receiver_t **out_receiver
);
NOZZLE_UNITY_API void nozzle_unity_receiver_destroy(nozzle_unity_receiver_t *receiver);
NOZZLE_UNITY_API int32_t nozzle_unity_receiver_acquire_frame(
    nozzle_unity_receiver_t *receiver,
    const nozzle_unity_acquire_desc *desc,
    nozzle_unity_frame_t **out_frame
);
NOZZLE_UNITY_API void nozzle_unity_frame_release(nozzle_unity_frame_t *frame);
NOZZLE_UNITY_API int32_t nozzle_unity_frame_get_info(
    nozzle_unity_frame_t *frame,
    nozzle_unity_frame_info *out_info
);
NOZZLE_UNITY_API int32_t nozzle_unity_frame_copy_to_native_texture(
    nozzle_unity_frame_t *frame,
    void *native_texture,
    uint32_t width,
    uint32_t height,
    int32_t texture_format
);
NOZZLE_UNITY_API int32_t nozzle_unity_receiver_enqueue_acquire_and_copy_native_texture(
    const nozzle_unity_receiver_acquire_copy_native_texture_desc *desc,
    nozzle_unity_operation_id_t *out_operation_id
);
NOZZLE_UNITY_API int32_t nozzle_unity_receiver_cancel_operations(nozzle_unity_receiver_t *receiver);

NOZZLE_UNITY_API int32_t nozzle_unity_operation_get_status(
    nozzle_unity_operation_id_t operation_id,
    nozzle_unity_operation_status *out_status
);
NOZZLE_UNITY_API int32_t nozzle_unity_operation_release(nozzle_unity_operation_id_t operation_id);
NOZZLE_UNITY_API int32_t nozzle_unity_queue_get_diagnostics(nozzle_unity_queue_diagnostics *out_diagnostics);

NOZZLE_UNITY_API int32_t nozzle_unity_discovery_enumerate_senders(
    nozzle_unity_sender_info_array *out_array
);
NOZZLE_UNITY_API void nozzle_unity_discovery_free_sender_info_array(
    nozzle_unity_sender_info_array *array
);

#ifdef __cplusplus
}
#endif
