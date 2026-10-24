# Exploratory pass: standalone resume skills and workspace identity

2026-10-24. Baseline `fe61c415b65782f1fbbdf0ae2bef90b09b7361a7`, fetched
`origin/main` before testing. macOS 26.6.2, Bash 3.2.57, Python 3.14.5.
Three confirmed bugs: [#214](https://github.com/jonbaldie/skills/issues/214),
[#215](https://github.com/jonbaldie/skills/issues/215),
[#216](https://github.com/jonbaldie/skills/issues/216). No product fixes.

## Setup and replay

The supported interfaces exercised were `install.sh` and the installed session
extractor CLIs. Each journey ran twice in separate clean homes/projects under
`.fleet/exploratory-2026-10-24/fixtures`. Session data was **synthetic**, using
Pi version-3 JSONL and Codex rollout records; no live agent sessions, provider
credentials, LLM calls, or TUIs were used. Conclusions concern extraction, not
the later agent's implementation of the interrupted task.

The selective install is documented by `install.sh --help`; the router skill
promises cross-agent discovery and an explicit-path escape hatch without
requiring sibling resume skills. Pi's skill promises the latest session for the
requested cwd. These are the expectations used below.

[Replay driver](evidence/2026-10-24/replay.py),
[run log](evidence/2026-10-24/run.log),
[observations](evidence/2026-10-24/observations.json),
[setup and harness diagnostics](evidence/2026-10-24/setup.log).
From the repository root:

```sh
python3 docs/exploratory-testing/evidence/2026-10-24/replay.py
```

The driver refuses an existing fixture directory. Remove only the run-owned
`.fleet/exploratory-2026-10-24/fixtures` before replaying; logs are overwritten.
Every command log records cwd, isolated HOME, arguments, stdout, stderr, and
exit status. Fixtures and mtime ordering are deterministic. No project lockfile
exists and no dependencies were installed; existing standard-library Python,
Bash, and pytest were sufficient. Mutable outputs stayed in this workspace;
temporary installer manifests used the supplied TMPDIR. Installed symlinks
resolved within the fixture project, never into another checkout.

## 1. Install one router skill and resume Codex work

Goal: after `install.sh --agent pi --without-prereqs --skill resume-from-agent`,
resume the project's Codex session with its real UUID, goal, turns, and
interrupted ending. The install succeeded twice; canonical script bytes matched
those visible through `.pi/skills`, and no Codex sibling was installed.

The fixture has `session_meta`, user/assistant `response_item` and `event_msg`
records, and `turn_aborted: interrupted`. Its goal is “Implement invoice
rounding and add boundary tests.”

**Confirmed [#214](https://github.com/jonbaldie/skills/issues/214):**
`<installed-router>/scripts/extract-session.py --cwd "$project" codex` exits 0
but omits all turns and the interruption reason. It prints the generic fallback
note and “no clear ending text.” The user cannot recover the task from that
brief. Both clean setups fail identically.

Variation/control: `--agent codex --path "$rollout"` reads the same file and
preserves the goal and interruption. Installing `resume-from-codex` next to the
router also makes ordinary discovery succeed. Discovery without a sibling uses
`_generic_jsonl_brief`, despite the router already having `_codex_rollout_brief`
for explicit paths.

[Failure 1](evidence/2026-10-24/codex-discovery-alone-1.log),
[failure 2](evidence/2026-10-24/codex-discovery-alone-2.log),
[path control](evidence/2026-10-24/codex-path-alone-1.log),
[sibling control](evidence/2026-10-24/codex-discovery-sibling-1.log).

## 2. Resume Pi work in neighboring project paths

Goal: no-id discovery resumes only work from the requested workspace. Ordinary
control with one matching session succeeds. Variation: two existing projects,
`apps/web-api` and `apps-web/api`, map to the same Pi directory encoding. Each
JSONL header truthfully records its own cwd; the unrelated session is newer.

**Confirmed [#215](https://github.com/jonbaldie/skills/issues/215):** both
`resume-from-pi --cwd "$base/apps/web-api"` and the standalone router's
`--cwd "$base/apps/web-api" pi` select the other project's UUID and goal,
“Migrate the OTHER project database.” Both exit 0. The standalone extractor
prints the actual, wrong cwd; the router's fallback instead prints the requested
cwd, hiding the mismatch that its grounding instructions tell the user to check.
The router's `--list` includes both sessions under the requested cwd.

Impact: a continuation can receive another project's instructions, with a false
workspace label in the router case. No migration or other goal was executed.
Directory membership is trusted without checking transcript header cwd.

Repeated in two clean setups. Pinning the correct partial UUID works; removing
only the unrelated session restores correct no-id selection. An unknown UUID
exits 1 with a clear error, not an invented session.

[Standalone failure](evidence/2026-10-24/pi-cwd-collision-1.log),
[router failure](evidence/2026-10-24/router-pi-cwd-collision-1.log),
[repeat](evidence/2026-10-24/router-pi-cwd-collision-2.log),
[list](evidence/2026-10-24/router-pi-list-1.log),
[pinned control](evidence/2026-10-24/pi-pinned-control-1.log),
[ordinary control](evidence/2026-10-24/pi-no-collision-control-1.log).

## 3. Resume from an explicit Pi transcript path

Goal: the documented `--agent pi --path "$jsonl"` escape hatch preserves the
transcript's UUID, cwd, and goal independently of sibling installations.
The path is readable, recognized as Pi, and contains a valid session header.

**Confirmed [#216](https://github.com/jonbaldie/skills/issues/216):** with only
the router installed, exit 0 preserves the goal but reports the entire
`2026-10-24T00-00-00_<uuid>` filename stem as `session_id` and omits `cwd`.
That loses both session identity and the workspace mismatch safety check.
Installing `resume-from-pi` next to the router restores the exact header UUID
and cwd on the same input. Both failures and controls repeat in the second
clean setup. A missing path exits 1 with a concrete error; correcting it returns
the brief, so the failure is not an invalid-path problem.

[Failure 1](evidence/2026-10-24/pi-explicit-path-1.log),
[failure 2](evidence/2026-10-24/pi-explicit-path-2.log),
[sibling control](evidence/2026-10-24/pi-explicit-path-sibling-1.log),
[missing path](evidence/2026-10-24/pi-missing-path-1.log).

## Other candidates, limitations, and usability

- **Unresolved format coverage:** the initial Codex probe had only `event_msg`
  turns, without `response_item` duplicates. Native explicit-path parsing also
  omitted its goal, while a sibling read it. This reduced fixture was not
  established as an ordinary current CLI recording, so no separate bug was
  filed on it. The final replay includes both record forms and still confirms
  #214. Initial diagnostics remain under
  [initial-probe](evidence/2026-10-24/initial-probe/run.log); its original mtimes
  were arbitrary future dates, corrected to the run date in the final replay.
- **Rejected setup candidates:** missing UUID/path errors are expected, useful
  failures. The edit ambiguity and GitHub legacy protection 404 were harness
  observations, not product bugs; see setup diagnostics.
- Observed usability: selectively installing a sibling silently changes both
  parsing completeness and metadata fidelity. A suggested improvement is to
  make any unsupported fallback explicit rather than returning a plausible
  incomplete brief as success. This is a suggestion, not another finding.
- Not explored: actual interrupted LLM execution, branch navigation/compaction,
  custom Pi state roots, other session adapters, PR-host extraction, global or
  one-line installs, prerequisite cloning, Windows/WSL, or filesystem faults.
  Synthetic data and local installs bound these claims; no exhaustive coverage
  or successful continuation is claimed. No selected journey was setup-blocked.

## Checks and cleanup

`RUN_ALL_SKIP=install-ship-spec.sh PYTHONDONTWRITEBYTECODE=1 tests/run-all.sh`:
**14 suites passed, 1 skipped, 0 failed; 197 Python tests passed**.
[Full check output](evidence/2026-10-24/tests.log). The deprecated Docker
ship-spec suite was explicitly outside scope. Green regression checks did not
cover these independently replayed failures.

All three confirmed findings were filed with `bug` and `needs-triage`, including
repeat observations and replay steps. Related architecture issues were checked
for duplicates; none describes these exact standalone/collision failures.

Run-owned installed skills, HOME stores, and fixture projects were removed.
Existing untracked `.claude/`, `.coverage`, and `.serena/` were left untouched.
**No Docker containers, images, or volumes were created by this run**, so none
needed removal; pre-existing resources were only inventoried and left alone.
[Cleanup record](evidence/2026-10-24/cleanup.log).
