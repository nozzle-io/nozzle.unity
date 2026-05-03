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

        void OnEnable()
        {
            if (initialized) return;

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
                    AllowFormatFallback = 1,
                };

                int ec = NozzleNative.nozzle_sender_create(&desc, &handle);
                if (ec != 0)
                {
                    Debug.LogError($"[Nozzle] Failed to create sender: error {ec}");
                    return;
                }
            }

            initialized = true;
        }

        void OnDisable()
        {
            if (!initialized) return;

            NozzleNative.nozzle_sender_destroy(handle);
            handle = null;
            initialized = false;
        }

        void Update()
        {
            if (!initialized || sourceTexture == null) return;

            int w = sourceTexture.width;
            int h = sourceTexture.height;
            IntPtr nativePtr = sourceTexture.GetNativeTexturePtr();

            int ec = NozzleNative.nozzle_sender_publish_native_texture(
                handle, (void*)nativePtr, (uint)w, (uint)h, (int)format
            );

            if (ec != 0)
            {
                Debug.LogError($"[Nozzle] publish_native_texture failed: error {ec}");
            }
        }
    }
}
