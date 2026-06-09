using System;
using System.Text;
using UnityEngine;
using UnityEngine.Rendering;

namespace Nozzle
{
    internal static unsafe class NozzleRenderThreadDispatch
    {
        internal const bool ManagedNativeTextureOperationsImplemented = false;
        internal const int SenderPublishNativeTextureEvent = NozzleNative.EVENT_SENDER_PUBLISH_NATIVE_TEXTURE;
        internal const int ReceiverAcquireAndCopyNativeTextureEvent = NozzleNative.EVENT_RECEIVER_ACQUIRE_AND_COPY_NATIVE_TEXTURE;

        static bool warnedManagedDispatchUnavailable;
        static bool warnedRenderEventUnavailable;

        internal struct PendingOperation
        {
            public ulong OperationId;
            public ulong ManagedGeneration;
            public UnityEngine.Object StrongTextureReference;
            public string OperationName;

            public bool IsActive => OperationId != 0;

            public void Clear()
            {
                OperationId = 0;
                ManagedGeneration = 0;
                StrongTextureReference = null;
                OperationName = null;
            }
        }

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

        internal static void IssuePluginEvent(CommandBuffer commandBuffer, int eventId)
        {
            if (commandBuffer == null)
            {
                Debug.LogError("[Nozzle] CommandBuffer.IssuePluginEvent dispatch requested with a null CommandBuffer.");
                return;
            }
            IntPtr renderEventFunc = NozzleNative.nozzle_unity_get_render_event_func();
            commandBuffer.IssuePluginEvent(renderEventFunc, eventId);
        }

