#!/usr/bin/env python3
"""Validate a nozzle.unity native payload directory and validation.json contract."""

from __future__ import annotations

import argparse
from pathlib import Path

from unity_release_contract import validate_payload_schema


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", required=True, type=Path, help="Path to native-payload/<platform>")
    parser.add_argument("--platform", required=True)
    parser.add_argument("--support-mode", choices=("stub", "runtime"), default=None, help="Require a specific payload support contract.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = validate_payload_schema(args.payload.resolve(), args.platform, expected_support_mode=args.support_mode)
    print(f"native payload validation passed: platform={data['platform']} binary={data['binary']['relative_path']}")


if __name__ == "__main__":
    main()
