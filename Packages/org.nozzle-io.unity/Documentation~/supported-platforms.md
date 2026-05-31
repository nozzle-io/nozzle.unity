# Supported platforms

No Unity runtime platform is currently supported as production-ready.

| Platform | Graphics API | Current status |
|----------|--------------|----------------|
| macOS | Metal | Target platform, unverified in Unity Editor/Player. CI builds a staged `nozzle_unity` native artifact, but runtime support is not claimed. |
| Windows | D3D11 | Target platform, unverified in Unity Editor/Player. CI builds a staged `nozzle_unity` native artifact, but runtime support is not claimed. |
| Linux | Vulkan/OpenGL | Unsupported. CI builds a staged `nozzle_unity` native artifact when system dependencies are present, but no proven Unity runtime path exists. |
| Mobile/console | Any | Unsupported. |

The package currently contains C# bindings plus a native bridge ABI. The Git package does not commit compiled native plugins; CI-staged package artifacts may contain a compiled `nozzle_unity` bridge binary under `Runtime/Plugins/<platform>/`. The default bridge build reports `runtime_supported = 0`. Support claims require a compiled native Unity bridge, nozzle core integration, and Editor/Player smoke evidence.
