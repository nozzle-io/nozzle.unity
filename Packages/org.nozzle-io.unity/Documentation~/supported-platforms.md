# Supported platforms

No Unity runtime platform is currently supported as production-ready.

| Platform | Graphics API | Current status |
|----------|--------------|----------------|
| macOS | Metal | Target platform, unverified in Unity Editor/Player. CI builds a staged `nozzle_unity` native artifact, but runtime support is not claimed. |
| Windows | D3D11 | Target platform, unverified in Unity Editor/Player. CI builds a staged `nozzle_unity` native artifact, but runtime support is not claimed. |
| Linux | Vulkan/OpenGL | Unsupported. CI builds a staged `nozzle_unity` native artifact when system dependencies are present, but no proven Unity runtime path exists. |
| Mobile/console | Any | Unsupported. |

The package currently contains C# bindings plus a native bridge ABI. The Git package does not commit compiled native plugins; CI-staged stub/native ABI payloads may contain compiled `nozzle_unity` bridge binaries under `Runtime/Plugins/<platform>/`. Release `.tgz` archives are validated as static UPM archive / manifest preflight plus native payload hash/importer/dependency checks; they are not Unity Editor import or Player runtime evidence. The default bridge build reports `runtime_supported = 0`. Support claims require a compiled native Unity bridge, nozzle core integration, and Editor/Player smoke evidence.
