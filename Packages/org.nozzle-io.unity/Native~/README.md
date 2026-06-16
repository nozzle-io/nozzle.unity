# nozzle_unity native bridge scaffold

This directory contains the native Unity bridge ABI for the package. The Git UPM package remains source-first and does **not** commit compiled `.dll`, `.dylib`, `.bundle`, or `.so` plugin binaries. CI builds staged package artifacts with a compiled `nozzle_unity` binary where the host platform can build it.

## CI stub build

The default CI-safe bridge build does not require Unity headers and intentionally reports `runtime_supported = 0` from `nozzle_unity_get_support`:

```sh
cmake -S . -B build/nozzle_unity_stub -DNOZZLE_UNITY_BUILD_NOZZLE_CORE=OFF
cmake --build build/nozzle_unity_stub --target nozzle_unity
```

That build verifies the exported `nozzle_unity_*` ABI and C# package boundary. It is not a runtime implementation.

## CI stub/native ABI package artifact

The CI artifact build compiles the bridge with the nozzle core submodule and stages a UPM package copy with the native binary under `Runtime/Plugins/<platform>/`:

```sh
cmake -S . -B build/nozzle_unity_native \
  -DNOZZLE_UNITY_BUILD_NOZZLE_CORE=ON \
  -DNOZZLE_BUILD_EXAMPLES=OFF \
  -DNOZZLE_BUILD_TESTS=OFF \
  -DNOZZLE_INSTALL=OFF
cmake --build build/nozzle_unity_native --target nozzle_unity_package_artifact --config Release
```

The default CI artifact is still runtime-unsupported. Without Unity Native Plugin API headers, `nozzle_unity_get_support` must report `runtime_supported = 0`. Unity-header runtime payloads are a separate explicit build mode.

## Real Unity-header build path

A real Unity native plugin build must be configured with Unity Native Plugin API headers supplied by the build environment. This repository does not vendor or download them.

```sh
cmake -S . -B build/nozzle_unity_unity \
  -DNOZZLE_UNITY_USE_UNITY_HEADERS=ON \
  -DNOZZLE_UNITY_PLUGIN_API_DIR=/path/to/Unity/NativePluginAPI \
  -DNOZZLE_UNITY_BUILD_NOZZLE_CORE=ON
cmake --build build/nozzle_unity_unity --target nozzle_unity
```

The Unity-header source compiles `UnityPluginLoad`, `UnityPluginUnload`, `IUnityGraphics` device callbacks, Metal/D3D11 device capture, a render-event function pointer, and queued sender/receiver/discovery calls into nozzle core. It still is not a support claim until Unity Editor and Player smoke tests prove frame exchange.
