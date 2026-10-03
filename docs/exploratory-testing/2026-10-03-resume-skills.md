# Exploratory pass: resume skills

2026-10-03. Checkout `9f3f0f4` (`origin/main`, after #166). macOS, Bash
3.2.57, Python 3.14.5, `codex-cli` 0.160.0, `pi` 1.0.0, `gh` logged in.
Real Codex and Pi sessions were written by the CLIs into isolated
`CODEX_HOME` and `HOME` directories under `/tmp`, with only auth and config
copied in. Live `~/.codex` and `~/.pi` stores were not read by the
extractors and were not written.

Confirmed bugs: [#167](https://github.com/jonbaldie/skills/issues/167),
[#168](https://github.com/jonbaldie/skills/issues/168),
[#169](https://github.com/jonbaldie/skills/issues/169).

This pass covers the skills the
[2026-09-26 pass](2026-09-26-skills.md) left unexplored.

## Journeys

1. Resume an interrupted Codex session (`resume-from-codex`).
2. Resume without knowing which harness ran last (`resume-from-agent`,
   with Codex and Pi sessions in the same project).
3. Resume from a pull request URL (`resume-from-pr`).

The goal for each: the extractor prints a brief the continuation can act
on. That means the real session id, cwd, the user's goal, the files in
play, and why the session stopped.

## Journey 1: resume from Codex

Setup: scratch git repo, `codex exec` writes a rollout. Documented call:

```bash
python3 skills/resume-from-codex/scripts/extract-session.py --cwd "$PWD"
```

| Action | Result |
| --- | --- |
| Completed session (append to `notes.txt`, add `TODO.md`) | Exit 0. UUID, cwd, model, goal, ending from `task_complete`. |
| Second session interrupted with SIGINT after `a.py`–`c.py` | Exit 0. Latest selected. Files in play `a.py`, `b.py`, `c.py`. |
| Partial id `01a0ff6b` | Exit 0, older session selected. |
| Unknown id | Exit 1. |
| `$PWD` is `/tmp/...`, Codex recorded `/private/tmp/...` | Matched. |

### Confirmed: interrupted turn reported as if finished

[#168](https://github.com/jonbaldie/skills/issues/168).

The rollout ends with
`{"type":"turn_aborted","reason":"interrupted"}`. The brief ignores it:

```text
## Ending
I’ll create each module with a separate `apply_patch` call, add a test for each function, and run `python3 -m unittest`.
```

That is the agent's opening plan, not where it stopped. The extractor
already reports `error`, `stream_error`, and rate-limit events as endings,
and the Pi extractor reports `stopReason: aborted`. Replayed on a second
real interrupted session in a fresh Codex home, then twice from a
four-line fixture (in the issue). `resume-from-agent` gives the same
Ending.

## Journey 2: resume from any agent

Same project, plus a newer `pi -p` session that created `d.py`.

| Action | Result |
| --- | --- |
| `--cwd "$PWD" --list` | Pi first, then both Codex sessions, newest first. |
| `--cwd "$PWD"` | Pi brief. Discovery notes name the Codex runner-up, 37s apart. |
| `codex` positional, `--agent codex` | Latest Codex session. |
| Bare id `01a0ff6b`, `codex 01a0ff6b`, `pi 01a0ff6d` | Correct session each time. |
| `codex deadbeef` | Exit 1, `No sessions found ... agent=codex id='deadbeef'`. |
| `notanagent` | Exit 1. Treated as a session id, not an unknown agent. |
| `--cwd /tmp/nowhere-xyz` | Exit 1. |
| `resume-from-pi --cwd "$PWD"` | Exit 0. Matches the router's Pi brief. |

### Confirmed: `--path` cannot read Codex or Pi transcripts

[#167](https://github.com/jonbaldie/skills/issues/167).

The SKILL.md's escape hatch is `--path`, with `--agent` to force the
parser. On the same files discovery reads correctly:

| Call | Result |
| --- | --- |
| `--path <pi or codex jsonl>` | Exit 0. `agent: unknown`, filename as `session_id`, no cwd, no goal, `## Ending` says `session may have stopped mid-tool` for a completed session. |
| `--agent pi --path <pi jsonl>` | Exit 1. `Could not identify ... as a pi session (no recognizable messages); refusing to emit a brief.` |
| `--agent codex --path <real rollout>` | Exit 0. Filename stem as `session_id`, no cwd, model, or files, and Codex's `<environment_context>` blocks shown as `### User`. |
| `--agent codex --path <minimal rollout>` | Exit 1, same refusal as Pi. |

Closed #63 stated that `--agent` should keep the session id, metadata,
goal, and ending, and that an unidentified path should fail, not return
an empty brief. Replayed twice from minimal fixtures and on the real
transcripts.

## Journey 3: resume from a PR

Fresh clone of this repo. Open PR #163 as the interrupted work.

| Action | Result |
| --- | --- |
| URL `.../pull/163` | Exit 0 in 1.3s. Title, head SHA, body, files with diffstat, `installer: SUCCESS`, commit. All match `gh pr view`. |
| Bare `163` | Same brief. |
| No argument, PR branch checked out with upstream | Same PR resolved. |
| `.../pull/99999` | Exit 1. Names each fetch path tried and its error. |
| `.../issues/159` | Exit 1, `Could not parse as a pull/merge request URL`. |
| No `gh` on `PATH`, no token | Exit 0, `source: api`. Missing data listed below. |

### Confirmed: API fallback drops checks silently

[#169](https://github.com/jonbaldie/skills/issues/169).

On cli/cli#13788, the `gh` brief lists three `build: FAILURE` check runs.
The API brief has no `## Checks` and no `## Missing data` note. It reads
`commits/{sha}/status` only, and GitHub Actions results are check runs.
Replayed on #163, which loses `installer: SUCCESS`. The API brief also drops
`## Linked issues`.

## Rejected

- No-`gh` traceback (`NotADirectoryError: 'gh'`). My `PATH` contained a
  file path, and `python3` resolved to the system 3.9. Rerun with a clean
  `PATH` succeeded.
- Interrupted `pi -p` brief shows no abort. Pi wrote no abort record on
  SIGINT (only `stopReason: toolUse`), so there was nothing to report.

## Unresolved

None.

## Not explored

`resume-from-agent` adapters for hermes, dirac, goose, cursor, gemini,
agy, and auggie. `resume-from-pr` on GitLab, Bitbucket, Gitea, and Azure
DevOps. Review-thread-heavy PRs. Install and sync, which the 2026-09-26
pass covered. The prose-only skills.

## Usability

Observations:

- On macOS, Codex and Pi record `/private/tmp/...` while `$PWD` is
  `/tmp/...`. Matching works, but each brief's `cwd` differs from `$PWD`.
  The SKILL.md tells the agent to remark on that difference.
- The router treats an unknown agent name as a session id. The error says
  `id='notanagent'` and does not list the known agents.
- After an interrupted Pi run that had written `g01`–`g04`, the brief's
  Ending was `[toolUse] Writing g02.txt next.`, the last text message,
  which lags the files on disk.

Suggestion: say in the `resume-from-agent` SKILL.md that the brief's
`cwd` may be the realpath of `$PWD`.

## Limitations

Sessions were driven non-interactively (`codex exec`, `pi -p`), not
through the TUIs. Interruption was SIGINT to the CLI process. The PR
journey used live GitHub data, and cli/cli#13788's check results may
change.
