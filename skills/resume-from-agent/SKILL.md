---
name: resume-from-agent
description: Resume interrupted work from any known coding-agent session (cross-agent discovery).
argument-hint: "[agent] [session-id]"
disable-model-invocation: true
---

# Resume from agent

Pick up **interrupted work** left in a coding-agent **session** — any harness this machine knows how to read. You are the continuation of that session, not a new agent taking a handoff summary and waiting.

Unlike `/resume-from-claude` (and siblings), this skill **discovers across agents** and picks the latest session for `$PWD` unless you name an agent or session.

Supported stores (when present on disk):

| Agent | Aliases | Root (typical) |
| --- | --- | --- |
| hermes | hermes-agent | `~/.hermes/state.db` |
| dirac | | `~/.dirac/data/tasks` |
| goose | | `~/.local/share/goose/sessions` |
| cursor | cursor-agent | `~/.cursor/projects/.../agent-transcripts` |
| gemini | gemini-cli | `~/.gemini/tmp/.../chats` |
| agy | antigravity, jetski | `~/.gemini/antigravity-cli` (best-effort) |
| claude | claude-code | `~/.claude/projects` |
| pi | | `~/.pi/agent/sessions` |
| codex | | `~/.codex/sessions` |
| opencode | | `~/.local/share/opencode/opencode.db` |
| auggie | augment | *(not observed — reports empty)* |

Research notes: `docs/research/resume-from-agent-session-stores.md` in the jonbaldie/skills repo.

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
python3 /absolute/path/to/resume-from-agent/scripts/extract-session.py --cwd "$PWD" [agent] [session-id]
```

Useful variants:

```bash
# Latest session for this cwd across every known agent
python3 .../extract-session.py --cwd "$PWD"

# Force one agent
python3 .../extract-session.py --cwd "$PWD" hermes
python3 .../extract-session.py --cwd "$PWD" --agent goose

# Pin a session id (with or without agent)
python3 .../extract-session.py --cwd "$PWD" 20260701_134450_4ae33b
python3 .../extract-session.py --cwd "$PWD" dirac <task-id>

# Ranked candidates only
python3 .../extract-session.py --cwd "$PWD" --list
python3 .../extract-session.py --cwd "$PWD" --agent cursor --list

# Escape hatch: explicit transcript/db path (combine with --agent to force the parser)
python3 .../extract-session.py --path ~/path/to/session.jsonl
python3 .../extract-session.py --agent codex --path ~/.codex/sessions/.../rollout-x.jsonl
```

- If the user passed an **agent** name and/or **session** id, pass them through (positional args or `--agent`).
- If they passed none, omit both — the script ranks every cwd match by mtime and takes the newest.
- With a session id, the script ranks exact id matches first, then id prefix/suffix, id substring, and title matches; mtime breaks ties within a tier. `--list` shows each candidate's real id and `match=` tier.
- On failure (nothing found, unknown agent, bad path), stop and report the error. Do not invent a session.
- Prefer this skill over the per-agent `/resume-from-*` skills when the user does not know which harness ran last. Use a per-agent skill when they explicitly name one and you only have that skill installed.

## 2. Ground against the live workspace

Treat the brief as a claim about the world, not ground truth. Before acting:

- If the brief's `cwd` differs from `$PWD`, say so once; continue only if the work still belongs here or the user pointed at that session on purpose.
- Read the **files in play** that still matter. Prefer the ones edited most, then the ones named in recent turns.
- Check live git state (`status`, branch, relevant diff) against the brief's `git_branch` (if any) and claimed progress.
- Open any artifact the recent turns depend on (spec, issue, log, failing test output) rather than trusting the transcript's memory of it.
- If **Discovery notes** mention a close runner-up from another agent, glance at `--list` only when the chosen brief looks empty or wrong for the work the user means.

## 3. Continue the interrupted work

Act on the next action immediately. You are resuming, not reporting.

- Carry forward the session's goal, constraints, and in-flight approach unless the live tree shows they are stale.
- Re-invoke any skill the session was mid-way through, when that skill still applies.
- Skip re-asking for the original goal. Ask only when the brief and the tree genuinely conflict and a wrong guess would be destructive.
- Antigravity/`agy` briefs are lossy (protobuf blobs). Treat them as weak hints; prefer a fuller brief from another agent when both match.
