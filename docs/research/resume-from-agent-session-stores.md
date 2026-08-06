# Research: coding-agent session stores (for `/resume-from-agent`)

Primary sources: live home-directory stores on this machine, plus the existing
`resume-from-{claude,codex,opencode,pi}` extractors in this repo.

Goal: what a **generic** resume skill must discover, rank, and parse — not only
the four already covered harnesses.

## What the per-agent skills already do

Each existing skill is a thin recipe over a bundled `scripts/extract-session.py`:

1. Resolve a session for `$PWD` (or an explicit id).
2. Print a **brief** (meta, skills, files in play, opening goal, recent turns, ending).
3. Agent grounds against the live tree and continues.

They differ only in store layout and record shape. A generic skill should keep
that brief contract and add **cross-agent discovery**.

## Store map (observed)

| Agent | CLI on this machine | Session root | Shape | Cwd match |
| --- | --- | --- | --- | --- |
| Claude Code | (existing skill) | `~/.claude/projects/<cwd-as-dashes>/*.jsonl` | JSONL events (`user`/`assistant`, tool_use) | Project dir name |
| Codex | (existing) | `~/.codex/sessions/YYYY/MM/DD/rollout-*-<uuid>.jsonl` | JSONL (`session_meta`, `event_msg`, `response_item`) | `session_meta.payload.cwd` |
| OpenCode | (existing) | `~/.local/share/opencode/opencode.db` | SQLite `session`/`message`/`part` | `session.directory` / project worktree |
| Pi | (existing) | `~/.pi/agent/sessions/--<cwd-dashes>--/<ts>_<uuid>.jsonl` | JSONL (`session`, `message` with toolCall) | Project dir name |
| Hermes | `hermes` | `~/.hermes/state.db` (+ legacy `~/.hermes/sessions/session_*.json`) | SQLite `sessions`/`messages`; JSON dump is OpenAI-style messages | `sessions.cwd` |
| Dirac | `dirac` | `~/.dirac/data/tasks/<id>/` + `state/taskHistory.json` | Per-task `ui_messages.json`, `api_conversation_history.json`, `task_metadata.json` | `cwdOnTaskInitialization` / `workspaceRootPath` |
| Goose | `goose` | `~/.local/share/goose/sessions/*.jsonl` | Line 0 = meta (`working_dir`, `description`); then role messages with `toolRequest`/`toolResponse` | Meta `working_dir` |
| Cursor (IDE + agent) | `cursor-agent` | `~/.cursor/projects/<path-as-dashes>/agent-transcripts/<uuid>/<uuid>.jsonl` | JSONL `{role,message.content[]}` with tool_use; trailing `turn_ended` | Project dir encoding of absolute path |
| Gemini CLI | `gemini` | `~/.gemini/tmp/<slug-or-hash>/chats/session-*.json(l)` | JSONL stream: header + message objects (`type`: user/gemini/info) + `$set` ops; tools in `toolCalls` | `.project_root` file in tmp dir, or `~/.gemini/history/<name>/.project_root` |
| Antigravity / agy | `agy` | `~/.gemini/antigravity-cli/conversations/<id>.db` | SQLite with **protobuf BLOBs** (`steps.step_payload`, `trajectory_metadata_blob`) | `cache/last_conversations.json` and `cache/projects.json` map cwd → id |
| Auggie (Augment) | not installed | unknown here | — | — |
| Aider | present but unused | often `.aider.chat.history.md` in project | Markdown chat log | Path presence |

### Hermes details

- Canonical: `state.db` tables `sessions` (id, title, cwd, model, started_at, ended_at, end_reason, message_count, git_branch, …) and `messages` (role, content, tool_calls JSON, tool_name, timestamp, finish_reason).
- Tool calls look like OpenAI function-call arrays; file tools include `read_file`, `write_file`, `search_files`, `patch`, `terminal`.
- Legacy JSON files under `sessions/session_*.json` hold full `messages` arrays; request dumps are API failure artifacts, not good resume sources.

### Dirac details

- Cline-family layout: task id directories with UI timeline + API history.
- `taskHistory.json` is the index for cwd and the human task string.
- UI `say: "task"` carries the goal; ending often `ask: "resume_task"`.
- `task_metadata.json` already lists `files_in_context`.

### Goose details

- First JSONL line is session meta, not a message.
- Assistant turns embed `toolRequest` with `toolCall.value.name` / `arguments` (e.g. `developer__text_editor` + `path`).

### Cursor details

- Path encoding: `/Users/foo/bar` → `Users-foo-bar` under `~/.cursor/projects/`.
- Skip `subagents/` transcripts when picking the primary session.
- Content model is Claude-like (`text` + `tool_use` blocks).

### Gemini CLI details

- Newer sessions are JSONL (not only monolithic JSON).
- Messages appear as top-level objects with `type` in {`user`,`gemini`,`info`,…}; interleaved `$set` updates `lastUpdated` / sometimes full `messages`.
- User turns often wrap real text after a large `<session_context>…` blob — strip it.
- `toolCalls[].name` + `args` carry paths (`file_path`, `path`, etc.).

### Antigravity / agy details

- `agy --help` exposes conversation resume flags; binary strings reference Jetski/Antigravity.
- Conversation DBs are not plain JSON. Best-effort resume = cwd map from cache JSON + printable-string extraction from blobs (lossy). Prefer other agents when they also match.

### Auggie

- No local install or session tree found. Generic skill should accept the name, report "no store discovered", and keep an extension point.

## Design implications (smarter than per-agent skills)

1. **Discovery registry** — each adapter yields zero-or-more `Candidate(agent, session_id, cwd, mtime, title, path)` for a cwd (and optional id query).
2. **Cross-agent default** — with no agent arg, rank all candidates by `mtime` and take the latest. That is the main win over remembering `/resume-from-hermes` vs `/resume-from-goose`.
3. **Agent filter** — first arg may be an agent alias (`hermes`, `dirac`, `goose`, `cursor`, `gemini`, `agy`/`antigravity`, plus the four existing).
4. **List mode** — `--list` prints ranked candidates so the human can disambiguate.
5. **Ambiguity signal** — if runner-up is another agent within a short window of the winner, stamp the brief so the continuing agent knows the pick was contested.
6. **Unified brief header** — always emit `agent:` and the same section set as the per-agent skills.
7. **Reuse, don't fork** — for claude/codex/opencode/pi, shell out to sibling `extract-session.py` when present; fall back to in-process adapters so the skill stays useful alone.
8. **Explicit path escape hatch** — `--path` for a transcript the registry does not know.
9. **Do not invent** — empty registry → hard error with which roots were probed.

## Out of scope for v1

- Full protobuf decode for Antigravity (lossy strings only).
- Auggie/Augment until a real store is observed.
- Aider markdown history (project-local, easy later).
- Writing back into foreign session stores.
