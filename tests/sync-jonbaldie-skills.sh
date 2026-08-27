#!/usr/bin/env bash

set -euo pipefail

repository_root="$(cd "$(dirname "$0")/.." && pwd -P)"
readonly repository_root
readonly sync_script="${repository_root}/skills/sync-jonbaldie-skills/scripts/sync-skills.sh"
readonly copy_script="${repository_root}/skills/sync-jonbaldie-skills/scripts/copy-to-skill-dirs.sh"
temporary_root="$(mktemp -d "${TMPDIR:-/tmp}/test-sync-jonbaldie-skills.XXXXXX")"
readonly temporary_root

cleanup() {
  rm -rf "${temporary_root}"
}
trap cleanup EXIT

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

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

make_skill() {
  local repository="$1"
  local relative_directory="$2"
  local name="$3"
  local content="$4"
  local skill_directory="${repository}/skills/${relative_directory}"

  mkdir -p "${skill_directory}"
  printf '%s\n' '---' "name: ${name}" 'description: Fixture skill.' '---' >"${skill_directory}/SKILL.md"
  printf '%s\n' "${content}" >"${skill_directory}/content.txt"
}

commit_repository() {
  local repository="$1"
  git -C "${repository}" add .
  git -C "${repository}" -c user.name=Fixture -c user.email=fixture@example.com commit --quiet -m fixture
}

readonly matt_repository="${temporary_root}/matt source"
readonly jon_repository="${temporary_root}/jon source"
readonly project="${temporary_root}/target project"
readonly external_destination="${temporary_root}/external skills"

git init --quiet "${matt_repository}"
make_skill "${matt_repository}" engineering/alpha alpha 'matt alpha'
make_skill "${matt_repository}" productivity/shared shared 'matt shared'
mkdir -p "${matt_repository}/skills/deprecated/ignored"
printf '%s\n' '---' 'name: ignored' 'description: Ignored fixture.' '---' >"${matt_repository}/skills/deprecated/ignored/SKILL.md"
commit_repository "${matt_repository}"

git init --quiet "${jon_repository}"
make_skill "${jon_repository}" beta beta 'jon beta'
make_skill "${jon_repository}" shared shared 'jon shared'
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

"${copy_script}" "${project}" .claude/skills "${external_destination}"

assert_content 'matt alpha' "${project}/.claude/skills/alpha/content.txt"
assert_content 'jon shared' "${project}/.claude/skills/shared/content.txt"
assert_content 'keep me too' "${project}/.claude/skills/unrelated/content.txt"
assert_missing "${project}/.claude/skills/retired"
assert_content 'jon beta' "${external_destination}/beta/content.txt"
assert_file "${external_destination}/.sync-jonbaldie-skills.manifest"

printf 'PASS: deterministic sync and optional copies\n'
