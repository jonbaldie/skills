#!/usr/bin/env bash

# Source checkouts may contain untracked __pycache__ and *.pyc files created
# when running Python scripts. Installers must exclude these build artifacts
# from installed skill trees in both symlink and copy modes, with and without rsync.

set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly repository_root
readonly sync_script="${repository_root}/skills/sync-jonbaldie-skills/scripts/sync-skills.sh"
readonly copy_script="${repository_root}/skills/sync-jonbaldie-skills/scripts/copy-to-skill-dirs.sh"
test_root="$(mktemp -d "${TMPDIR:-/tmp}/skills-pycache-test.XXXXXX")"
readonly test_root

cleanup() {
  rm -rf "${test_root}"
}
trap cleanup EXIT

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

# Construct fixture repository mimicking a source checkout with python caches
readonly fixture_repo="${test_root}/fixture-repo"
mkdir -p "${fixture_repo}/skills/fixture-pycache/scripts/__pycache__"
mkdir -p "${fixture_repo}/skills/fixture-pycache/scripts/.pytest_cache"
ln -s "${repository_root}/install.sh" "${fixture_repo}/install.sh"

cat >"${fixture_repo}/skills/fixture-pycache/SKILL.md" <<'EOF'
---
name: fixture-pycache
description: Fixture skill with python caches.
---

Fixture skill.
EOF

cat >"${fixture_repo}/skills/fixture-pycache/scripts/tool.py" <<'EOF'
print("hello world")
EOF

cat >"${fixture_repo}/skills/fixture-pycache/scripts/helper.sh" <<'EOF'
#!/usr/bin/env bash
echo "helper"
EOF
chmod +x "${fixture_repo}/skills/fixture-pycache/scripts/helper.sh"

cat >"${fixture_repo}/skills/fixture-pycache/scripts/__pycache__/tool.cpython-312.pyc" <<'EOF'
<fake-pyc-bytecode>
EOF

cat >"${fixture_repo}/skills/fixture-pycache/scripts/.pytest_cache/dummy" <<'EOF'
<fake-pytest-cache>
EOF

cat >"${fixture_repo}/skills/fixture-pycache/stray.pyc" <<'EOF'
<stray-pyc>
EOF

cat >"${fixture_repo}/skills/fixture-pycache/notes.txt" <<'EOF'
fixture note
EOF

assert_clean_installation() {
  local target_dir="$1"
  local mode_desc="$2"
  local relative_skill_dir="${3:-.agents/skills/fixture-pycache}"

  local skill_installed="${target_dir}/${relative_skill_dir}"
  [[ -f "${skill_installed}/SKILL.md" ]] ||
    fail "Skill not installed (${mode_desc})"
  [[ -f "${skill_installed}/scripts/tool.py" ]] ||
    fail "tool.py not installed (${mode_desc})"
  [[ -f "${skill_installed}/scripts/helper.sh" ]] ||
    fail "helper.sh not installed (${mode_desc})"
  [[ -f "${skill_installed}/notes.txt" ]] ||
    fail "notes.txt not installed (${mode_desc})"

  # Assert content matches byte-for-byte for preserved files
  cmp -s "${fixture_repo}/skills/fixture-pycache/SKILL.md" "${skill_installed}/SKILL.md" ||
    fail "SKILL.md content mismatch (${mode_desc})"
  cmp -s "${fixture_repo}/skills/fixture-pycache/scripts/tool.py" "${skill_installed}/scripts/tool.py" ||
    fail "tool.py content mismatch (${mode_desc})"
  cmp -s "${fixture_repo}/skills/fixture-pycache/scripts/helper.sh" "${skill_installed}/scripts/helper.sh" ||
    fail "helper.sh content mismatch (${mode_desc})"
  cmp -s "${fixture_repo}/skills/fixture-pycache/notes.txt" "${skill_installed}/notes.txt" ||
    fail "notes.txt content mismatch (${mode_desc})"

  # Assert no __pycache__ directory exists
  local pycache_dirs
  pycache_dirs="$(find "${target_dir}" -type d -name "__pycache__")"
  if [[ -n "${pycache_dirs}" ]]; then
    fail "Found __pycache__ directory in ${target_dir} (${mode_desc}): ${pycache_dirs}"
  fi

  # Assert no .pytest_cache directory exists
  local pytest_dirs
  pytest_dirs="$(find "${target_dir}" -type d -name ".pytest_cache")"
  if [[ -n "${pytest_dirs}" ]]; then
    fail "Found .pytest_cache directory in ${target_dir} (${mode_desc}): ${pytest_dirs}"
  fi

  # Assert no *.pyc file exists
  local pyc_files
  pyc_files="$(find "${target_dir}" -type f -name "*.pyc")"
  if [[ -n "${pyc_files}" ]]; then
    fail "Found *.pyc file in ${target_dir} (${mode_desc}): ${pyc_files}"
  fi
}

