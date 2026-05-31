# Nozzle Texture Sharing for Unity

Experimental Unity Package Manager wrapper for [nozzle](https://github.com/nozzle-io/nozzle).

This package is **not** a production-ready Unity runtime integration yet. The current C# components call the nozzle C ABI directly via `DllImport("nozzle")`; there is no bundled Unity native bridge plugin, no render-thread callback integration, and no verified Unity Editor/Player runtime support.

## Install

Use the package-path Git URL because `package.json` lives under `Packages/org.nozzle-io.unity`:

```text
https://github.com/nozzle-io/nozzle.unity.git?path=/Packages/org.nozzle-io.unity
```

Installing the UPM package only installs the C# package files. It does **not** install `libnozzle.dylib`, `nozzle.dll`, or a `nozzle_unity` bridge plugin.

## Current components

The current direct path is experimental direct C ABI and exists only as bounded scaffolding.

| Component | Current status |
|-----------|----------------|
| `NozzleSender` | Experimental direct C ABI path. Calls nozzle from `Update()` with `Texture.GetNativeTexturePtr()`. |
| `NozzleReceiver` | Experimental direct C ABI path. Calls nozzle from `Update()` and copies into a `RenderTexture` pointer. |
| `NozzleDiscovery` | Experimental direct C ABI path for sender enumeration. |

## Runtime limitations

It does not bundle native binaries or a Unity native plugin, and it has no Unity Editor/Player runtime support claim.


- No bundled native plugin or native binary import settings are present under `Runtime/Plugins`.
- No `UnityPluginLoad`, `IUnityGraphics`, `GL.IssuePluginEvent`, or `CommandBuffer.IssuePluginEvent` bridge exists in this package.
- Metal and D3D11 may be the intended future targets, but Editor and Player runtime behavior is currently unverified.
- OpenGL, Vulkan, Linux, mobile, and console runtime support are unsupported until proven by Unity runtime tests.
- If you manually provide a nozzle shared library for experiments, Unity must be able to resolve `DllImport("nozzle")`. That is a local experiment path, not a supported install flow.

## Required architecture before support claims

```text
Unity C# Runtime API
  -> Unity native bridge plugin (nozzle_unity)
  -> Unity render-thread/device lifecycle callbacks
  -> nozzle core C/C++ API
```

Until that bridge and its CI/runtime evidence exist, treat this package as package-shape scaffolding plus experimental bindings.