        internal static bool TryEnqueueSenderPublish(
            NozzleNative.NozzleSender* sender,
            Texture sourceTexture,
            int textureFormat,
            ulong managedGeneration,
            out PendingOperation pendingOperation)
        {
            pendingOperation = default;
            if (sender == null || sourceTexture == null) return false;

            IntPtr nativeTexture = sourceTexture.GetNativeTexturePtr();
            if (nativeTexture == IntPtr.Zero) return false;

            var desc = new NozzleNative.SenderPublishNativeTextureDesc
            {
                Sender = sender,
                NativeTexture = (void*)nativeTexture,
                Width = (uint)sourceTexture.width,
                Height = (uint)sourceTexture.height,
                TextureFormat = textureFormat,
                ManagedGeneration = managedGeneration,
            };

            ulong operationId = 0;
            try
            {
                int ec = NozzleNative.nozzle_unity_sender_enqueue_publish_native_texture(&desc, &operationId);
                if (NozzleRuntimeSupport.IsUnsupportedBridgeStatus(ec, "sender enqueue_publish_native_texture")) return false;
                if (ec != NozzleNative.STATUS_OK)
                {
                    Debug.LogError($"[Nozzle] bridge enqueue_publish_native_texture failed: error {ec}");
                    return false;
                }

                pendingOperation = new PendingOperation
                {
                    OperationId = operationId,
                    ManagedGeneration = managedGeneration,
                    StrongTextureReference = sourceTexture,
                    OperationName = "sender publish_native_texture",
                };
                IssuePluginEvent(SenderPublishNativeTextureEvent);
                return true;
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
        }

        internal static bool TryEnqueueReceiverAcquireAndCopy(
            NozzleNative.NozzleReceiver* receiver,
            RenderTexture targetTexture,
            int textureFormat,
            ulong managedGeneration,
            out PendingOperation pendingOperation)
        {
            pendingOperation = default;
            if (receiver == null || targetTexture == null) return false;

            IntPtr nativeTexture = targetTexture.GetNativeTexturePtr();
            if (nativeTexture == IntPtr.Zero) return false;

            var desc = new NozzleNative.ReceiverAcquireCopyNativeTextureDesc
            {
                Receiver = receiver,
                NativeTexture = (void*)nativeTexture,
                Width = (uint)targetTexture.width,
                Height = (uint)targetTexture.height,
                TextureFormat = textureFormat,
                TimeoutMs = 0,
                ManagedGeneration = managedGeneration,
            };

            ulong operationId = 0;
            try
            {
                int ec = NozzleNative.nozzle_unity_receiver_enqueue_acquire_and_copy_native_texture(&desc, &operationId);
                if (NozzleRuntimeSupport.IsUnsupportedBridgeStatus(ec, "receiver enqueue_acquire_and_copy_native_texture")) return false;
                if (ec != NozzleNative.STATUS_OK)
                {
                    Debug.LogError($"[Nozzle] bridge enqueue_acquire_and_copy_native_texture failed: error {ec}");
                    return false;
                }

                pendingOperation = new PendingOperation
                {
                    OperationId = operationId,
                    ManagedGeneration = managedGeneration,
                    StrongTextureReference = targetTexture,
                    OperationName = "receiver acquire/copy native texture",
                };
                IssuePluginEvent(ReceiverAcquireAndCopyNativeTextureEvent);
                return true;
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
        }

        internal static bool TryPollOperation(ref PendingOperation pendingOperation, out NozzleNative.OperationStatus status)
        {
            status = default;
            if (!pendingOperation.IsActive) return false;

            try
            {
                int ec = NozzleNative.nozzle_unity_operation_get_status(pendingOperation.OperationId, &status);
                if (ec != NozzleNative.STATUS_OK)
                {
                    Debug.LogWarning($"[Nozzle] bridge operation status query failed: op={pendingOperation.OperationId} error={ec}");
                    ReleaseOperation(ref pendingOperation);
                    return true;
                }
            }
            catch (DllNotFoundException exception)
            {
                NozzleRuntimeSupport.LogNativeLoadFailure(exception);
                ReleaseOperation(ref pendingOperation);
                return true;
            }
            catch (EntryPointNotFoundException exception)
            {
                NozzleRuntimeSupport.LogNativeLoadFailure(exception);
                ReleaseOperation(ref pendingOperation);
                return true;
            }

            if (status.State == (int)NozzleNative.OperationState.Queued ||
                status.State == (int)NozzleNative.OperationState.Running)
            {
                return false;
            }

            string message;
            fixed (byte* messagePtr = status.StatusMessage)
            {
                message = FixedUtf8ToString(messagePtr, NozzleNative.STATUS_MESSAGE_CAPACITY);
            }

            if (status.State == (int)NozzleNative.OperationState.Completed)
            {
                Debug.Log($"[Nozzle] bridge operation completed: op={status.OperationId} generation={status.ManagedGeneration}");
            }
            else
            {
                Debug.LogWarning(
                    $"[Nozzle] bridge operation ended without completion: op={status.OperationId} state={status.State} " +
                    $"result={status.Result} generation={status.ManagedGeneration} message='{message}'"
                );
            }

            ReleaseOperation(ref pendingOperation);
            return true;
        }

        internal static void CancelSenderOperations(NozzleNative.NozzleSender* sender, ref PendingOperation pendingOperation)
        {
            try
            {
                if (sender != null) NozzleNative.nozzle_unity_sender_cancel_operations(sender);
            }
            catch (DllNotFoundException exception)
            {
                NozzleRuntimeSupport.LogNativeLoadFailure(exception);
            }
            catch (EntryPointNotFoundException exception)
            {
                NozzleRuntimeSupport.LogNativeLoadFailure(exception);
            }
            ReleaseOperation(ref pendingOperation);
        }

        internal static void CancelReceiverOperations(NozzleNative.NozzleReceiver* receiver, ref PendingOperation pendingOperation)
        {
            try
            {
                if (receiver != null) NozzleNative.nozzle_unity_receiver_cancel_operations(receiver);
            }
            catch (DllNotFoundException exception)
            {
                NozzleRuntimeSupport.LogNativeLoadFailure(exception);
            }
            catch (EntryPointNotFoundException exception)
            {
                NozzleRuntimeSupport.LogNativeLoadFailure(exception);
            }
            ReleaseOperation(ref pendingOperation);
        }

        internal static void ReleaseOperation(ref PendingOperation pendingOperation)
        {
            if (!pendingOperation.IsActive)
            {
                pendingOperation.Clear();
                return;
            }

            try
            {
                NozzleNative.nozzle_unity_operation_release(pendingOperation.OperationId);
            }
            catch (DllNotFoundException exception)
            {
                NozzleRuntimeSupport.LogNativeLoadFailure(exception);
            }
            catch (EntryPointNotFoundException exception)
            {
                NozzleRuntimeSupport.LogNativeLoadFailure(exception);
            }
            pendingOperation.Clear();
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

        static string FixedUtf8ToString(byte* ptr, int capacity)
        {
            if (ptr == null || capacity <= 0) return "";
            int length = 0;
            while (length < capacity && ptr[length] != 0) length++;
            return Encoding.UTF8.GetString(ptr, length);
        }
    }
}
