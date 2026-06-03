#!/usr/bin/env python3
"""Shared release artifact contract helpers for nozzle.unity."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PACKAGE_NAME = "org.nozzle-io.unity"
PACKAGE_ROOT_RELATIVE = Path("Packages") / PACKAGE_NAME
VALIDATION_SCHEMA_VERSION = 1
EXPECTED_SUPPORT_MODE = "stub"
REQUIRED_EXPORTS = [
    "nozzle_unity_get_support",
    "nozzle_unity_get_version",
    "nozzle_unity_get_render_event_func",
    "nozzle_unity_sender_create",
    "nozzle_unity_sender_publish_native_texture",
    "nozzle_unity_receiver_create",
    "nozzle_unity_receiver_acquire_frame",
    "nozzle_unity_frame_get_info",
    "nozzle_unity_frame_copy_to_native_texture",
    "nozzle_unity_discovery_enumerate_senders",
]
FORBIDDEN_PACKAGE_PARTS = {
    ".git",
    ".github",
    "build",
    "Library",
    "Temp",
    "Obj",
    "Logs",
    "UserSettings",
    "validation.json",
}


@dataclass(frozen=True)
class PlatformContract:
    key: str
    host_system: str
    plugin_relative_path: Path
    unity_platform: str
    cpu: str
    expected_architectures: tuple[str, ...]
    dependency_tool: str


PLATFORMS: dict[str, PlatformContract] = {
    "macos": PlatformContract(
        key="macos",
        host_system="Darwin",
        plugin_relative_path=Path("Runtime") / "Plugins" / "macOS" / "libnozzle_unity.dylib",
        unity_platform="OSX",
        cpu="AnyCPU",
        expected_architectures=("x86_64", "arm64"),
        dependency_tool="otool -L",
    ),
    "windows-x86_64": PlatformContract(
        key="windows-x86_64",
        host_system="Windows",
        plugin_relative_path=Path("Runtime") / "Plugins" / "Windows" / "x86_64" / "nozzle_unity.dll",
        unity_platform="Windows",
        cpu="x86_64",
        expected_architectures=("x86_64",),
        dependency_tool="dumpbin /DEPENDENTS",
    ),
    "linux-x86_64": PlatformContract(
        key="linux-x86_64",
        host_system="Linux",
        plugin_relative_path=Path("Runtime") / "Plugins" / "Linux" / "x86_64" / "libnozzle_unity.so",
        unity_platform="Linux",
        cpu="x86_64",
        expected_architectures=("x86_64",),
        dependency_tool="ldd",
    ),
}

SYSTEM_DEPENDENCY_ALLOWLIST: dict[str, set[str]] = {
    "macos": {
        "/usr/lib/libSystem.B.dylib",
        "/usr/lib/libc++.1.dylib",
        "/usr/lib/libobjc.A.dylib",
        "/System/Library/Frameworks/Foundation.framework/Versions/C/Foundation",
        "/System/Library/Frameworks/Accelerate.framework/Versions/A/Accelerate",
        "/System/Library/Frameworks/IOSurface.framework/Versions/A/IOSurface",
        "/System/Library/Frameworks/Metal.framework/Versions/A/Metal",
        "/System/Library/Frameworks/OpenGL.framework/Versions/A/OpenGL",
        "/System/Library/Frameworks/CoreFoundation.framework/Versions/A/CoreFoundation",
        "/System/Library/Frameworks/CoreGraphics.framework/Versions/A/CoreGraphics",
        "/System/Library/Frameworks/IOKit.framework/Versions/A/IOKit",
    },
    "linux-x86_64": {
        "linux-vdso.so.1",
        "libc.so.6",
        "libstdc++.so.6",
        "libm.so.6",
        "libgcc_s.so.1",
        "ld-linux-x86-64.so.2",
        "libpthread.so.0",
        "libdl.so.2",
        "libdrm.so.2",
        "libexpat.so.1",
        "libgbm.so.1",
        "libEGL.so.1",
        "libGL.so.1",
        "libGLdispatch.so.0",
        "libGLX.so.0",
        "libX11.so.6",
        "libXau.so.6",
        "libXdmcp.so.6",
        "libxcb.so.1",
        "libbsd.so.0",
        "libmd.so.0",
    },
    "windows-x86_64": {
        "ADVAPI32.dll",
        "api-ms-win-crt-convert-l1-1-0.dll",
        "api-ms-win-crt-environment-l1-1-0.dll",
        "api-ms-win-crt-filesystem-l1-1-0.dll",
        "api-ms-win-crt-heap-l1-1-0.dll",
        "api-ms-win-crt-locale-l1-1-0.dll",
        "api-ms-win-crt-math-l1-1-0.dll",
        "api-ms-win-crt-private-l1-1-0.dll",
        "api-ms-win-crt-runtime-l1-1-0.dll",
        "api-ms-win-crt-stdio-l1-1-0.dll",
        "api-ms-win-crt-string-l1-1-0.dll",
        "api-ms-win-crt-time-l1-1-0.dll",
        "api-ms-win-crt-utility-l1-1-0.dll",
        "D3D11.dll",
        "DXGI.dll",
        "KERNEL32.dll",
        "MSVCP140.dll",
        "ucrtbase.dll",
        "VCRUNTIME140.dll",
        "VCRUNTIME140_1.dll",
    },
}

MACOS_ALLOWED_SYSTEM_PREFIXES = (
    "/usr/lib/",
    "/System/Library/",
)


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def repo_root_from_script(script_path: Path) -> Path:
    return script_path.resolve().parents[1]


def display_path(path: Path, root: Path | None = None) -> str:
    if root is not None:
        try:
            return str(path.relative_to(root))
        except ValueError:
            pass
    return str(path)


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"invalid JSON in {path}: {error}")
    if not isinstance(data, dict):
        fail(f"JSON root must be an object: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deterministic_guid(relative_path: Path) -> str:
    normalized = relative_path.as_posix()
    return hashlib.sha1(f"{PACKAGE_NAME}:{normalized}".encode("utf-8")).hexdigest()[:32]


def plugin_meta_text(contract: PlatformContract) -> str:
    relative_meta = Path(f"{contract.plugin_relative_path.as_posix()}.meta")
    guid = deterministic_guid(relative_meta)
    return f"""fileFormatVersion: 2
