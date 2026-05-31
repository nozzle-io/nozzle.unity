using System;
using UnityEngine;
using UnityEngine.Rendering;

namespace Nozzle
{
    public static class NozzleRuntimeSupport
    {
        public const string PackageGitUrl = "https://github.com/nozzle-io/nozzle.unity.git?path=/Packages/org.nozzle-io.unity";
        public const bool BundledNativePlugin = false;
        public const bool UnityNativeBridge = false;

        static bool warnedExperimentalRuntime;
        static bool warnedNativeLoadFailure;

        public static bool IsTargetGraphicsApi(GraphicsDeviceType graphicsDeviceType)
        {
            return graphicsDeviceType == GraphicsDeviceType.Metal ||
                   graphicsDeviceType == GraphicsDeviceType.Direct3D11;
        }

        public static string GetRuntimeLimitations()
        {
            return "Experimental direct C ABI path: no bundled native plugin, no nozzle_unity bridge, " +
                   "no Unity render-thread event integration, and no verified Editor/Player runtime support.";
        }

        internal static void WarnExperimentalRuntime(string componentName)
        {
            if (warnedExperimentalRuntime) return;

            warnedExperimentalRuntime = true;
            var graphicsDeviceType = SystemInfo.graphicsDeviceType;
            var graphicsStatus = IsTargetGraphicsApi(graphicsDeviceType)
                ? "target API but still unverified"
                : "unsupported API";

            Debug.LogWarning(
                $"[Nozzle] {componentName} is using the experimental direct C ABI path. " +
                $"{GetRuntimeLimitations()} Current graphics API: {graphicsDeviceType} ({graphicsStatus})."
            );
        }

        internal static void LogNativeLoadFailure(Exception exception)
        {
            if (warnedNativeLoadFailure) return;

            warnedNativeLoadFailure = true;
            Debug.LogError(
                "[Nozzle] Failed to load the native nozzle library. " +
                "This package does not bundle libnozzle.dylib, nozzle.dll, or a nozzle_unity bridge plugin. " +
                $"Install URL: {PackageGitUrl}. Loader error: {exception.Message}"
            );
        }
    }
}
