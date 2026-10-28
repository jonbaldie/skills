#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=tests/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
new_sandbox managed-manifest-cli

bundle="${test_root}/bundle/sync-jonbaldie-skills"
mkdir -p "$(dirname "${bundle}")"
cp -R "${repository_root}/skills/sync-jonbaldie-skills" "${bundle}"
sync="${bundle}/scripts/sync-skills.sh"
copy="${bundle}/scripts/copy-to-skill-dirs.sh"
project="${test_root}/project"
canonical="${project}/.agents/skills"
manifest="${project}/.agents/sync-jonbaldie-skills.manifest"
dest="${project}/extra"
make_skill "${test_root}/matt/skills/alpha" alpha
make_skill "${test_root}/jon/skills/beta" beta
commit_repository "${test_root}/matt"
commit_repository "${test_root}/jon"
mkdir -p "${canonical}/retired" "${canonical}/unrelated" "${project}/outside"
printf 'sentinel\n' >"${project}/outside/value"
printf '# header\n\nretired\n../outside\n bad\n#ignored\n' >"${manifest}"
(cd "${test_root}" && MATTPOCOCK_SKILLS_REPO="${test_root}/matt" JONBALDIE_SKILLS_REPO="${test_root}/jon" "${sync}" "${project}") >"${test_root}/sync.log" 2>&1 || { cat "${test_root}/sync.log"; fail sync; }
[[ ! -e "${canonical}/retired" && -d "${canonical}/unrelated" && -f "${project}/outside/value" ]] || fail 'sync retirement safety'
grep -Fxq '  removed retired skill retired' "${test_root}/sync.log" || fail 'sync retirement output'
printf '# retired\n\nalpha\nbeta\n# trailing comment\n' >"${manifest}"
mkdir -p "${dest}/retired" "${dest}/unrelated"
printf '# old\nretired\n../outside\n bad\n' >"${dest}/.sync-jonbaldie-skills.manifest"
(cd "${test_root}" && "${copy}" "${project}" extra) >"${test_root}/copy.log" 2>&1
[[ ! -e "${dest}/retired" && -d "${dest}/unrelated" && -f "${project}/outside/value" && -f "${dest}/alpha/SKILL.md" ]] || fail 'copy retirement and copying'
cmp "${manifest}" "${dest}/.sync-jonbaldie-skills.manifest" || fail 'manifest bytes differ'
grep -Fxq "  copied alpha -> ${dest}" "${test_root}/copy.log" || fail 'copy output'

for invalid in '../outside' ' bad' ' #comment' $'alpha\r'; do
  printf 'alpha\n%s\n' "${invalid}" >"${manifest}"
  mkdir -p "${dest}/retired"
  printf 'retired\n' >"${dest}/.sync-jonbaldie-skills.manifest"
  if "${copy}" "${project}" extra fresh >"${test_root}/invalid.log" 2>&1; then fail "accepted invalid name: ${invalid}"; fi
  grep -Fq 'error: unsafe skill name in manifest:' "${test_root}/invalid.log" || fail 'missing invalid name error'
  [[ -d "${dest}/retired" && ! -e "${project}/fresh" && -f "${project}/outside/value" ]] || fail 'invalid input caused mutation'
done
"${copy}" "${project}" .agents/skills >"${test_root}/canonical.log" 2>&1 || fail 'canonical shortcut validated input'
grep -Fxq "Already canonical: ${canonical}" "${test_root}/canonical.log" || fail 'canonical shortcut output'

printf '# only comment\n\nalpha\nunfinished' >"${manifest}"
"${copy}" "${project}" extra >"${test_root}/final.log" 2>&1
[[ ! -e "${dest}/retired" && -f "${dest}/alpha/SKILL.md" ]] || fail 'unterminated record or retirement'
cmp "${manifest}" "${dest}/.sync-jonbaldie-skills.manifest" || fail 'unterminated bytes differ'
make_skill "${canonical}/a.b-1_x" a.b-1_x
printf '# header\n\na.b-1_x\na.b-1_x\n' >"${manifest}"
"${copy}" "${project}" extra >"${test_root}/duplicates.log" 2>&1
[[ -f "${dest}/a.b-1_x/SKILL.md" ]] || fail 'valid punctuation not copied'
[[ $(grep -Fc "  copied a.b-1_x -> ${dest}" "${test_root}/duplicates.log") == 2 ]] || fail 'duplicate names not preserved'
printf '# a.b-1_x\n\n' >"${manifest}"
"${copy}" "${project}" extra >"${test_root}/empty.log" 2>&1
[[ ! -e "${dest}/a.b-1_x" && -d "${dest}/unrelated" ]] || fail 'comment-only set retirement'
cmp "${manifest}" "${dest}/.sync-jonbaldie-skills.manifest" || fail 'comment-only bytes differ'
pass 'standalone sync and copy manifest behavior'
