# nozzle.unity

Unity native plugin for [nozzle](https://github.com/nozzle-io/nozzle) GPU texture sharing.

Send and receive textures between Unity and other nozzle-compatible applications (openFrameworks, Max/MSP, etc.) on macOS and Windows.

## Features

- **NozzleSender**: Publish Unity textures to the nozzle network
- **NozzleReceiver**: Subscribe to textures from nozzle senders
- **NozzleDiscovery**: Enumerate available senders at runtime
- macOS (Metal/IOSurface) and Windows (D3D11) backends
- Unity Package Manager compatible

## Requirements

- Unity 2021.3+
- macOS 12+ (Metal) or Windows 10+ (D3D11)
- Built native plugin (`nozzle_unity.bundle` / `nozzle_unity.dll`)

## Installation

### From Git URL (Unity Package Manager)

1. Open Unity Package Manager (Window > Package Manager)
2. Click "+" > "Add package from git URL..."
3. Enter: `https://github.com/nozzle-io/nozzle.unity.git`

### Manual

1. Clone this repository recursively: `git clone --recursive https://github.com/nozzle-io/nozzle.unity.git`
2. Build the native plugin (see below)
3. Copy the built plugin into your Unity project's `Plugins/` folder

## Building the Native Plugin

```bash
git clone --recursive https://github.com/nozzle-io/nozzle.unity.git
cd nozzle.unity
cmake -B build -DCMAKE_OSX_DEPLOYMENT_TARGET=12.0
cmake --build build --config Release
```

The output plugin:
- macOS: `build/nozzle_unity.bundle`
- Windows: `build/Release/nozzle_unity.dll`

Place the plugin in your Unity project under `Assets/Plugins/Nozzle/`.

## Usage

### Sending Textures

1. Add a `NozzleSender` component to any GameObject
2. Set the sender name (used by receivers to find this sender)
3. Assign a `Texture` (Texture2D or RenderTexture) as the source
4. The texture is published every frame while the component is enabled

### Receiving Textures

1. Add a `NozzleReceiver` component to any GameObject
2. Set the sender name to connect to
3. A `RenderTexture` is automatically created and updated each frame
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
Unity C# (MonoBehaviour)  ←→  P/Invoke  ←→  nozzle_unity (C++ bridge)  ←→  nozzle (C static lib)
```

The native plugin wraps nozzle's C ABI (`nozzle_c.h`) with a handle-based API. Unity never sees raw pointers — all access is through integer handles managed by the bridge.

## License

MIT
