#!/usr/bin/env bash

set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test_root="$(mktemp -d "${TMPDIR:-/tmp}/skills-symlinked-agent-root.XXXXXX")"
test_home="${test_root}/home"

cleanup() {
  rm -rf "${test_root}"
}
trap cleanup EXIT

mkdir -p "${test_home}/.agents/skills" "${test_home}/.claude"
ln -s ../.agents/skills "${test_home}/.claude/skills"

HOME="${test_home}" \
CLAUDE_CONFIG_DIR="${test_home}/.claude" \
  "${repository_root}/install.sh" \
    --global \
    --agent claude-code \
    --skill ship-spec \
    --without-prereqs \
    --yes \
    >"${test_root}/install.log"

canonical_skill="${test_home}/.agents/skills/ship-spec"
claude_skill="${test_home}/.claude/skills/ship-spec"

if [[ -L "${canonical_skill}" ]]; then
  printf 'Canonical skill became a symlink: %s -> %s\n' \
    "${canonical_skill}" \
    "$(readlink "${canonical_skill}")" >&2
  exit 1
fi

test -f "${canonical_skill}/SKILL.md"
test -f "${claude_skill}/SKILL.md"
cmp \
  "${repository_root}/skills/ship-spec/SKILL.md" \
  "${canonical_skill}/SKILL.md"
