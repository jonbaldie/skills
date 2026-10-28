#!/usr/bin/env bash

read_newline_terminated_manifest_record() {
  IFS= read -r "$1"
}

read_managed_names() {
  local input_manifest="$1" mode="$2" name
  case "${mode}" in --skip|--strict) ;; *) return 2 ;; esac
  while read_newline_terminated_manifest_record name; do
    [[ -n "${name}" && "${name}" != \#* ]] || continue
    if ! skill_name_is_valid "${name}"; then
      if [[ "${mode}" == --strict ]]; then
        printf 'error: unsafe skill name in manifest: %s\n' "${name}" >&2
        return 1
      fi
      continue
    fi
    printf '%s\n' "${name}" || return 1
  done <"${input_manifest}"
}

retire_absent() {
  local retirement_dir="$1" old_manifest="$2" kept_file="$3" callback="${4:-}"
  local kept old name candidate found
  local -a kept_names=()

  [[ -f "${old_manifest}" ]] || return 0
  kept="$(read_managed_names "${kept_file}" --strict)" || return 1
  old="$(read_managed_names "${old_manifest}" --skip)" || return 1
  while IFS= read -r name; do
    [[ -n "${name}" ]] && kept_names+=("${name}")
  done <<<"${kept}"
  while IFS= read -r name; do
    [[ -n "${name}" ]] || continue
    found=false
    for candidate in "${kept_names[@]}"; do
      if [[ "${candidate}" == "${name}" ]]; then found=true; break; fi
    done
    if [[ "${found}" == false ]]; then
      rm -rf -- "${retirement_dir:?}/${name}" || return 1
      if [[ -n "${callback}" ]]; then "${callback}" "${name}" || return 1; fi
    fi
  done <<<"${old}"
}

publish_file() {
  local destination="$1" source="$2" temporary_path="$3"
  cp "${source}" "${temporary_path}" || return 1
  mv "${temporary_path}" "${destination}"
}
