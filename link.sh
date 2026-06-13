#!/usr/bin/env bash
# Symlink every skill in this repo into ~/.claude/skills and ~/.agents/skills.
# Source of truth = this repo. Run after adding a new skill folder.
#
#   ./link.sh          # link all skills
#   ./link.sh <name>   # link just one skill folder
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGETS=("$HOME/.claude/skills" "$HOME/.agents/skills")

link_one() {
  local skill_dir="$1" name
  name="$(basename "$skill_dir")"
  [ -f "$skill_dir/SKILL.md" ] || { echo "skip  $name (no SKILL.md)"; return; }
  for base in "${TARGETS[@]}"; do
    mkdir -p "$base"
    local dest="$base/$name"
    if [ -L "$dest" ] || [ -e "$dest" ]; then rm -rf "$dest"; fi
    ln -s "$skill_dir" "$dest"
    echo "link  $dest -> $skill_dir"
  done
}

if [ "${1:-}" ]; then
  link_one "$REPO/$1"
else
  for d in "$REPO"/*/; do
    [ -f "${d}SKILL.md" ] && link_one "${d%/}"
  done
fi
