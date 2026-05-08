using System;
using System.Runtime.InteropServices;

namespace Nozzle
{
    internal static unsafe class NozzleNative
    {
        const string LIBRARY = "nozzle";

        [StructLayout(LayoutKind.Sequential)]
        public struct NozzleSender;
        [StructLayout(LayoutKind.Sequential)]
        public struct NozzleReceiver;
        [StructLayout(LayoutKind.Sequential)]
        public struct NozzleFrame;
        [StructLayout(LayoutKind.Sequential)]
        public struct NozzleTexture;
        [StructLayout(LayoutKind.Sequential)]
        public struct NozzleDevice;

        [StructLayout(LayoutKind.Sequential)]
        public struct SenderDesc
        {
            public byte* Name;
            public byte* ApplicationName;
            public uint RingBufferSize;
            public int AllowFormatFallback;
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
        public struct ConnectedSenderInfo
        {
            public byte* Name;
            public byte* ApplicationName;
            public byte* Id;
            public int Backend;
            public uint Width;
            public uint Height;
            public int Format;
            public int SemanticFormat;
            public double EstimatedFps;
            public ulong FrameCounter;
            public ulong LastUpdateTimeNs;
            public ulong NativeFormatModifier;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct FrameInfo
        {
            public ulong FrameIndex;
            public ulong TimestampNs;
            public uint Width;
            public uint Height;
            public int Format;
            public int SemanticFormat;
            public int TransferMode;
            public int SyncMode;
            public uint DroppedFrameCount;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct SenderInfoArray
        {
            public SenderInfo* Items;
            public uint Count;
        }

        [DllImport(LIBRARY)]
        public static extern int nozzle_sender_create(SenderDesc* desc, NozzleSender** out_sender);

        [DllImport(LIBRARY)]
        public static extern void nozzle_sender_destroy(NozzleSender* sender);

        [DllImport(LIBRARY)]
        public static extern int nozzle_sender_publish_native_texture(
            NozzleSender* sender, void* native_texture, uint width, uint height, int format);

        [DllImport(LIBRARY)]
        public static extern int nozzle_sender_acquire_writable_frame(
            NozzleSender* sender, uint width, uint height, int format, NozzleFrame** out_frame);

        [DllImport(LIBRARY)]
        public static extern int nozzle_sender_commit_frame(NozzleSender* sender, NozzleFrame* frame);

        [DllImport(LIBRARY)]
        public static extern int nozzle_sender_get_info(NozzleSender* sender, SenderInfo* out_info);

        [DllImport(LIBRARY)]
        public static extern int nozzle_receiver_create(ReceiverDesc* desc, NozzleReceiver** out_receiver);

        [DllImport(LIBRARY)]
        public static extern void nozzle_receiver_destroy(NozzleReceiver* receiver);

        [DllImport(LIBRARY)]
        public static extern int nozzle_receiver_acquire_frame(
            NozzleReceiver* receiver, AcquireDesc* desc, NozzleFrame** out_frame);

        [DllImport(LIBRARY)]
        public static extern void nozzle_frame_release(NozzleFrame* frame);

        [DllImport(LIBRARY)]
        public static extern int nozzle_frame_get_info(NozzleFrame* frame, FrameInfo* out_info);

        [DllImport(LIBRARY)]
        public static extern int nozzle_frame_copy_to_native_texture(
            NozzleFrame* frame, void* native_texture, uint width, uint height, int format);

        [DllImport(LIBRARY)]
        public static extern int nozzle_receiver_get_connected_info(
            NozzleReceiver* receiver, ConnectedSenderInfo* out_info);

        [DllImport(LIBRARY)]
        public static extern int nozzle_enumerate_senders(SenderInfoArray* out_array);

        [DllImport(LIBRARY)]
        public static extern void nozzle_free_sender_info_array(SenderInfoArray* array);

        [DllImport(LIBRARY)]
        public static extern int nozzle_device_get_default(NozzleDevice** out_device);

        [DllImport(LIBRARY)]
        public static extern void nozzle_device_destroy(NozzleDevice* device);
    }
}
