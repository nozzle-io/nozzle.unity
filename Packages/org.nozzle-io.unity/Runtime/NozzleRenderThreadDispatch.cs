using System;
using UnityEngine;

namespace Nozzle
{
    internal static class NozzleRenderThreadDispatch
    {
        internal const bool ManagedNativeTextureOperationsImplemented = false;
        internal const int SenderPublishNativeTextureEvent = 0x4E5A0001;
        internal const int ReceiverAcquireAndCopyNativeTextureEvent = 0x4E5A0002;

        static bool warnedManagedDispatchUnavailable;
        static bool warnedRenderEventUnavailable;

        internal static bool RequireNativeTextureOperationDispatch(string operationName)
        {
            if (!ManagedNativeTextureOperationsImplemented)
            {
                if (!warnedManagedDispatchUnavailable)
                {
                    warnedManagedDispatchUnavailable = true;
                    Debug.LogError(
                        $"[Nozzle] {operationName} is blocked: managed native-texture runtime operations are not implemented until " +
                        "they are marshalled through GL.IssuePluginEvent or CommandBuffer.IssuePluginEvent on Unity's render thread. " +
                        "Do not enable runtime support by only flipping nozzle_unity runtime_supported."
                    );
                }
                return false;
            }

            if (!NozzleRuntimeSupport.TryGetBridgeSupport(out var support) || !support.RuntimeSupported)
            {
                return false;
            }

            if (!support.RenderThreadEventsAvailable)
            {
                WarnRenderEventUnavailable(operationName, support);
                return false;
            }

            IntPtr renderEventFunc;
            try
            {
                renderEventFunc = NozzleNative.nozzle_unity_get_render_event_func();
            }
            catch (DllNotFoundException exception)
            {
                NozzleRuntimeSupport.LogNativeLoadFailure(exception);
                return false;
            }
            catch (EntryPointNotFoundException exception)
            {
                NozzleRuntimeSupport.LogNativeLoadFailure(exception);
                return false;
            }

            if (renderEventFunc == IntPtr.Zero)
            {
                WarnRenderEventUnavailable(operationName, support);
                return false;
            }

            return true;
        }

        internal static void IssuePluginEvent(int eventId)
        {
            IntPtr renderEventFunc = NozzleNative.nozzle_unity_get_render_event_func();
            GL.IssuePluginEvent(renderEventFunc, eventId);
        }

        static void WarnRenderEventUnavailable(string operationName, NozzleRuntimeSupport.BridgeSupport support)
        {
            if (warnedRenderEventUnavailable) return;

            warnedRenderEventUnavailable = true;
            Debug.LogError(
                $"[Nozzle] {operationName} cannot run because the nozzle_unity bridge does not expose a render-thread event function. " +
                $"Bridge diagnostics: {NozzleRuntimeSupport.FormatBridgeSupportForDiagnostics(support)}"
            );
        }
    }
}
