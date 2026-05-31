#!/usr/bin/env python3
"""Project sanity checks for the nozzle Unity package.

This is intentionally not a Unity Editor build. It validates the package,
assembly definition, native P/Invoke boundary, and recursive submodule state.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = ROOT / "Packages" / "org.nozzle-io.unity"
RUNTIME_ROOT = PACKAGE_ROOT / "Runtime"
NATIVE_SOURCE_ROOT = PACKAGE_ROOT / "Native~"
DOCUMENTATION_ROOT = PACKAGE_ROOT / "Documentation~"
SAMPLES_ROOT = PACKAGE_ROOT / "Samples~"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def require_file(path: Path) -> None:
    if not path.is_file():
        fail(f"required file is missing: {path.relative_to(ROOT)}")


def require_dir(path: Path) -> None:
    if not path.is_dir():
        fail(f"required directory is missing: {path.relative_to(ROOT)}")


def require_meta(path: Path) -> None:
    meta = Path(f"{path}.meta")
    require_file(meta)


def load_json(path: Path) -> dict:
    require_file(path)
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as error:
        fail(f"invalid JSON in {path.relative_to(ROOT)}: {error}")
    if not isinstance(data, dict):
        fail(f"JSON root must be an object: {path.relative_to(ROOT)}")
    return data


def expect_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        fail(f"{label} must be {expected!r}, got {actual!r}")


def expect_present(value: object, label: str) -> None:
    if value in (None, ""):
        fail(f"{label} must be present")


def require_text(path: Path, needle: str, label: str | None = None) -> None:
    require_file(path)
    text = path.read_text(encoding="utf-8")
    if needle not in text:
        fail(f"{path.relative_to(ROOT)} must contain {label or needle!r}")


def check_package_manifest() -> None:
    manifest = load_json(PACKAGE_ROOT / "package.json")
    expect_equal(manifest.get("name"), "org.nozzle-io.unity", "package name")
    expect_present(manifest.get("unity"), "package unity minimum version")
    expect_present(manifest.get("license"), "package license")

    repository = manifest.get("repository")
    if not isinstance(repository, dict):
        fail("package repository must be an object")
    repository_url = repository.get("url")
    if not isinstance(repository_url, str) or "nozzle-io/nozzle.unity" not in repository_url:
        fail("package repository.url must reference nozzle-io/nozzle.unity")

    samples = manifest.get("samples")
    if not isinstance(samples, list) or len(samples) < 3:
        fail("package samples must list the current UPM sample stubs")
    sample_paths = {sample.get("path") for sample in samples if isinstance(sample, dict)}
    expected_sample_paths = {
        "Samples~/SenderSample",
        "Samples~/ReceiverSample",
        "Samples~/DiscoveryDiagnostics",
    }
    if sample_paths != expected_sample_paths:
        fail(f"package samples paths must be {sorted(expected_sample_paths)!r}, got {sorted(sample_paths)!r}")


def check_asmdef() -> None:
    asmdef = load_json(RUNTIME_ROOT / "Nozzle.Unity.asmdef")
    expect_equal(asmdef.get("name"), "Nozzle.Unity", "asmdef name")
    expect_equal(asmdef.get("rootNamespace"), "Nozzle", "asmdef rootNamespace")
    expect_equal(asmdef.get("allowUnsafeCode"), True, "asmdef allowUnsafeCode")


def check_runtime_sources() -> None:
    required_runtime_files = [
        RUNTIME_ROOT / "NozzleTypes.cs",
        RUNTIME_ROOT / "NozzleSender.cs",
        RUNTIME_ROOT / "NozzleReceiver.cs",
        RUNTIME_ROOT / "NozzleDiscovery.cs",
        RUNTIME_ROOT / "NozzleRuntimeSupport.cs",
        RUNTIME_ROOT / "Native" / "NozzleNative.cs",
    ]
    for path in required_runtime_files:
        require_file(path)

    runtime_sources = sorted(RUNTIME_ROOT.rglob("*.cs"))
    if not runtime_sources:
        fail(f"no runtime C# files found under {RUNTIME_ROOT.relative_to(ROOT)}")

    for path in runtime_sources:
        require_text(path, "namespace Nozzle")

    native = RUNTIME_ROOT / "Native" / "NozzleNative.cs"
    native_text = native.read_text(encoding="utf-8")
    require_text(native, 'const string LIBRARY = "nozzle_unity"')
    require_text(native, "[DllImport(LIBRARY)]")
    if 'const string LIBRARY = "nozzle"' in native_text:
        fail("NozzleNative.cs must not bind directly to DllImport(\"nozzle\")")

    forbidden_direct_symbols = [
        "nozzle_sender_create",
        "nozzle_receiver_create",
        "nozzle_frame_get_info",
        "nozzle_frame_copy_to_native_texture",
        "nozzle_enumerate_senders",
    ]
    for symbol in forbidden_direct_symbols:
        if symbol in native_text and f"nozzle_unity_{symbol.removeprefix('nozzle_')}" not in native_text:
            fail(f"NozzleNative.cs must route through nozzle_unity bridge, found stale direct symbol {symbol}")

    required_bridge_symbols = [
        "nozzle_unity_get_support",
        "nozzle_unity_get_render_event_func",
        "nozzle_unity_sender_create",
        "nozzle_unity_sender_publish_native_texture",
        "nozzle_unity_receiver_create",
        "nozzle_unity_receiver_acquire_frame",
        "nozzle_unity_frame_get_info",
        "nozzle_unity_frame_copy_to_native_texture",
        "nozzle_unity_discovery_enumerate_senders",
    ]
    for symbol in required_bridge_symbols:
        require_text(native, symbol, f"bridge symbol {symbol}")

    support = RUNTIME_ROOT / "NozzleRuntimeSupport.cs"
    require_text(support, "BundledNativePlugin = false")
    require_text(support, "UnityNativeBridgeSource = true")
    require_text(support, "UnityRuntimeVerified = false")
    require_text(support, "RequireBridgeRuntime")
    require_text(support, "runtime support")

    for component in [
        RUNTIME_ROOT / "NozzleSender.cs",
        RUNTIME_ROOT / "NozzleReceiver.cs",
        RUNTIME_ROOT / "NozzleDiscovery.cs",
    ]:
        require_text(component, "RequireBridgeRuntime")
        text = component.read_text(encoding="utf-8")
        if "WarnExperimentalRuntime" in text:
            fail(f"{component.relative_to(ROOT)} still uses stale direct-runtime warning path")


def check_docs_and_samples() -> None:
    root_readme = ROOT / "README.md"
    package_readme = PACKAGE_ROOT / "README.md"
    for path in [root_readme, package_readme]:
        require_text(path, "?path=/Packages/org.nozzle-io.unity", "package-path Git URL")
        require_text(path, "nozzle_unity", "bridge ABI wording")
        require_text(path, "does not bundle", "no bundled native plugin warning")
        require_text(path, "no Unity Editor/Player runtime support", "runtime support limitation")

    require_text(PACKAGE_ROOT / "CHANGELOG.md", "nozzle_unity")
    require_file(PACKAGE_ROOT / "LICENSE.md")
    require_file(PACKAGE_ROOT / "Third Party Notices.md")

    required_docs = [
        DOCUMENTATION_ROOT / "supported-platforms.md",
        DOCUMENTATION_ROOT / "graphics-api-support.md",
        DOCUMENTATION_ROOT / "troubleshooting.md",
    ]
    require_dir(DOCUMENTATION_ROOT)
    require_meta(DOCUMENTATION_ROOT)
    for path in required_docs:
        require_file(path)
        require_meta(path)
        require_text(path, "native", "native runtime limitation")
        require_text(path, "nozzle_unity", "bridge runtime limitation")

    required_sample_readmes = [
        SAMPLES_ROOT / "SenderSample" / "README.md",
        SAMPLES_ROOT / "ReceiverSample" / "README.md",
        SAMPLES_ROOT / "DiscoveryDiagnostics" / "README.md",
    ]
    require_dir(SAMPLES_ROOT)
    require_meta(SAMPLES_ROOT)
    for path in required_sample_readmes:
        require_file(path)
        require_meta(path)
        require_text(path, "stub")

    plugins_root = RUNTIME_ROOT / "Plugins"
    native_plugins = []
    if plugins_root.exists():
        native_plugins = [
            path
            for path in plugins_root.rglob("*")
            if path.suffix.lower() in {".dll", ".dylib", ".bundle", ".so"}
        ]
    if not native_plugins:
        require_text(package_readme, "No compiled native plugin")
        require_text(DOCUMENTATION_ROOT / "troubleshooting.md", "DllNotFoundException: nozzle_unity")


def check_native_bridge_sources() -> None:
    required_native_files = [
        NATIVE_SOURCE_ROOT / "README.md",
        NATIVE_SOURCE_ROOT / "include" / "nozzle_unity" / "nozzle_unity_bridge.h",
        NATIVE_SOURCE_ROOT / "src" / "nozzle_unity_bridge_common.cpp",
        NATIVE_SOURCE_ROOT / "src" / "nozzle_unity_bridge_stub.cpp",
        NATIVE_SOURCE_ROOT / "src" / "nozzle_unity_bridge_unity.cpp",
        NATIVE_SOURCE_ROOT / "src" / "nozzle_unity_environment.hpp",
    ]
    for path in required_native_files:
        require_file(path)

    header = NATIVE_SOURCE_ROOT / "include" / "nozzle_unity" / "nozzle_unity_bridge.h"
    for symbol in [
        "NOZZLE_UNITY_ABI_VERSION",
        "nozzle_unity_get_support",
        "nozzle_unity_get_render_event_func",
        "nozzle_unity_sender_create",
        "nozzle_unity_receiver_create",
        "nozzle_unity_discovery_enumerate_senders",
    ]:
        require_text(header, symbol, f"bridge header export {symbol}")

    unity_source = NATIVE_SOURCE_ROOT / "src" / "nozzle_unity_bridge_unity.cpp"
    require_text(unity_source, "UnityPluginLoad")
    require_text(unity_source, "UnityPluginUnload")
    require_text(unity_source, "IUnityGraphics")

    stub_source = NATIVE_SOURCE_ROOT / "src" / "nozzle_unity_bridge_stub.cpp"
    require_text(stub_source, "built without Unity Native Plugin API headers")

    cmake = ROOT / "CMakeLists.txt"
    require_text(cmake, "NOZZLE_UNITY_USE_UNITY_HEADERS")
    require_text(cmake, "NOZZLE_UNITY_PLUGIN_API_DIR")
    require_text(cmake, "nozzle_unity_bridge_stub.cpp")
    require_text(cmake, "nozzle_unity_bridge_unity.cpp")


def check_native_bridge_stub_build() -> None:
    build_dir = ROOT / "build" / "project-sanity-nozzle-unity-stub"
    configure = subprocess.run(
        [
            "cmake",
            "-S",
            str(ROOT),
            "-B",
            str(build_dir),
            "-DNOZZLE_UNITY_BUILD_NOZZLE_CORE=OFF",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if configure.stdout:
        print(configure.stdout, end="")
    if configure.stderr:
        print(configure.stderr, end="", file=sys.stderr)
    if configure.returncode != 0:
        fail(f"cmake configure for nozzle_unity stub failed with exit code {configure.returncode}")

    build = subprocess.run(
        ["cmake", "--build", str(build_dir), "--target", "nozzle_unity"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if build.stdout:
        print(build.stdout, end="")
    if build.stderr:
        print(build.stderr, end="", file=sys.stderr)
    if build.returncode != 0:
        fail(f"cmake build for nozzle_unity stub failed with exit code {build.returncode}")


def check_submodules() -> None:
    result = subprocess.run(
        ["git", "submodule", "status", "--recursive"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        fail(f"git submodule status --recursive failed with exit code {result.returncode}")

    for line in result.stdout.splitlines():
        if line.startswith(("-", "+", "U")):
            fail(f"submodule is not cleanly initialized at recorded gitlink: {line}")

    require_file(ROOT / "nozzle" / "include" / "nozzle" / "nozzle_c.h")
    require_file(ROOT / "nozzle" / "CMakeLists.txt")


def main() -> None:
    print("nozzle.unity: Project Sanity only; no Unity Editor build/test coverage.")
    check_package_manifest()
    check_asmdef()
    check_runtime_sources()
    check_native_bridge_sources()
    check_docs_and_samples()
    check_submodules()
    check_native_bridge_stub_build()
    print("Project sanity checks passed.")


if __name__ == "__main__":
    main()
