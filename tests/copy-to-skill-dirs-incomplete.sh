#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=tests/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
new_sandbox incomplete-managed-copy
project="${test_root}/project"
make_skill "${project}/.agents/skills/alpha" alpha
printf 'alpha\nmissing\n' >"${project}/.agents/sync-jonbaldie-skills.manifest"
make_skill "${project}/extra/alpha" old-alpha
make_skill "${project}/extra/retired" retired
printf 'alpha\nretired\n' >"${project}/extra/.sync-jonbaldie-skills.manifest"
cp -R "${project}/extra" "${test_root}/expected"
if "${repository_root}/skills/sync-jonbaldie-skills/scripts/copy-to-skill-dirs.sh" "${project}" extra fresh >"${test_root}/copy.log" 2>&1; then
  fail 'incomplete canonical installation reported success'
fi
grep -q 'managed skill is missing:' "${test_root}/copy.log" || fail 'missing source not reported'
diff -r "${test_root}/expected" "${project}/extra" || fail 'incomplete canonical installation changed destination'
[[ ! -e "${project}/fresh" ]] || fail 'incomplete canonical installation created destination'
pass 'incomplete canonical source fails before destination changes'
