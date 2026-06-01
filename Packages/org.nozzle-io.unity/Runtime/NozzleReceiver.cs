using System;
using System.Text;
using UnityEngine;

namespace Nozzle
{
    [AddComponentMenu("Nozzle/Nozzle Receiver")]
    public unsafe class NozzleReceiver : MonoBehaviour
    {
        [SerializeField] string senderName = "";
        [SerializeField] string applicationName = "";
        [SerializeField] RenderTexture targetTexture;
        [SerializeField] uint timeoutMs = 100;

        NozzleNative.NozzleReceiver* handle;
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

            if (!NozzleRuntimeSupport.RequireBridgeRuntime(nameof(NozzleReceiver))) return;

            string appName = string.IsNullOrEmpty(applicationName)
                ? Application.productName
                : applicationName;

            var nameBytes = Encoding.UTF8.GetBytes(senderName + '\0');
            var appBytes = Encoding.UTF8.GetBytes(appName + '\0');

            fixed (byte* pName = nameBytes)
            fixed (byte* pApp = appBytes)
            {
                var desc = new NozzleNative.ReceiverDesc
                {
                    Name = pName,
                    ApplicationName = pApp,
                    ReceiveMode = 0,
                };

                try
                {
                    int ec = NozzleNative.nozzle_unity_receiver_create(&desc, &handle);
                    if (NozzleRuntimeSupport.IsUnsupportedBridgeStatus(ec, "receiver create")) return;

                    if (ec != 0)
                    {
                        Debug.LogError($"[Nozzle] Failed to create receiver through nozzle_unity bridge: error {ec}");
                        return;
                    }
                }
                catch (DllNotFoundException exception)
                {
                    NozzleRuntimeSupport.LogNativeLoadFailure(exception);
                    return;
                }
                catch (EntryPointNotFoundException exception)
                {
                    NozzleRuntimeSupport.LogNativeLoadFailure(exception);
                    return;
                }
            }

            initialized = true;
        }

        void OnDisable()
        {
            if (!initialized) return;

            NozzleNative.nozzle_unity_receiver_destroy(handle);
            handle = null;
            initialized = false;
            connected = false;
        }

        void Update()
        {
            if (!initialized) return;
            if (!NozzleRenderThreadDispatch.RequireNativeTextureOperationDispatch("receiver acquire/copy native texture")) return;

            var acquireDesc = new NozzleNative.AcquireDesc { TimeoutMs = timeoutMs };
            NozzleNative.NozzleFrame* frame;

            int ec;
            try
            {
                ec = NozzleNative.nozzle_unity_receiver_acquire_frame(handle, &acquireDesc, &frame);
            }
            catch (DllNotFoundException exception)
            {
                connected = false;
                NozzleRuntimeSupport.LogNativeLoadFailure(exception);
                return;
            }
            catch (EntryPointNotFoundException exception)
            {
                connected = false;
                NozzleRuntimeSupport.LogNativeLoadFailure(exception);
                return;
            }

            if (ec == (int)NozzleErrorCode.Timeout)
            {
                connected = false;
                return;
            }

            if (NozzleRuntimeSupport.IsUnsupportedBridgeStatus(ec, "receiver acquire_frame"))
            {
                connected = false;
                return;
            }

            if (ec != 0)
            {
                connected = false;
                if (ec == (int)NozzleErrorCode.SenderNotFound ||
                    ec == (int)NozzleErrorCode.SenderClosed)
                {
                    return;
                }
                Debug.LogError($"[Nozzle] bridge acquire_frame failed: error {ec}");
                return;
            }

            var info = new NozzleNative.FrameInfo();
            ec = NozzleNative.nozzle_unity_frame_get_info(frame, &info);

            if (ec != 0)
            {
                NozzleNative.nozzle_unity_frame_release(frame);
                Debug.LogError($"[Nozzle] get_frame_info failed: error {ec}");
                return;
            }

            connected = true;
            LastFrameInfo = new NozzleFrameInfo
            {
                FrameIndex = info.FrameIndex,
                TimestampNs = info.TimestampNs,
                Width = info.Width,
                Height = info.Height,
                Format = (NozzleTextureFormat)info.TextureFormat,
                SemanticFormat = (NozzleTextureFormat)info.SemanticFormat,
                TransferMode = (NozzleTransferMode)info.TransferMode,
                SyncMode = (NozzleSyncMode)info.SyncMode,
                DroppedFrameCount = info.DroppedFrameCount,
            };

            EnsureTargetTexture((int)info.Width, (int)info.Height, (NozzleTextureFormat)info.TextureFormat);

            try
            {
                if (targetTexture != null)
                {
                    IntPtr nativePtr = targetTexture.GetNativeTexturePtr();
                    NozzleRenderThreadDispatch.IssuePluginEvent(NozzleRenderThreadDispatch.ReceiverAcquireAndCopyNativeTextureEvent);

                    int copyEc = NozzleNative.nozzle_unity_frame_copy_to_native_texture(
                        frame, (void*)nativePtr, info.Width, info.Height, info.TextureFormat
                    );

                    if (NozzleRuntimeSupport.IsUnsupportedBridgeStatus(copyEc, "receiver frame_copy_to_native_texture"))
                    {
                        connected = false;
                        return;
                    }

                    if (copyEc != 0)
                    {
                        connected = false;
                        Debug.LogError($"[Nozzle] bridge frame_copy_to_native_texture failed: error {copyEc}");
                        return;
                    }
                }
            }
            catch (DllNotFoundException exception)
            {
                connected = false;
                NozzleRuntimeSupport.LogNativeLoadFailure(exception);
            }
            catch (EntryPointNotFoundException exception)
            {
                connected = false;
                NozzleRuntimeSupport.LogNativeLoadFailure(exception);
            }
            finally
            {
                NozzleNative.nozzle_unity_frame_release(frame);
            }
        }

