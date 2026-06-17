# Graphics API support

The package now has a `nozzle_unity` bridge ABI and an opt-in Unity-header source path for Metal/D3D11 device capture and render-thread queued nozzle operations, but no graphics API has validated Player-executed sender/receiver frame-smoke support.

Present scaffolding:

- `nozzle_unity_get_support` diagnostics
- CI stub build without Unity headers
- CI native bridge artifact builds for macOS, Windows, and Linux package staging
- Separate manual runtime artifact workflow for macOS Metal and Windows D3D11 Unity-header payloads
- Opt-in `UnityPluginLoad` / `UnityPluginUnload` source when Unity Native Plugin API headers are provided
- Opt-in `IUnityGraphics` device initialize/shutdown callback source
- Render-event function pointer export for future `GL.IssuePluginEvent` or `CommandBuffer.IssuePluginEvent` use

Runtime artifact boundary:

- Stub artifacts use `org.nozzle-io.unity-latest-<short_sha>.tgz` / `org.nozzle-io.unity-<tag>.tgz` and must report runtime unsupported.
- Runtime artifacts use `org.nozzle-io.unity-runtime-latest-<short_sha>.tgz` / `org.nozzle-io.unity-runtime-<tag>.tgz` and must validate only `--support-mode runtime` payloads.
- Runtime payloads are currently declared for macOS Metal and Windows D3D11 only.
- Linux is not part of the runtime artifact package scope.
- Unity PluginAPI headers must come from a controlled local Unity installation; this package vendors/downloads none.

Missing runtime evidence:

- Editor and Player smoke tests for Metal and D3D11

CI-staged stub/native ABI artifacts only prove that the bridge can compile as a platform binary. Runtime artifacts prove package assembly, Unity-header payload provenance, static payload validation, Unity import, Player build inclusion, and `runtime_supported = true` bridge diagnostics. They do not execute a Player and do not prove sender/receiver frame exchange. Runtime support remains unverified until Player-executed frame smoke proves texture exchange.
