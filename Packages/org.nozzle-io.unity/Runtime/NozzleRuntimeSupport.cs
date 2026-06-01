using System;
using System.Text;
using UnityEngine;
using UnityEngine.Rendering;

namespace Nozzle
{
    public static unsafe class NozzleRuntimeSupport
    {
        public const string PackageGitUrl = "https://github.com/nozzle-io/nozzle.unity.git?path=/Packages/org.nozzle-io.unity";
        public const bool BundledNativePlugin = false;
        public const bool UnityNativeBridgeSource = true;
        public const bool UnityRuntimeVerified = false;
        public const string BridgeLibraryName = "nozzle_unity";

        static bool warnedBridgeUnavailable;
        static bool warnedNativeLoadFailure;
        static BridgeSupport cachedSupport;
        static bool hasCachedSupport;

        public struct BridgeSupport
        {
            public uint AbiVersion;
            public bool BridgeBinaryLoaded;
            public bool RuntimeSupported;
            public bool UnityHeadersCompiled;
            public bool UnityGraphicsDeviceAvailable;
            public bool RenderThreadEventsAvailable;
            public bool DirectNozzleCAbiAvailable;
            public string StatusMessage;
        }

        public static bool IsTargetGraphicsApi(GraphicsDeviceType graphicsDeviceType)
        {
            return graphicsDeviceType == GraphicsDeviceType.Metal ||
                   graphicsDeviceType == GraphicsDeviceType.Direct3D11;
        }

        public static string GetRuntimeLimitations()
        {
            return "nozzle_unity bridge source exists, but no bundled bridge binary, no completed sender/receiver/discovery bridge implementation, " +
                   "and no verified Unity Editor/Player runtime support.";
        }

        public static bool TryGetBridgeSupport(out BridgeSupport support)
        {
            if (hasCachedSupport)
            {
                support = cachedSupport;
                return true;
            }

            var nativeSupport = new NozzleNative.SupportInfo();
            try
            {
                int ec = NozzleNative.nozzle_unity_get_support(&nativeSupport);
                if (ec != NozzleNative.STATUS_OK)
                {
                    support = MakeUnavailableSupport($"nozzle_unity_get_support returned {ec}");
                    cachedSupport = support;
                    hasCachedSupport = true;
                    return false;
                }
            }
            catch (DllNotFoundException exception)
            {
                LogNativeLoadFailure(exception);
                support = MakeUnavailableSupport(exception.Message);
                cachedSupport = support;
                hasCachedSupport = true;
                return false;
            }
            catch (EntryPointNotFoundException exception)
            {
                LogNativeLoadFailure(exception);
                support = MakeUnavailableSupport(exception.Message);
                cachedSupport = support;
                hasCachedSupport = true;
                return false;
            }

            string statusMessage;
            fixed (byte* statusMessagePtr = nativeSupport.StatusMessage)
            {
                statusMessage = FixedUtf8ToString(statusMessagePtr, 256);
            }

            support = new BridgeSupport
            {
                AbiVersion = nativeSupport.AbiVersion,
                BridgeBinaryLoaded = nativeSupport.BridgeBinaryLoaded != 0,
                RuntimeSupported = nativeSupport.RuntimeSupported != 0,
                UnityHeadersCompiled = nativeSupport.UnityHeadersCompiled != 0,
                UnityGraphicsDeviceAvailable = nativeSupport.UnityGraphicsDeviceAvailable != 0,
                RenderThreadEventsAvailable = nativeSupport.RenderThreadEventsAvailable != 0,
                DirectNozzleCAbiAvailable = nativeSupport.DirectNozzleCAbiAvailable != 0,
                StatusMessage = statusMessage,
            };

            cachedSupport = support;
            hasCachedSupport = true;
            return true;
        }

        internal static bool RequireBridgeRuntime(string componentName)
        {
            TryGetBridgeSupport(out var support);
            if (support.RuntimeSupported && support.AbiVersion == NozzleNative.BRIDGE_ABI_VERSION)
            {
                if (RequiresRenderThreadDispatch(componentName))
                {
                    if (!NozzleRenderThreadDispatch.ManagedNativeTextureOperationsImplemented)
                    {
                        Debug.LogError(
                            $"[Nozzle] {componentName} runtime remains disabled: managed sender/receiver native-texture operations " +
                            "must be queued through GL.IssuePluginEvent or CommandBuffer.IssuePluginEvent before runtime support can be enabled."
                        );
                        return false;
                    }

                    if (!support.RenderThreadEventsAvailable)
                    {
                        Debug.LogError(
                            $"[Nozzle] {componentName} runtime remains disabled: the bridge reports runtime support but no render-thread event function. " +
                            $"Bridge diagnostics: {FormatBridgeSupportForDiagnostics(support)}"
                        );
                        return false;
                    }
                }

                return true;
            }

            if (warnedBridgeUnavailable) return false;
            warnedBridgeUnavailable = true;

            var graphicsDeviceType = SystemInfo.graphicsDeviceType;
            var graphicsStatus = IsTargetGraphicsApi(graphicsDeviceType)
                ? "target API but still unverified"
                : "unsupported API";

            Debug.LogWarning(
                $"[Nozzle] {componentName} cannot run because the {BridgeLibraryName} bridge does not report runtime support. " +
                $"{GetRuntimeLimitations()} Current graphics API: {graphicsDeviceType} ({graphicsStatus}). " +
                $"Bridge diagnostics: {FormatBridgeSupportForDiagnostics(support)}"
            );
            return false;
        }

        internal static bool IsUnsupportedBridgeStatus(int ec, string operationName)
        {
            if (ec != NozzleNative.STATUS_UNSUPPORTED) return false;

            TryGetBridgeSupport(out var support);
            Debug.LogWarning($"[Nozzle] {operationName} is not implemented by the current nozzle_unity bridge. {FormatBridgeSupportForDiagnostics(support)}");
            return true;
        }

        internal static void LogNativeLoadFailure(Exception exception)
        {
            if (warnedNativeLoadFailure) return;

            warnedNativeLoadFailure = true;
            Debug.LogError(
                $"[Nozzle] Failed to load the native {BridgeLibraryName} bridge plugin. " +
                "This package ships bridge source and C# bindings, but no bundled native binary. " +
                $"Install URL: {PackageGitUrl}. Loader error: {exception.Message}"
            );
        }

        static bool RequiresRenderThreadDispatch(string componentName)
        {
            return componentName == nameof(NozzleSender) || componentName == nameof(NozzleReceiver);
        }

        static BridgeSupport MakeUnavailableSupport(string message)
        {
            return new BridgeSupport
            {
                AbiVersion = 0,
                BridgeBinaryLoaded = false,
                RuntimeSupported = false,
                UnityHeadersCompiled = false,
                UnityGraphicsDeviceAvailable = false,
                RenderThreadEventsAvailable = false,
                DirectNozzleCAbiAvailable = false,
                StatusMessage = message ?? "nozzle_unity bridge unavailable",
            };
        }

        internal static string FormatBridgeSupportForDiagnostics(BridgeSupport support)
        {
            return $"abi={support.AbiVersion}, binary={support.BridgeBinaryLoaded}, runtime={support.RuntimeSupported}, " +
                   $"unity_headers={support.UnityHeadersCompiled}, graphics_device={support.UnityGraphicsDeviceAvailable}, " +
                   $"render_events={support.RenderThreadEventsAvailable}, direct_nozzle_c_abi={support.DirectNozzleCAbiAvailable}, " +
                   $"message='{support.StatusMessage}'";
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
