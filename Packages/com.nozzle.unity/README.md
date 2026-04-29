# Nozzle Texture Sharing for Unity

GPU texture sharing between Unity and other applications via [nozzle](https://github.com/nozzle-io/nozzle).

## Components

| Component | Description |
|-----------|-------------|
| NozzleSender | Publish textures from Unity to nozzle |
| NozzleReceiver | Receive textures from nozzle senders |
| NozzleDiscovery | Enumerate available senders |

## Quick Start

1. Build the native plugin from the repository root
2. Place `nozzle_unity.bundle` (macOS) or `nozzle_unity.dll` (Windows) in `Assets/Plugins/Nozzle/`
3. Add a NozzleSender or NozzleReceiver component to a GameObject
