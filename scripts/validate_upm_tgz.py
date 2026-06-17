#!/usr/bin/env python3
"""Static UPM archive / manifest preflight for nozzle.unity .tgz artifacts.

This intentionally does not claim Unity Editor import/install evidence.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tarfile
import tempfile
from pathlib import Path

from unity_release_contract import (
    PACKAGE_NAME,
    PLATFORMS,
    current_git_sha,
    fail,
    package_manifest,
    sha256_file,
    validate_no_forbidden_package_files,
    validate_unity_package_meta_contract,
    validate_payload_schema,
    validate_plugin_meta,
)

ROOT = Path(__file__).resolve().parents[1]


def safe_extract(archive: tarfile.TarFile, destination: Path) -> None:
    for member in archive.getmembers():
        target = destination / member.name
        if not target.resolve().is_relative_to(destination.resolve()):
            fail(f"tgz contains path escape: {member.name}")
    archive.extractall(destination)


def extract_tgz(tgz: Path, destination: Path) -> Path:
    if not tgz.is_file():
        fail(f"UPM tgz is missing: {tgz}")
    with tarfile.open(tgz, "r:gz") as archive:
        names = archive.getnames()
        if not names:
            fail("UPM tgz is empty")
        roots = {name.split("/", 1)[0] for name in names if name}
        if roots != {"package"}:
            fail(f"UPM tgz root must be exactly package/, got {sorted(roots)!r}")
        safe_extract(archive, destination)
    package_root = destination / "package"
    if not package_root.is_dir():
        fail("UPM tgz did not extract package/ root")
    return package_root


def validate_against_payloads(package_root: Path, payload_root: Path, expected_source_commit: str) -> None:
    if (payload_root / "native-payload").is_dir():
        payload_root = payload_root / "native-payload"
    for platform_key, contract in PLATFORMS.items():
        payload_dir = payload_root / platform_key
        payload = validate_payload_schema(payload_dir, platform_key, expected_source_commit)
        binary = package_root / contract.plugin_relative_path
        meta = Path(f"{binary}.meta")
        if not binary.is_file():
            fail(f"UPM tgz missing native binary for {platform_key}: {contract.plugin_relative_path.as_posix()}")
        if not meta.is_file():
            fail(f"UPM tgz missing native binary meta for {platform_key}: {contract.plugin_relative_path.as_posix()}.meta")
        if sha256_file(binary) != payload["binary"]["sha256"]:
            fail(f"UPM tgz binary hash does not match validated payload for {platform_key}")
        if sha256_file(meta) != payload["meta"]["sha256"]:
            fail(f"UPM tgz meta hash does not match validated payload for {platform_key}")
        validate_plugin_meta(meta, contract, package_root)

    expected = set()
    for contract in PLATFORMS.values():
        expected.add(contract.plugin_relative_path.as_posix())
        expected.add(f"{contract.plugin_relative_path.as_posix()}.meta")
    actual = {
        path.relative_to(package_root).as_posix()
        for path in (package_root / "Runtime" / "Plugins").rglob("*")
        if path.is_file()
    }
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        fail(f"UPM tgz native plugin payload mismatch; missing={missing!r} extra={extra!r}")


def validate_required_package_files(package_root: Path) -> None:
    required = [
        "package.json",
        "README.md",
        "LICENSE.md",
        "Third Party Notices.md",
        "Runtime.meta",
        "Runtime/Nozzle.Unity.asmdef",
        "Runtime/Nozzle.Unity.asmdef.meta",
        "Runtime/Native.meta",
        "Runtime/Native/NozzleNative.cs",
        "Runtime/Native/NozzleNative.cs.meta",
        "Native~/include/nozzle_unity/nozzle_unity_bridge.h",
        "Documentation~/supported-platforms.md",
        "Documentation~/graphics-api-support.md",
        "Documentation~/troubleshooting.md",
        "Samples~/SenderSample/README.md",
        "Samples~/ReceiverSample/README.md",
        "Samples~/DiscoveryDiagnostics/README.md",
    ]
    for rel in required:
        if not (package_root / rel).is_file():
            fail(f"UPM tgz missing required package file: {rel}")
    manifest = package_manifest(package_root)
    repository = manifest.get("repository")
    if not isinstance(repository, dict) or "nozzle-io/nozzle.unity" not in str(repository.get("url", "")):
        fail("UPM tgz package.json repository.url must reference nozzle-io/nozzle.unity")
    if manifest.get("license") != "MIT":
        fail("UPM tgz package.json license must be MIT")
    validate_unity_package_meta_contract(package_root)


def write_manifest_preflight(tgz: Path, destination: Path) -> None:
    packages = destination / "Packages"
    packages.mkdir(parents=True, exist_ok=True)
    manifest = {
        "dependencies": {
            PACKAGE_NAME: f"file:{tgz.resolve().as_posix()}",
        }
    }
    (packages / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    loaded = json.loads((packages / "manifest.json").read_text(encoding="utf-8"))
    if loaded["dependencies"][PACKAGE_NAME] != f"file:{tgz.resolve().as_posix()}":
        fail("static manifest preflight failed to reference generated tgz")
    print("Static UPM archive / manifest preflight passed; Unity Editor import was not executed.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tgz", required=True, type=Path)
    parser.add_argument("--payload-root", required=True, type=Path)
    parser.add_argument("--expected-source-commit", default=None, help="Expected git SHA for all native payloads; defaults to git rev-parse HEAD")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    expected_source_commit = args.expected_source_commit or current_git_sha(ROOT)
    with tempfile.TemporaryDirectory(prefix="nozzle-unity-upm-") as tmp:
        tmp_path = Path(tmp)
        package_root = extract_tgz(args.tgz.resolve(), tmp_path / "extract")
        validate_required_package_files(package_root)
        validate_no_forbidden_package_files(package_root)
        validate_against_payloads(package_root, args.payload_root.resolve(), expected_source_commit)
        write_manifest_preflight(args.tgz.resolve(), tmp_path / "manifest-preflight")
    print(f"UPM tgz static validation passed: {args.tgz}")


if __name__ == "__main__":
    main()
