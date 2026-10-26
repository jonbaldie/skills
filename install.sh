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
declare -a source_registries=()
# Collection roots. Set by resolve_*_root rather than printed, so clones made
# there are registered in cleanup_paths of this shell, not a subshell's copy.
jon_root=""
mp_root=""

script_from_stdin=false
repository_root=""
explicit_scope="" # global | project | empty
show_help=false

# Needs the agent-destinations module loaded.
usage() {
  cat <<EOF
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
                          $(supported_agents_list)
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
        show_help=true
        return
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

install_scope() {
  if [[ "${global_install}" == true ]]; then
    printf '%s\n' global
  else
    printf '%s\n' project
  fi
}

# The directory an install writes below: home for global, cwd for project.
install_root() {
  if [[ "${global_install}" == true ]]; then
    agent_home_dir
  else
    pwd
  fi
}

install_canonical_dir() {
  canonical_skills_dir "$(install_root)"
}

install_agent_dir() {
  agent_skills_dir "$1" "$(install_scope)" "$(pwd)" || exit 1
}

clone_repo() {
  local url="$1"
  local dest="$2"
  GIT_TERMINAL_PROMPT=0 git clone --depth 1 --quiet "${url}" "${dest}"
}

resolve_jonbaldie_root() {
  if [[ -n "${repository_root}" && -d "${repository_root}/skills" ]]; then
    jon_root="${repository_root}"
    return
  fi

  require_command git
  local tmp
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/jonbaldie-skills.XXXXXX")"
  cleanup_paths+=("${tmp}")
  log_status "Cloning jonbaldie/skills..."
  clone_repo "${JONBALDIE_REPO_URL}" "${tmp}/repo"
  jon_root="${tmp}/repo"
}

resolve_mattpocock_root() {
  require_command git
  local tmp
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/mattpocock-skills.XXXXXX")"
  cleanup_paths+=("${tmp}")
  log_status "Cloning mattpocock/skills..."
  clone_repo "${MATTPOCOCK_REPO_URL}" "${tmp}/repo"
  mp_root="${tmp}/repo"
}

# The skill-tree module defines how skills are discovered, named and copied;
# the agent-destinations module defines which agents exist and where their
# skills go. A curl|bash run has no checkout until the collection is cloned,
# so both are sourced from the resolved collection root.
load_collection_modules() {
  local lib="$1/skills/sync-jonbaldie-skills/scripts/lib"
  local module

  for module in skill-tree agent-destinations; do
    [[ -f "${lib}/${module}.sh" ]] || die "Missing ${module} module: ${lib}/${module}.sh"
    # shellcheck source=/dev/null
    source "${lib}/${module}.sh"
  done
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
  local name="$2"
  local canonical agent_name agent_dir
  local installed_any=false

  canonical="$(install_canonical_dir)/${name}"

  if [[ "${copy_mode}" == true ]]; then
    for agent_name in "${selected_agents[@]}"; do
      agent_dir="$(install_agent_dir "${agent_name}")/${name}"
      copy_skill_tree "${skill_dir}" "${agent_dir}"
      installed_any=true
    done
  else
    # Symlink mode: materialize once at the canonical path, then link agents in.
    copy_skill_tree "${skill_dir}" "${canonical}"
    installed_any=true
    for agent_name in "${selected_agents[@]}"; do
      agent_dir="$(install_agent_dir "${agent_name}")/${name}"
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

# Prints (via the root_skill_matches global) how many skills this registry
# contributed. A zero-match root is not fatal on its own: --skill filters may
# legitimately target only one collection, so the caller decides when the
# combined total across collections is fatal.
root_skill_matches=0

install_from_registry() {
  local registry="$1"
  local skill_dir name
  local count=0

  while IFS=$'\t' read -r name skill_dir; do
    [[ -n "${name}" ]] || continue
    install_skill_dir "${skill_dir}" "${name}"
    count=$((count + 1))
  done <"${registry}"

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
      # Non-interactive one-liner with no usable tty: take the [y/N] default.
      answer=""
      printf '\n'
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

detect_agents() {
  local agent
  while IFS= read -r agent; do
    selected_agents+=("${agent}")
  done < <(detected_agents)
}

validate_agents() {
  local agent
  for agent in "${selected_agents[@]}"; do
    agent_is_known "${agent}" ||
      die "Unsupported agent: ${agent}
Supported: $(supported_agents_list)"
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

validate_skill_collisions() {
  local root skill_dir name registry
  local manifest
  manifest="$(mktemp "${TMPDIR:-/tmp}/skills-collision-manifest.XXXXXX")"
  cleanup_paths+=("${manifest}")

  for root in "$@"; do
    [[ -n "${root}" ]] || continue
    registry="$(mktemp "${TMPDIR:-/tmp}/skills-sources.XXXXXX")"
    cleanup_paths+=("${registry}")
    source_registries+=("${registry}")
    while IFS= read -r skill_dir; do
      [[ -n "${skill_dir}" ]] || continue
      name="$(skill_name_from_dir "${skill_dir}" --slugify)"
      skill_selected "${name}" || continue
      append_skill_source "${registry}" "${name}" "${skill_dir}"
    done < <(discover_skill_dirs "${root}" | sort -u)
    cat "${registry}" >>"${manifest}"
  done

  if [[ ! -s "${manifest}" ]]; then
    return 0
  fi

  local collision_err
  if ! collision_err="$(assert_unique_skill_sources "${manifest}")"; then
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
  require_command cat
  require_command sort
  require_command mktemp
  require_command ln
  require_command sed
  require_command tr

  # curl|bash one-liner defaults to a global install unless --project was set.
  if [[ "${script_from_stdin}" == true && -z "${explicit_scope}" ]]; then
    global_install=true
  fi

  local total_matches=0
  resolve_jonbaldie_root
  load_collection_modules "${jon_root}"

  if [[ "${show_help}" == true ]]; then
    usage
    return
  fi

  if [[ ${#selected_agents[@]} -eq 0 ]]; then
    detect_agents
  fi
  validate_agents
  print_install_targets

  if ask_prereqs; then
    resolve_mattpocock_root
  fi

  local -a roots_to_install=()
  if [[ -n "${mp_root}" ]]; then
    roots_to_install+=("${mp_root}")
  fi
  roots_to_install+=("${jon_root}")

  validate_skill_collisions "${roots_to_install[@]}"

  if [[ -n "${mp_root}" ]]; then
    log "Installing mattpocock/skills..."
    install_from_registry "${source_registries[0]}"
    total_matches=$((total_matches + root_skill_matches))
  fi

  log "Installing jonbaldie/skills..."
  install_from_registry "${source_registries[${#source_registries[@]}-1]}"
  total_matches=$((total_matches + root_skill_matches))

  if [[ "${total_matches}" -eq 0 ]]; then
    if [[ ${#selected_skills[@]} -gt 0 ]]; then
      die "No matching skills found for: ${selected_skills[*]}"
    fi
    die "No skills found under ${jon_root}"
  fi

  if [[ "${global_install}" == true ]]; then
    log "Done. Skills installed under $(install_canonical_dir) (and agent paths as needed)."
  else
    log "Done. Skills installed for this project."
  fi
}

main "$@"
