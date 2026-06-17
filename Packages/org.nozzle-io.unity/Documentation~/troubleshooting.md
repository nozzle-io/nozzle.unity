# Troubleshooting

## `DllNotFoundException: nozzle_unity`

Expected with the Git UPM package unless you build and provide a native `nozzle_unity` bridge plugin that Unity can load. The package ships source and C# bindings, but it does not commit `libnozzle.dylib`, `nozzle.dll`, or a compiled `nozzle_unity` bridge plugin. CI-staged stub/native ABI artifacts may include a compiled bridge under `Runtime/Plugins/<platform>/`.

## Bridge loads but reports unsupported

Expected for the default CI stub bridge and for CI-staged stub/native ABI artifacts that are built without Unity Native Plugin API headers. They return diagnostics with `runtime_supported = 0`. Unity-header runtime payloads are a separate build mode and still require Player-executed sender/receiver frame smoke before support is claimed.

## Runtime `.tgz` contains the wrong native payloads

Runtime packages are not renamed stub packages. A runtime archive must be named `org.nozzle-io.unity-runtime-latest-<short_sha>.tgz` or `org.nozzle-io.unity-runtime-<tag>.tgz`, must contain only the declared runtime platform payloads (`macos`, `windows-x86_64`), and must validate with `scripts/validate_upm_tgz.py --support-mode runtime --platforms macos,windows-x86_64`. If a stub payload is present, validation must fail. If a declared runtime platform is missing, validation must fail. Linux payloads in the default stub archive do not imply Linux runtime support.

## Unity PluginAPI headers are missing

Expected unless the runtime workflow is running on a controlled machine with Unity installed. Runtime native builds require `NOZZLE_UNITY_USE_UNITY_HEADERS=ON` and an explicit `NOZZLE_UNITY_PLUGIN_API_DIR` pointing at the local Unity `PluginAPI` directory. The package does not vendor those headers and CI must not download them from arbitrary internet sources.

## Texture publish/copy fails or does nothing

The current runtime path refuses to proceed unless `nozzle_unity_get_support` reports runtime support. Unity-header runtime payloads wire sender, receiver, and discovery bridge operations to nozzle core, but default CI/release stub payloads do not. Treat runtime failures from stub payloads as expected limitations, and treat Unity-header runtime results as unclaimed until Player-executed sender/receiver frame smoke proves them.

## Unsupported graphics API

Only Metal and D3D11 are future target APIs. Other APIs are unsupported until the native bridge and smoke tests prove otherwise.
