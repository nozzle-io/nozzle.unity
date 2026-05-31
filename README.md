# nozzle.unity

Experimental Unity Package Manager wrapper for [nozzle](https://github.com/nozzle-io/nozzle) GPU texture sharing.

The uncomfortable truth: this repository is UPM-shaped, but it is **not** a reliable installable Unity runtime integration yet. The current runtime path is direct C# `DllImport("nozzle")` from MonoBehaviours. It does not include a Unity native bridge, render-thread event scheduling, graphics-device lifecycle handling, bundled native binaries, or Unity Editor/Player validation.

## Installation

Use Unity Package Manager with the package-path Git URL:

```text
https://github.com/nozzle-io/nozzle.unity.git?path=/Packages/org.nozzle-io.unity
```

Do not use the repository root URL; the package manifest is under `Packages/org.nozzle-io.unity/package.json`.

## Current status

It does not bundle native binaries or a Unity native plugin, and it has no Unity Editor/Player runtime support claim.


- Package manifest and runtime C# bindings exist.
- `NozzleSender`, `NozzleReceiver`, and `NozzleDiscovery` are experimental direct C ABI components.
- The package does **not** bundle `libnozzle.dylib`, `nozzle.dll`, or a `nozzle_unity` bridge plugin.
- No Unity Editor or Player runtime support is claimed.
- No macOS Metal or Windows D3D11 Unity runtime smoke evidence is present.

## Experimental local native-library path

If you want to experiment anyway, build nozzle as a shared library and make Unity resolve `DllImport("nozzle")` from your project. A common local experiment is placing the native library under a Unity project plugin folder, but that is not a supported package install flow and does not fix render-thread/device-lifecycle correctness.

## Architecture gap

Current implementation:

```text
Unity C# MonoBehaviours -> P/Invoke -> nozzle C ABI
```

Required implementation before real support claims:

```text
Unity C# Runtime API
  -> nozzle_unity native plugin
  -> UnityPluginLoad / UnityPluginUnload
  -> IUnityGraphics device events
  -> GL.IssuePluginEvent or CommandBuffer.IssuePluginEvent render-thread callbacks
  -> nozzle core C/C++ API
```

See `Packages/org.nozzle-io.unity/Documentation~/` for the current support matrix and troubleshooting notes.

## License

MIT. See `LICENSE` and `Packages/org.nozzle-io.unity/Third Party Notices.md`.
