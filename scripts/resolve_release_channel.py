#!/usr/bin/env python3
"""Resolve nozzle.unity release artifact channel and filename."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from unity_release_contract import PACKAGE_NAME, package_manifest, fail

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "Packages" / PACKAGE_NAME
SEMVER_TAG_RE = re.compile(r"^v([0-9]+\.[0-9]+\.[0-9]+)$")


def is_exact_semver_tag(tag: str) -> bool:
    return SEMVER_TAG_RE.match(tag) is not None


def git_value(args: list[str]) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        fail(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def resolve(ref: str | None, sha: str | None) -> dict[str, str]:
    manifest = package_manifest(PACKAGE_ROOT)
    resolved_sha = sha or git_value(["rev-parse", "HEAD"])
    short_sha = resolved_sha[:7]
    resolved_ref = ref or os.environ.get("GITHUB_REF") or git_value(["symbolic-ref", "-q", "HEAD"])
    if resolved_ref == "refs/heads/main":
        channel = "latest"
        artifact_name = f"{PACKAGE_NAME}-latest-{short_sha}.tgz"
        release_tag = "latest"
    elif resolved_ref.startswith("refs/tags/"):
        tag = resolved_ref.removeprefix("refs/tags/")
        match = SEMVER_TAG_RE.match(tag)
        if match is None:
            fail(f"versioned nozzle.unity release tag must be exact vX.Y.Z, got {tag!r}")
        version = match.group(1)
        if manifest["version"] != version:
            fail(f"package.json version {manifest['version']!r} must match release tag {tag!r}")
        channel = "versioned"
        artifact_name = f"{PACKAGE_NAME}-{tag}.tgz"
        release_tag = tag
    else:
        channel = "ci"
        artifact_name = f"{PACKAGE_NAME}-ci-{short_sha}.tgz"
        release_tag = ""
    return {
        "channel": channel,
        "artifact_name": artifact_name,
        "release_tag": release_tag,
        "short_sha": short_sha,
        "sha": resolved_sha,
        "ref": resolved_ref,
        "package_version": manifest["version"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref")
    parser.add_argument("--sha")
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    info = resolve(args.ref, args.sha)
    if args.github_output is not None:
        with args.github_output.open("a", encoding="utf-8") as file:
            for key, value in info.items():
                file.write(f"{key}={value}\n")
    if args.json or args.github_output is None:
        print(json.dumps(info, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
