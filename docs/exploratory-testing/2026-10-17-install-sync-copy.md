# Exploratory pass: install, update, and custom copy destinations

2026-10-17. Checkout `d6cd38afe8cd9eac76c7727db65442505ae867de`, matching
`origin/main` at setup. macOS, Bash 3.2; standard-library Python drives public
shell commands. Confirmed bug: [#204](https://github.com/jonbaldie/skills/issues/204).
No product fixes are included.

## Setup and evidence

Isolated projects and `HOME` lived under `.fleet/exploratory-2026-10-17/` in
this workspace. Live agent installations were not touched. The documented
repository URL overrides pinned jonbaldie to this checkout and mattpocock to a
workspace-local clone at `49dd158d1076134a641b33efb035946536778336`.
Temporary clones used the supplied `TMPDIR` and were removed by the scripts.
No dependencies were installed: there is no project lockfile, the product uses
Bash, and the existing Python/pytest installation could run the checks.
No mutable dependencies or build outputs were written through checkout symlinks.

[Replay driver](evidence/2026-10-17/replay.py),
[setup](evidence/2026-10-17/setup.log), and
[regression checks](evidence/2026-10-17/tests.log).
Each command log records arguments, output, and exit status, including expected
failures. The reduced copy fixtures use the real `options/SKILL.md` and the
manifest format produced by sync; they are disclosed fixture data, not a
replacement implementation.

To replay from the repository root, clone `mattpocock/skills` to
`.fleet/exploratory-2026-10-17/sources/mattpocock`, check out the SHA above,
and run `python3 docs/exploratory-testing/evidence/2026-10-17/replay.py`.
The driver requires its isolated `projects` directory to be absent; remove only
that directory before repeating. Replay rewrites the evidence logs.

## Journeys and checkpoints

### 1. Install selected skills for Pi

Goal: requested skills exist canonically and Pi can read them through its agent
path. Ran `install.sh --agent pi --without-prereqs --skill options --skill
mutation-testing` in two clean projects. Both exited 0, installed exactly those
two skills, and `.pi/skills/options` resolved to the project's canonical copy.

Variation: repeat with `--skill options --skill not-a-real-skill`. Both exited 0,
installed `options`, and did not warn about the unknown requested name.
The prior `mutation-testing` remained; this is not a pruning command.
[First install](evidence/2026-10-17/install-1.log),
[second install](evidence/2026-10-17/install-2.log),
[mixed filter](evidence/2026-10-17/install-mixed-filter-1.log).

### 2. Install both collections, then update

Goal: sync reports both source SHAs, replaces managed content, and preserves
unrelated content. Initial sync and repeat both exited 0. A stale file added to
`options` disappeared after updating; an unrelated skill's sentinel remained.
The manifest and canonical files were inspected, not just the success message.

Variation: point the prerequisite repository override at a missing repository.
Sync exited 128 with Git's repository error; the previous manifest remained
byte-identical. This deliberate unavailable-source configuration is not a
product bug. [Initial sync](evidence/2026-10-17/sync-first.log),
[update and state checks](evidence/2026-10-17/sync-update.log),
[failed fetch](evidence/2026-10-17/sync-fetch-failure.log).

### 3. Copy managed skills to other agents and custom paths

Goal: canonical skills become usable real copies in the chosen destinations.
Copied to Claude Code and the relative directory `custom skills`, then repeated.
Both runs exited 0. `options` and `sync-jonbaldie-skills` matched the canonical
`SKILL.md` bytes in Claude's destination. An invalid named agent following a
valid custom destination exited 1 before creating that earlier destination.
[Initial copy](evidence/2026-10-17/copy-first.log),
[repeat and byte checks](evidence/2026-10-17/copy-repeat.log),
[invalid agent](evidence/2026-10-17/copy-invalid-agent.log).

Variation: correct a destination mistakenly naming the project root. Literal
`.` was rejected and preserved user files. The equivalent `new/..`, where `new`
did not exist, was accepted and deleted user files. Both controls and failures
were replayed from two separate clean projects; details below.

## Confirmed: missing path component bypasses root protection

[#204](https://github.com/jonbaldie/skills/issues/204).

Impact: copying skills can delete unrelated project work. Starting with one
canonical managed skill named `options`, a valid manifest, and an unrelated
`<project>/options/user-work.txt`:

```bash
skills/sync-jonbaldie-skills/scripts/copy-to-skill-dirs.sh "$project" 'new/..'
```

Expected: reject a path resolving to the project root, just like `.`; preserve
unrelated project content. Actual: exit 0, `Additional destination: <project>`,
`options/user-work.txt` deleted, and `options/SKILL.md` installed in its place.
The manifest was also written into the project root.

The destination preflight skips physical resolution when the requested path
does not yet exist. Directory creation makes `new/..` resolve to the project
root, but the copying stage does not repeat the root/ancestor guard.

This is a remaining bypass of closed [#85](https://github.com/jonbaldie/skills/issues/85),
not a failure of its direct `.` case.
[Failure 1](evidence/2026-10-17/copy-root-bypass-1.log),
[failure 2](evidence/2026-10-17/copy-root-bypass-2.log),
[control 1](evidence/2026-10-17/copy-root-direct-1.log),
[control 2](evidence/2026-10-17/copy-root-direct-2.log).

## Other candidates

- **Unresolved safety policy:** a custom destination inside a canonical skill
  (`.agents/skills/options`) is accepted and writes a nested `options/options`
  copy into the source tree. Two clean fixtures each ended with two `SKILL.md`
  files and exit 0. The interface promises arbitrary destinations but does not
  explicitly define overlapping source/destination behavior; no separate bug
  was filed without that contract. [Replay 1](evidence/2026-10-17/copy-overlap-1.log),
  [replay 2](evidence/2026-10-17/copy-overlap-2.log).
- **Rejected as a confirmed bug:** mixed known/unknown `--skill` filters silently
  succeed. The observable missing warning is a usability concern, but the
  documented filter does not require every requested name to match. No issue
  filed on that expectation alone.
- **Rejected:** a bad later agent causes earlier copies. The output and absent
  destination show argument preflight prevented all copying.

## Checks, limits, and cleanup

`RUN_ALL_SKIP=install-ship-spec.sh tests/run-all.sh`: **14 suites passed,
1 skipped, 0 failed**, including **176 Python tests**. The Docker/sandbox
ship-spec suite was explicitly skipped: deprecated ship-spec is outside these
journeys, and no container was needed. Passing regression tests did not catch
#204; its separate public-command reproducer is preserved above.

No setup blockers on the three journeys. Not explored: interactive agent/LLM
execution of prose skills, remote one-line bootstrap, live prerequisite drift,
Windows/WSL, alternate copy backends, and fault recovery during filesystem
writes. Clone overrides and reduced fixtures limit claims to the pinned
collections and observed commands. No claim of exhaustive skill coverage.

All run-created project data, isolated home, and source clone were removed after
capturing evidence. No Docker containers, images, or volumes were created by
this run; pre-existing Docker resources were left untouched. The
[cleanup record](evidence/2026-10-17/cleanup.log) records the resource check.
