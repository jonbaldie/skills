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
  mkdir -p "${project}/alpha"
  printf '%s\n' 'valuable project file' >"${project}/alpha/user-work.txt"
  ln -s "${test_root}" "${project}/link"
  printf '%s\n' alpha >"${project}/.agents/sync-jonbaldie-skills.manifest"
}

for argument in "" "." "./" ".agents/.." "${project}" "${project}/" ".." \
  "new/.." "./missing/.." "a/b/../.." "a/b/../../.." \
  "${project}/absolute/.." "link/project/missing/.."; do
  make_project
  find "${project}" -print | sort >"${test_root}/before"
  if "${copy_script}" "${project}" .claude/skills "${argument}" >"${test_root}/copy.log" 2>&1; then
    fail "accepted skill directory '${argument}'"
  fi
  grep -q '^error: ' "${test_root}/copy.log" ||
    fail "no error reported for skill directory '${argument}'"
  if [[ -n "${argument}" ]]; then
    grep -Fqx "error: skill directory must not be the project root or one of its ancestors: ${argument}" \
      "${test_root}/copy.log" || fail "wrong error for '${argument}'"
  fi
  find "${project}" -print | sort >"${test_root}/after"
  diff -u "${test_root}/before" "${test_root}/after" ||
    fail "preflight modified project for '${argument}'"
  [[ "$(<"${project}/alpha/user-work.txt")" == 'valuable project file' ]] ||
    fail "project root entry overwritten for skill directory '${argument}'"
  [[ ! -e "${project}/.sync-jonbaldie-skills.manifest" ]] ||
    fail "manifest written into project root for skill directory '${argument}'"
  [[ ! -e "${project}/.claude/skills" ]] ||
    fail "valid destination processed before rejecting '${argument}'"
done

make_project
"${copy_script}" "${project}" .claude/skills custom-skills/dir \
  nested/new/../skills link/project/linked-skills >"${test_root}/copy.log" 2>&1 || {
  cat "${test_root}/copy.log" >&2
  fail "rejected a valid skill directory"
}
for destination in .claude/skills custom-skills/dir nested/skills linked-skills; do
  [[ -f "${project}/${destination}/alpha/SKILL.md" ]] ||
    fail "valid destination not populated: ${destination}"
done

pass
