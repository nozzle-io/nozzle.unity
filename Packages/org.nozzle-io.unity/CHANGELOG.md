# Changelog

## 0.1.0

Initial package-shape release.

- Added CI native bridge artifact staging for macOS, Windows, and Linux builds without claiming Unity Editor/Player runtime support.
- Added `nozzle_unity` bridge ABI source with a CI stub fallback that compiles without Unity headers.
- Added an opt-in Unity-header lifecycle scaffold for `UnityPluginLoad`, `IUnityGraphics`, and render-event function export.
- Routed `NozzleSender`, `NozzleReceiver`, and `NozzleDiscovery` through explicit bridge support diagnostics instead of direct `DllImport("nozzle")` runtime claims.
- Added UPM manifest under `Packages/org.nozzle-io.unity`.
- Added documentation and sample stubs that explicitly mark Unity runtime support as unverified.
- No committed compiled native plugin, Unity Editor validation, or Player validation is included in this release.
