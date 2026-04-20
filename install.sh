#!/usr/bin/env bash
# Install or update the library-catalog skill for Claude Code.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Hbrinj/library-catalog/main/install.sh | bash
#
#   Or clone the repo and run directly:
#   ./install.sh
#
# Environment variables:
#   SKILL_DIR  - override install location (default: ~/.claude/skills/library-catalog)

set -euo pipefail

REPO="Hbrinj/library-catalog"
BRANCH="main"
SKILL_DIR="${SKILL_DIR:-$HOME/.claude/skills/library-catalog}"

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
err()   { printf '\033[1;31mError:\033[0m %s\n' "$*" >&2; }

# --- Pre-flight checks -------------------------------------------------------

if ! command -v git &>/dev/null; then
    err "git is required but not found in PATH."
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    err "python3 is required but not found in PATH."
    exit 1
fi

# --- Install or update --------------------------------------------------------

if [ -d "$SKILL_DIR" ] && [ -f "$SKILL_DIR/version.json" ]; then
    # Existing install — delegate to the built-in updater
    info "Existing installation found at $SKILL_DIR"
    python3 "$SKILL_DIR/scripts/update_skill.py" --repo "$REPO" --branch "$BRANCH"
    exit $?
fi

info "Installing library-catalog skill to $SKILL_DIR ..."

TMPDIR_PATH=$(mktemp -d)
trap 'rm -rf "$TMPDIR_PATH"' EXIT

git clone --depth 1 --branch "$BRANCH" "https://github.com/$REPO.git" "$TMPDIR_PATH/repo"

mkdir -p "$(dirname "$SKILL_DIR")"

# Copy skill files (not the .git directory)
mkdir -p "$SKILL_DIR"
cp    "$TMPDIR_PATH/repo/version.json" "$SKILL_DIR/"
cp    "$TMPDIR_PATH/repo/SKILL.md"     "$SKILL_DIR/"
cp -r "$TMPDIR_PATH/repo/scripts"      "$SKILL_DIR/"
cp -r "$TMPDIR_PATH/repo/data"         "$SKILL_DIR/"

ok "Installed library-catalog v$(python3 -c "import json,sys;print(json.load(open('$SKILL_DIR/version.json'))['version'])")"
echo ""
echo "  Location: $SKILL_DIR"
echo ""
echo "  To update later:  python3 $SKILL_DIR/scripts/update_skill.py"
echo "  To uninstall:     rm -rf $SKILL_DIR"
echo ""
ok "Done! The skill will be available in your next Claude Code session."
