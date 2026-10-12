#!/usr/bin/env bash

# The agent-destinations module is the one declaration of which agents exist
# and where their skills go. install.sh and copy-to-skill-dirs.sh both resolve
# destinations through it, so its lookups are checked here directly instead of
# through a full install.

set -euo pipefail

# shellcheck source=tests/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
new_sandbox agent-destinations-test

# shellcheck source=/dev/null
source "${repository_root}/skills/sync-jonbaldie-skills/scripts/lib/agent-destinations.sh"

fake_home="${test_root}/home"
mkdir -p "${fake_home}"
project="${test_root}/project"

# Runs a lookup with only HOME set, so the caller's agent config overrides
# cannot leak into expectations.
with_home() {
  env -u CODEX_HOME -u CLAUDE_CONFIG_DIR -u XDG_CONFIG_HOME HOME="${fake_home}" "$@"
}

lookup() {
  with_home bash -c 'source "$1"; shift; "$@"' bash \
    "${repository_root}/skills/sync-jonbaldie-skills/scripts/lib/agent-destinations.sh" "$@"
}

assert_eq() {
  local actual="$1"
  local expected="$2"
  local description="$3"

  [[ "${actual}" == "${expected}" ]] ||
    fail "${description}: got '${actual}', expected '${expected}'"
}

# --- known_agents ---

assert_eq "$(known_agents | paste -sd, -)" \
  codex,claude-code,opencode,pi,cursor,gemini,universal \
  "known_agents"
assert_eq "$(supported_agents_list)" \
  "codex, claude-code, opencode, pi, cursor, gemini, universal" \
  "supported_agents_list"

for agent in codex claude-code opencode pi cursor gemini universal; do
  agent_is_known "${agent}" || fail "agent_is_known rejected ${agent}"
done
for agent in '' Codex claude gemini-cli '.claude/skills' 'codex|x'; do
  if agent_is_known "${agent}"; then
    fail "agent_is_known accepted '${agent}'"
  fi
done

# --- agent_display_name ---

assert_eq "$(agent_display_name claude-code)" "Claude Code" "claude-code display name"
assert_eq "$(agent_display_name gemini)" "Gemini CLI" "gemini display name"
if agent_display_name nope >/dev/null 2>&1; then
  fail "agent_display_name accepted an unknown agent"
fi

# --- canonical_skills_dir ---

assert_eq "$(canonical_skills_dir "${project}")" "${project}/.agents/skills" "canonical dir"

# --- agent_skills_dir: project scope ---

while IFS='=' read -r agent expected; do
  assert_eq "$(lookup agent_skills_dir "${agent}" project "${project}")" \
    "${project}/${expected}" "project dir for ${agent}"
done <<'EOF'
codex=.agents/skills
claude-code=.claude/skills
opencode=.agents/skills
pi=.pi/skills
cursor=.agents/skills
gemini=.gemini/skills
universal=.agents/skills
EOF

# --- agent_skills_dir: global scope ---

# Agents that read the canonical directory install globally to
# ~/.agents/skills, not to their own config directories.
while IFS='=' read -r agent expected; do
  assert_eq "$(lookup agent_skills_dir "${agent}" global)" \
    "${fake_home}/${expected}" "global dir for ${agent}"
done <<'EOF'
codex=.agents/skills
claude-code=.claude/skills
opencode=.agents/skills
pi=.pi/agent/skills
cursor=.agents/skills
gemini=.gemini/skills
universal=.agents/skills
EOF

assert_eq "$(with_home CLAUDE_CONFIG_DIR="${test_root}/claude-config" \
  bash -c 'source "$1"; agent_skills_dir claude-code global' bash \
  "${repository_root}/skills/sync-jonbaldie-skills/scripts/lib/agent-destinations.sh")" \
  "${test_root}/claude-config/skills" "CLAUDE_CONFIG_DIR override"

# CODEX_HOME and XDG_CONFIG_HOME move detection only; Codex and OpenCode still
# install to the canonical directory.
assert_eq "$(with_home CODEX_HOME="${test_root}/codex-home" XDG_CONFIG_HOME="${test_root}/xdg" \
  bash -c 'source "$1"; agent_skills_dir codex global; agent_skills_dir opencode global' bash \
  "${repository_root}/skills/sync-jonbaldie-skills/scripts/lib/agent-destinations.sh" | paste -sd, -)" \
  "${fake_home}/.agents/skills,${fake_home}/.agents/skills" "codex/opencode global with overrides"

# --- agent_uses_canonical_dir ---

for agent in codex opencode cursor universal; do
  agent_uses_canonical_dir "${agent}" || fail "${agent} should use the canonical directory"
done
for agent in claude-code pi gemini; do
  if agent_uses_canonical_dir "${agent}"; then
    fail "${agent} should not use the canonical directory"
  fi
done

# --- unknown agents and scopes ---

if lookup agent_skills_dir nope project "${project}" >/dev/null 2>"${test_root}/unknown.err"; then
  fail "agent_skills_dir resolved an unknown agent"
fi
grep -q 'unknown agent: nope' "${test_root}/unknown.err" ||
  fail "unknown agent not reported: $(<"${test_root}/unknown.err")"
if lookup agent_skills_dir codex elsewhere >/dev/null 2>&1; then
  fail "agent_skills_dir accepted an unknown scope"
fi
if lookup agent_skills_dir codex project >/dev/null 2>&1; then
  fail "agent_skills_dir accepted project scope without a project root"
fi

# --- detected_agents ---

detect_home="${test_root}/detect-home"
detect() {
  env -u CODEX_HOME -u CLAUDE_CONFIG_DIR -u XDG_CONFIG_HOME HOME="${detect_home}" "$@" \
    bash -c 'source "$1"; detected_agents' bash \
    "${repository_root}/skills/sync-jonbaldie-skills/scripts/lib/agent-destinations.sh" |
    paste -sd, -
}

mkdir -p "${detect_home}"
assert_eq "$(detect)" universal "detection falls back to universal"

mkdir -p "${detect_home}/.claude" "${detect_home}/.gemini" "${detect_home}/.pi/agent"
assert_eq "$(detect)" claude-code,pi,gemini "detection by home directories"

mkdir -p "${test_root}/codex-home" "${test_root}/xdg/opencode"
assert_eq "$(detect CODEX_HOME="${test_root}/codex-home" XDG_CONFIG_HOME="${test_root}/xdg")" \
  codex,claude-code,opencode,pi,gemini "detection honors CODEX_HOME and XDG_CONFIG_HOME"

pass
