#include "nozzle_unity.h"

#include <nozzle/nozzle_c.h>

#include <cstring>
#include <mutex>
#include <unordered_map>
#include <string>

namespace {

struct sender_entry {
    NozzleSender *sender{nullptr};
    NozzleFrame *pending_frame{nullptr};
    NozzleErrorCode last_error{NOZZLE_OK};
    std::string last_error_msg;
};

struct receiver_entry {
    NozzleReceiver *receiver{nullptr};
    NozzleFrame *current_frame{nullptr};
    NozzleErrorCode last_error{NOZZLE_OK};
    std::string last_error_msg;
};

std::unordered_map<int, sender_entry> g_senders;
std::unordered_map<int, receiver_entry> g_receivers;
std::mutex g_senders_mutex;
std::mutex g_receivers_mutex;
int g_next_sender_handle{1};
int g_next_receiver_handle{1};

static NozzleTextureFormat to_nozzle_format(int format) {
    return static_cast<NozzleTextureFormat>(format);
}

static int to_error_code(NozzleErrorCode ec) {
    return static_cast<int>(ec);
}

}

int nozzle_unity_sender_create(const char *name, const char *app_name, uint32_t ring_size) {
    NozzleSenderDesc desc{};
    desc.name = name;
    desc.application_name = app_name ? app_name : "";
    desc.ring_buffer_size = ring_size > 0 ? ring_size : 3;
    desc.allow_format_fallback = 1;

    NozzleSender *sender{nullptr};
    auto ec = nozzle_sender_create(&desc, &sender);
    if (ec != NOZZLE_OK || !sender) {
        return to_error_code(ec);
    }

    std::lock_guard<std::mutex> lock(g_senders_mutex);
    int handle = g_next_sender_handle++;
    g_senders[handle] = {sender, nullptr, NOZZLE_OK, ""};
    return handle;
}

void nozzle_unity_sender_destroy(int handle) {
    std::lock_guard<std::mutex> lock(g_senders_mutex);
    auto it = g_senders.find(handle);
    if (it == g_senders.end()) return;

    if (it->second.pending_frame) {
        nozzle_frame_release(it->second.pending_frame);
    }
    if (it->second.sender) {
        nozzle_sender_destroy(it->second.sender);
    }
    g_senders.erase(it);
}

int nozzle_unity_sender_publish_texture(int handle, void *native_texture, uint32_t width, uint32_t height, int format) {
    std::lock_guard<std::mutex> lock(g_senders_mutex);
    auto it = g_senders.find(handle);
    if (it == g_senders.end()) return to_error_code(NOZZLE_ERROR_INVALID_ARGUMENT);

    if (it->second.pending_frame) {
        nozzle_frame_release(it->second.pending_frame);
        it->second.pending_frame = nullptr;
    }

    // native_texture: Unity's RenderTexture native pointer
    // (ID3D11Texture2D* on Windows, MTLTexture* on macOS).
    // Acquires a nozzle frame, then the C# side copies via CPU readback (v0.1).
    auto ec = nozzle_sender_acquire_writable_frame(
        it->second.sender, width, height, to_nozzle_format(format),
        &it->second.pending_frame
    );

    it->second.last_error = ec;
    return to_error_code(ec);
}

int nozzle_unity_sender_commit_frame(int handle) {
    std::lock_guard<std::mutex> lock(g_senders_mutex);
    auto it = g_senders.find(handle);
    if (it == g_senders.end()) return to_error_code(NOZZLE_ERROR_INVALID_ARGUMENT);

    if (!it->second.pending_frame) {
        it->second.last_error = NOZZLE_ERROR_INVALID_ARGUMENT;
        return to_error_code(NOZZLE_ERROR_INVALID_ARGUMENT);
    }

    auto ec = nozzle_sender_commit_frame(it->second.sender, it->second.pending_frame);
    it->second.pending_frame = nullptr;
    it->second.last_error = ec;
    return to_error_code(ec);
}

