using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using UnityEngine;

namespace Nozzle
{
    [AddComponentMenu("Nozzle/Nozzle Discovery")]
    public unsafe class NozzleDiscovery : MonoBehaviour
    {
        public List<NozzleSenderInfo> AvailableSenders { get; private set; } = new List<NozzleSenderInfo>();

        public void Refresh()
        {
            if (!NozzleRuntimeSupport.RequireBridgeRuntime(nameof(NozzleDiscovery)))
            {
                AvailableSenders.Clear();
                return;
            }

            AvailableSenders.Clear();

            NozzleNative.SenderInfoArray* array = stackalloc NozzleNative.SenderInfoArray[1];
            int ec;
            try
            {
                ec = NozzleNative.nozzle_unity_discovery_enumerate_senders(array);
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

            if (NozzleRuntimeSupport.IsUnsupportedBridgeStatus(ec, "discovery enumerate_senders")) return;

            if (ec != 0)
            {
                Debug.LogError($"[Nozzle] Bridge enumerate senders failed: {ec}");
                return;
            }

            var results = new List<NozzleSenderInfo>();
            for (uint i = 0; i < array->Count; i++)
            {
                var item = array->Items[i];
                results.Add(new NozzleSenderInfo
                {
                    Name = PtrToString(item.Name),
                    ApplicationName = PtrToString(item.ApplicationName),
                    Id = PtrToString(item.Id),
                    Backend = (NozzleBackendType)item.Backend,
                });
            }

            NozzleNative.nozzle_unity_discovery_free_sender_info_array(array);
            AvailableSenders = results;
        }

        public string[] GetSenderNames()
        {
            var names = new string[AvailableSenders.Count];
            for (int i = 0; i < AvailableSenders.Count; i++)
            {
                names[i] = AvailableSenders[i].Name;
            }
            return names;
        }

        static string PtrToString(byte* ptr)
        {
            if (ptr == null) return "";
            int len = 0;
            while (ptr[len] != 0) len++;
            return Encoding.UTF8.GetString(ptr, len);
        }
    }
}
