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


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def require_file(path: Path) -> None:
    if not path.is_file():
        fail(f"required file is missing: {path.relative_to(ROOT)}")


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
    require_text(native, 'const string LIBRARY = "nozzle"')
    require_text(native, "[DllImport(LIBRARY)]")

    required_symbols = [
        "nozzle_sender_create",
        "nozzle_receiver_create",
        "nozzle_frame_get_info",
        "nozzle_frame_copy_to_native_texture",
    ]
    for symbol in required_symbols:
        require_text(native, symbol, f"native symbol {symbol}")

    native_text = native.read_text(encoding="utf-8")
    publish_symbols = [
        "nozzle_sender_publish_native_texture",
        "nozzle_sender_publish_native_texture_ex",
    ]
    if not any(symbol in native_text for symbol in publish_symbols):
        fail("NozzleNative.cs must contain a native texture publish API symbol")


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
    check_submodules()
    print("Project sanity checks passed.")


if __name__ == "__main__":
    main()