int nozzle_unity_sender_get_info(int handle, char *name_buf, uint32_t name_buf_size, char *app_buf, uint32_t app_buf_size) {
    std::lock_guard<std::mutex> lock(g_senders_mutex);
    auto it = g_senders.find(handle);
    if (it == g_senders.end()) return to_error_code(NOZZLE_ERROR_INVALID_ARGUMENT);

    NozzleSenderInfo info{};
    auto ec = nozzle_sender_get_info(it->second.sender, &info);
    if (ec != NOZZLE_OK) {
        it->second.last_error = ec;
        return to_error_code(ec);
    }

    if (name_buf && name_buf_size > 0 && info.name) {
        strncpy(name_buf, info.name, name_buf_size - 1);
        name_buf[name_buf_size - 1] = '\0';
    }
    if (app_buf && app_buf_size > 0 && info.application_name) {
        strncpy(app_buf, info.application_name, app_buf_size - 1);
        app_buf[app_buf_size - 1] = '\0';
    }

    return to_error_code(NOZZLE_OK);
}



int nozzle_unity_receiver_create(const char *name, const char *app_name) {
    NozzleReceiverDesc desc{};
    desc.name = name;
    desc.application_name = app_name ? app_name : "";
    desc.receive_mode = NOZZLE_RECEIVE_LATEST_ONLY;

    NozzleReceiver *receiver{nullptr};
    auto ec = nozzle_receiver_create(&desc, &receiver);
    if (ec != NOZZLE_OK || !receiver) {
        return to_error_code(ec);
    }

    std::lock_guard<std::mutex> lock(g_receivers_mutex);
    int handle = g_next_receiver_handle++;
    g_receivers[handle] = {receiver, nullptr, NOZZLE_OK, ""};
    return handle;
}

void nozzle_unity_receiver_destroy(int handle) {
    std::lock_guard<std::mutex> lock(g_receivers_mutex);
    auto it = g_receivers.find(handle);
    if (it == g_receivers.end()) return;

    if (it->second.current_frame) {
        nozzle_frame_release(it->second.current_frame);
    }
    if (it->second.receiver) {
        nozzle_receiver_destroy(it->second.receiver);
    }
    g_receivers.erase(it);
}

int nozzle_unity_receiver_acquire_frame(int handle, uint64_t timeout_ms) {
    std::lock_guard<std::mutex> lock(g_receivers_mutex);
    auto it = g_receivers.find(handle);
    if (it == g_receivers.end()) return to_error_code(NOZZLE_ERROR_INVALID_ARGUMENT);

    if (it->second.current_frame) {
        nozzle_frame_release(it->second.current_frame);
        it->second.current_frame = nullptr;
    }

    NozzleAcquireDesc acquire_desc{};
    acquire_desc.timeout_ms = timeout_ms;

    auto ec = nozzle_receiver_acquire_frame(it->second.receiver, &acquire_desc, &it->second.current_frame);
    it->second.last_error = ec;
    return to_error_code(ec);
}

int nozzle_unity_receiver_get_frame_info(int handle, uint32_t *w, uint32_t *h, int *format, uint64_t *frame_index, uint64_t *timestamp_ns) {
    std::lock_guard<std::mutex> lock(g_receivers_mutex);
    auto it = g_receivers.find(handle);
    if (it == g_receivers.end()) return to_error_code(NOZZLE_ERROR_INVALID_ARGUMENT);

    if (!it->second.current_frame) {
        it->second.last_error = NOZZLE_ERROR_INVALID_ARGUMENT;
        return to_error_code(NOZZLE_ERROR_INVALID_ARGUMENT);
    }

    NozzleFrameInfo info{};
    auto ec = nozzle_frame_get_info(it->second.current_frame, &info);
    if (ec != NOZZLE_OK) {
        it->second.last_error = ec;
        return to_error_code(ec);
    }

    if (w) *w = info.width;
    if (h) *h = info.height;
    if (format) *format = static_cast<int>(info.format);
    if (frame_index) *frame_index = info.frame_index;
    if (timestamp_ns) *timestamp_ns = info.timestamp_ns;

    return to_error_code(NOZZLE_OK);
}

int nozzle_unity_receiver_copy_to_texture(int handle, void *native_texture, uint32_t width, uint32_t height) {
    std::lock_guard<std::mutex> lock(g_receivers_mutex);
    auto it = g_receivers.find(handle);
    if (it == g_receivers.end()) return to_error_code(NOZZLE_ERROR_INVALID_ARGUMENT);

    if (!it->second.current_frame) {
        it->second.last_error = NOZZLE_ERROR_INVALID_ARGUMENT;
        return to_error_code(NOZZLE_ERROR_INVALID_ARGUMENT);
    }

    NozzleFrameInfo info{};
    auto ec = nozzle_frame_get_info(it->second.current_frame, &info);
    if (ec != NOZZLE_OK) {
        it->second.last_error = ec;
        return to_error_code(ec);
    }

    NozzleMappedPixels pixels{};
    ec = nozzle_frame_lock_pixels(it->second.current_frame, &pixels);
    if (ec != NOZZLE_OK) {
        it->second.last_error = ec;
        return to_error_code(ec);
    }

    nozzle_frame_unlock_pixels(it->second.current_frame);
    it->second.last_error = NOZZLE_OK;
    return to_error_code(NOZZLE_OK);
}

