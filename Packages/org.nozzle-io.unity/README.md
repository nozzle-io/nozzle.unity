# Nozzle Texture Sharing for Unity

Experimental Unity Package Manager wrapper for [nozzle](https://github.com/nozzle-io/nozzle).

This package is **not** a production-ready Unity runtime integration yet. The current C# components target a `nozzle_unity` bridge ABI instead of treating direct `DllImport("nozzle")` calls as final. The Git package ships bridge source and diagnostics, but no committed native bridge binary, no Unity Editor/Player runtime support claim, and no verified Unity Editor/Player runtime evidence. CI may attach staged package artifacts with a compiled bridge binary; those artifacts still report unsupported runtime unless the native diagnostics prove otherwise.

## Install

Use the package-path Git URL because `package.json` lives under `Packages/org.nozzle-io.unity`:

```text
https://github.com/nozzle-io/nozzle.unity.git?path=/Packages/org.nozzle-io.unity
```

Installing the UPM package only installs package files. It does **not** install `libnozzle.dylib`, `nozzle.dll`, or a compiled `nozzle_unity` bridge plugin.

## Current components

| Component | Current status |
|-----------|----------------|
| `NozzleSender` | Routes through `nozzle_unity` bridge diagnostics; refuses support when the bridge reports unsupported. |
| `NozzleReceiver` | Routes through `nozzle_unity` bridge diagnostics; no validated render-thread copy path yet. |
| `NozzleDiscovery` | Routes through `nozzle_unity` bridge diagnostics; no supported runtime enumeration claim yet. |
| `Native~/` | Source bridge ABI with a CI fallback build, a native artifact staging target, and an opt-in Unity-header lifecycle scaffold. |

## Runtime limitations

The Git package does not bundle native binaries, and it has no Unity Editor/Player runtime support claim.

- No compiled native plugin or native binary import settings are committed under `Runtime/Plugins`.
- CI-built staged artifacts place a compiled `nozzle_unity` bridge binary under `Runtime/Plugins/<platform>/`, but this is only a build artifact and not Editor/Player smoke evidence.
- The default bridge build compiles without Unity headers and intentionally reports `runtime_supported = 0`.
- The Unity-header bridge path requires externally supplied Unity Native Plugin API headers; this package vendors/downloads none.
- Sender, receiver, and discovery bridge operations are not wired to nozzle core yet.
- Metal and D3D11 are intended future targets, but Editor and Player runtime behavior is currently unverified.
- OpenGL, Vulkan, Linux, mobile, and console runtime support are unsupported until proven by Unity runtime tests.

## Native bridge build scaffold

CI-safe ABI build:

```sh
cmake -S . -B build/nozzle_unity_stub -DNOZZLE_UNITY_BUILD_NOZZLE_CORE=OFF
cmake --build build/nozzle_unity_stub --target nozzle_unity
```

CI-style staged package artifact:

```sh
cmake -S . -B build/nozzle_unity_native \
  -DNOZZLE_UNITY_BUILD_NOZZLE_CORE=ON \
  -DNOZZLE_BUILD_EXAMPLES=OFF \
  -DNOZZLE_BUILD_TESTS=OFF \
  -DNOZZLE_INSTALL=OFF
cmake --build build/nozzle_unity_native --target nozzle_unity_package_artifact --config Release
```

No compiled native plugin is committed to this package. The staged artifact is for CI/download validation and must still be treated as runtime unsupported unless `nozzle_unity_get_support` reports `runtime_supported != 0`.

Unity-header lifecycle build path:

```sh
cmake -S . -B build/nozzle_unity_unity \
  -DNOZZLE_UNITY_USE_UNITY_HEADERS=ON \
  -DNOZZLE_UNITY_PLUGIN_API_DIR=/path/to/Unity/NativePluginAPI
cmake --build build/nozzle_unity_unity --target nozzle_unity
```

## Required architecture before support claims

```text
Unity C# Runtime API
  -> compiled Unity native bridge plugin (nozzle_unity)
  -> Unity render-thread/device lifecycle callbacks
  -> nozzle core C/C++ API
  -> Unity Editor and Player smoke evidence
```

Until that implementation and evidence exist, treat this package as package-shape scaffolding, bridge ABI scaffolding, and diagnostics.
