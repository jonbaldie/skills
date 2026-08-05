#!/usr/bin/env bash

set -euo pipefail

# Pure-bash installer for jonbaldie/skills (and optional mattpocock/skills).
# No Node.js/npm required. Works from a checkout or via:
#   curl -fsSL https://raw.githubusercontent.com/jonbaldie/skills/main/install.sh | bash

readonly JONBALDIE_REPO_URL="${JONBALDIE_SKILLS_REPO:-https://github.com/jonbaldie/skills.git}"
readonly MATTPOCOCK_REPO_URL="${MATTPOCOCK_SKILLS_REPO:-https://github.com/mattpocock/skills.git}"

global_install=false
copy_mode=false
with_prereqs="" # yes | no | empty (ask)
declare -a selected_agents=()
declare -a selected_skills=()
declare -a cleanup_paths=()

script_from_stdin=false
repository_root=""
explicit_scope="" # global | project | empty

usage() {
  cat <<'EOF'
Install jonbaldie/skills for coding agents (no npm required).

Usage:
  install.sh [options]
  curl -fsSL https://raw.githubusercontent.com/jonbaldie/skills/main/install.sh | bash
  curl -fsSL ... | bash -s -- [options]

Options:
  -g, --global            Install into your home directory (default for the
                          curl one-liner)
      --project           Install into the current directory only
  -a, --agent <name>      Target agent (repeatable). Supported:
                          codex, claude-code, opencode, pi, cursor, universal
  -s, --skill <name>      Install only named skill(s). Default: all
  -y, --yes               Accepted for compatibility (no prompts beyond prereqs)
      --copy              Copy into agent dirs instead of symlinking
      --with-prereqs      Install mattpocock/skills without asking
      --without-prereqs   Skip mattpocock/skills without asking
  -h, --help              Show this help

Environment:
  JONBALDIE_SKILLS_REPO   Override jonbaldie/skills git URL
  MATTPOCOCK_SKILLS_REPO  Override mattpocock/skills git URL
EOF
}

log() {
  printf '%s\n' "$*"
}

# Helpers that print a return value on stdout must not use log(); use this.
log_status() {
  printf '%s\n' "$*" >&2
}

die() {
  printf '%s\n' "$*" >&2
  exit 1
}

on_exit() {
  local path
  for path in "${cleanup_paths[@]+"${cleanup_paths[@]}"}"; do
    rm -rf "${path}"
  done
}
trap on_exit EXIT

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

is_truthy() {
  case "${1:-}" in
    y | Y | yes | YES | true | TRUE | 1) return 0 ;;
    *) return 1 ;;
  esac
}

