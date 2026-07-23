#!/usr/bin/env bash

set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
public_source="${1:-}"
expected_revision="${2:-}"
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
if ! docker info >/dev/null 2>&1; then
  printf '%s\n' \
    'Docker is required to prove global-install isolation.' >&2
  exit 1
fi

cleanup() {
  rm -rf "${installation_root}"
}
trap cleanup EXIT

run_installer_for_agent() {
  local permission_response="$1"
  local agent="$2"
  local output_file="$3"

  printf '%s\n' "${permission_response}" |
    sandbox-exec -p "${sandbox_policy}" \
      "${repository_root}/install.sh" \
      --agent "${agent}" \
      --copy \
      --yes \
      >"${output_file}"
}

run_public_installer() {
  local source="$1"
  local expected_head="$2"
  local output_file="$3"
  local manual_commands
  local remote_head

  remote_head="$(
    GIT_CONFIG_GLOBAL=/dev/null \
    GIT_CONFIG_SYSTEM=/dev/null \
    GIT_TERMINAL_PROMPT=0 \
    git -c credential.helper= \
      ls-remote \
      "https://github.com/${source}.git" \
      HEAD |
      awk '{print $1}'
  )"
  if [[ -z "${remote_head}" ]]; then
    printf 'Expected an anonymously cloneable repository: %s\n' \
      "${source}" >&2
    return 1
  fi
  if [[ "${remote_head}" != "${expected_head}" ]]; then
    printf 'Expected %s at remote HEAD, got %s\n' \
      "${expected_head}" \
      "${remote_head}" >&2
    return 1
  fi

  manual_commands="$(read_bash_block_after '### In one project manually')"
  grep -Fq "add ${source}" <<<"${manual_commands}"

  (
    unset GH_TOKEN GITHUB_TOKEN
    export GIT_CONFIG_GLOBAL=/dev/null
    export GIT_CONFIG_SYSTEM=/dev/null
    export GIT_TERMINAL_PROMPT=0

    sandbox-exec -p "${sandbox_policy}" \
      bash -euo pipefail -c "${manual_commands}"
  ) >"${output_file}"
}

run_public_ship_only() {
  local source="$1"
  local output_file="$2"
  local manual_commands
  local ship_only_commands

  manual_commands="$(read_bash_block_after '### In one project manually')"
  ship_only_commands="$(
    printf '%s\n' "${manual_commands}" |
      awk -v source="${source}" '
        /^agent=/ { print }
        index($0, "add " source) { print }
      '
  )"
  grep -Fq "add ${source}" <<<"${ship_only_commands}"

  (
    unset GH_TOKEN GITHUB_TOKEN
    export GIT_CONFIG_GLOBAL=/dev/null
    export GIT_CONFIG_SYSTEM=/dev/null
    export GIT_TERMINAL_PROMPT=0

    sandbox-exec -p "${sandbox_policy}" \
      bash -euo pipefail -c "${ship_only_commands}"
  ) >"${output_file}"
}

install_scenario() {
  local scenario_root="$1"
  local scenario_runner="$2"
  shift 2

  mkdir -p "${scenario_root}"
  git -C "${scenario_root}" init --quiet

  (
    cd "${scenario_root}"
    "${scenario_runner}" "$@"
  )
}

read_bash_block_after() {
  local heading="$1"

  awk -v heading="${heading}" '
    $0 == heading { found = 1; next }
    found && /^```bash$/ { in_block = 1; next }
    in_block && /^```$/ { exit }
    in_block { print }
  ' "${repository_root}/README.md"
}

run_scenario() {
  local name="$1"
  shift

  printf 'Verifying %s\n' "${name}"
  "$@"
}

run_documented_global_clone() {
  local readme_commands

  readme_commands="$(read_bash_block_after '### Globally with the installer')"
  test -n "${readme_commands}"
  readme_commands="$(
    printf '%s\n' "${readme_commands}" |
      sed 's#https://github.com/jonbaldie/skills.git#/source#'
  )"

  docker run --rm \
    --volume "${repository_root}:/source:ro" \
    --workdir /work \
    node:22-bookworm \
    bash -euo pipefail -c '
      mkdir -p /root/.codex
      printf "y\n" | eval "$1"
      test -f /root/.agents/skills/ship-spec/SKILL.md
      test -f /root/.agents/skills/implement/SKILL.md
      test ! -e /work/jonbaldie-skills/.agents
    ' bash "${readme_commands}"
}

