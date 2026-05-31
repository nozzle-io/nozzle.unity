using System;
using System.Runtime.InteropServices;

namespace Nozzle
{
    internal static unsafe class NozzleNative
    {
        const string LIBRARY = "nozzle_unity";

        internal const uint BRIDGE_ABI_VERSION = 1;
        internal const int STATUS_OK = 0;
        internal const int STATUS_UNSUPPORTED = 3;

        [StructLayout(LayoutKind.Sequential)]
        public struct NozzleSender
        {
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct NozzleReceiver
        {
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct NozzleFrame
        {
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct SupportInfo
        {
            public uint AbiVersion;
            public uint BridgeBinaryLoaded;
            public uint RuntimeSupported;
            public uint UnityHeadersCompiled;
            public uint UnityGraphicsDeviceAvailable;
            public uint RenderThreadEventsAvailable;
            public uint DirectNozzleCAbiAvailable;
            public fixed byte StatusMessage[256];
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct SenderDesc
        {
            public byte* Name;
            public byte* ApplicationName;
            public uint RingBufferSize;
            public int TextureFormat;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct ReceiverDesc
        {
            public byte* Name;
            public byte* ApplicationName;
            public int ReceiveMode;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct AcquireDesc
        {
            public ulong TimeoutMs;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct SenderInfo
        {
            public byte* Name;
            public byte* ApplicationName;
            public byte* Id;
            public int Backend;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct SenderInfoArray
        {
            public SenderInfo* Items;
            public uint Count;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct FrameInfo
        {
            public ulong FrameIndex;
            public ulong TimestampNs;
            public uint Width;
            public uint Height;
            public int TextureFormat;
            public int SemanticFormat;
            public int TransferMode;
            public int SyncMode;
            public uint DroppedFrameCount;
        }

        [DllImport(LIBRARY)]
        public static extern int nozzle_unity_get_support(SupportInfo* out_support);

        [DllImport(LIBRARY)]
        public static extern IntPtr nozzle_unity_get_render_event_func();

        [DllImport(LIBRARY)]
        public static extern int nozzle_unity_sender_create(SenderDesc* desc, NozzleSender** out_sender);

        [DllImport(LIBRARY)]
        public static extern void nozzle_unity_sender_destroy(NozzleSender* sender);

        [DllImport(LIBRARY)]
        public static extern int nozzle_unity_sender_publish_native_texture(
            NozzleSender* sender, void* native_texture, uint width, uint height, int texture_format);

        [DllImport(LIBRARY)]
        public static extern int nozzle_unity_receiver_create(ReceiverDesc* desc, NozzleReceiver** out_receiver);

        [DllImport(LIBRARY)]
        public static extern void nozzle_unity_receiver_destroy(NozzleReceiver* receiver);

        [DllImport(LIBRARY)]
        public static extern int nozzle_unity_receiver_acquire_frame(
            NozzleReceiver* receiver, AcquireDesc* desc, NozzleFrame** out_frame);

        [DllImport(LIBRARY)]
        public static extern void nozzle_unity_frame_release(NozzleFrame* frame);

        [DllImport(LIBRARY)]
        public static extern int nozzle_unity_frame_get_info(NozzleFrame* frame, FrameInfo* out_info);

        [DllImport(LIBRARY)]
        public static extern int nozzle_unity_frame_copy_to_native_texture(
            NozzleFrame* frame, void* native_texture, uint width, uint height, int texture_format);

        [DllImport(LIBRARY)]
        public static extern int nozzle_unity_discovery_enumerate_senders(SenderInfoArray* out_array);

        [DllImport(LIBRARY)]
        public static extern void nozzle_unity_discovery_free_sender_info_array(SenderInfoArray* array);
    }
}