void nozzle_unity_receiver_release_frame(int handle) {
    std::lock_guard<std::mutex> lock(g_receivers_mutex);
    auto it = g_receivers.find(handle);
    if (it == g_receivers.end()) return;

    if (it->second.current_frame) {
        nozzle_frame_release(it->second.current_frame);
        it->second.current_frame = nullptr;
    }
}

int nozzle_unity_receiver_get_connected_info(int handle, char *name_buf, uint32_t name_buf_size, char *app_buf, uint32_t app_buf_size, uint32_t *w, uint32_t *h, double *fps) {
    std::lock_guard<std::mutex> lock(g_receivers_mutex);
    auto it = g_receivers.find(handle);
    if (it == g_receivers.end()) return to_error_code(NOZZLE_ERROR_INVALID_ARGUMENT);

    NozzleConnectedSenderInfo info{};
    auto ec = nozzle_receiver_get_connected_info(it->second.receiver, &info);
    if (ec != NOZZLE_OK) {
        it->second.last_error = ec;
        return to_error_code(ec);
    }

    if (name_buf && name_buf_size > 0 && info.name) {
        strncpy(name_buf, info.name, name_buf_size - 1);
        name_buf[name_buf_size - 1] = '\0';
    }
    if (app_buf && app_buf_size > 0 && info.application_name) {
        strncpy(app_buf, info.application_name, app_buf_size - 1);
        app_buf[app_buf_size - 1] = '\0';
    }
    if (w) *w = info.width;
    if (h) *h = info.height;
    if (fps) *fps = info.estimated_fps;

    return to_error_code(NOZZLE_OK);
}


int nozzle_unity_enumerate_senders(void (*callback)(const char *name, const char *app_name, const char *id, int backend, void *ctx), void *ctx) {
    if (!callback) return to_error_code(NOZZLE_ERROR_INVALID_ARGUMENT);

    NozzleSenderInfoArray array{};
    auto ec = nozzle_enumerate_senders(&array);
    if (ec != NOZZLE_OK) return to_error_code(ec);

    for (uint32_t i = 0; i < array.count; i++) {
        callback(
            array.items[i].name,
            array.items[i].application_name,
            array.items[i].id,
            static_cast<int>(array.items[i].backend),
            ctx
        );
    }

    nozzle_free_sender_info_array(&array);
    return to_error_code(NOZZLE_OK);
}


int nozzle_unity_get_last_error_code(int handle) {
    {
        std::lock_guard<std::mutex> lock(g_senders_mutex);
        auto it = g_senders.find(handle);
        if (it != g_senders.end()) return to_error_code(it->second.last_error);
    }
    {
        std::lock_guard<std::mutex> lock(g_receivers_mutex);
        auto it = g_receivers.find(handle);
        if (it != g_receivers.end()) return to_error_code(it->second.last_error);
    }
    return to_error_code(NOZZLE_ERROR_INVALID_ARGUMENT);
}

void nozzle_unity_get_last_error_message(int handle, char *buf, uint32_t buf_size) {
    if (!buf || buf_size == 0) return;

    std::string msg;
    {
        std::lock_guard<std::mutex> lock(g_senders_mutex);
        auto it = g_senders.find(handle);
        if (it != g_senders.end()) {
            msg = it->second.last_error_msg;
            strncpy(buf, msg.c_str(), buf_size - 1);
            buf[buf_size - 1] = '\0';
            return;
        }
    }
    {
        std::lock_guard<std::mutex> lock(g_receivers_mutex);
        auto it = g_receivers.find(handle);
        if (it != g_receivers.end()) {
            msg = it->second.last_error_msg;
            strncpy(buf, msg.c_str(), buf_size - 1);
            buf[buf_size - 1] = '\0';
            return;
        }
    }
    strncpy(buf, "Unknown handle", buf_size - 1);
    buf[buf_size - 1] = '\0';
}
