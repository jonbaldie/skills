# shellcheck shell=bash

# Which agents exist and where each one reads skills from. Sourced by
# install.sh and copy-to-skill-dirs.sh so installing and syncing agree on the
# same agents and destinations. It lives inside the sync skill so installed
# copies of that skill can still source it.

# The shared Agent Skills directory, relative to a project or home directory.
AGENT_CANONICAL_SKILLS_DIR=".agents/skills"

agent_home_dir() {
  printf '%s\n' "${HOME:-$(cd ~ && pwd)}"
}

agent_config_home() {
  printf '%s\n' "${XDG_CONFIG_HOME:-$(agent_home_dir)/.config}"
}

agent_codex_home() {
  printf '%s\n' "${CODEX_HOME:-$(agent_home_dir)/.codex}"
}

agent_claude_home() {
  printf '%s\n' "${CLAUDE_CONFIG_DIR:-$(agent_home_dir)/.claude}"
}

# Prints: name|display|project_skills_dir|global_skills_dir|detect_path
# A skills dir of "canonical" is AGENT_CANONICAL_SKILLS_DIR under the project
# or home directory. An empty detect_path is never detected; that agent is the
# fallback when no other agent is detected.
agent_db() {
  cat <<EOF
codex|Codex|canonical|canonical|$(agent_codex_home)
claude-code|Claude Code|.claude/skills|$(agent_claude_home)/skills|$(agent_claude_home)
opencode|OpenCode|canonical|canonical|$(agent_config_home)/opencode
pi|Pi|.pi/skills|$(agent_home_dir)/.pi/agent/skills|$(agent_home_dir)/.pi/agent
cursor|Cursor|canonical|canonical|$(agent_home_dir)/.cursor
gemini|Gemini CLI|.gemini/skills|$(agent_home_dir)/.gemini/skills|$(agent_home_dir)/.gemini
universal|Universal|canonical|canonical|
EOF
}

# Prints the agent_db row for <agent>, or fails when the agent is unknown.
agent_row() {
  local want="$1" line
  while IFS= read -r line; do
    if [[ "${line%%|*}" == "${want}" ]]; then
      printf '%s\n' "${line}"
      return 0
    fi
  done < <(agent_db)
  return 1
}

# Prints every known agent name, one per line, in declaration order.
known_agents() {
  local name
  while IFS='|' read -r name _; do
    printf '%s\n' "${name}"
  done < <(agent_db)
}

# Prints the known agent names as one comma-separated line.
supported_agents_list() {
  local joined
  joined="$(known_agents | tr '\n' ',')"
  joined="${joined%,}"
  printf '%s\n' "${joined//,/, }"
}

agent_is_known() {
  [[ -n "$1" ]] && agent_row "$1" >/dev/null
}

agent_display_name() {
  local line display
  line="$(agent_row "$1")" || return 1
  IFS='|' read -r _ display _ <<<"${line}"
  printf '%s\n' "${display}"
}

agent_uses_canonical_dir() {
  local line project_dir
  line="$(agent_row "$1")" || return 1
  IFS='|' read -r _ _ project_dir _ <<<"${line}"
  [[ "${project_dir}" == canonical ]]
}

# Prints AGENT_CANONICAL_SKILLS_DIR under <root>.
canonical_skills_dir() {
  printf '%s/%s\n' "$1" "${AGENT_CANONICAL_SKILLS_DIR}"
}

# Prints where <agent> reads skills in <scope>: "project" (below
# <project-root>) or "global" (below the home directory).
agent_skills_dir() {
  local agent="$1"
  local scope="$2"
  local project_root="${3:-}"
  local line project_dir global_dir

  line="$(agent_row "${agent}")" || {
    printf 'unknown agent: %s\n' "${agent}" >&2
    return 1
  }
  IFS='|' read -r _ _ project_dir global_dir _ <<<"${line}"

  case "${scope}" in
    project)
      [[ -n "${project_root}" ]] || {
        printf 'agent_skills_dir: project scope needs a project root\n' >&2
        return 2
      }
      if [[ "${project_dir}" == canonical ]]; then
        canonical_skills_dir "${project_root}"
      else
        printf '%s/%s\n' "${project_root}" "${project_dir}"
      fi
      ;;
    global)
      if [[ "${global_dir}" == canonical ]]; then
        canonical_skills_dir "$(agent_home_dir)"
      else
        printf '%s\n' "${global_dir}"
      fi
      ;;
    *)
      printf 'agent_skills_dir: expected project or global, got %s\n' "${scope:-nothing}" >&2
      return 2
      ;;
  esac
}

# Prints each agent whose detect path exists, one per line, or the fallback
# agent when none is detected.
detected_agents() {
  local name detect_path fallback="" found=false

  while IFS='|' read -r name _ _ _ detect_path; do
    if [[ -z "${detect_path}" ]]; then
      fallback="${name}"
    elif [[ -e "${detect_path}" ]]; then
      printf '%s\n' "${name}"
      found=true
    fi
  done < <(agent_db)

  if [[ "${found}" == false ]]; then
    printf '%s\n' "${fallback}"
  fi
}
