#!/usr/bin/env bash

# copy-to-skill-dirs.sh must reject skill-directory arguments that are empty or
# resolve to the project root (or one of its ancestors) before touching any
# destination; otherwise it deletes root entries named like managed skills.

set -euo pipefail

# shellcheck source=tests/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
new_sandbox skills-copy-root-test

readonly copy_script="${repository_root}/skills/sync-jonbaldie-skills/scripts/copy-to-skill-dirs.sh"
readonly project="${test_root}/project"

make_project() {
  rm -rf "${project}"
  make_skill "${project}/.agents/skills/alpha" alpha
  printf '%s\n' 'valuable project file' >"${project}/alpha"
  printf '%s\n' alpha >"${project}/.agents/sync-jonbaldie-skills.manifest"
}

for argument in "" "." "./" ".agents/.." "${project}" "${project}/" ".."; do
  make_project
  if "${copy_script}" "${project}" .claude/skills "${argument}" >"${test_root}/copy.log" 2>&1; then
    fail "accepted skill directory '${argument}'"
  fi
  grep -q '^error: ' "${test_root}/copy.log" ||
    fail "no error reported for skill directory '${argument}'"
  [[ "$(<"${project}/alpha")" == 'valuable project file' ]] ||
    fail "project root entry overwritten for skill directory '${argument}'"
  [[ ! -e "${project}/.sync-jonbaldie-skills.manifest" ]] ||
    fail "manifest written into project root for skill directory '${argument}'"
  [[ ! -e "${project}/.claude/skills" ]] ||
    fail "valid destination processed before rejecting '${argument}'"
done

make_project
"${copy_script}" "${project}" .claude/skills >"${test_root}/copy.log" 2>&1 || {
  cat "${test_root}/copy.log" >&2
  fail "rejected a valid skill directory"
}
[[ -f "${project}/.claude/skills/alpha/SKILL.md" ]] || fail "valid destination not populated"

pass