detect_script_origin() {
  local source_path="${BASH_SOURCE[0]:-}"

  if [[ -z "${source_path}" || "${source_path}" == "bash" || "${source_path}" == "-" ]]; then
    script_from_stdin=true
    return
  fi

  if [[ "${source_path}" == /dev/fd/* || "${source_path}" == /proc/self/fd/* ]]; then
    script_from_stdin=true
    return
  fi

  if [[ ! -f "${source_path}" ]]; then
    script_from_stdin=true
    return
  fi

  repository_root="$(cd "$(dirname "${source_path}")" && pwd)"
  if [[ ! -d "${repository_root}/skills" ]]; then
    script_from_stdin=true
    repository_root=""
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -g | --global)
        global_install=true
        explicit_scope="global"
        shift
        ;;
      --project)
        global_install=false
        explicit_scope="project"
        shift
        ;;
      -a | --agent)
        [[ $# -ge 2 ]] || die "Missing value for $1"
        selected_agents+=("$2")
        shift 2
        ;;
      --agent=*)
        selected_agents+=("${1#*=}")
        shift
        ;;
      -s | --skill)
        [[ $# -ge 2 ]] || die "Missing value for $1"
        selected_skills+=("$2")
        shift 2
        ;;
      --skill=*)
        selected_skills+=("${1#*=}")
        shift
        ;;
      -y | --yes)
        # Compatibility with the previous skills-CLI-based installer.
        shift
        ;;
      --copy)
        copy_mode=true
        shift
        ;;
      --with-prereqs)
        with_prereqs="yes"
        shift
        ;;
      --without-prereqs)
        with_prereqs="no"
        shift
        ;;
      -h | --help)
        usage
        exit 0
        ;;
      --)
        shift
        break
        ;;
      *)
        die "Unknown option: $1"
        ;;
    esac
  done

  if [[ $# -gt 0 ]]; then
    die "Unexpected arguments: $*"
  fi
}

home_dir() {
  printf '%s\n' "${HOME:-$(cd ~ && pwd)}"
}

config_home() {
  printf '%s\n' "${XDG_CONFIG_HOME:-$(home_dir)/.config}"
}

codex_home() {
  if [[ -n "${CODEX_HOME:-}" ]]; then
    printf '%s\n' "${CODEX_HOME}"
  else
    printf '%s\n' "$(home_dir)/.codex"
  fi
}

claude_home() {
  if [[ -n "${CLAUDE_CONFIG_DIR:-}" ]]; then
    printf '%s\n' "${CLAUDE_CONFIG_DIR}"
  else
    printf '%s\n' "$(home_dir)/.claude"
  fi
}

# Prints: name|display|project_skills_dir|global_skills_dir|detect_path
agent_db() {
  cat <<EOF
codex|Codex|.agents/skills|$(codex_home)/skills|$(codex_home)
claude-code|Claude Code|.claude/skills|$(claude_home)/skills|$(claude_home)
opencode|OpenCode|.agents/skills|$(config_home)/opencode/skills|$(config_home)/opencode
pi|Pi|.pi/skills|$(home_dir)/.pi/agent/skills|$(home_dir)/.pi/agent
cursor|Cursor|.agents/skills|$(home_dir)/.cursor/skills|$(home_dir)/.cursor
universal|Universal|.agents/skills|$(home_dir)/.agents/skills|
EOF
}

lookup_agent() {
  local want="$1" line name
  while IFS= read -r line; do
    name="${line%%|*}"
    if [[ "${name}" == "${want}" ]]; then
      printf '%s\n' "${line}"
      return 0
    fi
  done < <(agent_db)
  return 1
}

agent_is_universal() {
  local project_dir="$1"
  [[ "${project_dir}" == ".agents/skills" ]]
}

detect_agents() {
  local name display project_dir global_dir detect_path
  local -a found=()

  while IFS='|' read -r name display project_dir global_dir detect_path; do
    [[ "${name}" == "universal" ]] && continue
    if [[ -n "${detect_path}" && -e "${detect_path}" ]]; then
      found+=("${name}")
    fi
  done < <(agent_db)

  if [[ ${#found[@]} -eq 0 ]]; then
    found=(universal)
  fi

  selected_agents=("${found[@]}")
}

canonical_skills_dir() {
  if [[ "${global_install}" == true ]]; then
    printf '%s\n' "$(home_dir)/.agents/skills"
  else
    printf '%s\n' "$(pwd)/.agents/skills"
  fi
}

agent_skills_dir() {
  local agent_name="$1"
  local display project_dir global_dir
  local line
  line="$(lookup_agent "${agent_name}")" || die "Unsupported agent: ${agent_name}"
  IFS='|' read -r _ display project_dir global_dir _ <<<"${line}"

  if [[ "${global_install}" == true ]]; then
    if [[ -z "${global_dir}" ]]; then
      die "${display} does not support global skill installation"
    fi
    # Agents whose project dir is already .agents/skills install globally to the
    # canonical ~/.agents/skills path (same behavior as the skills CLI).
    if agent_is_universal "${project_dir}"; then
      canonical_skills_dir
      return
    fi
    printf '%s\n' "${global_dir}"
  else
    printf '%s\n' "$(pwd)/${project_dir}"
  fi
}

agent_display_name() {
  local line display
  line="$(lookup_agent "$1")" || die "Unsupported agent: $1"
  IFS='|' read -r _ display _ <<<"${line}"
  printf '%s\n' "${display}"
}

clone_repo() {
  local url="$1"
  local dest="$2"
  GIT_TERMINAL_PROMPT=0 git clone --depth 1 --quiet "${url}" "${dest}"
}

resolve_jonbaldie_root() {
  if [[ -n "${repository_root}" && -d "${repository_root}/skills" ]]; then
    printf '%s\n' "${repository_root}"
    return
  fi

  require_command git
  local tmp
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/jonbaldie-skills.XXXXXX")"
  cleanup_paths+=("${tmp}")
  log_status "Cloning jonbaldie/skills..."
  clone_repo "${JONBALDIE_REPO_URL}" "${tmp}/repo"
  printf '%s\n' "${tmp}/repo"
}

resolve_mattpocock_root() {
  require_command git
  local tmp
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/mattpocock-skills.XXXXXX")"
  cleanup_paths+=("${tmp}")
  log_status "Cloning mattpocock/skills..."
  clone_repo "${MATTPOCOCK_REPO_URL}" "${tmp}/repo"
  printf '%s\n' "${tmp}/repo"
}

discover_skill_dirs() {
  local root="$1"
  local max_depth=6
  local search_root="${root}"

  # Prefer the conventional skills/ package directory so a checkout that has
  # already been used as an install target does not re-discover destination copies.
  if [[ -d "${root}/skills" ]]; then
    search_root="${root}/skills"
  fi

  find "${search_root}" \
    \( -name node_modules -o -name .git -o -name dist -o -name build -o -name __pycache__ \
       -o -name .agents -o -name .claude -o -name .codex -o -name .pi -o -name .cursor \) -prune -o \
    -type f -name SKILL.md -print 2>/dev/null |
    while IFS= read -r skill_md; do
      local rel="${skill_md#"${search_root}"/}"
      local depth
      depth="$(printf '%s' "${rel}" | awk -F/ '{print NF-1}')"
      if [[ "${depth}" -le "${max_depth}" ]]; then
        dirname "${skill_md}"
      fi
    done
}

skill_name_from_dir() {
  local skill_dir="$1"
  local skill_md="${skill_dir}/SKILL.md"
  local name=""

  if [[ -f "${skill_md}" ]]; then
    name="$(
      awk '
        BEGIN { in_fm = 0 }
        /^---[[:space:]]*$/ {
          if (in_fm == 0) { in_fm = 1; next }
          else { exit }
        }
        in_fm && /^name:[[:space:]]*/ {
          sub(/^name:[[:space:]]*/, "")
          gsub(/^[[:space:]]+|[[:space:]]+$/, "")
          gsub(/^["'\'']|["'\'']$/, "")
          print
          exit
        }
      ' "${skill_md}"
    )"
  fi

  if [[ -z "${name}" ]]; then
    name="$(basename "${skill_dir}")"
  fi

  name="$(printf '%s' "${name}" | tr '[:upper:]' '[:lower:]')"
  name="$(printf '%s' "${name}" | sed -E 's/[^a-z0-9._]+/-/g; s/^[.-]+//; s/[.-]+$//; s/^$/unnamed-skill/')"
  printf '%s\n' "${name}"
}

skill_selected() {
  local name="$1"
  local skill

  if [[ ${#selected_skills[@]} -eq 0 ]]; then
    return 0
  fi

  for skill in "${selected_skills[@]}"; do
    if [[ "${skill}" == "*" || "${skill}" == "${name}" ]]; then
      return 0
    fi
  done
  return 1
}

copy_tree() {
  local src="$1"
  local dest="$2"

  rm -rf "${dest}"
  mkdir -p "$(dirname "${dest}")"

  if command -v rsync >/dev/null 2>&1; then
    mkdir -p "${dest}"
    rsync -a --delete "${src}/" "${dest}/"
    return
  fi

  if cp -a "${src}" "${dest}" 2>/dev/null; then
    return
  fi
  cp -R "${src}" "${dest}"
}

install_skill_dir() {
  local skill_dir="$1"
  local name canonical agent_name agent_dir
  local installed_any=false

  name="$(skill_name_from_dir "${skill_dir}")"
  skill_selected "${name}" || return 0

  canonical="$(canonical_skills_dir)/${name}"

  if [[ "${copy_mode}" == true ]]; then
    for agent_name in "${selected_agents[@]}"; do
      agent_dir="$(agent_skills_dir "${agent_name}")/${name}"
      copy_tree "${skill_dir}" "${agent_dir}"
      installed_any=true
    done
  else
    # Symlink mode: materialize once at the canonical path, then link agents in.
    copy_tree "${skill_dir}" "${canonical}"
    installed_any=true
    for agent_name in "${selected_agents[@]}"; do
      agent_dir="$(agent_skills_dir "${agent_name}")/${name}"
      if [[ "${agent_dir}" == "${canonical}" ]]; then
        continue
      fi
      mkdir -p "$(dirname "${agent_dir}")"
      rm -rf "${agent_dir}"
      if ! ln -s "${canonical}" "${agent_dir}" 2>/dev/null; then
        copy_tree "${canonical}" "${agent_dir}"
      fi
    done
  fi

  if [[ "${installed_any}" == true ]]; then
    log "  installed ${name}"
  fi
}

install_from_root() {
  local root="$1"
  local skill_dir
  local count=0

  while IFS= read -r skill_dir; do
    [[ -n "${skill_dir}" ]] || continue
    local name
    name="$(skill_name_from_dir "${skill_dir}")"
    skill_selected "${name}" || continue
    install_skill_dir "${skill_dir}"
    count=$((count + 1))
  done < <(discover_skill_dirs "${root}" | sort -u)

  if [[ "${count}" -eq 0 ]]; then
    die "No matching skills found under ${root}"
  fi
}

ask_prereqs() {
  if [[ "${with_prereqs}" == "yes" ]]; then
    return 0
  fi
  if [[ "${with_prereqs}" == "no" ]]; then
    return 1
  fi

  log '$ship-spec and other skills in this collection will not work without mattpocock/skills.'
  printf 'Install mattpocock/skills now? [y/N] '

  local answer=""
  if [[ "${script_from_stdin}" == true ]]; then
    # /dev/tty may exist but be unusable inside CI/docker; fall back cleanly.
    if ! { IFS= read -r answer </dev/tty; } 2>/dev/null; then
      # Non-interactive one-liner with no usable tty: install prerequisites.
      answer="y"
      printf 'y\n'
    fi
  else
    IFS= read -r answer || answer=""
  fi

  if is_truthy "${answer}"; then
    return 0
  fi

  log 'Continuing without mattpocock/skills.'
  log '$ship-spec and other dependent skills will not work until it is installed.'
  return 1
}

validate_agents() {
  local agent
  for agent in "${selected_agents[@]}"; do
    lookup_agent "${agent}" >/dev/null ||
      die "Unsupported agent: ${agent}
Supported: codex, claude-code, opencode, pi, cursor, universal"
  done
}

print_install_targets() {
  local agent
  local -a names=()
  for agent in "${selected_agents[@]}"; do
    names+=("$(agent_display_name "${agent}")")
  done
  local joined
  joined="$(printf '%s, ' "${names[@]}")"
  joined="${joined%, }"
  log "Installing to: ${joined}"
}

main() {
  detect_script_origin
  parse_args "$@"

  require_command git
  require_command find
  require_command awk
  require_command dirname
  require_command basename
  require_command mkdir
  require_command rm
  require_command cp
  require_command sort
  require_command mktemp
  require_command ln
  require_command sed
  require_command tr

  # curl|bash one-liner defaults to a global install unless --project was set.
  if [[ "${script_from_stdin}" == true && -z "${explicit_scope}" ]]; then
    global_install=true
  fi

  if [[ ${#selected_agents[@]} -eq 0 ]]; then
    detect_agents
  fi
  validate_agents
  print_install_targets

  local jon_root
  jon_root="$(resolve_jonbaldie_root)"

  if ask_prereqs; then
    local mp_root
    mp_root="$(resolve_mattpocock_root)"
    log "Installing mattpocock/skills..."
    install_from_root "${mp_root}"
  fi

  log "Installing jonbaldie/skills..."
  install_from_root "${jon_root}"

  if [[ "${global_install}" == true ]]; then
    log "Done. Skills installed under $(canonical_skills_dir) (and agent paths as needed)."
  else
    log "Done. Skills installed for this project."
  fi
}

main "$@"
