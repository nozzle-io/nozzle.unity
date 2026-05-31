# Supported platforms

No Unity runtime platform is currently supported as production-ready.

| Platform | Graphics API | Current status |
|----------|--------------|----------------|
| macOS | Metal | Target platform, unverified in Unity Editor/Player. No bundled native plugin. |
| Windows | D3D11 | Target platform, unverified in Unity Editor/Player. No bundled native plugin. |
| Linux | Vulkan/OpenGL | Unsupported. No proven Unity runtime path. |
| Mobile/console | Any | Unsupported. |

The package currently contains experimental direct C ABI bindings only. Support claims require a native Unity bridge plus Editor and Player smoke evidence.