        void EnsureTargetTexture(int w, int h, NozzleTextureFormat fmt)
        {
            if (targetTexture != null && lastWidth == w && lastHeight == h) return;

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
                case NozzleTextureFormat.R8_UNORM:
                case NozzleTextureFormat.RG8_UNORM:
                case NozzleTextureFormat.RGB8_UNORM:
                case NozzleTextureFormat.RGBA8_UNORM:
                case NozzleTextureFormat.BGRA8_UNORM:
                case NozzleTextureFormat.RGBA8_SRGB:
                case NozzleTextureFormat.BGRA8_SRGB:
                    return RenderTextureFormat.ARGB32;
                case NozzleTextureFormat.R16_UNORM:
                    return RenderTextureFormat.R16;
                case NozzleTextureFormat.RG16_UNORM:
                case NozzleTextureFormat.RGB16_UNORM:
                case NozzleTextureFormat.RGBA16_UNORM:
                    return RenderTextureFormat.ARGBHalf;
                case NozzleTextureFormat.R16_FLOAT:
                    return RenderTextureFormat.RHalf;
                case NozzleTextureFormat.RG16_FLOAT:
                    return RenderTextureFormat.RGHalf;
                case NozzleTextureFormat.RGB16_FLOAT:
                case NozzleTextureFormat.RGBA16_FLOAT:
                    return RenderTextureFormat.ARGBHalf;
                case NozzleTextureFormat.R32_FLOAT:
                    return RenderTextureFormat.RFloat;
                case NozzleTextureFormat.RG32_FLOAT:
                    return RenderTextureFormat.RGFloat;
                case NozzleTextureFormat.RGB32_FLOAT:
                case NozzleTextureFormat.RGBA32_FLOAT:
                    return RenderTextureFormat.ARGBFloat;
                case NozzleTextureFormat.R32_UINT:
                case NozzleTextureFormat.RGBA32_UINT:
                case NozzleTextureFormat.RGB32_UINT:
                case NozzleTextureFormat.Depth32_FLOAT:
                    Debug.LogWarning($"[Nozzle] Unsupported RenderTexture format: {fmt}, falling back to ARGB32");
                    return RenderTextureFormat.ARGB32;
                default:
                    Debug.LogWarning($"[Nozzle] Unknown texture format: {fmt}, falling back to ARGB32");
                    return RenderTextureFormat.ARGB32;
            }
        }
    }
}
