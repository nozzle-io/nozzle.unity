# nozzle.unity

Experimental Unity Package Manager wrapper for [nozzle](https://github.com/nozzle-io/nozzle) GPU texture sharing.

The uncomfortable truth: this repository is UPM-shaped and now has a source-level `nozzle_unity` native bridge ABI, but it is **not** a reliable installable Unity runtime integration yet. The C# runtime no longer treats direct `DllImport("nozzle")` calls as the final path; it expects a `nozzle_unity` bridge plugin and refuses to claim runtime support when that bridge reports unsupported diagnostics.

## Installation

Use Unity Package Manager with the package-path Git URL:

```text
https://github.com/nozzle-io/nozzle.unity.git?path=/Packages/org.nozzle-io.unity
```

Do not use the repository root URL; the package manifest is under `Packages/org.nozzle-io.unity/package.json`.

## Current status

The Git UPM package does not bundle native binaries, and it has no Unity Editor/Player runtime support claim. CI now also builds per-OS staged package artifacts that include a compiled `nozzle_unity` bridge binary, but those artifacts are still unsupported at runtime. Even a future bridge that reports `runtime_supported != 0` is not enough by itself: sender/receiver runtime remains blocked until managed render-thread dispatch, native queue wiring, Unity graphics-device lifecycle handling, and Editor/Player smoke evidence exist.

- Package manifest, runtime C# bindings, and a source-only `nozzle_unity` bridge ABI exist.
- `NozzleSender`, `NozzleReceiver`, and `NozzleDiscovery` route through bridge support diagnostics before attempting runtime work.
- The package does **not** bundle `libnozzle.dylib`, `nozzle.dll`, or a compiled `nozzle_unity` bridge plugin.
- CI builds macOS, Windows, and Linux CI-staged stub/native ABI payloads with compiled `nozzle_unity` native bridge binaries when platform dependencies are available.
- CI assembles a validated UPM `.tgz` from those payloads: `org.nozzle-io.unity-latest-<short_sha>.tgz` for `main` and `org.nozzle-io.unity-<tag>.tgz` for tags.
- The `.tgz` validator is static UPM archive / manifest preflight only. It verifies archive shape, native plugin payload hashes, deterministic `PluginImporter` `.meta` files, dependency inspection evidence, and package metadata; it does not run Unity Editor import.
- The default native bridge build compiles without Unity headers and reports runtime support as disabled.
- No Unity Editor or Player runtime support is claimed.
- No macOS Metal or Windows D3D11 Unity runtime smoke evidence is present.

## Native bridge build scaffold

The CI-safe bridge build checks ABI/export shape only:

```sh
cmake -S . -B build/nozzle_unity_stub -DNOZZLE_UNITY_BUILD_NOZZLE_CORE=OFF
cmake --build build/nozzle_unity_stub --target nozzle_unity
```

To build the same staged package shape used by CI:

```sh
cmake -S . -B build/nozzle_unity_native \
  -DNOZZLE_UNITY_BUILD_NOZZLE_CORE=ON \
  -DNOZZLE_BUILD_EXAMPLES=OFF \
  -DNOZZLE_BUILD_TESTS=OFF \
  -DNOZZLE_INSTALL=OFF
cmake --build build/nozzle_unity_native --target nozzle_unity_package_artifact --config Release
```

The staged artifact is written under `build/nozzle_unity_native/nozzle-unity-artifact/Packages/org.nozzle-io.unity` with the native binary under `Runtime/Plugins/<platform>/`. It is a build artifact, not a runtime support claim.

Release packaging CI converts validated platform payloads into a single UPM archive. The aggregate package starts from the checked-in source package and copies only validated `Runtime/Plugins/...` binary plus `.meta` payloads from platform jobs; it does not overlay full platform package trees.

## Unity Editor/Player validation

Static archive checks are not a substitute for Unity. Use `scripts/unity_validate.py` to generate a clean Unity project, install `org.nozzle-io.unity` through UPM as a `file:` dependency, run Editor-side import/compile/plugin importer checks, build a minimal Player, and verify that the expected `nozzle_unity` native plugin is present in the Player output.

The script discovers Unity from `--unity`, then `UNITY_EDITOR` / `UNITY_EDITOR_PATH`, then known platform install paths. For a macOS first pass:

```sh
cmake -S . -B build/local-unity-native \
  -DNOZZLE_UNITY_BUILD_NOZZLE_CORE=ON \
  -DNOZZLE_BUILD_EXAMPLES=OFF \
  -DNOZZLE_BUILD_TESTS=OFF \
  -DNOZZLE_INSTALL=OFF \
  -DNOZZLE_UNITY_ARTIFACT_ROOT="$PWD/build/local-unity-artifact" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_OSX_ARCHITECTURES="arm64;x86_64"
cmake --build build/local-unity-native --target nozzle_unity_package_artifact --config Release

python3 scripts/create_native_payload.py \
  --platform macos \
  --artifact-root build/local-unity-artifact \
  --output-root build/local-unity-payload

python3 scripts/unity_validate.py \
  --target macos \
  --native-payload build/local-unity-payload/native-payload/macos \
  --project build/unity-validation/project
```

Success prints `NOZZLE_UNITY_VALIDATION_RESULT` with the Unity version, package SHA, nozzle SHA, project path, Editor log path, Player output path, and native plugin files found in the Player. A missing or broken Unity Editor is an environment blocker, not a runtime failure; report the exact Unity path and process/signature error instead of claiming validation passed.

A real Unity native plugin build must provide Unity Native Plugin API headers explicitly:

```sh
cmake -S . -B build/nozzle_unity_unity \
  -DNOZZLE_UNITY_USE_UNITY_HEADERS=ON \
  -DNOZZLE_UNITY_PLUGIN_API_DIR=/path/to/Unity/NativePluginAPI
cmake --build build/nozzle_unity_unity --target nozzle_unity
```

This repository vendors/downloads no Unity headers. The Unity-header bridge source contains lifecycle and render-event entry points, but sender/receiver/discovery implementation remains blocked until it is wired to nozzle core and validated in Unity.

## Architecture

Current bounded scaffold:

```text
Unity C# MonoBehaviours
  -> P/Invoke -> nozzle_unity bridge diagnostics/ABI
  -> CI stub fallback or Unity-header lifecycle scaffold
```

Required implementation before real support claims:

```text
Unity C# Runtime API
  -> compiled nozzle_unity native plugin bundled with import settings
  -> UnityPluginLoad / UnityPluginUnload
  -> IUnityGraphics device events
  -> GL.IssuePluginEvent or CommandBuffer.IssuePluginEvent render-thread callbacks
  -> nozzle core C/C++ API
  -> Editor and Player smoke evidence on target graphics APIs
```

See `Packages/org.nozzle-io.unity/Documentation~/` for the current support matrix and troubleshooting notes.

## License

MIT. See `LICENSE` and `Packages/org.nozzle-io.unity/Third Party Notices.md`.
