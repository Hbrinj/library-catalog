#!/usr/bin/env python3
"""
Bump the skill version in version.json.

Increments the minor version by default (0.1.0 → 0.2.0). Can also bump
major or patch, or set an explicit version.

Usage:
  python bump_version.py              # 0.1.0 → 0.2.0
  python bump_version.py --minor      # 0.1.0 → 0.2.0  (same as default)
  python bump_version.py --major      # 0.1.0 → 1.0.0
  python bump_version.py --patch      # 0.1.0 → 0.1.1
  python bump_version.py --set 2.0.0  # set explicitly
"""

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
VERSION_FILE = SCRIPT_DIR.parent / "version.json"


def load_version() -> str:
    if not VERSION_FILE.exists():
        return "0.0.0"
    with VERSION_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("version", "0.0.0")


def save_version(version: str) -> None:
    data = {"version": version}
    with VERSION_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def parse_semver(version: str) -> tuple[int, int, int]:
    parts = version.strip().split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid semver: {version!r}")
    return (int(parts[0]), int(parts[1]), int(parts[2]))


def format_semver(major: int, minor: int, patch: int) -> str:
    return f"{major}.{minor}.{patch}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--major", action="store_true", help="Bump major version (X.0.0)")
    group.add_argument("--minor", action="store_true", help="Bump minor version (0.X.0)")
    group.add_argument("--patch", action="store_true", help="Bump patch version (0.0.X)")
    group.add_argument("--set", dest="explicit", help="Set an explicit version string")
    args = parser.parse_args()

    current = load_version()
    major, minor, patch = parse_semver(current)

    if args.explicit:
        # Validate the explicit version
        parse_semver(args.explicit)
        new_version = args.explicit
    elif args.major:
        new_version = format_semver(major + 1, 0, 0)
    elif args.patch:
        new_version = format_semver(major, minor, patch + 1)
    else:
        # Default: bump minor
        new_version = format_semver(major, minor + 1, 0)

    save_version(new_version)
    print(f"{current} → {new_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
