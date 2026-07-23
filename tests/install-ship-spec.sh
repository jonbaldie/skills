#!/usr/bin/env bash

set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
installation_root="$(mktemp -d "${TMPDIR:-/tmp}/ship-spec-install.XXXXXX")"
user_root="$(node -p 'require("node:os").homedir()')"
sandbox_policy="(version 1)
(allow default)
(deny file-read* file-write*
  (subpath \"${user_root}/.agents\")
  (subpath \"${user_root}/.codex\"))"

if ! command -v sandbox-exec >/dev/null 2>&1; then
  printf '%s\n' \
    'sandbox-exec is required to prove agent-home isolation.' >&2
  exit 1
fi

cleanup() {
  rm -rf "${installation_root}"
}
trap cleanup EXIT

run_installer() {
  local permission_response="$1"
  local output_file="$2"

  printf '%s\n' "${permission_response}" |
    sandbox-exec -p "${sandbox_policy}" \
      "${repository_root}/install.sh" \
      --agent codex \
      --copy \
      --yes \
      >"${output_file}"
}

install_scenario() {
  local scenario_root="$1"
  local permission_response="$2"
  local output_file="$3"

  mkdir -p "${scenario_root}"
  git -C "${scenario_root}" init --quiet

  (
    cd "${scenario_root}"
    run_installer "${permission_response}" "${output_file}"
  )
}

project_root="${installation_root}/project"
install_scenario \
  "${project_root}" \
  y \
  "${installation_root}/accepted-install.log"

grep -Fq '$ship-spec and other skills in this collection will not work' \
  "${installation_root}/accepted-install.log"
grep -Fq 'Install mattpocock/skills now? [y/N]' \
  "${installation_root}/accepted-install.log"

installed_skills="${project_root}/.agents/skills"
installed_ship_spec="${installed_skills}/ship-spec"

test -f "${installed_ship_spec}/SKILL.md"
test -f "${installed_ship_spec}/agents/openai.yaml"
test -f "${installed_skills}/implement/SKILL.md"
test -f "${installed_skills}/tdd/SKILL.md"
test -f "${installed_skills}/code-review/SKILL.md"
test -f "${installed_skills}/setup-matt-pocock-skills/SKILL.md"
test -f "${installed_ship_spec}/../implement/SKILL.md"

cmp "${repository_root}/skills/ship-spec/SKILL.md" \
  "${installed_ship_spec}/SKILL.md"
cmp "${repository_root}/skills/ship-spec/agents/openai.yaml" \
  "${installed_ship_spec}/agents/openai.yaml"

grep -q '^name: ship-spec$' "${installed_ship_spec}/SKILL.md"
grep -Eq '^description: .+$' "${installed_ship_spec}/SKILL.md"
grep -q 'display_name: "Ship Spec"' \
  "${installed_ship_spec}/agents/openai.yaml"
grep -q 'allow_implicit_invocation: false' \
  "${installed_ship_spec}/agents/openai.yaml"

ruby - "${installed_ship_spec}/SKILL.md" \
  "${installed_ship_spec}/agents/openai.yaml" <<'RUBY'
require "yaml"

skill_contents = File.read(ARGV.fetch(0))
frontmatter = skill_contents.match(/\A---\n(.*?)\n---\n/m)
abort "invalid SKILL.md frontmatter" unless frontmatter

skill_metadata = YAML.safe_load(frontmatter[1])
abort "invalid skill name" unless skill_metadata["name"] == "ship-spec"
abort "missing skill description" unless skill_metadata["description"].is_a?(String)

agent_metadata = YAML.safe_load(File.read(ARGV.fetch(1)))
abort "invalid agent interface" unless agent_metadata.dig("interface", "display_name") == "Ship Spec"
abort "invalid invocation policy" unless agent_metadata.dig("policy", "allow_implicit_invocation") == false
RUBY

declined_project="${installation_root}/declined-project"
install_scenario \
  "${declined_project}" \
  n \
  "${installation_root}/declined-install.log"

grep -Fq 'Continuing without mattpocock/skills.' \
  "${installation_root}/declined-install.log"
grep -Fq '$ship-spec and other dependent skills will not work' \
  "${installation_root}/declined-install.log"
test -f "${declined_project}/.agents/skills/ship-spec/SKILL.md"
test ! -e "${declined_project}/.agents/skills/implement"
