#!/usr/bin/env bash

set -euo pipefail

usage() {
  printf 'Usage: %s <project-directory> (<skill-directory> | --agent <name>)...\n' "$(basename "$0")" >&2
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

[[ $# -ge 2 ]] || {
  usage
  exit 2
}

for command_name in mkdir rm cp grep mv find dirname mktemp; do
  command -v "${command_name}" >/dev/null 2>&1 || die "missing required command: ${command_name}"
done

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/lib/skill-tree.sh"
# shellcheck source=skills/sync-jonbaldie-skills/scripts/lib/managed-manifest.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib/managed-manifest.sh"
# shellcheck source=skills/sync-jonbaldie-skills/scripts/lib/agent-destinations.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib/agent-destinations.sh"

[[ -d "$1" ]] || die "project directory does not exist: $1"
project_root="$(cd "$1" && pwd -P)"
readonly project_root
canonical_skills_dir="$(canonical_skills_dir "${project_root}")"
canonical_manifest="$(dirname "${canonical_skills_dir}")/sync-jonbaldie-skills.manifest"
readonly canonical_manifest
shift

[[ -d "${canonical_skills_dir}" ]] || die "canonical skills directory is missing; run sync-skills.sh first"
[[ -f "${canonical_manifest}" ]] || die "managed-skill manifest is missing; run sync-skills.sh first"
canonical_skills_dir="$(cd "${canonical_skills_dir}" && pwd -P)"
readonly canonical_skills_dir

requested_path() {
  if [[ "$1" = /* ]]; then
    printf '%s\n' "$1"
  else
    printf '%s\n' "${project_root}/$1"
  fi
}

# Resolve existing directories physically, but model missing components without
# creating them. Resolve each component before processing '..': collapsing the
# whole path lexically would give the wrong parent for a directory symlink.
resolve_requested_directory() {
  local remaining component candidate
  local resolved=/

  remaining="$(requested_path "$1")"
  while [[ -n "${remaining}" ]]; do
    component="${remaining%%/*}"
    if [[ "${remaining}" == */* ]]; then
      remaining="${remaining#*/}"
    else
      remaining=
    fi
    case "${component}" in
      ''|.) continue ;;
      ..) resolved="${resolved%/*}"; resolved="${resolved:-/}" ;;
      *)
        candidate="${resolved%/}/${component}"
        if [[ -d "${candidate}" ]]; then
          resolved="$(cd "${candidate}" && pwd -P)" ||
            die "cannot resolve skill directory: $1"
        elif [[ -e "${candidate}" || -L "${candidate}" ]]; then
          die "not a directory in skill directory: $1"
        else
          resolved="${candidate}"
        fi
        ;;
    esac
  done
  printf '%s\n' "${resolved}"
}

reject_project_ancestor() {
  local resolved="$1"
  local requested_directory="$2"

  if [[ "${project_root}" == "${resolved}" || "${project_root}" == "${resolved%/}/"* ]]; then
    die "skill directory must not be the project root or one of its ancestors: ${requested_directory}"
  fi
}

validate_requested_directory() {
  local requested_directory="$1"
  local resolved

  [[ -n "${requested_directory}" ]] || die "skill directory must not be empty"
  resolved="$(resolve_requested_directory "${requested_directory}")" || exit 1
  reject_project_ancestor "${resolved}" "${requested_directory}"
}

temporary_root=""
cleanup() {
  if [[ -n "${temporary_root}" ]]; then rm -rf "${temporary_root}"; fi
}
trap cleanup EXIT

prepare_manifest() {
  [[ -z "${temporary_root}" ]] || return 0
  temporary_root="$(mktemp -d "${TMPDIR:-/tmp}/copy-managed-skills.XXXXXX")" || return 1
  cp "${canonical_manifest}" "${temporary_root}/manifest" || return 1
  read_managed_names "${temporary_root}/manifest" --strict >"${temporary_root}/names" || return 1
}

copy_to_directory() {
  local requested_directory="$1"
  local destination
  local destination_manifest
  local name

  destination="$(resolve_requested_directory "${requested_directory}")" || return 1
  reject_project_ancestor "${destination}" "${requested_directory}"

  if [[ "${destination}" == "${canonical_skills_dir}" ]]; then
    printf 'Already canonical: %s\n' "${destination}"
    return
  fi

  prepare_manifest || return 1
  mkdir -p "${destination}"
  destination="$(cd "${destination}" && pwd -P)"
  reject_project_ancestor "${destination}" "${requested_directory}"
  destination_manifest="${destination}/.sync-jonbaldie-skills.manifest"
  retire_absent "${destination}" "${destination_manifest}" "${temporary_root}/names" || return 1

  while IFS= read -r name; do
    [[ -d "${canonical_skills_dir}/${name}" ]] || die "managed skill is missing: ${canonical_skills_dir}/${name}"
    copy_skill_tree "${canonical_skills_dir}/${name}" "${destination:?}/${name}"
    printf '  copied %s -> %s\n' "${name}" "${destination}"
  done <"${temporary_root}/names"

  publish_file "${destination_manifest}" "${temporary_root}/manifest" "${destination}/.sync-jonbaldie-skills.manifest.tmp" || return 1
  printf 'Additional destination: %s\n' "${destination}"
}

agent_directory() {
  local agent="$1"

  [[ -n "${agent}" ]] || die "--agent needs an agent name"
  agent_is_known "${agent}" ||
    die "unknown agent: ${agent} (supported: $(supported_agents_list))"
  agent_skills_dir "${agent}" project "${project_root}"
}

# Named agents resolve to their project destinations; every other argument is
# a skill directory, even when it is spelled like an agent name.
requested_directories=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)
      [[ $# -ge 2 ]] || die "--agent needs an agent name"
      requested_directories+=("$(agent_directory "$2")") || exit 1
      shift 2
      ;;
    --agent=*)
      requested_directories+=("$(agent_directory "${1#*=}")") || exit 1
      shift
      ;;
    *)
      requested_directories+=("$1")
      shift
      ;;
  esac
done

for requested_directory in "${requested_directories[@]}"; do
  validate_requested_directory "${requested_directory}"
done

for requested_directory in "${requested_directories[@]}"; do
  copy_to_directory "${requested_directory}"
done
