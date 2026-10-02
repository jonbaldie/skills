#!/usr/bin/env bash

set -euo pipefail

# shellcheck source=tests/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
new_sandbox skills-skill-filter

# Fixture "prerequisite" collection (stand-in for mattpocock/skills) that does
# NOT contain any jonbaldie collection skill names.
fixture_root="${test_root}/prereq-fixture"
make_skill "${fixture_root}/skills/fixture-mp" fixture-mp
commit_repository "${fixture_root}"

run_install() {
  local project="$1"
  shift
  mkdir -p "${project}"
  (
    cd "${project}"
    MATTPOCOCK_SKILLS_REPO="${fixture_root}" \
      "${repository_root}/install.sh" \
      --agent universal \
      --with-prereqs \
      --yes \
      "$@"
  )
}

assert_installed() {
  local project="$1"
  shift
  local name
  for name in "$@"; do
    test -f "${project}/.agents/skills/${name}/SKILL.md"
  done
}

# Filter matches only the jonbaldie collection; the prerequisite collection has
# zero matches. The install must still succeed.
jon_only_project="${test_root}/jon-only"
run_install "${jon_only_project}" --skill bmf \
  >"${test_root}/jon-only.log" 2>"${test_root}/jon-only.err" ||
  {
    cat "${test_root}/jon-only.log" "${test_root}/jon-only.err" >&2
    fail "filter matching only jonbaldie collection aborted the install"
  }
assert_installed "${jon_only_project}" bmf

# Filter matches only the prerequisite collection; the jonbaldie collection has
# zero matches. The install must still succeed (no partial-install abort).
prereq_only_project="${test_root}/prereq-only"
run_install "${prereq_only_project}" --skill fixture-mp \
  >"${test_root}/prereq-only.log" 2>"${test_root}/prereq-only.err" ||
  {
    cat "${test_root}/prereq-only.log" "${test_root}/prereq-only.err" >&2
    fail "filter matching only prerequisite collection aborted the install"
  }
assert_installed "${prereq_only_project}" fixture-mp

# Filter matching nothing in either collection must still fail.
no_match_project="${test_root}/no-match"
if run_install "${no_match_project}" --skill definitely-not-a-skill \
  >"${test_root}/no-match.log" 2>&1; then
  fail "filter matching nothing in either collection succeeded"
fi
test ! -e "${no_match_project}/.agents/skills/bmf"

# No filter: full install of both collections still works.
all_project="${test_root}/all"
run_install "${all_project}" >"${test_root}/all.log"
assert_installed "${all_project}" bmf fixture-mp

pass
