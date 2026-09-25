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
installed_skills_registry=""

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

# The skill-tree module defines how skills are discovered, named and copied.
# A curl|bash run has no checkout until the collection is cloned, so it is
# sourced from the resolved collection root.
load_skill_tree_module() {
  local module="$1/skills/sync-jonbaldie-skills/scripts/lib/skill-tree.sh"
  [[ -f "${module}" ]] || die "Missing skill-tree module: ${module}"
  # shellcheck source=/dev/null
  source "${module}"
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

physical_entry_path() {
  local path="$1"
  local parent name

  parent="$(dirname "${path}")"
  name="$(basename "${path}")"
  parent="$(cd -P "${parent}" && pwd)"
  printf '%s/%s\n' "${parent}" "${name}"
}

install_skill_dir() {
  local skill_dir="$1"
  local name canonical agent_name agent_dir
  local installed_any=false
  local real_dir existing_source

  name="$(skill_name_from_dir "${skill_dir}" --slugify)"
  skill_selected "${name}" || return 0

  real_dir="$(cd -P "${skill_dir}" 2>/dev/null && pwd -P || printf '%s' "${skill_dir}")"
  if [[ -n "${installed_skills_registry}" && -f "${installed_skills_registry}" ]]; then
    existing_source="$(awk -F'\t' -v n="${name}" '$1 == n { print $2; exit }' "${installed_skills_registry}")"
    if [[ -n "${existing_source}" && "${existing_source}" != "${real_dir}" ]]; then
      die "error: refusing to overwrite destination for colliding skill '${name}' from ${skill_dir}"
    fi
  fi
  if [[ -n "${installed_skills_registry}" ]]; then
    printf '%s\t%s\n' "${name}" "${real_dir}" >>"${installed_skills_registry}"
  fi

  canonical="$(canonical_skills_dir)/${name}"

  if [[ "${copy_mode}" == true ]]; then
    for agent_name in "${selected_agents[@]}"; do
      agent_dir="$(agent_skills_dir "${agent_name}")/${name}"
      copy_skill_tree "${skill_dir}" "${agent_dir}"
      installed_any=true
    done
  else
    # Symlink mode: materialize once at the canonical path, then link agents in.
    copy_skill_tree "${skill_dir}" "${canonical}"
    installed_any=true
    for agent_name in "${selected_agents[@]}"; do
      agent_dir="$(agent_skills_dir "${agent_name}")/${name}"
      if [[ "${agent_dir}" == "${canonical}" ]]; then
        continue
      fi
      mkdir -p "$(dirname "${agent_dir}")"
      if [[ "$(physical_entry_path "${agent_dir}")" == \
        "$(physical_entry_path "${canonical}")" ]]; then
        continue
      fi
      rm -rf "${agent_dir}"
      if ! ln -s "${canonical}" "${agent_dir}" 2>/dev/null; then
        copy_skill_tree "${canonical}" "${agent_dir}"
      fi
    done
  fi

  if [[ "${installed_any}" == true ]]; then
    log "  installed ${name}"
  fi
}

# Prints (via the root_skill_matches global) how many skills this root
# contributed. A zero-match root is not fatal on its own: --skill filters may
# legitimately target only one collection, so the caller decides when the
# combined total across collections is fatal.
root_skill_matches=0

install_from_root() {
  local root="$1"
  local skill_dir
  local count=0

  while IFS= read -r skill_dir; do
    [[ -n "${skill_dir}" ]] || continue
    local name
    name="$(skill_name_from_dir "${skill_dir}" --slugify)"
    skill_selected "${name}" || continue
    install_skill_dir "${skill_dir}"
    count=$((count + 1))
  done < <(discover_skill_dirs "${root}" | sort -u)

  root_skill_matches="${count}"
}

ask_prereqs() {
  if [[ "${with_prereqs}" == "yes" ]]; then
    return 0
  fi
  if [[ "${with_prereqs}" == "no" ]]; then
    return 1
  fi

  log 'Some skills in this collection need mattpocock/skills.'
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
  log 'Skills that depend on it will not work until it is installed.'
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

check_collisions_manifest() {
  local manifest="$1"
  sort -u "${manifest}" | awk -F'\t' '
    {
      name = $1
      dir = $2
      if (!(name in count)) {
        names[++num_names] = name
      }
      dirs[name] = dirs[name] ? dirs[name] "\n  " dir : dir
      count[name]++
    }
    END {
      has_collision = 0
      for (i = 1; i <= num_names; i++) {
        n = names[i]
        if (count[n] > 1) {
          has_collision = 1
          printf "normalized skill name '\''%s'\'' collides across multiple source directories:\n  %s\n", n, dirs[n]
        }
      }
      if (has_collision) exit 1
    }
  '
}

validate_skill_collisions() {
  local root skill_dir name real_dir
  local manifest
  manifest="$(mktemp "${TMPDIR:-/tmp}/skills-collision-manifest.XXXXXX")"
  cleanup_paths+=("${manifest}")

  for root in "$@"; do
    [[ -n "${root}" ]] || continue
    while IFS= read -r skill_dir; do
      [[ -n "${skill_dir}" ]] || continue
      name="$(skill_name_from_dir "${skill_dir}" --slugify)"
      skill_selected "${name}" || continue
      real_dir="$(cd -P "${skill_dir}" 2>/dev/null && pwd -P || printf '%s' "${skill_dir}")"
      printf '%s\t%s\n' "${name}" "${real_dir}" >>"${manifest}"
    done < <(discover_skill_dirs "${root}" | sort -u)
  done

  if [[ ! -s "${manifest}" ]]; then
    return 0
  fi

  local collision_err
  if ! collision_err="$(check_collisions_manifest "${manifest}")"; then
    die "error: ${collision_err}"
  fi
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

  installed_skills_registry="$(mktemp "${TMPDIR:-/tmp}/skills-installed-reg.XXXXXX")"
  cleanup_paths+=("${installed_skills_registry}")

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
  local total_matches=0
  jon_root="$(resolve_jonbaldie_root)"
  load_skill_tree_module "${jon_root}"

  local mp_root=""
  if ask_prereqs; then
    mp_root="$(resolve_mattpocock_root)"
  fi

  local -a roots_to_install=()
  if [[ -n "${mp_root}" ]]; then
    roots_to_install+=("${mp_root}")
  fi
  roots_to_install+=("${jon_root}")

  validate_skill_collisions "${roots_to_install[@]}"

  if [[ -n "${mp_root}" ]]; then
    log "Installing mattpocock/skills..."
    install_from_root "${mp_root}"
    total_matches=$((total_matches + root_skill_matches))
  fi

  log "Installing jonbaldie/skills..."
  install_from_root "${jon_root}"
  total_matches=$((total_matches + root_skill_matches))

  if [[ "${total_matches}" -eq 0 ]]; then
    if [[ ${#selected_skills[@]} -gt 0 ]]; then
      die "No matching skills found for: ${selected_skills[*]}"
    fi
    die "No skills found under ${jon_root}"
  fi

  if [[ "${global_install}" == true ]]; then
    log "Done. Skills installed under $(canonical_skills_dir) (and agent paths as needed)."
  else
    log "Done. Skills installed for this project."
  fi
}

main "$@"
