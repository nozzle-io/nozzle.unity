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
        [SerializeField] NozzleTextureFormat targetFormat = NozzleTextureFormat.BGRA8_UNORM;

        NozzleNative.NozzleReceiver* handle;
        bool initialized;
        bool connected;
        bool warnedMissingTargetTexture;
        ulong nextManagedGeneration = 1;
        NozzleRenderThreadDispatch.PendingOperation pendingAcquireCopy;

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
            NozzleRenderThreadDispatch.CancelReceiverOperations(handle, ref pendingAcquireCopy);

            if (!initialized) return;

            NozzleNative.nozzle_unity_receiver_destroy(handle);
            handle = null;
            initialized = false;
            connected = false;
        }

        void OnDestroy()
        {
            OnDisable();
        }

        void Update()
        {
            if (NozzleRenderThreadDispatch.TryPollOperation(ref pendingAcquireCopy, out var completedStatus))
            {
                connected = completedStatus.State == (int)NozzleNative.OperationState.Completed;
                if (connected)
                {
                    LastFrameInfo = new NozzleFrameInfo
                    {
                        FrameIndex = completedStatus.FrameIndex,
                        Width = completedStatus.Width,
                        Height = completedStatus.Height,
                        Format = (NozzleTextureFormat)completedStatus.TextureFormat,
                    };
                }
            }

            if (!initialized) return;
            if (pendingAcquireCopy.IsActive) return;

            if (!NozzleRenderThreadDispatch.RequireNativeTextureOperationDispatch("receiver acquire/copy native texture")) return;

            if (targetTexture == null)
            {
                connected = false;
                if (!warnedMissingTargetTexture)
                {
                    warnedMissingTargetTexture = true;
                    Debug.LogWarning(
                        "[Nozzle] Receiver native texture copy needs an explicit target RenderTexture in this render-thread bridge slice. " +
                        "The previous blocking acquire_frame/copy path from Update() has been removed."
                    );
                }
                return;
            }

            ulong generation = nextManagedGeneration;
            nextManagedGeneration += 1;
            if (nextManagedGeneration == 0) nextManagedGeneration = 1;

            NozzleRenderThreadDispatch.TryEnqueueReceiverAcquireAndCopy(
                handle,
                targetTexture,
                (int)targetFormat,
                generation,
                out pendingAcquireCopy
            );
        }
    }
}
