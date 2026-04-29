using System;
using System.Text;
using UnityEngine;

namespace Nozzle
{
    [AddComponentMenu("Nozzle/Nozzle Sender")]
    public class NozzleSender : MonoBehaviour
    {
        [SerializeField] string senderName = "NozzleSender";
        [SerializeField] string applicationName = "";
        [SerializeField] uint ringBufferSize = 3;
        [SerializeField] Texture sourceTexture;
        [SerializeField] NozzleTextureFormat format = NozzleTextureFormat.BGRA8_UNORM;

        int handle;
        bool initialized;

        void OnEnable()
        {
            if (initialized) return;

            string appName = string.IsNullOrEmpty(applicationName)
                ? Application.productName
                : applicationName;

            handle = NozzleNative.nozzle_unity_sender_create(senderName, appName, ringBufferSize);

            if (handle <= 0)
            {
                Debug.LogError($"[Nozzle] Failed to create sender: error {handle}");
                return;
            }

            initialized = true;
        }

        void OnDisable()
        {
            if (!initialized) return;

            NozzleNative.nozzle_unity_sender_destroy(handle);
            handle = 0;
            initialized = false;
        }

        void Update()
        {
            if (!initialized || sourceTexture == null) return;

            int w = sourceTexture.width;
            int h = sourceTexture.height;

            int ec = NozzleNative.nozzle_unity_sender_publish_texture(
                handle, IntPtr.Zero, (uint)w, (uint)h, (int)format
            );

            if (ec != 0)
            {
                LogError(handle, "publish_texture");
                return;
            }

            ec = NozzleNative.nozzle_unity_sender_commit_frame(handle);
            if (ec != 0)
            {
                LogError(handle, "commit_frame");
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
