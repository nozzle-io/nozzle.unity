#!/usr/bin/env python3
"""Assemble and pack the nozzle.unity UPM .tgz from validated native payloads."""

from __future__ import annotations

import argparse
import gzip
import shutil
import tarfile
from pathlib import Path

from unity_release_contract import (
    PACKAGE_NAME,
    PACKAGE_ROOT_RELATIVE,
    PLATFORMS,
    current_git_sha,
    fail,
    package_manifest,
    validate_no_forbidden_package_files,
    validate_unity_package_meta_contract,
    validate_payload_schema,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PACKAGE_ROOT = ROOT / "Packages" / PACKAGE_NAME


def copy_source_package(destination_package_root: Path) -> None:
    if destination_package_root.exists():
        shutil.rmtree(destination_package_root)
    def ignore(_dir: str, names: list[str]) -> set[str]:
        return {name for name in names if name in {".git", "Runtime/Plugins", "__pycache__"}}
    shutil.copytree(SOURCE_PACKAGE_ROOT, destination_package_root, ignore=ignore)
    plugins = destination_package_root / "Runtime" / "Plugins"
    if plugins.exists():
        shutil.rmtree(plugins)


def copy_payload(payload_dir: Path, package_root: Path, platform_key: str, expected_source_commit: str) -> dict:
    data = validate_payload_schema(payload_dir, platform_key, expected_source_commit)
    contract = PLATFORMS[platform_key]
    for relative in [contract.plugin_relative_path, Path(f"{contract.plugin_relative_path.as_posix()}.meta")]:
        source = payload_dir / relative
        destination = package_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return data


def parse_platforms(text: str) -> list[str]:
    platforms = [item.strip() for item in text.split(",") if item.strip()]
    if not platforms:
        fail("--platforms must contain at least one platform")
    invalid = sorted(set(platforms) - set(PLATFORMS))
    if invalid:
        fail(f"unsupported package platform(s): {invalid!r}")
    return platforms


def assert_expected_plugin_set(package_root: Path, platforms: list[str]) -> None:
    expected = set()
    for platform_key in platforms:
        contract = PLATFORMS[platform_key]
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
        fail(f"UPM package native plugin payload mismatch; missing={missing!r} extra={extra!r}")


def deterministic_tgz(package_root: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    files = sorted(path for path in package_root.rglob("*") if path.is_file())
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as archive:
                for path in files:
                    arcname = Path("package") / path.relative_to(package_root)
                    info = archive.gettarinfo(str(path), arcname.as_posix())
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = 0
                    if info.isfile():
                        with path.open("rb") as file:
                            archive.addfile(info, file)
                    else:
                        archive.addfile(info)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload-root", required=True, type=Path, help="Directory containing native-payload/<platform> payloads")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--work-dir", default=ROOT / "build" / "upm-package-work", type=Path)
    parser.add_argument("--expected-source-commit", default=None, help="Expected git SHA for all native payloads; defaults to git rev-parse HEAD")
    parser.add_argument("--platforms", default=",".join(sorted(PLATFORMS)), help="Comma-separated native payload platforms to include.")
    parser.add_argument("--support-mode", choices=("stub", "runtime"), default=None, help="Require all included payloads to declare this support mode.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload_root = args.payload_root.resolve()
    if (payload_root / "native-payload").is_dir():
        payload_root = payload_root / "native-payload"
    platforms = parse_platforms(args.platforms)
    expected_source_commit = args.expected_source_commit or current_git_sha(ROOT)
    work_dir = args.work_dir.resolve()
    package_root = work_dir / "package"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    package_root.parent.mkdir(parents=True, exist_ok=True)
    copy_source_package(package_root)
    manifest = package_manifest(package_root)
    payloads = {}
    for platform_key in platforms:
        payload_dir = payload_root / platform_key
        payloads[platform_key] = copy_payload(payload_dir, package_root, platform_key, expected_source_commit)
        if args.support_mode is not None and payloads[platform_key]["expected_support_mode"] != args.support_mode:
            fail(f"payload support mode mismatch for {platform_key}: expected {args.support_mode}, got {payloads[platform_key]['expected_support_mode']}")
        if payloads[platform_key]["package"]["name"] != manifest["name"] or payloads[platform_key]["package"]["version"] != manifest["version"]:
            fail(f"payload package identity mismatch for {platform_key}")
        if payloads[platform_key]["source_commit"] != expected_source_commit:
            fail(f"payload source_commit mismatch for {platform_key}")
    assert_expected_plugin_set(package_root, platforms)
    validate_unity_package_meta_contract(package_root)
    validate_no_forbidden_package_files(package_root)
    deterministic_tgz(package_root, args.output.resolve())
    print(f"UPM tgz created: {args.output.resolve()}")


if __name__ == "__main__":
    main()
