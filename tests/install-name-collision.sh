#!/usr/bin/env bash

# When distinct skill directories normalize to the same canonical name,
# install.sh and sync-skills.sh must detect the collision before copying,
# report the normalized name and colliding source paths, and abort without
# overwriting destination files.

set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly repository_root
readonly sync_script="${repository_root}/skills/sync-jonbaldie-skills/scripts/sync-skills.sh"
test_root="$(mktemp -d "${TMPDIR:-/tmp}/skills-collision-test.XXXXXX")"
readonly test_root

cleanup() {
  rm -rf "${test_root}"
}
trap cleanup EXIT

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

make_skill() {
  local repo_dir="$1"
  local rel_dir="$2"
  local name="$3"
  local body="$4"
  local skill_dir="${repo_dir}/skills/${rel_dir}"

  mkdir -p "${skill_dir}"
  printf -- '---\nname: %s\ndescription: %s\n---\n%s\n' "${name}" "${rel_dir}" "${body}" >"${skill_dir}/SKILL.md"
}

commit_repo() {
  local repo_dir="$1"
  git -C "${repo_dir}" add .
  git -C "${repo_dir}" -c user.name=Fixture -c user.email=fixture@example.com commit --quiet -m fixture
}

# --- Scenario 1: install.sh detects collision within single repository ---
repo1="${test_root}/repo1"
mkdir -p "${repo1}"
git init --quiet "${repo1}"
make_skill "${repo1}" alpha "My Skill" "alpha body"
make_skill "${repo1}" beta "my-skill" "beta body"
make_skill "${repo1}" fine "fine-skill" "fine body"
commit_repo "${repo1}"
cp "${repository_root}/install.sh" "${repo1}/install.sh"

project1="${test_root}/project1"
mkdir -p "${project1}"

set +e
output1="$(
  cd "${project1}" &&
    HOME="${test_root}/home1" \
    bash "${repo1}/install.sh" \
      --project \
      --agent universal \
      --without-prereqs \
      --yes 2>&1
)"
exit1=$?
set -e

[[ ${exit1} -ne 0 ]] || fail "Scenario 1: install.sh exited 0 on intra-repo collision"
echo "${output1}" | grep -q "my-skill" || fail "Scenario 1: install.sh did not report normalized name 'my-skill'"
echo "${output1}" | grep -q "alpha" || fail "Scenario 1: install.sh did not report colliding source 'alpha'"
echo "${output1}" | grep -q "beta" || fail "Scenario 1: install.sh did not report colliding source 'beta'"
[[ ! -e "${project1}/.agents/skills/my-skill" ]] || fail "Scenario 1: install.sh created or modified colliding destination"

# --- Scenario 2: install.sh detects collision across prerequisite and primary repo ---
mp_repo="${test_root}/mp_repo"
jb_repo="${test_root}/jb_repo"
mkdir -p "${mp_repo}" "${jb_repo}"
git init --quiet "${mp_repo}"
git init --quiet "${jb_repo}"
make_skill "${mp_repo}" mp-colliding "Cross Skill" "mp body"
commit_repo "${mp_repo}"
make_skill "${jb_repo}" jb-colliding "cross-skill" "jb body"
commit_repo "${jb_repo}"
cp "${repository_root}/install.sh" "${jb_repo}/install.sh"

project2="${test_root}/project2"
mkdir -p "${project2}"

set +e
output2="$(
  cd "${project2}" &&
    HOME="${test_root}/home2" \
    MATTPOCOCK_SKILLS_REPO="${mp_repo}" \
    bash "${jb_repo}/install.sh" \
      --project \
      --agent universal \
      --with-prereqs \
      --yes 2>&1
)"
exit2=$?
set -e

[[ ${exit2} -ne 0 ]] || fail "Scenario 2: install.sh exited 0 on cross-repo collision"
echo "${output2}" | grep -q "cross-skill" || fail "Scenario 2: install.sh did not report normalized name 'cross-skill'"
echo "${output2}" | grep -q "mp-colliding" || fail "Scenario 2: install.sh did not report colliding source 'mp-colliding'"
echo "${output2}" | grep -q "jb-colliding" || fail "Scenario 2: install.sh did not report colliding source 'jb-colliding'"
[[ ! -e "${project2}/.agents/skills/cross-skill" ]] || fail "Scenario 2: install.sh created or modified colliding destination"

# --- Scenario 3: install.sh with --skill filter ignores unselected colliding skills ---
project3="${test_root}/project3"
mkdir -p "${project3}"

(
  cd "${project3}" &&
    HOME="${test_root}/home3" \
    bash "${repo1}/install.sh" \
      --project \
      --agent universal \
      --without-prereqs \
      --skill fine-skill \
      --yes >/dev/null 2>&1
) || fail "Scenario 3: install.sh failed when filter excluded colliding skills"

[[ -f "${project3}/.agents/skills/fine-skill/SKILL.md" ]] || fail "Scenario 3: selected non-colliding skill was not installed"
[[ ! -e "${project3}/.agents/skills/my-skill" ]] || fail "Scenario 3: unselected colliding skills were installed"

# --- Scenario 4: sync-skills.sh detects collision across collections ---
sync_project="${test_root}/sync_project"
mkdir -p "${sync_project}"

set +e
output4="$(
  MATTPOCOCK_SKILLS_REPO="${mp_repo}" \
  JONBALDIE_SKILLS_REPO="${jb_repo}" \
  bash "${sync_script}" "${sync_project}" 2>&1
)"
exit4=$?
set -e

[[ ${exit4} -ne 0 ]] || fail "Scenario 4: sync-skills.sh exited 0 on collision"
echo "${output4}" | grep -q "cross-skill" || fail "Scenario 4: sync-skills.sh did not report normalized name 'cross-skill'"
echo "${output4}" | grep -q "mp-colliding" || fail "Scenario 4: sync-skills.sh did not report colliding source 'mp-colliding'"
echo "${output4}" | grep -q "jb-colliding" || fail "Scenario 4: sync-skills.sh did not report colliding source 'jb-colliding'"
[[ ! -e "${sync_project}/.agents/skills/cross-skill" ]] || fail "Scenario 4: sync-skills.sh created or modified colliding destination"

printf '%s\n' 'install-name-collision: all scenarios passed'
