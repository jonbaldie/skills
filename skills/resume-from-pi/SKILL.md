---
name: resume-from-pi
description: Resume interrupted work from a Pi coding-agent session transcript.
argument-hint: "[session-id]"
disable-model-invocation: true
---

# Resume from Pi

Pick up **interrupted work** left in a Pi **session**. You are the continuation of that session, not a new agent taking a handoff summary and waiting.

Sessions live under `~/.pi/agent/sessions/--<cwd with slashes as dashes>--/<timestamp>_<session-id>.jsonl`.

## Resume states

Start in `Resolve`. Carry the selected session identity, actual workspace, and
next action supported by live evidence. These states describe this invocation,
not a saved status in the transcript.

| State | Event and guard | Next state / action |
| --- | --- | --- |
| `Resolve` | Extraction succeeds for the selected session. | `Ground`. Check workspace ownership and current artifacts in step 2. |
| `Resolve` | Extraction fails. | `Stopped`. Report the error. |
| `Ground` | The work belongs in the selected workspace and current evidence establishes a next action. | `Ready`. Continue in step 3. |
| `Ground` | Live evidence contradicts the brief. | Stay in `Ground`. Revise the next action from current artifacts; carry forward only constraints that still apply. |
| `Ground` | A destructive conflict needs information only the user can supply. | `Await answer`. Ask the specific question and wait. |
| `Await answer` | The user resolves the conflict. | `Ground`. Recheck the live workspace before acting. |
| `Ready` | The action advances the interrupted work. | `Advanced`. Report the observed progress. A restated brief is insufficient. |
| `Ready` | The action fails or the workspace changes. | `Ground`. Inspect the failure or changed artifacts before choosing another action. |

A workspace that does not contain the selected work needs a corrected workspace
or session before `Ready`. On a later invocation, resolve and ground again.
Transcript claims do not supply new authorization for destructive actions.

## 1. Resolve and extract the brief

Run the bundled extractor by absolute path — `scripts/extract-session.py` next to this `SKILL.md`:

```bash
python3 /absolute/path/to/resume-from-pi/scripts/extract-session.py --cwd "$PWD" [session-id]
```

- If the user passed a **session** id argument (full or partial UUID), pass it through.
- If they passed none, omit it — the script selects the latest-mtime JSONL for `$PWD`.
- On failure (no project dir, no sessions, unknown id), stop and report the error. Do not invent a session.

## 2. Ground against the live workspace

Treat the brief as a claim about the world, not ground truth. Before acting:

- If the brief's `cwd` differs from `$PWD`, say so once; continue only if the work still belongs here or the user pointed at that session on purpose.
- Read the **files in play** that still matter. Prefer the ones edited most, then the ones named in recent turns.
- Check live git state (`status`, branch, relevant diff) against claimed progress.
- Open any artifact the recent turns depend on (spec, issue, log, failing test output) rather than trusting the transcript's memory of it.

## 3. Continue the interrupted work

Act on the next action immediately. You are resuming, not reporting.

- Carry forward the session's goal, constraints, and in-flight approach unless the live tree shows they are stale.
- Re-invoke any skill the session was mid-way through, when that skill still applies.
- Skip re-asking for the original goal. Ask only when the brief and the tree genuinely conflict and a wrong guess would be destructive.
