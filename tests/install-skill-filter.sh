#!/usr/bin/env bash

set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test_root="$(mktemp -d "${TMPDIR:-/tmp}/skills-skill-filter.XXXXXX")"

cleanup() {
  rm -rf "${test_root}"
}
trap cleanup EXIT

# Fixture "prerequisite" collection (stand-in for mattpocock/skills) that does
# NOT contain any jonbaldie collection skill names.
fixture_root="${test_root}/prereq-fixture"
mkdir -p "${fixture_root}/skills/fixture-mp"
cat >"${fixture_root}/skills/fixture-mp/SKILL.md" <<'EOF'
---
name: fixture-mp
description: Fixture-only skill for filter testing.
---

Fixture skill.
EOF
git -C "${fixture_root}" init --quiet
git -C "${fixture_root}" add skills
git -C "${fixture_root}" -c user.email=test@example.com -c user.name=test commit --quiet -m fixture

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
    die_expected="filter matching only jonbaldie collection aborted the install"
    printf 'FAIL: %s\n' "${die_expected}" >&2
    exit 1
  }
assert_installed "${jon_only_project}" bmf

# Filter matches only the prerequisite collection; the jonbaldie collection has
# zero matches. The install must still succeed (no partial-install abort).
prereq_only_project="${test_root}/prereq-only"
run_install "${prereq_only_project}" --skill fixture-mp \
  >"${test_root}/prereq-only.log" 2>"${test_root}/prereq-only.err" ||
  {
    cat "${test_root}/prereq-only.log" "${test_root}/prereq-only.err" >&2
    printf 'FAIL: filter matching only prerequisite collection aborted the install\n' >&2
    exit 1
  }
assert_installed "${prereq_only_project}" fixture-mp

# Filter matching nothing in either collection must still fail.
no_match_project="${test_root}/no-match"
if run_install "${no_match_project}" --skill definitely-not-a-skill \
  >"${test_root}/no-match.log" 2>&1; then
  printf 'FAIL: filter matching nothing in either collection succeeded\n' >&2
  exit 1
fi
test ! -e "${no_match_project}/.agents/skills/bmf"

# No filter: full install of both collections still works.
all_project="${test_root}/all"
run_install "${all_project}" >"${test_root}/all.log"
assert_installed "${all_project}" bmf fixture-mp

printf '%s\n' 'install-skill-filter: all scenarios passed'
