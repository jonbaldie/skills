#!/usr/bin/env bash

# tests/lib.sh is the fixture harness every shell suite sources. Exercise each
# helper from a fresh Bash process, the way a suite would use it.

set -euo pipefail

# shellcheck source=tests/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
new_sandbox shell-lib-test

readonly harness="${repository_root}/tests/lib.sh"

# Run a snippet as a suite named <name>.sh that sources the harness.
run_suite_snippet() {
  local name="$1"
  local body="$2"
  local suite="${test_root}/suites/${name}.sh"

  mkdir -p "${test_root}/suites"
  printf '%s\n' 'set -euo pipefail' "source '${harness}'" "${body}" >"${suite}"
  bash "${suite}"
}

# --- repo_root ---

[[ "$(repo_root)" == "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)" ]] ||
  fail "repo_root returned '$(repo_root)'"
[[ "${repository_root}" == "$(repo_root)" ]] ||
  fail "repository_root is '${repository_root}', expected '$(repo_root)'"
[[ "$(run_suite_snippet root 'cd /; repo_root')" == "$(repo_root)" ]] ||
  fail "repo_root depends on the caller's working directory"

# --- new_sandbox ---

sandbox_path="$(run_suite_snippet sandbox 'new_sandbox lib-sandbox; touch "${test_root}/file"; printf "%s" "${test_root}"')"
[[ -n "${sandbox_path}" ]] || fail "new_sandbox did not set test_root"
[[ "$(basename "${sandbox_path}")" == lib-sandbox.* ]] ||
  fail "new_sandbox ignored its prefix: ${sandbox_path}"
[[ ! -e "${sandbox_path}" ]] || fail "new_sandbox left ${sandbox_path} behind on exit"

if failed_sandbox="$(run_suite_snippet sandbox-fail 'new_sandbox; printf "%s" "${test_root}"; false')"; then
  fail "a failing suite exited 0"
fi
[[ "$(basename "${failed_sandbox}")" == sandbox-fail.* ]] ||
  fail "new_sandbox did not default its prefix to the suite name: ${failed_sandbox}"
[[ ! -e "${failed_sandbox}" ]] || fail "new_sandbox left ${failed_sandbox} behind after a failure"

# --- fail and pass ---

if run_suite_snippet failing 'fail "broken thing"; echo unreachable' \
  >"${test_root}/fail.out" 2>"${test_root}/fail.err"; then
  fail "fail exited 0"
fi
[[ "$(<"${test_root}/fail.err")" == 'FAIL: failing: broken thing' ]] ||
  fail "fail wrote '$(<"${test_root}/fail.err")' to stderr"
[[ ! -s "${test_root}/fail.out" ]] || fail "fail kept running or wrote to stdout"

[[ "$(run_suite_snippet passing 'pass')" == 'PASS: passing: all scenarios passed' ]] ||
  fail "pass printed '$(run_suite_snippet passing 'pass')'"
[[ "$(run_suite_snippet passing 'pass custom outcome')" == 'PASS: passing: custom outcome' ]] ||
  fail "pass ignored its message"

# --- make_skill ---

# shellcheck source=/dev/null
source "${repository_root}/skills/sync-jonbaldie-skills/scripts/lib/skill-tree.sh"

make_skill "${test_root}/fixture/skills/alpha" alpha
[[ "$(skill_name_from_dir "${test_root}/fixture/skills/alpha" --strict)" == alpha ]] ||
  fail "make_skill wrote a SKILL.md whose name does not parse"
grep -qx 'description: Fixture skill.' "${test_root}/fixture/skills/alpha/SKILL.md" ||
  fail "make_skill wrote no description"

make_skill "${test_root}/fixture/skills/group/beta" "'Beta Skill'" 'beta body'
[[ "$(skill_name_from_dir "${test_root}/fixture/skills/group/beta" --slugify)" == beta-skill ]] ||
  fail "make_skill did not write the given name verbatim"
[[ "$(tail -n 1 "${test_root}/fixture/skills/group/beta/SKILL.md")" == 'beta body' ]] ||
  fail "make_skill did not write the given body"

# --- commit_repository ---

commit_repository "${test_root}/fixture"
[[ -z "$(git -C "${test_root}/fixture" status --porcelain)" ]] ||
  fail "commit_repository left uncommitted files"
git -C "${test_root}/fixture" cat-file -e HEAD:skills/group/beta/SKILL.md ||
  fail "commit_repository did not commit nested fixture files"

make_skill "${test_root}/fixture/skills/gamma" gamma
commit_repository "${test_root}/fixture"
[[ "$(git -C "${test_root}/fixture" rev-list --count HEAD)" == 2 ]] ||
  fail "commit_repository did not add a commit to an existing repository"

# --- run-all.sh treats the harness as a library, not a suite ---

# Skip every real suite so the runner only reports what it discovered.
run_all_skip=pytest
while IFS= read -r suite; do
  [[ "${suite}" == lib.sh ]] || run_all_skip+=",${suite}"
done < <(cd "${repository_root}/tests" && find . -type f -name '*.sh' -exec basename {} \;)
run_all_output="$(RUN_ALL_SKIP="${run_all_skip}" "${repository_root}/tests/run-all.sh" 2>&1)" ||
  fail "run-all.sh failed with every suite skipped: ${run_all_output}"
if grep -q 'tests/lib.sh' <<<"${run_all_output}"; then
  fail "run-all.sh ran tests/lib.sh as a suite: ${run_all_output}"
fi

pass
