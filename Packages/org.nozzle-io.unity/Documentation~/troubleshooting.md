# Troubleshooting

## `DllNotFoundException: nozzle`

Expected with the current package unless you manually provide a native nozzle shared library that Unity can load. The package does not bundle `libnozzle.dylib`, `nozzle.dll`, or a `nozzle_unity` bridge plugin.

## Texture publish/copy fails or behaves inconsistently

The current runtime path calls the nozzle C ABI directly from MonoBehaviour `Update()`. There is no Unity render-thread bridge or graphics-device lifecycle handling yet. Treat runtime failures as expected limitations, not as supported behavior.

## Unsupported graphics API

Only Metal and D3D11 are future target APIs. Other APIs are unsupported until the native bridge and smoke tests prove otherwise.
