#!/usr/bin/env bash

# The optional mattpocock/skills prerequisite prompt is [y/N]: an unanswered
# prompt must skip the prerequisite. Explicit --with-prereqs/--without-prereqs
# choices and real terminal answers must keep their meaning.

set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly repository_root
readonly skill_tree_module="${repository_root}/skills/sync-jonbaldie-skills/scripts/lib/skill-tree.sh"
python_command="${PYTHON:-python3}"
test_root="$(mktemp -d "${TMPDIR:-/tmp}/skills-prereq-prompt.XXXXXX")"
readonly test_root

cleanup() {
  rm -rf "${test_root}"
}
trap cleanup EXIT

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

make_fixture_repo() {
  local repo_dir="$1"
  local name="$2"

  mkdir -p "${repo_dir}/skills/${name}"
  printf -- '---\nname: %s\ndescription: Fixture skill.\n---\nFixture.\n' "${name}" \
    >"${repo_dir}/skills/${name}/SKILL.md"
  git -C "${repo_dir}" init --quiet
}

commit_repo() {
  local repo_dir="$1"
  git -C "${repo_dir}" add .
  git -C "${repo_dir}" -c user.name=Fixture -c user.email=fixture@example.com commit --quiet -m fixture
}

# A piped installer clones jonbaldie/skills and sources its skill-tree module.
jon_repo="${test_root}/jon-repo"
make_fixture_repo "${jon_repo}" fixture-jon
mkdir -p "${jon_repo}/skills/sync-jonbaldie-skills/scripts/lib"
cp "${skill_tree_module}" "${jon_repo}/skills/sync-jonbaldie-skills/scripts/lib/skill-tree.sh"
commit_repo "${jon_repo}"

mp_repo="${test_root}/mp-repo"
make_fixture_repo "${mp_repo}" fixture-mp
commit_repo "${mp_repo}"

# Stream install.sh to Bash the way the one-line install does, in a new session
# with no controlling terminal, so /dev/tty cannot be opened.
piped_install_without_tty() {
  local home="$1"
  shift
  mkdir -p "${home}"
  HOME="${home}" \
    JONBALDIE_SKILLS_REPO="file://${jon_repo}" \
    MATTPOCOCK_SKILLS_REPO="file://${mp_repo}" \
    "${python_command}" -c 'import os, sys; os.setsid(); os.execvp(sys.argv[1], sys.argv[1:])' \
    bash -c 'bash -s -- --agent universal "$@" <"$0"' "${repository_root}/install.sh" "$@"
}

# Run a piped install with a real terminal as /dev/tty and type an answer.
piped_install_with_tty_answer() {
  local home="$1"
  local answer="$2"
  mkdir -p "${home}"
  HOME="${home}" \
    JONBALDIE_SKILLS_REPO="file://${jon_repo}" \
    MATTPOCOCK_SKILLS_REPO="file://${mp_repo}" \
    "${python_command}" - "${repository_root}/install.sh" "${answer}" <<'PY'
import os, pty, sys

installer, answer = sys.argv[1], sys.argv[2]
pid, master = pty.fork()
if pid == 0:
    os.execvp("bash", ["bash", "-c",
        'bash -s -- --agent universal <"$0"', installer])

output = b""
answered = False
while True:
    try:
        chunk = os.read(master, 1024)
    except OSError:
        break
    if not chunk:
        break
    output += chunk
    if not answered and b"[y/N]" in output:
        os.write(master, answer.encode() + b"\n")
        answered = True
_, status = os.waitpid(pid, 0)
sys.stdout.write(output.decode(errors="replace"))
sys.exit(os.waitstatus_to_exitcode(status))
PY
}

installed() {
  local home="$1"
  local name="$2"
  test -f "${home}/.agents/skills/${name}/SKILL.md"
}

# --- Piped install with no usable terminal skips the prerequisite ---
home="${test_root}/no-tty"
piped_install_without_tty "${home}" >"${test_root}/no-tty.log" 2>&1 </dev/null ||
  { cat "${test_root}/no-tty.log" >&2; fail 'piped install without a terminal failed'; }
installed "${home}" fixture-jon ||
  { cat "${test_root}/no-tty.log" >&2; fail 'piped install without a terminal skipped the collection'; }
if installed "${home}" fixture-mp; then
  cat "${test_root}/no-tty.log" >&2
  fail 'piped install without a terminal installed mattpocock/skills'
fi

# --- Explicit choices apply without prompting ---
home="${test_root}/with-prereqs"
piped_install_without_tty "${home}" --with-prereqs >"${test_root}/with.log" 2>&1 </dev/null ||
  { cat "${test_root}/with.log" >&2; fail '--with-prereqs install failed'; }
installed "${home}" fixture-mp || fail '--with-prereqs did not install mattpocock/skills'
installed "${home}" fixture-jon || fail '--with-prereqs skipped the collection'
if grep -q '\[y/N\]' "${test_root}/with.log"; then
  fail '--with-prereqs prompted'
fi

home="${test_root}/without-prereqs"
piped_install_without_tty "${home}" --without-prereqs >"${test_root}/without.log" 2>&1 </dev/null ||
  { cat "${test_root}/without.log" >&2; fail '--without-prereqs install failed'; }
if installed "${home}" fixture-mp; then
  fail '--without-prereqs installed mattpocock/skills'
fi
installed "${home}" fixture-jon || fail '--without-prereqs skipped the collection'
if grep -q '\[y/N\]' "${test_root}/without.log"; then
  fail '--without-prereqs prompted'
fi

# --- Piped install with a terminal honours the typed answer ---
home="${test_root}/tty-yes"
piped_install_with_tty_answer "${home}" y >"${test_root}/tty-yes.log" 2>&1 ||
  { cat "${test_root}/tty-yes.log" >&2; fail 'terminal Yes install failed'; }
installed "${home}" fixture-mp || { cat "${test_root}/tty-yes.log" >&2; fail 'terminal Yes did not install mattpocock/skills'; }

home="${test_root}/tty-no"
piped_install_with_tty_answer "${home}" n >"${test_root}/tty-no.log" 2>&1 ||
  { cat "${test_root}/tty-no.log" >&2; fail 'terminal No install failed'; }
if installed "${home}" fixture-mp; then
  cat "${test_root}/tty-no.log" >&2
  fail 'terminal No installed mattpocock/skills'
fi
installed "${home}" fixture-jon || fail 'terminal No skipped the collection'

# --- Direct invocation with closed stdin skips the prerequisite ---
project="${test_root}/direct-project"
mkdir -p "${project}"
(
  cd "${project}"
  MATTPOCOCK_SKILLS_REPO="file://${mp_repo}" \
    "${repository_root}/install.sh" --agent universal --skill bmf
) >"${test_root}/direct.log" 2>&1 <&- ||
  { cat "${test_root}/direct.log" >&2; fail 'direct install with closed stdin failed'; }
test -f "${project}/.agents/skills/bmf/SKILL.md" || fail 'direct install skipped the collection'
if [[ -e "${project}/.agents/skills/fixture-mp" ]]; then
  fail 'direct install with closed stdin installed mattpocock/skills'
fi

printf 'PASS: prerequisite prompt defaults to No without an answer\n'
