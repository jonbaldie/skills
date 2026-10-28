#!/usr/bin/env bash

set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
new_sandbox installed-skill-name

sync_script="${repository_root}/skills/sync-jonbaldie-skills/scripts/sync-skills.sh"
jon="${test_root}/jon"
matt="${test_root}/matt"
make_skill "${jon}/skills/good" 'My Skill' 'new content'
make_skill "${jon}/skills/fallback Name" '' 'fallback content'
make_skill "${matt}/skills/other" other
add_collection_modules "${jon}"
cp "${repository_root}/install.sh" "${jon}/install.sh"
commit_repository "${jon}"
commit_repository "${matt}"

run_install() {
  local project="$1"
  shift
  (cd "${project}" && bash "${jon}/install.sh" --project --agent universal --without-prereqs --yes "$@")
}
run_sync() {
  MATTPOCOCK_SKILLS_REPO="${matt}" JONBALDIE_SKILLS_REPO="${jon}" bash "${sync_script}" "$1"
}

for command in install sync; do
  project="${test_root}/${command}-valid"
  mkdir -p "${project}"
  "run_${command}" "${project}" >"${test_root}/${command}-valid.log" 2>&1 || fail "${command} rejected valid names"
  [[ -f "${project}/.agents/skills/my-skill/SKILL.md" ]] || fail "${command} did not normalize frontmatter"
  [[ -f "${project}/.agents/skills/fallback-name/SKILL.md" ]] || fail "${command} did not normalize fallback"
done

make_skill "${jon}/skills/unsafe" '_private'
commit_repository "${jon}"

selected="${test_root}/selected"
mkdir -p "${selected}"
run_install "${selected}" --skill my-skill >"${test_root}/selected.log" 2>&1 || fail 'unselected invalid name blocked install'
[[ -f "${selected}/.agents/skills/my-skill/SKILL.md" ]] || fail 'selected skill missing'
[[ ! -e "${selected}/.agents/skills/_private" ]] || fail 'unselected invalid skill installed'

for command in install sync; do
  for state in fresh existing; do
    project="${test_root}/${command}-${state}"
    mkdir -p "${project}"
    if [[ "${state}" == existing ]]; then
      mkdir -p "${project}/.agents/skills/my-skill"
      printf 'original\n' >"${project}/.agents/skills/my-skill/SKILL.md"
      printf 'my-skill\n' >"${project}/.agents/sync-jonbaldie-skills.manifest"
      cp -a "${project}/.agents" "${test_root}/before-${command}"
    fi
    if "run_${command}" "${project}" >"${test_root}/${command}-${state}.log" 2>&1; then
      fail "${command} accepted invalid name (${state})"
    fi
    grep -q "unsafe skill name '_private'" "${test_root}/${command}-${state}.log" || fail "${command} did not report invalid name"
    if [[ "${state}" == existing ]]; then
      diff -r "${test_root}/before-${command}" "${project}/.agents" >/dev/null || fail "${command} changed destination on failure"
    else
      [[ ! -e "${project}/.agents" ]] || fail "${command} created destination on failure"
    fi
  done
done

cp -a "${selected}/.agents" "${test_root}/before-selected"
if run_install "${selected}" --skill _private >"${test_root}/selected-invalid.log" 2>&1; then
  fail 'selected invalid name accepted'
fi
grep -q "unsafe skill name '_private'" "${test_root}/selected-invalid.log" || fail 'selected invalid name not reported'
diff -r "${test_root}/before-selected" "${selected}/.agents" >/dev/null || fail 'selected invalid name changed destination'

copy_project="${test_root}/copy"
mkdir -p "${copy_project}/.agents/skills/my-skill"
printf 'original\n' >"${copy_project}/.agents/skills/my-skill/SKILL.md"
cp -a "${copy_project}/.agents" "${test_root}/before-copy"
if run_install "${copy_project}" --copy >"${test_root}/copy.log" 2>&1; then
  fail 'copy install accepted invalid name'
fi
grep -q "unsafe skill name '_private'" "${test_root}/copy.log" || fail 'copy install did not report invalid name'
diff -r "${test_root}/before-copy" "${copy_project}/.agents" >/dev/null || fail 'copy install changed destination on failure'

pass
