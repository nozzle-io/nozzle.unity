using System;
using System.Text;
using UnityEngine;

namespace Nozzle
{
    [AddComponentMenu("Nozzle/Nozzle Sender")]
    public unsafe class NozzleSender : MonoBehaviour
    {
        [SerializeField] string senderName = "NozzleSender";
        [SerializeField] string applicationName = "";
        [SerializeField] uint ringBufferSize = 3;
        [SerializeField] Texture sourceTexture;
        [SerializeField] NozzleTextureFormat format = NozzleTextureFormat.BGRA8_UNORM;

        NozzleNative.NozzleSender* handle;
        bool initialized;
        ulong nextManagedGeneration = 1;
        NozzleRenderThreadDispatch.PendingOperation pendingPublish;

        void OnEnable()
        {
            if (initialized) return;

            if (!NozzleRuntimeSupport.RequireBridgeRuntime(nameof(NozzleSender))) return;

            string appName = string.IsNullOrEmpty(applicationName)
                ? Application.productName
                : applicationName;

            var nameBytes = Encoding.UTF8.GetBytes(senderName + '\0');
            var appBytes = Encoding.UTF8.GetBytes(appName + '\0');

            fixed (byte* pName = nameBytes)
            fixed (byte* pApp = appBytes)
            {
                var desc = new NozzleNative.SenderDesc
                {
                    Name = pName,
                    ApplicationName = pApp,
                    RingBufferSize = ringBufferSize,
                    TextureFormat = (int)format,
                };

                try
                {
                    int ec = NozzleNative.nozzle_unity_sender_create(&desc, &handle);
                    if (NozzleRuntimeSupport.IsUnsupportedBridgeStatus(ec, "sender create")) return;

                    if (ec != 0)
                    {
                        Debug.LogError($"[Nozzle] Failed to create sender through nozzle_unity bridge: error {ec}");
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
            NozzleRenderThreadDispatch.CancelSenderOperations(handle, ref pendingPublish);

            if (!initialized) return;

            NozzleNative.nozzle_unity_sender_destroy(handle);
            handle = null;
            initialized = false;
        }

        void OnDestroy()
        {
            OnDisable();
        }

        void Update()
        {
            NozzleRenderThreadDispatch.TryPollOperation(ref pendingPublish, out _);

            if (!initialized || sourceTexture == null) return;
            if (pendingPublish.IsActive) return;

            if (!NozzleRenderThreadDispatch.RequireNativeTextureOperationDispatch("sender publish_native_texture")) return;

            ulong generation = nextManagedGeneration;
            nextManagedGeneration += 1;
            if (nextManagedGeneration == 0) nextManagedGeneration = 1;

            NozzleRenderThreadDispatch.TryEnqueueSenderPublish(
                handle,
                sourceTexture,
                (int)format,
                generation,
                out pendingPublish
            );
        }
    }
}
