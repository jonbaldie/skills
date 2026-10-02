#!/usr/bin/env bash

# Skills parked under skills/in-progress/ are unfinished, and skills under
# skills/deprecated/ are retired; neither may reach users through either
# distribution path (install.sh or sync-skills.sh).

set -euo pipefail

# shellcheck source=tests/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
new_sandbox skills-in-progress

readonly sync_script="${repository_root}/skills/sync-jonbaldie-skills/scripts/sync-skills.sh"
readonly matt_repository="${test_root}/matt-source"
readonly jon_repository="${test_root}/jon-source"

make_skill "${matt_repository}/skills/fixture-mp" fixture-mp
make_skill "${matt_repository}/skills/in-progress/matt-unfinished" matt-unfinished
commit_repository "${matt_repository}"

make_skill "${jon_repository}/skills/fixture-jb" fixture-jb
make_skill "${jon_repository}/skills/in-progress/jon-unfinished" jon-unfinished
commit_repository "${jon_repository}"

# install.sh run from this checkout installs the real collection, so it is
# asserted against the skills actually parked under skills/in-progress/ here.
readonly in_progress_dir="${repository_root}/skills/in-progress"
readonly install_project="${test_root}/install-project"
mkdir -p "${install_project}"
(
  cd "${install_project}"
  MATTPOCOCK_SKILLS_REPO="${matt_repository}" \
    "${repository_root}/install.sh" --agent universal --with-prereqs --yes
) >"${test_root}/install.log" 2>&1 || {
  cat "${test_root}/install.log" >&2
  fail "install.sh exited non-zero"
}

[[ -f "${install_project}/.agents/skills/bmf/SKILL.md" ]] ||
  fail "install.sh did not install a shipped jonbaldie skill"
[[ -f "${install_project}/.agents/skills/fixture-mp/SKILL.md" ]] ||
  fail "install.sh did not install the shipped prerequisite fixture skill"
if [[ -d "${in_progress_dir}" ]]; then
  while IFS= read -r skill_md; do
    name="$(basename "$(dirname "${skill_md}")")"
    [[ ! -e "${install_project}/.agents/skills/${name}" ]] ||
      fail "install.sh installed skills/in-progress skill: ${name}"
  done < <(find "${in_progress_dir}" -type f -name SKILL.md)
fi
readonly deprecated_dir="${repository_root}/skills/deprecated"
if [[ -d "${deprecated_dir}" ]]; then
  while IFS= read -r skill_md; do
    name="$(basename "$(dirname "${skill_md}")")"
    [[ ! -e "${install_project}/.agents/skills/${name}" ]] ||
      fail "install.sh installed skills/deprecated skill: ${name}"
  done < <(find "${deprecated_dir}" -type f -name SKILL.md)
fi
[[ ! -e "${install_project}/.agents/skills/matt-unfinished" ]] ||
  fail "install.sh installed a skills/in-progress skill from the prerequisite collection"

# sync-skills.sh
readonly sync_project="${test_root}/sync-project"
mkdir -p "${sync_project}"
MATTPOCOCK_SKILLS_REPO="${matt_repository}" \
JONBALDIE_SKILLS_REPO="${jon_repository}" \
  "${sync_script}" "${sync_project}" >"${test_root}/sync.log" 2>&1 || {
  cat "${test_root}/sync.log" >&2
  fail "sync-skills.sh exited non-zero"
}

[[ -f "${sync_project}/.agents/skills/fixture-jb/SKILL.md" ]] ||
  fail "sync-skills.sh did not install the shipped jonbaldie fixture skill"
[[ ! -e "${sync_project}/.agents/skills/jon-unfinished" ]] ||
  fail "sync-skills.sh installed a skills/in-progress skill"
[[ ! -e "${sync_project}/.agents/skills/matt-unfinished" ]] ||
  fail "sync-skills.sh installed a skills/in-progress skill from the prerequisite collection"
grep -qx jon-unfinished "${sync_project}/.agents/sync-jonbaldie-skills.manifest" &&
  fail "sync-skills.sh listed a skills/in-progress skill in the manifest"

pass 'in-progress skills are not distributed'
