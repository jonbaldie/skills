#!/usr/bin/env bash

set -euo pipefail

# shellcheck source=tests/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
new_sandbox skills-symlinked-agent-root

test_home="${test_root}/home"

mkdir -p "${test_home}/.agents/skills" "${test_home}/.claude"
ln -s ../.agents/skills "${test_home}/.claude/skills"

HOME="${test_home}" \
CLAUDE_CONFIG_DIR="${test_home}/.claude" \
  "${repository_root}/install.sh" \
    --global \
    --agent claude-code \
    --skill bmf \
    --without-prereqs \
    --yes \
    >"${test_root}/install.log"

canonical_skill="${test_home}/.agents/skills/bmf"
claude_skill="${test_home}/.claude/skills/bmf"

if [[ -L "${canonical_skill}" ]]; then
  fail "Canonical skill became a symlink: ${canonical_skill} -> $(readlink "${canonical_skill}")"
fi

test -f "${canonical_skill}/SKILL.md"
test -f "${claude_skill}/SKILL.md"
cmp \
  "${repository_root}/skills/bmf/SKILL.md" \
  "${canonical_skill}/SKILL.md"

pass
