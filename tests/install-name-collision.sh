#!/usr/bin/env bash

# When distinct skill directories normalize to the same canonical name,
# install.sh and sync-skills.sh must detect the collision before copying,
# report the normalized name and colliding source paths, and abort without
# overwriting destination files.

set -euo pipefail

# shellcheck source=tests/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
new_sandbox skills-collision-test

readonly sync_script="${repository_root}/skills/sync-jonbaldie-skills/scripts/sync-skills.sh"
readonly skill_tree_module="${repository_root}/skills/sync-jonbaldie-skills/scripts/lib/skill-tree.sh"

# install.sh sources the skill-tree module from the collection it installs.
add_installer() {
  local repo_dir="$1"
  local module_dir="${repo_dir}/skills/sync-jonbaldie-skills/scripts/lib"

  cp "${repository_root}/install.sh" "${repo_dir}/install.sh"
  mkdir -p "${module_dir}"
  cp "${skill_tree_module}" "${module_dir}/skill-tree.sh"
}

# --- Scenario 1: install.sh detects collision within single repository ---
repo1="${test_root}/repo1"
make_skill "${repo1}/skills/alpha" "My Skill" "alpha body"
make_skill "${repo1}/skills/beta" "my-skill" "beta body"
make_skill "${repo1}/skills/fine" "fine-skill" "fine body"
commit_repository "${repo1}"
add_installer "${repo1}"

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
make_skill "${mp_repo}/skills/mp-colliding" "Cross Skill" "mp body"
commit_repository "${mp_repo}"
make_skill "${jb_repo}/skills/jb-colliding" "cross-skill" "jb body"
commit_repository "${jb_repo}"
add_installer "${jb_repo}"

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

pass
