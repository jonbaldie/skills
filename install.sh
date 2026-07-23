#!/usr/bin/env bash

set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

printf '%s\n' \
  '$ship-spec and other skills in this collection will not work without mattpocock/skills.'
printf 'Install mattpocock/skills now? [y/N] '
IFS= read -r install_prerequisites || install_prerequisites=

case "${install_prerequisites}" in
  y | Y | yes | YES)
    npx --yes skills@latest add mattpocock/skills \
      --skill '*' \
      "$@"
    ;;
  *)
    printf '%s\n' \
      'Continuing without mattpocock/skills.' \
      '$ship-spec and other dependent skills will not work until it is installed.'
    ;;
esac

npx --yes skills@latest add "${repository_root}" \
  --skill '*' \
  "$@"
