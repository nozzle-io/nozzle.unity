# Graphics API support

The current package does not own Unity graphics-device lifecycle or render-thread execution.

Missing pieces:

- `UnityPluginLoad` / `UnityPluginUnload`
- `IUnityGraphics` device initialize/shutdown handling
- `GL.IssuePluginEvent` or `CommandBuffer.IssuePluginEvent`
- bundled native plugin import settings under `Runtime/Plugins`

Runtime support remains unverified until those pieces exist and pass Unity Editor and Player smoke tests.

Because those pieces are absent, the direct `Texture.GetNativeTexturePtr()` + P/Invoke path is experimental and can be wrong even if it appears to work on one machine.
