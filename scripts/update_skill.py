#!/usr/bin/env python3
"""
Update the installed library-catalog skill from the remote GitHub repository.

Compares the local version (version.json) against the remote version on the
default branch of the GitHub repo. If the remote version is newer, clones
the repo to a temporary directory and copies updated files into the skill
directory — preserving the local libraries.json so user-added entries are
not overwritten.

Usage:
  # Check and update the installed skill
  python update_skill.py

  # Check only, don't apply changes
  python update_skill.py --check

  # Update from a custom repo or branch
  python update_skill.py --repo owner/repo --branch main

  # Force update even if versions match
  python update_skill.py --force

Environment variables:
  GITHUB_TOKEN - optional, raises API rate limit from 60/hr to 5000/hr
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
VERSION_FILE = SKILL_ROOT / "version.json"
LOCAL_CATALOG = SKILL_ROOT / "data" / "libraries.json"

DEFAULT_REPO = "hbrinj/library-catalog"
DEFAULT_BRANCH = "main"


def load_local_version() -> str:
    """Read the version string from the local version.json."""
    if not VERSION_FILE.exists():
        return "0.0.0"
    with VERSION_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("version", "0.0.0")


def fetch_remote_version(repo: str, branch: str, token: str | None = None) -> str:
    """Fetch the version string from the remote version.json via GitHub raw content."""
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/version.json"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "library-catalog-skill-updater")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("version", "0.0.0")
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"Failed to fetch remote version from {url}: HTTP {e.code}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Network error fetching remote version: {e.reason}"
        ) from e


def parse_semver(version: str) -> tuple[int, int, int]:
    """Parse a semver string into a (major, minor, patch) tuple."""
    parts = version.strip().split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid semver: {version!r}")
    return (int(parts[0]), int(parts[1]), int(parts[2]))


def is_newer(remote: str, local: str) -> bool:
    """Return True if the remote version is strictly newer than the local."""
    return parse_semver(remote) > parse_semver(local)


def clone_repo(repo: str, branch: str, dest: Path) -> None:
    """Shallow-clone the repo into dest."""
    url = f"https://github.com/{repo}.git"
    cmd = ["git", "clone", "--depth", "1", "--branch", branch, url, str(dest)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"git clone failed (exit {result.returncode}):\n{result.stderr.strip()}"
        )


def apply_update(source: Path, target: Path) -> list[str]:
    """Copy files from the cloned repo to the skill directory.

    Preserves the local libraries.json so user-added entries are kept.
    Returns a list of updated file paths (relative to skill root).
    """
    updated: list[str] = []

    # Back up the local catalog if it exists
    catalog_backup = None
    if LOCAL_CATALOG.exists():
        catalog_backup = LOCAL_CATALOG.read_text(encoding="utf-8")

    # Files and directories to copy
    entries_to_copy = [
        "version.json",
        "SKILL.md",
        "data/taxonomy.json",
        "scripts/",
    ]

    for entry in entries_to_copy:
        src = source / entry
        dst = target / entry
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            for f in src.rglob("*"):
                if f.is_file():
                    updated.append(str(f.relative_to(source)))
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            updated.append(entry)

    # Restore the local catalog
    if catalog_backup is not None:
        LOCAL_CATALOG.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_CATALOG.write_text(catalog_backup, encoding="utf-8")

    return sorted(updated)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check if an update is available; don't apply it.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Apply the update even if versions match.",
    )
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPO,
        help=f"GitHub repo in owner/repo format. Default: {DEFAULT_REPO}",
    )
    parser.add_argument(
        "--branch",
        default=DEFAULT_BRANCH,
        help=f"Remote branch to update from. Default: {DEFAULT_BRANCH}",
    )
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")

    # Load versions
    local_version = load_local_version()
    print(f"Local version:  {local_version}")

    try:
        remote_version = fetch_remote_version(args.repo, args.branch, token)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    print(f"Remote version: {remote_version}")

    if not args.force and not is_newer(remote_version, local_version):
        print("Already up to date.")
        return 0

    if args.check:
        print(f"Update available: {local_version} → {remote_version}")
        return 0

    # Clone and apply
    print(f"Updating {local_version} → {remote_version} ...")
    with tempfile.TemporaryDirectory(prefix="library-catalog-update-") as tmpdir:
        clone_dir = Path(tmpdir) / "repo"
        try:
            clone_repo(args.repo, args.branch, clone_dir)
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 2

        updated_files = apply_update(clone_dir, SKILL_ROOT)

    print(f"Updated {len(updated_files)} file(s):")
    for f in updated_files:
        print(f"  {f}")
    print(f"\nSuccessfully updated to {remote_version}.")
    print("Note: local libraries.json was preserved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
