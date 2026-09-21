#!/usr/bin/env bash

# Discover and run every test suite in this checkout.  Suites that need a host
# capability can be named in RUN_ALL_SKIP as a comma-separated list.  The
# installer ship-spec suite is also skipped automatically when Docker or
# sandbox-exec is unavailable.

set -uo pipefail

repository_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
tests_root="${repository_root}/tests"
runner_path="${tests_root}/$(basename -- "${BASH_SOURCE[0]}")"
python_command="${PYTHON:-python3}"

passed=0
skipped=0
failed=0

run_suite() {
  local name="$1"
  shift

  printf 'RUN: %s\n' "${name}"
  if "$@"; then
    printf 'PASS: %s\n' "${name}"
    passed=$((passed + 1))
  else
    local status=$?
    printf 'FAIL: %s (exit %d)\n' "${name}" "${status}" >&2
    failed=$((failed + 1))
  fi
}

skip_suite() {
  local name="$1"
  local reason="$2"

  printf 'SKIP: %s (%s)\n' "${name}" "${reason}" >&2
  skipped=$((skipped + 1))
}

is_requested_skip() {
  local name="$1"
  local basename="${name##*/}"
  local requested_skips="${RUN_ALL_SKIP:-}"

  case ",${requested_skips}," in
    *,"${name}",*|*,"${basename}",*) return 0 ;;
    *) return 1 ;;
  esac
}

special_suite_skip_reason() {
  local -a missing=()

  command -v sandbox-exec >/dev/null 2>&1 || missing+=(sandbox-exec)
  if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
    missing+=(Docker)
  fi

  if ((${#missing[@]} > 0)); then
    local joined="${missing[*]}"
    printf 'requires %s' "${joined}"
    return 0
  fi

  return 1
}

cd -- "${repository_root}" || exit 1

while IFS= read -r suite; do
  [[ "${suite}" == "${runner_path}" ]] && continue

  suite_name="${suite#"${repository_root}"/}"
  if is_requested_skip "${suite_name}"; then
    skip_suite "${suite_name}" 'RUN_ALL_SKIP requested'
    continue
  fi

  if [[ "${suite}" == "${tests_root}/install-ship-spec.sh" ]]; then
    if reason="$(special_suite_skip_reason)"; then
      skip_suite "${suite_name}" "${reason}"
      continue
    fi
  fi

  run_suite "${suite_name}" bash "${suite}"
done < <(find "${tests_root}" -type f -name '*.sh' -print | sort)

if is_requested_skip 'pytest'; then
  skip_suite 'pytest tests' 'RUN_ALL_SKIP requested'
elif ! command -v "${python_command}" >/dev/null 2>&1; then
  printf 'FAIL: pytest tests (command not found: %s)\n' "${python_command}" >&2
  failed=$((failed + 1))
else
  run_suite 'pytest tests' "${python_command}" -m pytest tests
fi

printf '\nTest suites: %d passed, %d skipped, %d failed\n' \
  "${passed}" "${skipped}" "${failed}"

if ((failed > 0)); then
  exit 1
fi