run_public_global_clone() {
  local readme_commands

  readme_commands="$(read_bash_block_after '### Globally with the installer')"
  test -n "${readme_commands}"

  docker run --rm \
    --workdir /work \
    node:22-bookworm \
    bash -euo pipefail -c '
      printf "y\n" | eval "$1"
      test -f /root/.agents/skills/ship-spec/SKILL.md
      test -f /root/.agents/skills/implement/SKILL.md
      test ! -e /work/jonbaldie-skills/.agents
    ' bash "${readme_commands}"
}

run_documented_project_clone() {
  local project_commands
  local project_with_spaces="${installation_root}/project with spaces"

  project_commands="$(
    read_bash_block_after '### In one project with the installer'
  )"
  test -n "${project_commands}"
  project_commands="$(
    printf '%s\n' "${project_commands}" |
      sed \
        -e "s#/path/to/your-project#${project_with_spaces}#" \
        -e "s#https://github.com/jonbaldie/skills.git#${repository_root}#"
  )"

  mkdir -p "${project_with_spaces}"
  git -C "${project_with_spaces}" init --quiet
  printf 'y\n' |
    sandbox-exec -p "${sandbox_policy}" \
      bash -euo pipefail -c "${project_commands}"

  test -f "${project_with_spaces}/.agents/skills/ship-spec/SKILL.md"
  test -f "${project_with_spaces}/.agents/skills/implement/SKILL.md"
  test ! -e "${installation_root}/jonbaldie-skills/.agents"
}

run_documented_project_manual() {
  local manual_commands
  local manual_project="${installation_root}/manual-project"

  manual_commands="$(read_bash_block_after '### In one project manually')"
  test -n "${manual_commands}"
  manual_commands="$(
    printf '%s\n' "${manual_commands}" |
      sed "s#jonbaldie/skills#${repository_root}#"
  )"

  mkdir -p "${manual_project}"
  git -C "${manual_project}" init --quiet
  (
    cd "${manual_project}"
    sandbox-exec -p "${sandbox_policy}" \
      bash -euo pipefail -c "${manual_commands}"
  ) >"${installation_root}/manual-project.log"

  test -f "${manual_project}/.agents/skills/ship-spec/SKILL.md"
  test -f "${manual_project}/.agents/skills/implement/SKILL.md"
}

run_documented_global_manual() {
  local manual_commands

  manual_commands="$(read_bash_block_after '### Globally manually')"
  test -n "${manual_commands}"
  manual_commands="$(
    printf '%s\n' "${manual_commands}" |
      sed 's#jonbaldie/skills#/source#'
  )"

  docker run --rm \
    --volume "${repository_root}:/source:ro" \
    --workdir /work \
    node:22-bookworm \
    bash -euo pipefail -c '
      eval "$1" >/tmp/first-install.log
      eval "$1" >/tmp/second-install.log
      test -f /root/.agents/skills/ship-spec/SKILL.md
      test -f /root/.agents/skills/implement/SKILL.md
      test ! -e /work/.agents
    ' bash "${manual_commands}"
}

run_public_global_manual() {
  local manual_commands

  manual_commands="$(read_bash_block_after '### Globally manually')"
  test -n "${manual_commands}"

  docker run --rm \
    --workdir /work \
    node:22-bookworm \
    bash -euo pipefail -c '
      eval "$1" >/tmp/install.log
      test -f /root/.agents/skills/ship-spec/SKILL.md
      test -f /root/.agents/skills/implement/SKILL.md
      test ! -e /work/.agents
    ' bash "${manual_commands}"
}

run_global_decline() {
  docker run --rm \
    --volume "${repository_root}:/source:ro" \
    --workdir /work \
    node:22-bookworm \
    bash -euo pipefail -c '
      printf "n\n" |
        /source/install.sh \
          --global \
          --agent codex \
          --copy \
          --yes \
          >/tmp/declined-install.log
      grep -Fq "Continuing without mattpocock/skills." \
        /tmp/declined-install.log
      test -f /root/.agents/skills/ship-spec/SKILL.md
      test ! -e /root/.agents/skills/implement
      test ! -e /work/.agents
    '
}

run_automatic_codex_detection() {
  docker run --rm \
    --volume "${repository_root}:/source:ro" \
    --workdir /work \
    node:22-bookworm \
    bash -euo pipefail -c '
      mkdir -p /root/.codex
      git init --quiet
      printf "y\n" |
        /source/install.sh \
          --copy \
          --yes \
          >/tmp/automatic-codex-install.log
      grep -Eiq "Installing to:.*Codex" \
        /tmp/automatic-codex-install.log
      test -f /work/.agents/skills/ship-spec/SKILL.md
      test -f /work/.agents/skills/implement/SKILL.md
    '
}

