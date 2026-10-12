#!/usr/bin/env bash

# install.sh takes its agents from the shared agent-destinations module:
# help and unsupported-agent errors list the declared names, and declared
# agents (Gemini included) install to their declared destinations from a
# checkout and from a piped install.

set -euo pipefail

# shellcheck source=tests/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
new_sandbox skills-install-agent-destinations

readonly installer="${repository_root}/install.sh"
readonly supported='codex, claude-code, opencode, pi, cursor, gemini, universal'

# A collection repository for piped installs: one skill plus the modules
# install.sh sources from the clone.
jon_repo="${test_root}/jon-repo"
make_skill "${jon_repo}/skills/fixture-jon" fixture-jon
add_collection_modules "${jon_repo}"
commit_repository "${jon_repo}"

# Runs install.sh from this checkout in <dir> with HOME=<home>.
local_install() {
  local dir="$1"
  local home="$2"
  shift 2
  mkdir -p "${dir}" "${home}"
  (
    cd "${dir}"
    env -u CODEX_HOME -u CLAUDE_CONFIG_DIR -u XDG_CONFIG_HOME HOME="${home}" \
      "${installer}" --without-prereqs "$@"
  )
}

# Streams install.sh to Bash the way the one-line install does.
readonly piped_tmp="${test_root}/piped-tmp"
piped_install() {
  local dir="$1"
  local home="$2"
  shift 2
  mkdir -p "${dir}" "${home}" "${piped_tmp}"
  (
    cd "${dir}"
    env -u CODEX_HOME -u CLAUDE_CONFIG_DIR -u XDG_CONFIG_HOME HOME="${home}" \
      TMPDIR="${piped_tmp}" \
      JONBALDIE_SKILLS_REPO="file://${jon_repo}" \
      bash -s -- --without-prereqs "$@" <"${installer}"
  )
}

# The clone a piped install makes must not outlive the run.
assert_piped_cleaned_up() {
  [[ ! -d "${piped_tmp}" || -z "$(ls -A "${piped_tmp}")" ]] ||
    fail "piped install left temporary files: $(ls -A "${piped_tmp}")"
}

for runner in local_install piped_install; do
  scenario="${test_root}/${runner}"

  # Help lists the declared agents.
  "${runner}" "${scenario}/help" "${scenario}/home" --help >"${test_root}/help.log" 2>&1 || {
    cat "${test_root}/help.log" >&2
    fail "${runner} --help failed"
  }
  grep -Fq "${supported}" "${test_root}/help.log" ||
    fail "${runner} --help does not list '${supported}': $(<"${test_root}/help.log")"

  # Unsupported agents are rejected with the declared names.
  if "${runner}" "${scenario}/unknown" "${scenario}/home" --project --agent nope \
    >"${test_root}/unknown.log" 2>&1; then
    fail "${runner} accepted an unsupported agent"
  fi
  grep -Fxq 'Unsupported agent: nope' "${test_root}/unknown.log" ||
    fail "${runner} did not name the unsupported agent: $(<"${test_root}/unknown.log")"
  grep -Fxq "Supported: ${supported}" "${test_root}/unknown.log" ||
    fail "${runner} did not list supported agents: $(<"${test_root}/unknown.log")"
  [[ ! -e "${scenario}/unknown/.agents" ]] ||
    fail "${runner} installed before rejecting an unsupported agent"
  assert_piped_cleaned_up
done

# Gemini installs into .gemini/skills in project scope, linked to the
# canonical copy.
project="${test_root}/project"
local_install "${project}" "${test_root}/project-home" --project --agent gemini --skill bmf \
  >"${test_root}/project.log" 2>&1 || {
  cat "${test_root}/project.log" >&2
  fail "project install for gemini failed"
}
grep -Fq 'Installing to: Gemini CLI' "${test_root}/project.log" ||
  fail "project install did not name Gemini CLI: $(<"${test_root}/project.log")"
cmp -s "${repository_root}/skills/bmf/SKILL.md" "${project}/.gemini/skills/bmf/SKILL.md" ||
  fail "bmf not installed into .gemini/skills"
[[ -L "${project}/.gemini/skills/bmf" ]] ||
  fail ".gemini/skills/bmf is not linked to the canonical copy"
[[ -f "${project}/.agents/skills/bmf/SKILL.md" ]] ||
  fail "bmf not installed into the canonical directory"

# A detected ~/.gemini selects Gemini for a global install.
gemini_home="${test_root}/gemini-home"
mkdir -p "${gemini_home}/.gemini"
local_install "${test_root}/global-work" "${gemini_home}" --global --skill bmf --copy \
  >"${test_root}/global.log" 2>&1 || {
  cat "${test_root}/global.log" >&2
  fail "global install with detected gemini failed"
}
grep -Fxq 'Installing to: Gemini CLI' "${test_root}/global.log" ||
  fail "global install did not detect only Gemini CLI: $(<"${test_root}/global.log")"
[[ -f "${gemini_home}/.gemini/skills/bmf/SKILL.md" ]] ||
  fail "bmf not installed into ~/.gemini/skills"

# A piped install loads the declarations from its clone.
piped_project="${test_root}/piped-project"
piped_install "${piped_project}" "${test_root}/piped-home" --project --agent gemini --agent claude-code \
  >"${test_root}/piped.log" 2>&1 || {
  cat "${test_root}/piped.log" >&2
  fail "piped project install failed"
}
for destination in .agents/skills .gemini/skills .claude/skills; do
  [[ -f "${piped_project}/${destination}/fixture-jon/SKILL.md" ]] ||
    fail "piped install did not populate ${destination}"
done
assert_piped_cleaned_up

pass
