#!/usr/bin/env bash

set -euo pipefail

# shellcheck source=tests/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
new_sandbox test-sync-jonbaldie-skills

readonly sync_script="${repository_root}/skills/sync-jonbaldie-skills/scripts/sync-skills.sh"
readonly copy_script="${repository_root}/skills/sync-jonbaldie-skills/scripts/copy-to-skill-dirs.sh"

assert_file() {
  [[ -f "$1" ]] || fail "expected file: $1"
}

assert_missing() {
  [[ ! -e "$1" ]] || fail "expected missing path: $1"
}

assert_content() {
  local expected="$1"
  local file="$2"
  local actual
  actual="$(<"${file}")"
  [[ "${actual}" == "${expected}" ]] ||
    fail "expected '${expected}' in ${file}, got '${actual}'"
}

# content.txt identifies which collection an installed copy came from.
make_skill_with_content() {
  local skill_directory="$1"
  local name="$2"
  local content="$3"

  make_skill "${skill_directory}" "${name}"
  printf '%s\n' "${content}" >"${skill_directory}/content.txt"
}

readonly matt_repository="${test_root}/matt source"
readonly jon_repository="${test_root}/jon source"
readonly project="${test_root}/target project"
readonly external_destination="${test_root}/external skills"

make_skill_with_content "${matt_repository}/skills/engineering/alpha" alpha 'matt alpha'
make_skill_with_content "${matt_repository}/skills/productivity/helper" helper 'matt helper'
make_skill "${matt_repository}/skills/deprecated/ignored" ignored
commit_repository "${matt_repository}"

make_skill_with_content "${jon_repository}/skills/beta" beta 'jon beta'
make_skill_with_content "${jon_repository}/skills/shared" shared 'jon shared'
commit_repository "${jon_repository}"

mkdir -p "${project}/.agents/skills/unrelated" "${project}/.agents/skills/retired"
printf '%s\n' 'keep me' >"${project}/.agents/skills/unrelated/content.txt"
printf '%s\n' 'remove me' >"${project}/.agents/skills/retired/content.txt"
printf '%s\n' retired >"${project}/.agents/sync-jonbaldie-skills.manifest"

MATTPOCOCK_SKILLS_REPO="${matt_repository}" \
JONBALDIE_SKILLS_REPO="${jon_repository}" \
  "${sync_script}" "${project}"

assert_content 'matt alpha' "${project}/.agents/skills/alpha/content.txt"
assert_content 'jon beta' "${project}/.agents/skills/beta/content.txt"
assert_content 'jon shared' "${project}/.agents/skills/shared/content.txt"
assert_content 'keep me' "${project}/.agents/skills/unrelated/content.txt"
assert_missing "${project}/.agents/skills/retired"
assert_missing "${project}/.agents/skills/ignored"
assert_missing "${project}/.claude"

printf '%s\n' stale >"${project}/.agents/skills/alpha/stale.txt"
MATTPOCOCK_SKILLS_REPO="${matt_repository}" \
JONBALDIE_SKILLS_REPO="${jon_repository}" \
  "${sync_script}" "${project}"
assert_missing "${project}/.agents/skills/alpha/stale.txt"

mkdir -p "${project}/.claude/skills/unrelated" "${project}/.claude/skills/retired"
printf '%s\n' 'keep me too' >"${project}/.claude/skills/unrelated/content.txt"
printf '%s\n' retired >"${project}/.claude/skills/.sync-jonbaldie-skills.manifest"
mkdir -p "${project}/.agents/skills/alpha/scripts/__pycache__"
touch "${project}/.agents/skills/alpha/scripts/__pycache__/tool.cpython-311.pyc"
touch "${project}/.agents/skills/alpha/stray.pyc"

"${copy_script}" "${project}" .claude/skills "${external_destination}"

assert_content 'matt alpha' "${project}/.claude/skills/alpha/content.txt"
assert_content 'jon shared' "${project}/.claude/skills/shared/content.txt"
assert_content 'keep me too' "${project}/.claude/skills/unrelated/content.txt"
assert_missing "${project}/.claude/skills/retired"
assert_missing "${project}/.claude/skills/alpha/scripts/__pycache__"
assert_missing "${project}/.claude/skills/alpha/stray.pyc"
assert_content 'jon beta' "${external_destination}/beta/content.txt"
assert_missing "${external_destination}/alpha/scripts/__pycache__"
assert_missing "${external_destination}/alpha/stray.pyc"
assert_file "${external_destination}/.sync-jonbaldie-skills.manifest"

make_skill_with_content "${matt_repository}/skills/productivity/shared" shared 'matt shared'
commit_repository "${matt_repository}"
if MATTPOCOCK_SKILLS_REPO="${matt_repository}" \
   JONBALDIE_SKILLS_REPO="${jon_repository}" \
   "${sync_script}" "${project}" >"${test_root}/collision.log" 2>&1; then
  fail "expected sync-skills.sh to fail on collision"
fi
grep -q "shared" "${test_root}/collision.log" || fail "expected collision error to mention 'shared'"

pass 'deterministic sync and optional copies'