run_slash_command_harness() {
  local slash_project="${installation_root}/slash-command-project"

  install_scenario \
    "${slash_project}" \
    run_installer_for_agent \
    y \
    claude-code \
    "${installation_root}/slash-command-install.log"

  test -f "${slash_project}/.claude/skills/ship-spec/SKILL.md"
  test -f "${slash_project}/.claude/skills/implement/SKILL.md"
  test ! -e "${slash_project}/.agents/skills/ship-spec"
}

run_spaced_checkout() {
  local spaced_checkout="${installation_root}/collection checkout"
  local spaced_project="${installation_root}/spaced-checkout-project"

  git clone --quiet "${repository_root}" "${spaced_checkout}"
  mkdir -p "${spaced_project}"
  git -C "${spaced_project}" init --quiet
  (
    cd "${spaced_project}"
    printf 'y\n' |
      sandbox-exec -p "${sandbox_policy}" \
        "${spaced_checkout}/install.sh" \
        --agent codex \
        --copy \
        --yes
  ) >"${installation_root}/spaced-checkout-install.log"

  test -f "${spaced_project}/.agents/skills/ship-spec/SKILL.md"
  test -f "${spaced_project}/.agents/skills/implement/SKILL.md"
}

project_root="${installation_root}/project"
if [[ -n "${public_source}" ]]; then
  if [[ -z "${expected_revision}" ]]; then
    printf '%s\n' \
      'Public verification requires an expected remote revision.' >&2
    exit 1
  fi
  run_scenario \
    'anonymous public README project manual install' \
    install_scenario \
    "${project_root}" \
    run_public_installer \
    "${public_source}" \
    "${expected_revision}" \
    "${installation_root}/public-install.log"

  public_ship_only_project="${installation_root}/public-ship-only-project"
  run_scenario \
    'anonymous public README ship-spec-only install' \
    install_scenario \
    "${public_ship_only_project}" \
    run_public_ship_only \
    "${public_source}" \
    "${installation_root}/public-ship-only-install.log"
  test -f \
    "${public_ship_only_project}/.agents/skills/ship-spec/SKILL.md"
  test ! -e \
    "${public_ship_only_project}/.agents/skills/implement"

  run_scenario \
    'anonymous public README global cloned install' \
    run_public_global_clone
  run_scenario \
    'anonymous public README global manual install' \
    run_public_global_manual
else
  run_scenario \
    'accepted project install' \
    install_scenario \
    "${project_root}" \
    run_installer_for_agent \
    y \
    codex \
    "${installation_root}/accepted-install.log"
  run_scenario \
    'accepted project reinstall' \
    install_scenario \
    "${project_root}" \
    run_installer_for_agent \
    y \
    codex \
    "${installation_root}/accepted-reinstall.log"

  grep -Fq '$ship-spec and other skills in this collection will not work' \
    "${installation_root}/accepted-install.log"
  grep -Fq 'Install mattpocock/skills now? [y/N]' \
    "${installation_root}/accepted-install.log"

  run_scenario \
    'documented global cloned install' \
    run_documented_global_clone
  run_scenario \
    'documented project cloned install' \
    run_documented_project_clone
  run_scenario \
    'documented project manual install' \
    run_documented_project_manual
  run_scenario \
    'documented global manual install and rerun' \
    run_documented_global_manual
  run_scenario \
    'declined global prerequisites' \
    run_global_decline
  run_scenario \
    'automatic Codex project detection' \
    run_automatic_codex_detection
  run_scenario \
    'explicit slash-command harness' \
    run_slash_command_harness
  run_scenario \
    'installer checkout path containing spaces' \
    run_spaced_checkout
fi

if [[ -n "${public_source}" ]]; then
  printf '%s\n' \
    'Verifying anonymous public project artifacts and metadata'
else
  printf '%s\n' \
    'Verifying accepted project artifacts and metadata'
fi

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

if [[ -z "${public_source}" ]]; then
  declined_project="${installation_root}/declined-project"
  run_scenario \
    'declined project prerequisites' \
    install_scenario \
    "${declined_project}" \
    run_installer_for_agent \
    n \
    codex \
    "${installation_root}/declined-install.log"

  grep -Fq 'Continuing without mattpocock/skills.' \
    "${installation_root}/declined-install.log"
  grep -Fq '$ship-spec and other dependent skills will not work' \
    "${installation_root}/declined-install.log"
  test -f "${declined_project}/.agents/skills/ship-spec/SKILL.md"
  test ! -e "${declined_project}/.agents/skills/implement"
fi
