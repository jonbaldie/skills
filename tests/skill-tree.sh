#!/usr/bin/env bash

# The skill-tree module is sourced by install.sh, sync-skills.sh and
# copy-to-skill-dirs.sh. Exercise its interface directly so discovery, name
# policy and copying are checked without a full install.

set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly repository_root
test_root="$(mktemp -d "${TMPDIR:-/tmp}/skill-tree-test.XXXXXX")"
readonly test_root

cleanup() {
  rm -rf "${test_root}"
}
trap cleanup EXIT

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

# shellcheck source=/dev/null
source "${repository_root}/skills/sync-jonbaldie-skills/scripts/lib/skill-tree.sh"

make_skill_md() {
  local directory="$1"
  local frontmatter_name="$2"

  mkdir -p "${directory}"
  printf '%s\n' '---' "name: ${frontmatter_name}" 'description: Fixture.' '---' 'Body.' \
    >"${directory}/SKILL.md"
}

# --- discover_skill_dirs ---

discovery_root="${test_root}/discovery"
make_skill_md "${discovery_root}/skills/shipped" shipped
make_skill_md "${discovery_root}/skills/group/nested" nested
make_skill_md "${discovery_root}/skills/a/b/c/d/e/f/too-deep" too-deep
for pruned in node_modules .git dist build __pycache__ .pytest_cache in-progress deprecated \
  .agents .claude .codex .pi .cursor .gemini; do
  make_skill_md "${discovery_root}/skills/${pruned}/hidden" hidden
done
# A SKILL.md outside skills/ is ignored when skills/ exists.
make_skill_md "${discovery_root}/outside" outside

discovered="$(discover_skill_dirs "${discovery_root}" | sort)"
expected="$(printf '%s\n' \
  "${discovery_root}/skills/group/nested" \
  "${discovery_root}/skills/shipped")"
[[ "${discovered}" == "${expected}" ]] ||
  fail "discover_skill_dirs returned:
${discovered}
expected:
${expected}"

# --- skill_name_from_dir ---

names_root="${test_root}/names"
make_skill_md "${names_root}/quoted" "'My Skill'"
make_skill_md "${names_root}/underscore" _private
mkdir -p "${names_root}/Fallback Dir"
printf '%s\n' '# No frontmatter' >"${names_root}/Fallback Dir/SKILL.md"

for policy in --slugify --strict; do
  actual="$(skill_name_from_dir "${names_root}/quoted" "${policy}")"
  [[ "${actual}" == my-skill ]] ||
    fail "skill_name_from_dir ${policy} normalized quoted name to '${actual}', expected 'my-skill'"
  actual="$(skill_name_from_dir "${names_root}/Fallback Dir" "${policy}")"
  [[ "${actual}" == fallback-dir ]] ||
    fail "skill_name_from_dir ${policy} fell back to '${actual}', expected 'fallback-dir'"
done

actual="$(skill_name_from_dir "${names_root}/underscore" --slugify)"
[[ "${actual}" == _private ]] ||
  fail "skill_name_from_dir --slugify returned '${actual}', expected '_private'"

if actual="$(skill_name_from_dir "${names_root}/underscore" --strict 2>"${test_root}/strict.err")"; then
  fail "skill_name_from_dir --strict accepted unsafe name '${actual}'"
fi
grep -q "unsafe skill name '_private'" "${test_root}/strict.err" ||
  fail "skill_name_from_dir --strict did not report the unsafe name: $(<"${test_root}/strict.err")"

if skill_name_from_dir "${names_root}/quoted" >/dev/null 2>&1; then
  fail "skill_name_from_dir accepted a call without an invalid-name policy"
fi

# --- skill_name_is_valid ---

for valid in alpha a1 my-skill v1.2_beta 0day; do
  skill_name_is_valid "${valid}" || fail "skill_name_is_valid rejected '${valid}'"
done
for invalid in '' -lead .hidden _private Upper 'has space' ../escape; do
  if skill_name_is_valid "${invalid}"; then
    fail "skill_name_is_valid accepted '${invalid}'"
  fi
done

# --- copy_skill_tree ---

copy_source="${test_root}/copy-source/fixture"
make_skill_md "${copy_source}" fixture
mkdir -p "${copy_source}/scripts/__pycache__" "${copy_source}/scripts/.pytest_cache" \
  "${copy_source}/build"
printf '%s\n' 'print("hi")' >"${copy_source}/scripts/tool.py"
printf '%s\n' bytecode >"${copy_source}/scripts/__pycache__/tool.cpython-312.pyc"
printf '%s\n' cache >"${copy_source}/scripts/.pytest_cache/state"
printf '%s\n' stray >"${copy_source}/stray.pyc"
printf '%s\n' kept >"${copy_source}/build/output.txt"

assert_copied() {
  local destination="$1"
  local description="$2"

  cmp -s "${copy_source}/SKILL.md" "${destination}/SKILL.md" ||
    fail "SKILL.md not copied (${description})"
  cmp -s "${copy_source}/scripts/tool.py" "${destination}/scripts/tool.py" ||
    fail "scripts/tool.py not copied (${description})"
  # Discovery-only exclusions are still part of a skill's own tree.
  cmp -s "${copy_source}/build/output.txt" "${destination}/build/output.txt" ||
    fail "build/output.txt not copied (${description})"
  [[ ! -e "${destination}/stale.txt" ]] ||
    fail "stale destination content survived (${description})"
  for artifact in scripts/__pycache__ scripts/.pytest_cache stray.pyc; do
    [[ ! -e "${destination}/${artifact}" ]] ||
      fail "${artifact} copied (${description})"
  done
}

with_rsync_destination="${test_root}/with-rsync/nested/fixture"
mkdir -p "${with_rsync_destination}"
printf '%s\n' stale >"${with_rsync_destination}/stale.txt"
copy_skill_tree "${copy_source}" "${with_rsync_destination}"
assert_copied "${with_rsync_destination}" "default PATH"

no_rsync_bin="${test_root}/no-rsync-bin"
mkdir -p "${no_rsync_bin}"
for command_name in find mkdir rm cp dirname; do
  ln -s "$(command -v "${command_name}")" "${no_rsync_bin}/${command_name}"
done
no_rsync_destination="${test_root}/no-rsync/nested/fixture"
mkdir -p "${no_rsync_destination}"
printf '%s\n' stale >"${no_rsync_destination}/stale.txt"
(
  PATH="${no_rsync_bin}"
  copy_skill_tree "${copy_source}" "${no_rsync_destination}"
)
assert_copied "${no_rsync_destination}" "without rsync"

# --- prune_build_artifacts ---

prune_target="${test_root}/prune/fixture"
mkdir -p "$(dirname "${prune_target}")"
cp -R "${copy_source}" "${prune_target}"
prune_build_artifacts "${prune_target}"
assert_copied "${prune_target}" "prune_build_artifacts"

printf '%s\n' 'skill-tree: all scenarios passed'
