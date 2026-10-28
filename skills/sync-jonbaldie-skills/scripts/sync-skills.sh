#!/usr/bin/env bash

set -euo pipefail

readonly MATTPOCOCK_REPO_URL="${MATTPOCOCK_SKILLS_REPO:-https://github.com/mattpocock/skills.git}"
readonly JONBALDIE_REPO_URL="${JONBALDIE_SKILLS_REPO:-https://github.com/jonbaldie/skills.git}"

usage() {
  printf 'Usage: %s <project-directory>\n' "$(basename "$0")" >&2
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

[[ $# -eq 1 ]] || {
  usage
  exit 2
}

for command_name in git find awk dirname basename mkdir rm cp cat sort grep mktemp mv sed tr; do
  command -v "${command_name}" >/dev/null 2>&1 || die "missing required command: ${command_name}"
done

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/lib/skill-tree.sh"
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/lib/agent-destinations.sh"

[[ -d "$1" ]] || die "project directory does not exist: $1"
project_root="$(cd "$1" && pwd -P)"
readonly project_root
skills_dir="$(canonical_skills_dir "${project_root}")"
readonly skills_dir
agent_root="$(dirname "${skills_dir}")"
readonly agent_root
readonly manifest="${agent_root}/sync-jonbaldie-skills.manifest"
temporary_root="$(mktemp -d "${TMPDIR:-/tmp}/sync-jonbaldie-skills.XXXXXX")"
readonly temporary_root
readonly names_file="${temporary_root}/managed-names"
readonly sorted_names_file="${temporary_root}/managed-names.sorted"
readonly preflight_manifest="${temporary_root}/skills-preflight.tsv"
readonly mattpocock_sources="${temporary_root}/mattpocock-sources.tsv"
readonly jonbaldie_sources="${temporary_root}/jonbaldie-sources.tsv"

cleanup() {
  rm -rf "${temporary_root}"
}
trap cleanup EXIT

collect_collection_skills() {
  local repository_root="$1"
  local registry="$2"
  local skill_directory name

  : >"${registry}"
  while IFS= read -r skill_directory; do
    name="$(installed_skill_name "${skill_directory}")" || exit 1
    append_skill_source "${registry}" "${name}" "${skill_directory}"
  done < <(discover_skill_dirs "${repository_root}")
}

copy_skill() {
  local source_directory="$1"
  local name="$2"
  local destination="${skills_dir}/${name}"
  copy_skill_tree "${source_directory}" "${destination}"
  printf '%s\n' "${name}" >>"${names_file}"
  printf '  installed %s\n' "${name}"
}

install_collection() {
  local registry="$1"
  local repository_root="$2"
  local skill_directory name
  local count=0

  while IFS=$'\t' read -r name skill_directory; do
    copy_skill "${skill_directory}" "${name}"
    count=$((count + 1))
  done <"${registry}"

  [[ ${count} -gt 0 ]] || die "no skills found in ${repository_root}"
}

printf 'Fetching mattpocock/skills...\n'
GIT_TERMINAL_PROMPT=0 git clone --depth 1 --quiet "${MATTPOCOCK_REPO_URL}" "${temporary_root}/mattpocock"
printf 'Fetching jonbaldie/skills...\n'
GIT_TERMINAL_PROMPT=0 git clone --depth 1 --quiet "${JONBALDIE_REPO_URL}" "${temporary_root}/jonbaldie"

mattpocock_commit="$(git -C "${temporary_root}/mattpocock" rev-parse HEAD)"
readonly mattpocock_commit
jonbaldie_commit="$(git -C "${temporary_root}/jonbaldie" rev-parse HEAD)"
readonly jonbaldie_commit

collect_collection_skills "${temporary_root}/mattpocock" "${mattpocock_sources}"
collect_collection_skills "${temporary_root}/jonbaldie" "${jonbaldie_sources}"
cat "${mattpocock_sources}" "${jonbaldie_sources}" >"${preflight_manifest}"
collision_err="$(assert_unique_skill_sources "${preflight_manifest}")" || die "${collision_err}"

mkdir -p "${skills_dir}"
: >"${names_file}"

printf 'Installing mattpocock/skills...\n'
install_collection "${mattpocock_sources}" "${temporary_root}/mattpocock"
printf 'Installing jonbaldie/skills...\n'
install_collection "${jonbaldie_sources}" "${temporary_root}/jonbaldie"

sort -u "${names_file}" >"${sorted_names_file}"

if [[ -f "${manifest}" ]]; then
  while IFS= read -r old_name; do
    [[ -n "${old_name}" && "${old_name}" != \#* ]] || continue
    skill_name_is_valid "${old_name}" || continue
    if ! grep -Fqx "${old_name}" "${sorted_names_file}"; then
      rm -rf "${skills_dir:?}/${old_name}"
      printf '  removed retired skill %s\n' "${old_name}"
    fi
  done <"${manifest}"
fi

{
  printf '# mattpocock/skills %s\n' "${mattpocock_commit}"
  printf '# jonbaldie/skills %s\n' "${jonbaldie_commit}"
  while IFS= read -r managed_name; do
    printf '%s\n' "${managed_name}"
  done <"${sorted_names_file}"
} >"${temporary_root}/manifest"
cp "${temporary_root}/manifest" "${agent_root}/.sync-jonbaldie-skills.manifest.tmp"
mv "${agent_root}/.sync-jonbaldie-skills.manifest.tmp" "${manifest}"

printf 'mattpocock/skills commit: %s\n' "${mattpocock_commit}"
printf 'jonbaldie/skills commit: %s\n' "${jonbaldie_commit}"
printf 'Canonical destination: %s\n' "${skills_dir}"
