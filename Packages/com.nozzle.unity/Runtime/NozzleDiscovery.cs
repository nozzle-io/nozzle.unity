using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using UnityEngine;

namespace Nozzle
{
    [AddComponentMenu("Nozzle/Nozzle Discovery")]
    public class NozzleDiscovery : MonoBehaviour
    {
        public List<NozzleSenderInfo> AvailableSenders { get; private set; } = new List<NozzleSenderInfo>();

        public void Refresh()
        {
            AvailableSenders.Clear();

            var results = new List<NozzleSenderInfo>();
            var callback = new NozzleNative.EnumerateCallback(
                (name, appName, id, backend, ctx) =>
                {
                    results.Add(new NozzleSenderInfo
                    {
                        Name = name,
                        ApplicationName = appName,
                        Id = id,
                        Backend = (NozzleBackendType)backend,
                    });
                }
            );

            int ec = NozzleNative.nozzle_unity_enumerate_senders(callback, IntPtr.Zero);

            if (ec != 0)
            {
                Debug.LogError($"[Nozzle] Enumerate senders failed: {ec}");
                return;
            }

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
    }
}
