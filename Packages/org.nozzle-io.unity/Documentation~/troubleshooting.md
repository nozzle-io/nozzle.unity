# Troubleshooting

## `DllNotFoundException: nozzle_unity`

Expected with the current package unless you build and provide a native `nozzle_unity` bridge plugin that Unity can load. The package ships source and C# bindings, but it does not bundle `libnozzle.dylib`, `nozzle.dll`, or a compiled `nozzle_unity` bridge plugin.

## Bridge loads but reports unsupported

Expected for the default CI stub bridge. The stub is deliberately built without Unity Native Plugin API headers and returns diagnostics with `runtime_supported = 0`. It exists to prevent false support claims while keeping the ABI buildable in CI.

## Texture publish/copy fails or does nothing

The current runtime path refuses to proceed unless `nozzle_unity_get_support` reports runtime support. Sender, receiver, and discovery bridge operations are not wired to nozzle core yet. Treat runtime failures as expected limitations, not as supported behavior.

## Unsupported graphics API

Only Metal and D3D11 are future target APIs. Other APIs are unsupported until the native bridge and smoke tests prove otherwise.
