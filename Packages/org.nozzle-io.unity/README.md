# Nozzle Texture Sharing for Unity

GPU texture sharing between Unity and other applications via [nozzle](https://github.com/nozzle-io/nozzle).

## Components

| Component | Description |
|-----------|-------------|
| NozzleSender | Publish textures from Unity to nozzle |
| NozzleReceiver | Receive textures from nozzle senders |
| NozzleDiscovery | Enumerate available senders |

## Quick Start

1. Build nozzle as a shared library (`-DBUILD_SHARED_LIBS=ON`)
2. Place `libnozzle.dylib` (macOS) or `nozzle.dll` (Windows) in `Assets/Plugins/Nozzle/`
3. Add a NozzleSender or NozzleReceiver component to a GameObject
