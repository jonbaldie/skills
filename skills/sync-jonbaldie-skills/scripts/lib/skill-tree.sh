# shellcheck shell=bash

# What a skill tree is and how to copy one. Sourced by install.sh,
# sync-skills.sh and copy-to-skill-dirs.sh so discovery, naming and copying
# follow one set of rules. It lives inside the sync skill so installed copies
# of that skill can still source it.

# Build artifacts never shipped in a skill tree. Copies exclude them and
# discovery does not descend into them.
SKILL_TREE_EXCLUDES=(__pycache__ .pytest_cache '*.pyc')

# Directories discovery does not descend into, in addition to
# SKILL_TREE_EXCLUDES: dependencies and VCS data, unshipped collections, and
# agent install targets that may hold copies of already-discovered skills.
SKILL_TREE_DISCOVERY_EXCLUDES=(
  node_modules .git dist build
  in-progress deprecated
  .agents .claude .codex .pi .cursor .gemini
)

SKILL_TREE_MAX_DEPTH=6

# Prints one skill directory per line. Searches <root>/skills when it exists so
# a checkout that has been used as an install target does not re-discover
# destination copies.
discover_skill_dirs() {
  local root="$1"
  local search_root="${root}"
  local -a prune=()
  local pattern skill_md rel depth

  if [[ -d "${root}/skills" ]]; then
    search_root="${root}/skills"
  fi

  for pattern in "${SKILL_TREE_DISCOVERY_EXCLUDES[@]}" "${SKILL_TREE_EXCLUDES[@]}"; do
    prune+=(-o -name "${pattern}")
  done

  find "${search_root}" \( "${prune[@]:1}" \) -prune -o -type f -name SKILL.md -print 2>/dev/null |
    while IFS= read -r skill_md; do
      rel="${skill_md#"${search_root}"/}"
      depth="$(printf '%s' "${rel}" | awk -F/ '{print NF-1}')"
      if [[ "${depth}" -le "${SKILL_TREE_MAX_DEPTH}" ]]; then
        dirname "${skill_md}"
      fi
    done
}

# Succeeds when <name> is safe to use as a skill directory and manifest entry.
skill_name_is_valid() {
  [[ "$1" =~ ^[a-z0-9][a-z0-9._-]*$ ]]
}

# Prints the normalized skill name from <dir>/SKILL.md frontmatter, falling
# back to the directory name. The policy decides what happens when the
# normalized name is still unsafe: --slugify prints it anyway, --strict reports
# it on stderr and fails.
skill_name_from_dir() {
  local skill_dir="$1"
  local policy="${2:-}"
  local skill_md="${skill_dir}/SKILL.md"
  local name=""

  case "${policy}" in
    --slugify | --strict) ;;
    *)
      printf 'skill_name_from_dir: expected --slugify or --strict, got %s\n' "${policy:-nothing}" >&2
      return 2
      ;;
  esac

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

  if [[ "${policy}" == --strict ]] && ! skill_name_is_valid "${name}"; then
    printf "error: unsafe skill name '%s' in %s\n" "${name}" "${skill_md}" >&2
    return 1
  fi
  printf '%s\n' "${name}"
}

# Removes everything matching SKILL_TREE_EXCLUDES below <target>.
prune_build_artifacts() {
  local target="$1"
  local -a matches=()
  local pattern

  for pattern in "${SKILL_TREE_EXCLUDES[@]}"; do
    matches+=(-o -name "${pattern}")
  done
  find "${target}" -mindepth 1 \( "${matches[@]:1}" \) -prune -exec rm -rf {} +
}

# Replaces <dst> with a copy of <src> without SKILL_TREE_EXCLUDES.
copy_skill_tree() {
  local src="$1"
  local dest="$2"
  local -a rsync_excludes=()
  local pattern

  rm -rf "${dest}"
  mkdir -p "$(dirname "${dest}")"

  if command -v rsync >/dev/null 2>&1; then
    for pattern in "${SKILL_TREE_EXCLUDES[@]}"; do
      rsync_excludes+=("--exclude=${pattern}")
    done
    mkdir -p "${dest}"
    rsync -a --delete "${rsync_excludes[@]}" "${src}/" "${dest}/"
    return
  fi

  if ! cp -a "${src}" "${dest}" 2>/dev/null; then
    rm -rf "${dest}"
    cp -R "${src}" "${dest}"
  fi
  prune_build_artifacts "${dest}"
}
