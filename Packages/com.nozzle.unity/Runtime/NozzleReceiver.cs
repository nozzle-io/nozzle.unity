using System;
using System.Text;
using UnityEngine;

namespace Nozzle
{
    [AddComponentMenu("Nozzle/Nozzle Receiver")]
    public class NozzleReceiver : MonoBehaviour
    {
        [SerializeField] string senderName = "";
        [SerializeField] string applicationName = "";
        [SerializeField] RenderTexture targetTexture;
        [SerializeField] uint timeoutMs = 100;

        int handle;
        bool initialized;
        uint lastWidth;
        uint lastHeight;
        bool connected;

        public bool IsConnected => connected;
        public RenderTexture TargetTexture => targetTexture;
        public NozzleFrameInfo LastFrameInfo { get; private set; }

        void OnEnable()
        {
            if (string.IsNullOrEmpty(senderName))
            {
                Debug.LogWarning("[Nozzle] Receiver senderName is empty");
                return;
            }

            if (initialized) return;

            string appName = string.IsNullOrEmpty(applicationName)
                ? Application.productName
                : applicationName;

            handle = NozzleNative.nozzle_unity_receiver_create(senderName, appName);

            if (handle <= 0)
            {
                Debug.LogError($"[Nozzle] Failed to create receiver: error {handle}");
                return;
            }

            initialized = true;
        }

        void OnDisable()
        {
            if (!initialized) return;

            NozzleNative.nozzle_unity_receiver_release_frame(handle);
            NozzleNative.nozzle_unity_receiver_destroy(handle);
            handle = 0;
            initialized = false;
            connected = false;
        }

        void Update()
        {
            if (!initialized) return;

            int ec = NozzleNative.nozzle_unity_receiver_acquire_frame(handle, timeoutMs);

            if (ec == (int)NozzleErrorCode.Timeout)
            {
                connected = false;
                return;
            }

            if (ec != 0)
            {
                connected = false;

                if (ec == (int)NozzleErrorCode.SenderNotFound || ec == (int)NozzleErrorCode.SenderClosed)
                {
                    return;
                }

                LogError(handle, "acquire_frame");
                return;
            }

            uint w, h;
            int fmt;
            ulong frameIndex, timestampNs;

            ec = NozzleNative.nozzle_unity_receiver_get_frame_info(
                handle, out w, out h, out fmt, out frameIndex, out timestampNs
            );

            if (ec != 0)
            {
                LogError(handle, "get_frame_info");
                return;
            }

            connected = true;
            LastFrameInfo = new NozzleFrameInfo
            {
                FrameIndex = frameIndex,
                TimestampNs = timestampNs,
                Width = w,
                Height = h,
                Format = (NozzleTextureFormat)fmt,
            };

            EnsureTargetTexture((int)w, (int)h, (NozzleTextureFormat)fmt);

            if (targetTexture != null)
            {
                NozzleNative.nozzle_unity_receiver_copy_to_texture(
                    handle, targetTexture.GetNativeTexturePtr(), w, h
                );
            }
        }

        void EnsureTargetTexture(int w, int h, NozzleTextureFormat fmt)
        {
            if (targetTexture != null && lastWidth == w && lastHeight == h)
            {
                return;
            }

            if (targetTexture != null)
            {
                targetTexture.Release();
                Destroy(targetTexture);
            }

            var texFmt = FormatToRenderTextureFormat(fmt);
            targetTexture = new RenderTexture(w, h, 0, texFmt);
            targetTexture.Create();
            lastWidth = (uint)w;
            lastHeight = (uint)h;
        }

        static RenderTextureFormat FormatToRenderTextureFormat(NozzleTextureFormat fmt)
        {
            switch (fmt)
            {
                case NozzleTextureFormat.BGRA8_UNORM:
                case NozzleTextureFormat.RGBA8_UNORM:
                    return RenderTextureFormat.ARGB32;
                case NozzleTextureFormat.BGRA8_SRGB:
                case NozzleTextureFormat.RGBA8_SRGB:
                    return RenderTextureFormat.ARGB32;
                case NozzleTextureFormat.RGBA16_FLOAT:
                    return RenderTextureFormat.ARGBHalf;
                case NozzleTextureFormat.R16_FLOAT:
                    return RenderTextureFormat.RHalf;
                case NozzleTextureFormat.RG16_FLOAT:
                    return RenderTextureFormat.RGHalf;
                case NozzleTextureFormat.RGBA32_FLOAT:
                    return RenderTextureFormat.ARGBFloat;
                case NozzleTextureFormat.R32_FLOAT:
                    return RenderTextureFormat.RFloat;
                case NozzleTextureFormat.RG32_FLOAT:
                    return RenderTextureFormat.RGFloat;
                case NozzleTextureFormat.R16_UNORM:
                    return RenderTextureFormat.R16;
                case NozzleTextureFormat.RG8_UNORM:
                    return RenderTextureFormat.RG16;
                default:
                    return RenderTextureFormat.ARGB32;
            }
        }

        static void LogError(int handle, string operation)
        {
            int ec = NozzleNative.nozzle_unity_get_last_error_code(handle);
            byte[] buf = new byte[256];
            NozzleNative.nozzle_unity_get_last_error_message(handle, buf, 256);
            string msg = Encoding.UTF8.GetString(buf).TrimEnd('\0');
            Debug.LogError($"[Nozzle] {operation} failed: (0x{ec:x}) {msg}");
        }
    }
}
