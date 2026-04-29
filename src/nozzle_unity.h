#pragma once

#include <stdint.h>
#include <stddef.h>

#ifdef _WIN32
#define NOZZLE_UNITY_API __declspec(dllexport)
#else
#define NOZZLE_UNITY_API __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

// Sender
NOZZLE_UNITY_API int nozzle_unity_sender_create(const char *name, const char *app_name, uint32_t ring_size);
NOZZLE_UNITY_API void nozzle_unity_sender_destroy(int handle);
NOZZLE_UNITY_API int nozzle_unity_sender_publish_texture(int handle, void *native_texture, uint32_t width, uint32_t height, int format);
NOZZLE_UNITY_API int nozzle_unity_sender_commit_frame(int handle);
NOZZLE_UNITY_API int nozzle_unity_sender_get_info(int handle, char *name_buf, uint32_t name_buf_size, char *app_buf, uint32_t app_buf_size);

// Receiver
NOZZLE_UNITY_API int nozzle_unity_receiver_create(const char *name, const char *app_name);
NOZZLE_UNITY_API void nozzle_unity_receiver_destroy(int handle);
NOZZLE_UNITY_API int nozzle_unity_receiver_acquire_frame(int handle, uint64_t timeout_ms);
NOZZLE_UNITY_API int nozzle_unity_receiver_get_frame_info(int handle, uint32_t *w, uint32_t *h, int *format, uint64_t *frame_index, uint64_t *timestamp_ns);
NOZZLE_UNITY_API int nozzle_unity_receiver_copy_to_texture(int handle, void *native_texture, uint32_t width, uint32_t height);
NOZZLE_UNITY_API void nozzle_unity_receiver_release_frame(int handle);
NOZZLE_UNITY_API int nozzle_unity_receiver_get_connected_info(int handle, char *name_buf, uint32_t name_buf_size, char *app_buf, uint32_t app_buf_size, uint32_t *w, uint32_t *h, double *fps);

// Discovery
NOZZLE_UNITY_API int nozzle_unity_enumerate_senders(void (*callback)(const char *name, const char *app_name, const char *id, int backend, void *ctx), void *ctx);

// Error info
NOZZLE_UNITY_API int nozzle_unity_get_last_error_code(int handle);
NOZZLE_UNITY_API void nozzle_unity_get_last_error_message(int handle, char *buf, uint32_t buf_size);

#ifdef __cplusplus
}
#endif
