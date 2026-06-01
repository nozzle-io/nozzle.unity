# Graphics API support

The package now has a `nozzle_unity` bridge ABI and an opt-in Unity-header source file for graphics-device lifecycle callbacks, but no graphics API has validated runtime support.

Present scaffolding:

- `nozzle_unity_get_support` diagnostics
- CI stub build without Unity headers
- CI native bridge artifact builds for macOS, Windows, and Linux package staging
- Opt-in `UnityPluginLoad` / `UnityPluginUnload` source when Unity Native Plugin API headers are provided
- Opt-in `IUnityGraphics` device initialize/shutdown callback source
- Render-event function pointer export for future `GL.IssuePluginEvent` or `CommandBuffer.IssuePluginEvent` use

Missing runtime implementation:

- committed compiled bridge binaries and Unity import settings under `Runtime/Plugins`
- render-thread sender/receiver work submission
- Unity graphics resource mapping into nozzle core native texture/device calls
- Editor and Player smoke tests for Metal and D3D11

CI-staged stub/native ABI artifacts only prove that the bridge can compile as a platform binary. Runtime support remains unverified until the missing pieces exist and pass Unity Editor and Player smoke tests.
