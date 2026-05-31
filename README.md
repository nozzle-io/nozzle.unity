# nozzle.unity

Experimental Unity Package Manager wrapper for [nozzle](https://github.com/nozzle-io/nozzle) GPU texture sharing.

The uncomfortable truth: this repository is UPM-shaped and now has a source-level `nozzle_unity` native bridge ABI, but it is **not** a reliable installable Unity runtime integration yet. The C# runtime no longer treats direct `DllImport("nozzle")` calls as the final path; it expects a `nozzle_unity` bridge plugin and refuses to claim runtime support when that bridge reports unsupported diagnostics.

## Installation

Use Unity Package Manager with the package-path Git URL:

```text
https://github.com/nozzle-io/nozzle.unity.git?path=/Packages/org.nozzle-io.unity
```

Do not use the repository root URL; the package manifest is under `Packages/org.nozzle-io.unity/package.json`.

## Current status

It does not bundle native binaries, and it has no Unity Editor/Player runtime support claim.

- Package manifest, runtime C# bindings, and a source-only `nozzle_unity` bridge ABI exist.
- `NozzleSender`, `NozzleReceiver`, and `NozzleDiscovery` route through bridge support diagnostics before attempting runtime work.
- The package does **not** bundle `libnozzle.dylib`, `nozzle.dll`, or a compiled `nozzle_unity` bridge plugin.
- The default native bridge build is a CI stub that compiles without Unity headers and reports runtime support as disabled.
- No Unity Editor or Player runtime support is claimed.
- No macOS Metal or Windows D3D11 Unity runtime smoke evidence is present.

## Native bridge build scaffold

The CI-safe bridge build checks ABI/export shape only:

```sh
cmake -S . -B build/nozzle_unity_stub -DNOZZLE_UNITY_BUILD_NOZZLE_CORE=OFF
cmake --build build/nozzle_unity_stub --target nozzle_unity
```

A real Unity native plugin build must provide Unity Native Plugin API headers explicitly:

```sh
cmake -S . -B build/nozzle_unity_unity \
  -DNOZZLE_UNITY_USE_UNITY_HEADERS=ON \
  -DNOZZLE_UNITY_PLUGIN_API_DIR=/path/to/Unity/NativePluginAPI
cmake --build build/nozzle_unity_unity --target nozzle_unity
```

This repository vendors/downloads no Unity headers. The Unity-header bridge source contains lifecycle and render-event entry points, but sender/receiver/discovery implementation remains blocked until it is wired to nozzle core and validated in Unity.

## Architecture

Current bounded scaffold:

```text
Unity C# MonoBehaviours
  -> P/Invoke -> nozzle_unity bridge diagnostics/ABI
  -> CI stub fallback or Unity-header lifecycle scaffold
```

Required implementation before real support claims:

```text
Unity C# Runtime API
  -> compiled nozzle_unity native plugin bundled with import settings
  -> UnityPluginLoad / UnityPluginUnload
  -> IUnityGraphics device events
  -> GL.IssuePluginEvent or CommandBuffer.IssuePluginEvent render-thread callbacks
  -> nozzle core C/C++ API
  -> Editor and Player smoke evidence on target graphics APIs
```

See `Packages/org.nozzle-io.unity/Documentation~/` for the current support matrix and troubleshooting notes.

## License

MIT. See `LICENSE` and `Packages/org.nozzle-io.unity/Third Party Notices.md`.
