#!/usr/bin/env bash

# copy-to-skill-dirs.sh must reject skill-directory arguments that are empty or
# resolve to the project root (or one of its ancestors) before touching any
# destination; otherwise it deletes root entries named like managed skills.

set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly repository_root
readonly copy_script="${repository_root}/skills/sync-jonbaldie-skills/scripts/copy-to-skill-dirs.sh"
test_root="$(mktemp -d "${TMPDIR:-/tmp}/skills-copy-root-test.XXXXXX")"
readonly test_root
readonly project="${test_root}/project"

cleanup() {
  rm -rf "${test_root}"
}
trap cleanup EXIT

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

make_project() {
  rm -rf "${project}"
  mkdir -p "${project}/.agents/skills/alpha"
  printf '%s\n' 'valuable project file' >"${project}/alpha"
  printf '%s\n' '---' 'name: alpha' '---' >"${project}/.agents/skills/alpha/SKILL.md"
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

printf '%s\n' 'copy-to-skill-dirs-project-root: all scenarios passed'
