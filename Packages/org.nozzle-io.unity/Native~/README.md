# nozzle_unity native bridge scaffold

This directory contains the native Unity bridge ABI for the package. It is source-only: the UPM package does **not** currently ship compiled `.dll`, `.dylib`, `.bundle`, or `.so` plugin binaries.

## CI stub build

The default CI-safe bridge build does not require Unity headers and intentionally reports `runtime_supported = 0` from `nozzle_unity_get_support`:

```sh
cmake -S . -B build/nozzle_unity_stub -DNOZZLE_UNITY_BUILD_NOZZLE_CORE=OFF
cmake --build build/nozzle_unity_stub --target nozzle_unity
```

That build verifies the exported `nozzle_unity_*` ABI and C# package boundary. It is not a runtime implementation.

## Real Unity-header build path

A real Unity native plugin build must be configured with Unity Native Plugin API headers supplied by the build environment. This repository does not vendor or download them.

```sh
cmake -S . -B build/nozzle_unity_unity \
  -DNOZZLE_UNITY_USE_UNITY_HEADERS=ON \
  -DNOZZLE_UNITY_PLUGIN_API_DIR=/path/to/Unity/NativePluginAPI \
  -DNOZZLE_UNITY_BUILD_NOZZLE_CORE=ON
cmake --build build/nozzle_unity_unity --target nozzle_unity
```

The Unity-header source compiles `UnityPluginLoad`, `UnityPluginUnload`, `IUnityGraphics` device callbacks, and a render-event function pointer. Sender, receiver, and discovery operations still return `nozzle_unity_status_unsupported` until the bridge maps Unity render-thread/device state to nozzle core calls and is validated in Unity Editor and Player smoke tests.
