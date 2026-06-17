# Supported platforms

No Unity runtime platform is currently supported as production-ready.

| Platform | Graphics API | Current status |
|----------|--------------|----------------|
| macOS | Metal | Runtime artifact target. Manual runtime workflow may package a Unity-header `nozzle_unity` payload, but runtime support is not claimed until Player-executed sender/receiver frame smoke passes. |
| Windows | D3D11 | Runtime artifact target. Manual runtime workflow may package a Unity-header `nozzle_unity` payload, but runtime support is not claimed until Player-executed sender/receiver frame smoke passes. |
| Linux | Vulkan/OpenGL | Unsupported. Stub packaging CI may build a staged `nozzle_unity` native artifact when system dependencies are present, but Linux is excluded from runtime `.tgz` packages. |
| Mobile/console | Any | Unsupported. |

The package currently contains C# bindings plus a native bridge ABI. The Git package does not commit compiled native plugins; CI-staged stub/native ABI payloads may contain compiled `nozzle_unity` bridge binaries under `Runtime/Plugins/<platform>/`. Stub release `.tgz` archives are named `org.nozzle-io.unity-latest-<short_sha>.tgz` or `org.nozzle-io.unity-<tag>.tgz` and are validated as static UPM archive / manifest preflight plus native payload hash/importer/dependency checks; they are not Unity Editor import or Player runtime evidence. The default bridge build reports `runtime_supported = 0`.

Runtime release `.tgz` archives are a separate manual lane named `org.nozzle-io.unity-runtime-latest-<short_sha>.tgz` or `org.nozzle-io.unity-runtime-<tag>.tgz`. They must be built from Unity-header payloads, validated with `--support-mode runtime --platforms macos,windows-x86_64`, and currently include only macOS and Windows payloads. A missing runtime payload or a stub payload in that lane is an invalid release artifact. An opt-in Unity-header Metal/D3D11 runtime bridge source path exists, but support claims still require compiled runtime payloads plus Player-executed sender/receiver frame-smoke evidence.
