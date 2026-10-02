#!/usr/bin/env bash

# Fixture harness sourced by every shell suite in tests/. It is a library, not
# a suite: run-all.sh skips it.
#
#   repository_root / repo_root   canonical path of this checkout
#   new_sandbox [prefix]          temporary $test_root, removed on exit
#   fail <message>                report a failed assertion and exit 1
#   pass [message]                report the suite passed
#   make_skill <dir> <name> [body]
#   commit_repository <dir>

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly repository_root

suite_name="$(basename "$0" .sh)"
readonly suite_name

repo_root() {
  printf '%s\n' "${repository_root}"
}

# Sets test_root to a fresh directory named <prefix>.XXXXXX (default: the
# suite name) and removes it when the suite exits, pass or fail. Call it once:
# it owns the EXIT trap.
new_sandbox() {
  local prefix="${1:-${suite_name}}"

  test_root="$(mktemp -d "${TMPDIR:-/tmp}/${prefix}.XXXXXX")"
  readonly test_root
  trap 'rm -rf "${test_root}"' EXIT
}

fail() {
  printf 'FAIL: %s: %s\n' "${suite_name}" "$*" >&2
  exit 1
}

# The message is optional; most suites call pass with none.
# shellcheck disable=SC2120
pass() {
  printf 'PASS: %s: %s\n' "${suite_name}" "${*:-all scenarios passed}"
}

# Writes <dir>/SKILL.md with the given frontmatter name, written verbatim so
# fixtures can exercise quoting and name normalization.
make_skill() {
  local directory="$1"
  local name="$2"
  local body="${3:-Fixture.}"

  mkdir -p "${directory}"
  printf '%s\n' '---' "name: ${name}" 'description: Fixture skill.' '---' "${body}" \
    >"${directory}/SKILL.md"
}

# Commits everything under <dir>, initializing the repository on first use.
commit_repository() {
  local repository="$1"

  git -C "${repository}" init --quiet
  git -C "${repository}" add .
  git -C "${repository}" -c user.name=Fixture -c user.email=fixture@example.com \
    commit --quiet -m fixture
}
