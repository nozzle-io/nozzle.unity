# Nozzle Texture Sharing for Unity

Experimental Unity Package Manager wrapper for [nozzle](https://github.com/nozzle-io/nozzle).

This package is **not** a production-ready Unity runtime integration yet. The current C# components target a `nozzle_unity` bridge ABI instead of treating direct `DllImport("nozzle")` calls as final. The Git package ships bridge source and diagnostics, but no committed native bridge binary, no Unity Editor/Player runtime support claim, and no verified Unity Editor/Player frame evidence. CI may attach staged package artifacts with a compiled bridge binary; the default release-oriented artifacts are CI-staged stub/native ABI artifacts and remain runtime-disabled. An opt-in Unity-header runtime bridge source path exists for Metal/D3D11 builds with external Unity PluginAPI headers, but support is not claimed until Editor/Player smoke proves it.

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
| `Native~/` | Source bridge ABI with a CI fallback build, a native artifact staging target, and an opt-in Unity-header Metal/D3D11 runtime bridge source path. |

## Runtime limitations

The Git package does not bundle native binaries, and it has no Unity Editor/Player runtime support claim.

- No compiled native plugin or native binary import settings are committed under `Runtime/Plugins`.
- CI-staged stub/native ABI payloads place compiled `nozzle_unity` bridge binaries under `Runtime/Plugins/<platform>/`, but these are only build artifacts and not Editor/Player smoke evidence.
- Release packaging CI may publish a UPM `.tgz` named `org.nozzle-io.unity-latest-<short_sha>.tgz` or `org.nozzle-io.unity-<tag>.tgz`. That archive is validated by static UPM archive / manifest preflight plus native payload hash checks; it is not Unity Editor import evidence.
- Native plugin `.meta` files in release archives are deterministic `PluginImporter` metadata generated for the target plugin paths. Random Unity importer output must not be treated as release evidence.
- The default bridge build compiles without Unity headers and intentionally reports `runtime_supported = 0`.
- The Unity-header bridge path requires externally supplied Unity Native Plugin API headers; this package vendors/downloads none. That source path captures Metal/D3D11 Unity devices and routes queued sender/receiver/discovery operations into nozzle core, but it is not Editor/Player smoke evidence by itself.
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

No compiled native plugin is committed to this package. The staged artifact and UPM `.tgz` release archive are for CI/download validation and must still be treated as runtime unsupported. Native diagnostics alone are not a support claim: sender/receiver runtime also requires managed render-thread dispatch through `GL.IssuePluginEvent` or `CommandBuffer.IssuePluginEvent`, native operation queue wiring, Unity graphics-device lifecycle handling, and Editor/Player smoke evidence.

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
