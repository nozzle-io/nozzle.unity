# nozzle.unity

> This codebase is currently in its AI-slob prototyping phase: the code runs on momentum, vibes, and plausible intent.
> Proper debugging will be introduced once demand graduates from hypothetical to measurable.

Unity plugin for [nozzle](https://github.com/nozzle-io/nozzle) GPU texture sharing.

Send and receive textures between Unity and other nozzle-compatible applications (openFrameworks, Max/MSP, TouchDesigner, etc.) on macOS and Windows. GPU-side texture copy — no CPU readback.

## Disclaimer / Notice

This library is currently a work in progress and contains many incomplete features and unverified implementations.
Although it may appear usable at first glance, it may not function correctly.

Please use it with the understanding that no guarantees are made regarding its behavior, and perform debugging, validation, and review as needed.
If you encounter problems, please do not become angry; instead, contributions in the form of Issues or Pull Requests would be greatly appreciated.

## Features

- **NozzleSender**: Publish Unity textures to the nozzle network via GPU copy
- **NozzleReceiver**: Subscribe to textures from nozzle senders via GPU copy
- **NozzleDiscovery**: Enumerate available senders at runtime
- macOS (Metal/IOSurface) and Windows (D3D11) backends
- Unity Package Manager compatible

## Requirements

- Unity 2021.3+
- macOS 12+ (Metal) or Windows 10+ (D3D11)
- Built [nozzle](https://github.com/nozzle-io/nozzle) native library (`libnozzle.a` / `nozzle.lib`)

## Installation

### From Git URL (Unity Package Manager)

1. Open Unity Package Manager (Window > Package Manager)
2. Click "+" > "Add package from git URL..."
3. Enter: `https://github.com/nozzle-io/nozzle.unity.git`

### Manual

1. Clone this repository recursively: `git clone --recursive https://github.com/nozzle-io/nozzle.unity.git`
2. Build the nozzle native library
3. Place the built library in your Unity project's `Assets/Plugins/Nozzle/`

## Building the Native Library

```bash
git clone --recursive https://github.com/nozzle-io/nozzle.unity.git
cd nozzle.unity/nozzle
cmake -B build -DCMAKE_OSX_DEPLOYMENT_TARGET=12.0
cmake --build build --config Release
```

Place `libnozzle.a` (macOS) or `nozzle.lib` (Windows) in your Unity project under `Assets/Plugins/Nozzle/`.

## Usage

### Sending Textures

1. Add a `NozzleSender` component to any GameObject
2. Set the sender name (used by receivers to find this sender)
3. Assign a `Texture` (Texture2D or RenderTexture) as the source
4. The texture is published every frame via GPU copy while the component is enabled

### Receiving Textures

1. Add a `NozzleReceiver` component to any GameObject
2. Set the sender name to connect to
3. A `RenderTexture` is automatically created and updated each frame via GPU copy
4. Read `LastFrameInfo` for metadata (resolution, frame index, timestamp)

### Discovery

1. Add a `NozzleDiscovery` component to any GameObject
2. Call `Refresh()` to enumerate available senders
3. Access `AvailableSenders` for the list of sender info

### Scripting Example

```csharp
// Receive a texture and apply it to a material
var receiver = gameObject.AddComponent<Nozzle.NozzleReceiver>();
receiver.senderName = "MyOFApp";

// Later, in Update or a coroutine:
if (receiver.IsConnected && receiver.TargetTexture != null)
{
    GetComponent<Renderer>().material.mainTexture = receiver.TargetTexture;
}
```

## Architecture

```
Unity C# (MonoBehaviour)  ←→  P/Invoke  ←→  nozzle (C ABI — libnozzle)
```

The C# plugin calls nozzle's C ABI (`nozzle_c.h`) directly. Native texture pointers (`MTLTexture*` / `ID3D11Texture2D*`) from Unity's `Texture.GetNativeTexturePtr()` are passed to `nozzle_sender_publish_native_texture` and `nozzle_frame_copy_to_native_texture` for GPU-side texture copy. No intermediate C++ bridge layer.

## License

MIT

Third-party dependencies:

- [nozzle](https://github.com/nozzle-io/nozzle) — MIT