guid: {guid}
PluginImporter:
  externalObjects: {{}}
  serializedVersion: 2
  iconMap: {{}}
  executionOrder: {{}}
  defineConstraints: []
  isPreloaded: 0
  isOverridable: 0
  isExplicitlyReferenced: 0
  validateReferences: 1
  platformData:
  - first:
      Any: 
    second:
      enabled: 0
      settings: {{}}
  - first:
      Editor: Editor
    second:
      enabled: 1
      settings:
        CPU: {contract.cpu}
        OS: {contract.unity_platform}
  - first:
      Standalone: {contract.unity_platform}
    second:
      enabled: 1
      settings:
        CPU: {contract.cpu}
        OS: {contract.unity_platform}
  userData: nozzle.unity deterministic native plugin importer for {contract.key}
  assetBundleName: 
  assetBundleVariant: 
"""


def validate_plugin_meta(meta_path: Path, contract: PlatformContract, package_root: Path) -> dict[str, str]:
    if not meta_path.is_file():
        fail(f"native plugin .meta is missing: {display_path(meta_path, package_root)}")
    expected = plugin_meta_text(contract)
    actual = meta_path.read_text(encoding="utf-8")
    if actual != expected:
        fail(f"native plugin .meta is not deterministic importer metadata for {contract.key}: {display_path(meta_path, package_root)}")
    for needle in ["PluginImporter:", "enabled: 0", "enabled: 1", f"CPU: {contract.cpu}", f"OS: {contract.unity_platform}"]:
        if needle not in actual:
            fail(f"native plugin .meta missing {needle!r}: {display_path(meta_path, package_root)}")
    return {"relative_path": str(meta_path.relative_to(package_root).as_posix()), "sha256": sha256_file(meta_path)}


class NativeSupportInfo(ctypes.Structure):
    _fields_ = [
        ("abi_version", ctypes.c_uint32),
        ("bridge_binary_loaded", ctypes.c_uint32),
        ("runtime_supported", ctypes.c_uint32),
        ("unity_headers_compiled", ctypes.c_uint32),
        ("unity_graphics_device_available", ctypes.c_uint32),
        ("render_thread_events_available", ctypes.c_uint32),
        ("direct_nozzle_c_abi_available", ctypes.c_uint32),
        ("status_message", ctypes.c_char * 256),
    ]


def load_native_library(native_plugin: Path) -> ctypes.CDLL:
    try:
        if platform.system() == "Windows":
            return ctypes.WinDLL(str(native_plugin))
        return ctypes.CDLL(str(native_plugin))
    except OSError as error:
        fail(f"failed to load native plugin {native_plugin}: {error}")


def check_exported_symbols(native_plugin: Path, library: ctypes.CDLL) -> dict[str, Any]:
    missing: list[str] = []
    for symbol in REQUIRED_EXPORTS:
        try:
            getattr(library, symbol)
        except AttributeError:
            missing.append(symbol)
    if missing:
        fail(f"native plugin {native_plugin} is missing exported symbols: {', '.join(missing)}")
    return {"required": REQUIRED_EXPORTS, "missing": [], "result": "pass"}


def check_native_support_contract(native_plugin: Path, library: ctypes.CDLL) -> dict[str, Any]:
    get_support = library.nozzle_unity_get_support
    get_support.argtypes = [ctypes.POINTER(NativeSupportInfo)]
    get_support.restype = ctypes.c_int32

    support = NativeSupportInfo()
    status = get_support(ctypes.byref(support))
    if status != 0:
        fail(f"nozzle_unity_get_support returned {status} for {native_plugin}")
    message = bytes(support.status_message).split(b"\0", 1)[0].decode("utf-8", errors="replace")
    fields = {
        "abi_version": int(support.abi_version),
        "bridge_binary_loaded": int(support.bridge_binary_loaded),
        "runtime_supported": int(support.runtime_supported),
        "unity_headers_compiled": int(support.unity_headers_compiled),
        "unity_graphics_device_available": int(support.unity_graphics_device_available),
        "render_thread_events_available": int(support.render_thread_events_available),
        "direct_nozzle_c_abi_available": int(support.direct_nozzle_c_abi_available),
        "status_message": message,
    }
    expected = {
        "abi_version": 1,
        "bridge_binary_loaded": 1,
        "runtime_supported": 0,
        "unity_headers_compiled": 0,
        "render_thread_events_available": 0,
    }
    for key, value in expected.items():
        if fields[key] != value:
            fail(f"stub native support field {key} must be {value}, got {fields[key]} for {native_plugin}")
    if "CI stub" not in message or "runtime" not in message:
        fail(f"native support message must identify CI stub/runtime-disabled boundary, got {message!r}")
    return {"expected_mode": EXPECTED_SUPPORT_MODE, "fields": fields, "result": "pass"}


def run_command(command: list[str], cwd: Path | None = None) -> tuple[str, str]:
    result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        fail(f"command failed with exit code {result.returncode}: {' '.join(command)}")
    return result.stdout, result.stderr


def parse_macos_dependencies(output: str, native_plugin: Path) -> list[str]:
    deps: list[str] = []
    for line in output.splitlines():
        if not line.startswith(("\t", " ")):
            continue
        stripped = line.strip()
        if not stripped:
            continue
        dependency = stripped.split(" (", 1)[0]
        if Path(dependency).name == native_plugin.name:
            continue
        deps.append(dependency)
    return deps


def parse_linux_dependencies(output: str) -> list[str]:
    deps: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if "not found" in stripped:
            deps.append(stripped)
            continue
        if "=>" in stripped:
            deps.append(stripped.split("=>", 1)[0].strip())
        else:
            deps.append(Path(stripped.split()[0]).name)
    return deps


def parse_windows_dependencies(output: str) -> list[str]:
    deps: list[str] = []
    in_section = False
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("Image has the following dependencies"):
            in_section = True
            continue
        if not in_section:
            continue
        if stripped.endswith(":"):
            continue
        if re.match(r"^[A-Za-z0-9_.-]+\.dll$", stripped, flags=re.IGNORECASE):
            deps.append(stripped)
    return deps


def reject_bad_dependencies(contract: PlatformContract, dependencies: list[str]) -> list[str]:
    rejected: list[str] = []
    allowlist = SYSTEM_DEPENDENCY_ALLOWLIST[contract.key]
    for dep in dependencies:
        dep_basename = Path(dep).name
        dep_lower = dep_basename.lower()
        if "not found" in dep:
            rejected.append(dep)
            continue
        if dep_lower in {"libnozzle.dylib", "libnozzle.so", "nozzle.dll"} or dep_lower.startswith("libnozzle.so."):
            rejected.append(dep)
            continue
        if contract.key == "macos":
            if dep.startswith("@rpath/") or dep.startswith("@loader_path/") or dep.startswith("@executable_path/"):
                rejected.append(dep)
            elif dep not in allowlist and not dep.startswith(MACOS_ALLOWED_SYSTEM_PREFIXES):
                rejected.append(dep)
        elif contract.key == "linux-x86_64":
            if dep_basename not in allowlist:
                rejected.append(dep)
        elif contract.key == "windows-x86_64":
            allowed_lower = {item.lower() for item in allowlist}
            if dep_lower not in allowed_lower:
                rejected.append(dep)
    if rejected:
        fail(f"unexpected or unstaged loader dependencies for {contract.key}: {', '.join(rejected)}")
    return rejected


def inspect_dependencies(native_plugin: Path, contract: PlatformContract, root: Path) -> dict[str, Any]:
    if contract.key == "macos":
        command = ["otool", "-L", str(native_plugin)]
        stdout, _ = run_command(command, cwd=root)
        deps = parse_macos_dependencies(stdout, native_plugin)
    elif contract.key == "linux-x86_64":
        command = ["ldd", str(native_plugin)]
        stdout, _ = run_command(command, cwd=root)
        deps = parse_linux_dependencies(stdout)
    elif contract.key == "windows-x86_64":
        dumpbin = shutil.which("dumpbin")
        if dumpbin is None:
            fail("Windows dependency inspection requires dumpbin; configure a Visual Studio developer environment instead of skipping")
        command = [dumpbin, "/DEPENDENTS", str(native_plugin)]
        stdout, _ = run_command(command, cwd=root)
        deps = parse_windows_dependencies(stdout)
    else:
        fail(f"unsupported platform dependency contract: {contract.key}")
    rejected = reject_bad_dependencies(contract, deps)
    return {
        "tool": contract.dependency_tool,
        "command": command,
        "allowed_dependencies": sorted(SYSTEM_DEPENDENCY_ALLOWLIST[contract.key]),
        "allowed_system_prefixes": list(MACOS_ALLOWED_SYSTEM_PREFIXES) if contract.key == "macos" else [],
        "dependencies": deps,
        "rejected": rejected,
        "result": "pass",
    }


def inspect_architecture(native_plugin: Path, contract: PlatformContract, root: Path) -> dict[str, Any]:
    if contract.key == "macos":
        command = ["lipo", "-info", str(native_plugin)]
        stdout, _ = run_command(command, cwd=root)
        archs = [arch for arch in contract.expected_architectures if arch in stdout]
    elif contract.key == "linux-x86_64":
        readelf = shutil.which("readelf")
        if readelf is not None:
            command = [readelf, "-h", str(native_plugin)]
            stdout, _ = run_command(command, cwd=root)
            archs = ["x86_64"] if "Advanced Micro Devices X86-64" in stdout or "X86-64" in stdout else []
        else:
            command = ["file", str(native_plugin)]
            stdout, _ = run_command(command, cwd=root)
            archs = ["x86_64"] if "x86-64" in stdout or "x86_64" in stdout else []
    elif contract.key == "windows-x86_64":
        dumpbin = shutil.which("dumpbin")
        if dumpbin is None:
            fail("Windows architecture inspection requires dumpbin; configure a Visual Studio developer environment instead of skipping")
        command = [dumpbin, "/HEADERS", str(native_plugin)]
        stdout, _ = run_command(command, cwd=root)
        archs = ["x86_64"] if "machine (x64)" in stdout.lower() or "8664 machine" in stdout.lower() else []
    else:
        fail(f"unsupported platform architecture contract: {contract.key}")
    missing = [arch for arch in contract.expected_architectures if arch not in archs]
    if missing:
        fail(f"native plugin architecture for {contract.key} missing {missing}; output from {' '.join(command)} did not prove {contract.expected_architectures}")
    return {"tool": command[0], "command": command, "parsed_architectures": archs, "expected_architectures": list(contract.expected_architectures), "result": "pass"}


def validate_payload_schema(payload_dir: Path, platform_key: str | None = None, expected_source_commit: str | None = None) -> dict[str, Any]:
    validation_path = payload_dir / "validation.json"
    data = read_json(validation_path)
    if data.get("schema_version") != VALIDATION_SCHEMA_VERSION:
        fail(f"payload validation schema_version must be {VALIDATION_SCHEMA_VERSION}: {validation_path}")
    key = data.get("platform")
    if not isinstance(key, str) or key not in PLATFORMS:
        fail(f"payload validation has invalid platform: {key!r}")
    if platform_key is not None and key != platform_key:
        fail(f"payload platform mismatch: expected {platform_key}, got {key}")
    contract = PLATFORMS[key]
    source_commit = data.get("source_commit")
    if not isinstance(source_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        fail(f"payload validation source_commit must be a 40-character git SHA: {validation_path}")
    if expected_source_commit is not None and source_commit != expected_source_commit:
        fail(f"payload source_commit mismatch for {key}: expected {expected_source_commit}, got {source_commit}")
    if data.get("expected_support_mode") != EXPECTED_SUPPORT_MODE:
        fail(f"payload expected_support_mode must be {EXPECTED_SUPPORT_MODE}: {validation_path}")
    binary_relative = data.get("binary", {}).get("relative_path")
    meta_relative = data.get("meta", {}).get("relative_path")
    if binary_relative != contract.plugin_relative_path.as_posix():
        fail(f"payload binary path must be {contract.plugin_relative_path.as_posix()}, got {binary_relative!r}")
    expected_meta = f"{contract.plugin_relative_path.as_posix()}.meta"
    if meta_relative != expected_meta:
        fail(f"payload meta path must be {expected_meta}, got {meta_relative!r}")
    binary_path = payload_dir / binary_relative
    meta_path = payload_dir / meta_relative
    if not binary_path.is_file():
        fail(f"payload binary missing: {binary_path}")
    if not meta_path.is_file():
        fail(f"payload meta missing: {meta_path}")
    if sha256_file(binary_path) != data.get("binary", {}).get("sha256"):
        fail(f"payload binary hash mismatch: {binary_path}")
    if sha256_file(meta_path) != data.get("meta", {}).get("sha256"):
        fail(f"payload meta hash mismatch: {meta_path}")
    validate_plugin_meta(meta_path, contract, payload_dir)
    for rel_path in payload_files(payload_dir):
        if rel_path == Path("validation.json"):
            continue
        if rel_path not in {contract.plugin_relative_path, Path(f"{contract.plugin_relative_path.as_posix()}.meta")}: 
            fail(f"payload contains unexpected file outside allowed plugin payload: {rel_path.as_posix()}")
    required_sections = ["architecture", "dependencies", "exports", "support"]
    for section in required_sections:
        if not isinstance(data.get(section), dict):
            fail(f"payload validation missing object section {section}: {validation_path}")
        if data[section].get("result") != "pass":
            fail(f"payload validation section {section} did not pass: {validation_path}")
    return data


def payload_files(payload_dir: Path) -> list[Path]:
    return sorted(path.relative_to(payload_dir) for path in payload_dir.rglob("*") if path.is_file())


def validate_no_forbidden_package_files(package_root: Path) -> None:
    for path in package_root.rglob("*"):
        rel = path.relative_to(package_root)
        if any(part in FORBIDDEN_PACKAGE_PARTS for part in rel.parts):
            fail(f"forbidden file leaked into UPM package: {rel.as_posix()}")
        if path.is_file() and path.suffix in {".pyc", ".pdb"}:
            fail(f"forbidden build/debug file leaked into UPM package: {rel.as_posix()}")


def current_git_sha(root: Path) -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        fail(f"git rev-parse HEAD failed: {result.stderr.strip()}")
    return result.stdout.strip()


def package_manifest(package_root: Path) -> dict[str, Any]:
    data = read_json(package_root / "package.json")
    if data.get("name") != PACKAGE_NAME:
        fail(f"package.json name must be {PACKAGE_NAME}, got {data.get('name')!r}")
    if not isinstance(data.get("version"), str) or not data["version"]:
        fail("package.json version must be a non-empty string")
    return data
