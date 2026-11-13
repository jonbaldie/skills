#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=tests/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
new_sandbox skill-copy-failure
# shellcheck source=/dev/null
source "${repository_root}/skills/sync-jonbaldie-skills/scripts/lib/skill-tree.sh"

make_skill "${test_root}/source" new
make_skill "${test_root}/destination" old
printf 'keep me\n' >"${test_root}/destination/local.txt"
cp -R "${test_root}/destination" "${test_root}/expected"
mkdir -p "${test_root}/bin"
cat >"${test_root}/bin/rsync" <<'RSYNC'
#!/usr/bin/env bash
printf 'simulated read failure\n' >&2
exit 23
RSYNC
chmod +x "${test_root}/bin/rsync"
if PATH="${test_root}/bin:${PATH}" copy_skill_tree "${test_root}/source" "${test_root}/destination" >"${test_root}/failure.log" 2>&1; then
  fail 'failed source copy reported success'
fi
diff -r "${test_root}/expected" "${test_root}/destination" || fail 'failed copy changed the installed tree'
[[ $(find "${test_root}" -maxdepth 1 -name '.skill-copy.*' | wc -l) -eq 0 ]] || fail 'failed copy leaked staging files'
real_mv="$(command -v mv)"
export real_mv
cat >"${test_root}/bin/mv" <<'MOVE'
#!/usr/bin/env bash
if [[ "$1" == */tree ]]; then
  printf 'simulated publish failure\n' >&2
  exit 1
fi
exec "${real_mv}" "$@"
MOVE
chmod +x "${test_root}/bin/mv"
rm "${test_root}/bin/rsync"
if PATH="${test_root}/bin:${PATH}" copy_skill_tree "${test_root}/source" "${test_root}/destination" >"${test_root}/publish.log" 2>&1; then
  fail 'failed publication reported success'
fi
diff -r "${test_root}/expected" "${test_root}/destination" || fail 'failed publication did not restore installed tree'
[[ $(find "${test_root}" -maxdepth 1 -name '.skill-copy.*' | wc -l) -eq 0 ]] || fail 'failed publication leaked staging files'
pass 'failed copy and publication preserve installed tree'
