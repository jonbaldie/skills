#!/usr/bin/env bash

# copy-to-skill-dirs.sh accepts --agent <name> alongside raw skill-directory
# arguments. Named agents resolve to the same project destinations install.sh
# uses; raw arguments keep their meaning even when they look like agent names.

set -euo pipefail

# shellcheck source=tests/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
new_sandbox skills-copy-agents-test

readonly sync_skill="${repository_root}/skills/sync-jonbaldie-skills"
readonly project="${test_root}/project"

make_project() {
  rm -rf "${project}"
  make_skill "${project}/.agents/skills/alpha" alpha
  printf '%s\n' alpha >"${project}/.agents/sync-jonbaldie-skills.manifest"
}

run_copy() {
  "${copy_script}" "${project}" "$@" >"${test_root}/copy.log" 2>&1
}

copied_to() {
  [[ -f "$1/alpha/SKILL.md" && -f "$1/.sync-jonbaldie-skills.manifest" ]]
}

# The installed sync skill carries its own lib/, so named agents resolve
# without the source checkout.
installed_skill="${test_root}/installed/sync-jonbaldie-skills"
mkdir -p "$(dirname "${installed_skill}")"
cp -R "${sync_skill}" "${installed_skill}"

for copy_script in \
  "${sync_skill}/scripts/copy-to-skill-dirs.sh" \
  "${installed_skill}/scripts/copy-to-skill-dirs.sh"; do

  # Named agents resolve to their project destinations.
  make_project
  run_copy --agent claude-code --agent=gemini --agent pi || {
    cat "${test_root}/copy.log" >&2
    fail "named agents rejected by ${copy_script}"
  }
  for destination in .claude/skills .gemini/skills .pi/skills; do
    copied_to "${project}/${destination}" ||
      fail "--agent did not populate ${destination} (${copy_script})"
  done

  # Agents that read the canonical directory need no copy.
  for agent in codex opencode cursor universal; do
    make_project
    run_copy --agent "${agent}" || {
      cat "${test_root}/copy.log" >&2
      fail "--agent ${agent} failed"
    }
    grep -Fq "Already canonical: ${project}/.agents/skills" "${test_root}/copy.log" ||
      fail "--agent ${agent} did not report the canonical directory: $(<"${test_root}/copy.log")"
    [[ ! -e "${project}/.agents/skills/.sync-jonbaldie-skills.manifest" ]] ||
      fail "--agent ${agent} wrote a copy manifest into the canonical directory"
  done
done

copy_script="${sync_skill}/scripts/copy-to-skill-dirs.sh"

# Raw relative and absolute destinations mix with named agents, and a raw
# argument spelled like an agent name stays a path.
make_project
run_copy gemini "${test_root}/absolute/skills" --agent claude-code || {
  cat "${test_root}/copy.log" >&2
  fail "mixed raw and named destinations rejected"
}
copied_to "${project}/gemini" || fail "raw 'gemini' was not treated as a path"
[[ ! -e "${project}/.gemini" ]] || fail "raw 'gemini' was treated as an agent name"
copied_to "${test_root}/absolute/skills" || fail "absolute destination not populated"
copied_to "${project}/.claude/skills" || fail "named destination not populated alongside raw ones"

# Unknown agents fail before any destination is written.
make_project
if run_copy .claude/skills --agent nope; then
  fail "accepted unknown agent"
fi
grep -q '^error: unknown agent: nope' "${test_root}/copy.log" ||
  fail "unknown agent not reported: $(<"${test_root}/copy.log")"
grep -Fq 'codex, claude-code, opencode, pi, cursor, gemini, universal' "${test_root}/copy.log" ||
  fail "unknown agent error does not list supported agents: $(<"${test_root}/copy.log")"
[[ ! -e "${project}/.claude" ]] || fail "destination written before rejecting unknown agent"

# --agent needs a value, and at least one destination is required.
make_project
for arguments in "--agent" "--agent="; do
  # shellcheck disable=SC2086
  if run_copy ${arguments}; then
    fail "accepted '${arguments}' without an agent name"
  fi
done
if run_copy; then
  fail "accepted a call with no destinations"
fi

pass
