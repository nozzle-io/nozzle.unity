# Troubleshooting

## `DllNotFoundException: nozzle_unity`

Expected with the Git UPM package unless you build and provide a native `nozzle_unity` bridge plugin that Unity can load. The package ships source and C# bindings, but it does not commit `libnozzle.dylib`, `nozzle.dll`, or a compiled `nozzle_unity` bridge plugin. CI-staged stub/native ABI artifacts may include a compiled bridge under `Runtime/Plugins/<platform>/`.

## Bridge loads but reports unsupported

Expected for the default CI stub bridge and for CI-staged stub/native ABI artifacts that are built without Unity Native Plugin API headers or completed render-thread/nozzle runtime wiring. They return diagnostics with `runtime_supported = 0`. This exists to prevent false support claims while keeping the ABI buildable in CI.

## Texture publish/copy fails or does nothing

The current runtime path refuses to proceed unless `nozzle_unity_get_support` reports runtime support. Sender, receiver, and discovery bridge operations are not wired to nozzle core yet. Treat runtime failures as expected limitations, not as supported behavior.

## Unsupported graphics API

Only Metal and D3D11 are future target APIs. Other APIs are unsupported until the native bridge and smoke tests prove otherwise.
