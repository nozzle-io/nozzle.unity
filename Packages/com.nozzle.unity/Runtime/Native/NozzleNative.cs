using System;
using System.Runtime.InteropServices;

namespace Nozzle
{
    internal static class NozzleNative
    {
        const string LIBRARY = "nozzle_unity";

        [DllImport(LIBRARY)]
        public static extern int nozzle_unity_sender_create(string name, string app_name, uint ring_size);

        [DllImport(LIBRARY)]
        public static extern void nozzle_unity_sender_destroy(int handle);

        [DllImport(LIBRARY)]
        public static extern int nozzle_unity_sender_publish_texture(int handle, IntPtr native_texture, uint width, uint height, int format);

        [DllImport(LIBRARY)]
        public static extern int nozzle_unity_sender_commit_frame(int handle);

        [DllImport(LIBRARY)]
        public static extern int nozzle_unity_sender_get_info(int handle, byte[] name_buf, uint name_buf_size, byte[] app_buf, uint app_buf_size);

        [DllImport(LIBRARY)]
        public static extern int nozzle_unity_receiver_create(string name, string app_name);

        [DllImport(LIBRARY)]
        public static extern void nozzle_unity_receiver_destroy(int handle);

        [DllImport(LIBRARY)]
        public static extern int nozzle_unity_receiver_acquire_frame(int handle, ulong timeout_ms);

        [DllImport(LIBRARY)]
        public static extern int nozzle_unity_receiver_get_frame_info(int handle, out uint w, out uint h, out int format, out ulong frame_index, out ulong timestamp_ns);

        [DllImport(LIBRARY)]
        public static extern int nozzle_unity_receiver_copy_to_texture(int handle, IntPtr native_texture, uint width, uint height);

        [DllImport(LIBRARY)]
        public static extern void nozzle_unity_receiver_release_frame(int handle);

        [DllImport(LIBRARY)]
        public static extern int nozzle_unity_receiver_get_connected_info(int handle, byte[] name_buf, uint name_buf_size, byte[] app_buf, uint app_buf_size, out uint w, out uint h, out double fps);

        public delegate void EnumerateCallback(string name, string app_name, string id, int backend, IntPtr ctx);

        [DllImport(LIBRARY)]
        public static extern int nozzle_unity_enumerate_senders(EnumerateCallback callback, IntPtr ctx);

        [DllImport(LIBRARY)]
        public static extern int nozzle_unity_get_last_error_code(int handle);

        [DllImport(LIBRARY)]
        public static extern void nozzle_unity_get_last_error_message(int handle, byte[] buf, uint buf_size);
    }
}