# Test 1: Symlink mode (materializes at .agents/skills)
project_symlink="${test_root}/project-symlink"
mkdir -p "${project_symlink}"
(
  cd "${project_symlink}"
  "${fixture_repo}/install.sh" --project --agent universal --without-prereqs --yes
) >"${test_root}/install-symlink.log" 2>&1 || {
  cat "${test_root}/install-symlink.log" >&2
  fail "install.sh failed in symlink mode"
}
assert_clean_installation "${project_symlink}" "symlink mode"

# Test 2: Copy mode
project_copy="${test_root}/project-copy"
mkdir -p "${project_copy}"
(
  cd "${project_copy}"
  "${fixture_repo}/install.sh" --project --agent universal --without-prereqs --yes --copy
) >"${test_root}/install-copy.log" 2>&1 || {
  cat "${test_root}/install-copy.log" >&2
  fail "install.sh failed in copy mode"
}
assert_clean_installation "${project_copy}" "copy mode"

# Test 3: Fallback path without rsync
fake_bin="${test_root}/fake-bin"
mkdir -p "${fake_bin}"
# Put a non-rsync path in front: symlink all essential commands except rsync
for cmd in bash git find awk dirname basename mkdir rm cp sort mktemp ln sed tr uname cut cat cmp; do
  cmd_path="$(command -v "${cmd}" || true)"
  if [[ -n "${cmd_path}" ]]; then
    ln -s "${cmd_path}" "${fake_bin}/${cmd}"
  fi
done

project_no_rsync="${test_root}/project-no-rsync"
mkdir -p "${project_no_rsync}"
(
  cd "${project_no_rsync}"
  PATH="${fake_bin}" "${fixture_repo}/install.sh" --project --agent universal --without-prereqs --yes --copy
) >"${test_root}/install-no-rsync.log" 2>&1 || {
  cat "${test_root}/install-no-rsync.log" >&2
  fail "install.sh failed in fallback (no rsync) mode"
}
assert_clean_installation "${project_no_rsync}" "fallback cp mode"

# Test 4: Defense-in-depth in sync-skills.sh
readonly sync_project="${test_root}/sync-project"
mkdir -p "${sync_project}"
git -C "${fixture_repo}" init --quiet
git -C "${fixture_repo}" add .
git -C "${fixture_repo}" -c user.name=Fixture -c user.email=fixture@example.com commit --quiet -m fixture

# Also create empty prerequisite repo for sync-skills
readonly empty_prereq="${test_root}/empty-prereq"
git init --quiet "${empty_prereq}"
mkdir -p "${empty_prereq}/skills/prereq-dummy"
cat >"${empty_prereq}/skills/prereq-dummy/SKILL.md" <<'EOF'
---
name: prereq-dummy
description: Dummy prereq.
---
EOF
git -C "${empty_prereq}" add .
git -C "${empty_prereq}" -c user.name=Fixture -c user.email=fixture@example.com commit --quiet -m fixture

MATTPOCOCK_SKILLS_REPO="${empty_prereq}" \
JONBALDIE_SKILLS_REPO="${fixture_repo}" \
  "${sync_script}" "${sync_project}" >"${test_root}/sync.log" 2>&1 || {
  cat "${test_root}/sync.log" >&2
  fail "sync-skills.sh exited non-zero"
}
assert_clean_installation "${sync_project}" "sync-skills.sh"

# Test 5: Defense-in-depth in copy-to-skill-dirs.sh
# Re-introduce python caches into the canonical skills directory to simulate post-sync execution
mkdir -p "${sync_project}/.agents/skills/fixture-pycache/scripts/__pycache__"
mkdir -p "${sync_project}/.agents/skills/fixture-pycache/scripts/.pytest_cache"
cat >"${sync_project}/.agents/skills/fixture-pycache/scripts/__pycache__/tool.cpython-312.pyc" <<'EOF'
<fake-pyc-bytecode>
EOF
cat >"${sync_project}/.agents/skills/fixture-pycache/scripts/.pytest_cache/dummy" <<'EOF'
<fake-pytest-cache>
EOF
cat >"${sync_project}/.agents/skills/fixture-pycache/stray.pyc" <<'EOF'
<stray-pyc>
EOF

"${copy_script}" "${sync_project}" .claude/skills >"${test_root}/copy.log" 2>&1 || {
  cat "${test_root}/copy.log" >&2
  fail "copy-to-skill-dirs.sh exited non-zero"
}
assert_clean_installation "${sync_project}/.claude/skills" "copy-to-skill-dirs.sh" "fixture-pycache"

printf '%s\n' 'install-pycache-exclusion: all scenarios passed'
