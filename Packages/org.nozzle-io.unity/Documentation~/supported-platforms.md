# Supported platforms

No Unity runtime platform is currently supported as production-ready.

| Platform | Graphics API | Current status |
|----------|--------------|----------------|
| macOS | Metal | Target platform, unverified in Unity Editor/Player. No bundled compiled `nozzle_unity` plugin. |
| Windows | D3D11 | Target platform, unverified in Unity Editor/Player. No bundled compiled `nozzle_unity` plugin. |
| Linux | Vulkan/OpenGL | Unsupported. The CI bridge stub may compile, but no proven Unity runtime path exists. |
| Mobile/console | Any | Unsupported. |

The package currently contains C# bindings plus a source-only native bridge ABI. The default bridge build is a stub that reports `runtime_supported = 0`. Support claims require a compiled native Unity bridge, nozzle core integration, and Editor/Player smoke evidence.
