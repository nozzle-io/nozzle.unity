#!/usr/bin/env python3
"""Publish validated nozzle.unity UPM .tgz artifacts to GitHub Releases."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from resolve_release_channel import resolve
from unity_release_contract import fail


def run(command: list[str]) -> str:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    if result.returncode != 0:
        fail(f"command failed with exit code {result.returncode}: {' '.join(command)}")
    return result.stdout


def release_exists(tag: str) -> bool:
    result = subprocess.run(["gh", "release", "view", tag, "--json", "tagName"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return result.returncode == 0


def asset_names(tag: str) -> set[str]:
    result = subprocess.run(["gh", "release", "view", tag, "--json", "assets", "--jq", ".assets[].name"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--ref")
    parser.add_argument("--sha")
    parser.add_argument("--variant", choices=("stub", "runtime"), default="stub")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifact = args.artifact.resolve()
    if not artifact.is_file():
        fail(f"release artifact is missing: {artifact}")
    info = resolve(args.ref, args.sha, args.variant)
    if info["channel"] == "ci":
        print("CI channel artifact; release mutation skipped.")
        return
    expected_name = info["artifact_name"]
    if artifact.name != expected_name:
        fail(f"artifact name must be {expected_name}, got {artifact.name}")
    tag = info["release_tag"]
    if args.dry_run:
        print(f"Dry-run release upload: tag={tag} artifact={artifact.name}")
        return
    if info["channel"] == "latest":
        if not release_exists("latest"):
            run(["gh", "release", "create", "latest", "--title", "Latest development snapshot", "--notes", "Moving nozzle.unity development snapshot.", "--prerelease"])
        for existing in sorted(asset_names("latest")):
            expected_prefix = "org.nozzle-io.unity-runtime-latest-" if args.variant == "runtime" else "org.nozzle-io.unity-latest-"
            if existing.startswith(expected_prefix) and existing.endswith(".tgz"):
                run(["gh", "release", "delete-asset", "latest", existing, "--yes"])
        run(["gh", "release", "upload", "latest", str(artifact), "--clobber"])
    else:
        if release_exists(tag) and artifact.name in asset_names(tag):
            fail(f"versioned release asset already exists: {tag} {artifact.name}")
        if not release_exists(tag):
            run(["gh", "release", "create", tag, "--title", tag, "--notes", f"nozzle.unity {tag}"])
        run(["gh", "release", "upload", tag, str(artifact)])
    print(f"Release upload complete: tag={tag} artifact={artifact.name}")


if __name__ == "__main__":
    main()
