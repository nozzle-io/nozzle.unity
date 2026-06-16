# Troubleshooting

## `DllNotFoundException: nozzle_unity`

Expected with the Git UPM package unless you build and provide a native `nozzle_unity` bridge plugin that Unity can load. The package ships source and C# bindings, but it does not commit `libnozzle.dylib`, `nozzle.dll`, or a compiled `nozzle_unity` bridge plugin. CI-staged stub/native ABI artifacts may include a compiled bridge under `Runtime/Plugins/<platform>/`.

## Bridge loads but reports unsupported

Expected for the default CI stub bridge and for CI-staged stub/native ABI artifacts that are built without Unity Native Plugin API headers. They return diagnostics with `runtime_supported = 0`. Unity-header runtime payloads are a separate build mode and still require Editor/Player frame smoke before support is claimed.

## Texture publish/copy fails or does nothing

The current runtime path refuses to proceed unless `nozzle_unity_get_support` reports runtime support. Unity-header runtime payloads wire sender, receiver, and discovery bridge operations to nozzle core, but default CI/release stub payloads do not. Treat runtime failures from stub payloads as expected limitations, and treat Unity-header runtime results as unclaimed until Editor/Player frame smoke proves them.

## Unsupported graphics API

Only Metal and D3D11 are future target APIs. Other APIs are unsupported until the native bridge and smoke tests prove otherwise.
