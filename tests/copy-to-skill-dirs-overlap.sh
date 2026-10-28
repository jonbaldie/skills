#!/usr/bin/env bash

set -euo pipefail

# shellcheck source=tests/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
new_sandbox skills-copy-overlap-test

readonly copy_script="${repository_root}/skills/sync-jonbaldie-skills/scripts/copy-to-skill-dirs.sh"
readonly project="${test_root}/project"
readonly manifest="${project}/.agents/sync-jonbaldie-skills.manifest"
readonly canonical="${project}/.agents/skills"
failures=0

problem() {
  printf 'FAIL: %s\n' "$*" >&2
  failures=$((failures + 1))
}

make_project() {
  rm -rf "${project}"
  make_skill "${canonical}/skills" skills
  printf '%s\n' 'canonical sentinel' >"${canonical}/skills/sentinel"
  printf '%s\n' skills >"${manifest}"
  cp "${manifest}" "${test_root}/manifest.expected"
}

check_preserved() {
  local scenario="$1"
  [[ -f "${canonical}/skills/SKILL.md" ]] &&
    [[ -f "${canonical}/skills/sentinel" ]] &&
    [[ "$(cat "${canonical}/skills/sentinel")" == 'canonical sentinel' ]] ||
    problem "${scenario}: canonical skill or sentinel changed"
  cmp -s "${manifest}" "${test_root}/manifest.expected" ||
    problem "${scenario}: canonical manifest changed"
}

reject_overlap() {
  local scenario="$1"
  shift
  if "${copy_script}" "${project}" "$@" >"${test_root}/copy.log" 2>&1; then
    problem "${scenario}: overlapping destination accepted"
  fi
  check_preserved "${scenario}"
}

make_project
reject_overlap 'canonical parent reproducer' .agents

make_project
ln -s .agents "${project}/alias"
reject_overlap 'symlink alias' alias

make_project
reject_overlap 'missing descendant' .agents/skills/new/nested
[[ ! -e "${canonical}/new" ]] || problem 'missing descendant: destination created'

make_project
mkdir -p "${project}/neighbor/skills"
printf '%s\n' 'existing destination' >"${project}/neighbor/skills/sentinel"
printf '%s\n' skills >"${project}/neighbor/.sync-jonbaldie-skills.manifest"
cp -R "${project}/neighbor" "${test_root}/neighbor.expected"
reject_overlap 'later overlap' neighbor .agents
diff -r "${test_root}/neighbor.expected" "${project}/neighbor" >/dev/null ||
  problem 'later overlap: earlier destination changed'

make_project
if ! "${copy_script}" "${project}" .agents/skills-neighbor >"${test_root}/copy.log" 2>&1; then
  problem "valid neighbor rejected: $(<"${test_root}/copy.log")"
else
  cmp -s "${canonical}/skills/SKILL.md" "${project}/.agents/skills-neighbor/skills/SKILL.md" ||
    problem 'valid neighbor: skill not copied'
  cmp -s "${manifest}" "${project}/.agents/skills-neighbor/.sync-jonbaldie-skills.manifest" ||
    problem 'valid neighbor: manifest not copied'
fi
check_preserved 'valid neighbor'

make_project
printf '%s\n' '../invalid' >"${manifest}"
cp "${manifest}" "${test_root}/manifest.expected"
if ! "${copy_script}" "${project}" .agents/skills >"${test_root}/copy.log" 2>&1; then
  problem "canonical no-op rejected: $(<"${test_root}/copy.log")"
fi
check_preserved 'canonical no-op'
[[ ! -e "${canonical}/.sync-jonbaldie-skills.manifest" ]] ||
  problem 'canonical no-op: destination manifest created'

((failures == 0)) || exit 1
pass
