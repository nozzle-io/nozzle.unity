#!/usr/bin/env python3
"""Create and validate a platform-specific nozzle.unity native plugin payload."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from unity_release_contract import (
    EXPECTED_SUPPORT_MODE,
    PACKAGE_NAME,
    PACKAGE_ROOT_RELATIVE,
    PLATFORMS,
    VALIDATION_SCHEMA_VERSION,
    check_exported_symbols,
    check_native_support_contract,
    current_git_sha,
    fail,
    inspect_architecture,
    inspect_dependencies,
    load_native_library,
    package_manifest,
    plugin_meta_text,
    sha256_file,
    validate_payload_schema,
    validate_plugin_meta,
    write_json,
)

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", required=True, choices=sorted(PLATFORMS))
    parser.add_argument("--artifact-root", required=True, type=Path, help="CMake-staged full artifact root containing Packages/org.nozzle-io.unity")
    parser.add_argument("--output-root", required=True, type=Path, help="Output root. The script writes native-payload/<platform>/...")
    parser.add_argument("--support-mode", choices=("stub", "runtime"), default=EXPECTED_SUPPORT_MODE, help="Expected bridge support contract for this payload.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    contract = PLATFORMS[args.platform]
    artifact_root = args.artifact_root.resolve()
    artifact_package_root = artifact_root / PACKAGE_ROOT_RELATIVE
    manifest = package_manifest(artifact_package_root)

    source_binary = artifact_package_root / contract.plugin_relative_path
    if not source_binary.is_file():
        fail(f"staged native plugin binary is missing: {source_binary}")

    payload_dir = args.output_root.resolve() / "native-payload" / contract.key
    if payload_dir.exists():
        shutil.rmtree(payload_dir)
    payload_binary = payload_dir / contract.plugin_relative_path
    payload_meta = Path(f"{payload_binary}.meta")
    payload_binary.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_binary, payload_binary)
    payload_meta.write_text(plugin_meta_text(contract), encoding="utf-8")

    meta_record = validate_plugin_meta(payload_meta, contract, payload_dir)
    library = load_native_library(payload_binary)
    exports = check_exported_symbols(payload_binary, library)
    support = check_native_support_contract(payload_binary, library, args.support_mode)
    architecture = inspect_architecture(payload_binary, contract, ROOT)
    dependencies = inspect_dependencies(payload_binary, contract, ROOT)

    validation = {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "source_commit": current_git_sha(ROOT),
        "package": {
            "name": PACKAGE_NAME,
            "version": manifest["version"],
        },
        "platform": contract.key,
        "expected_unity_plugin_path": contract.plugin_relative_path.as_posix(),
        "binary": {
            "relative_path": contract.plugin_relative_path.as_posix(),
            "sha256": sha256_file(payload_binary),
        },
        "meta": meta_record,
        "architecture": architecture,
        "dependencies": dependencies,
        "exports": exports,
        "support": support,
        "expected_support_mode": args.support_mode,
    }
    write_json(payload_dir / "validation.json", validation)
    validate_payload_schema(payload_dir, contract.key, expected_support_mode=args.support_mode)
    print(f"native payload created: {payload_dir}")
    print(f"native payload binary: {contract.plugin_relative_path.as_posix()}")
    print(f"native payload sha256: {validation['binary']['sha256']}")


if __name__ == "__main__":
    main()
