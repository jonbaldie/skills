# Skills

A small, curated subset of Jonathan Baldie's agent skills.

## Prerequisite

Some skills extend the engineering workflow from
[`mattpocock/skills`](https://github.com/mattpocock/skills). `/ship-spec` and
other dependent skills will not work without that collection.

## Install

These instructions require Bash, Git, Node.js/npm, and network access on macOS,
Linux, or WSL.

### Or just ask your agent

These steps look like a lot? Paste this into your agent:

```text
Install jonbaldie/skills for me. It needs mattpocock/skills, so install that
too. First ask: this project, or my user (global)? Use the same scope and agent
for both, then check ship-spec can find implement.
```

### Globally with the installer

Clone this repository and pass `--global` so the skills are available across
projects:

```bash
git clone https://github.com/jonbaldie/skills.git jonbaldie-skills
cd jonbaldie-skills
agent=codex # Or claude-code, opencode, or another skills CLI agent
./install.sh --global --agent "${agent}" --yes
```

### In one project with the installer

Run the cloned installer while the project is the working directory:

```bash
cd "/path/to/your-project"
git clone https://github.com/jonbaldie/skills.git ../jonbaldie-skills
agent=codex # Or claude-code, opencode, or another skills CLI agent
../jonbaldie-skills/install.sh --agent "${agent}" --yes
```

The installer asks before installing the full `mattpocock/skills` prerequisite
set. Any options, including agent selection, apply to both collections.
If the collection is already cloned, skip the `git clone` command and rerun
`install.sh` from the documented working directory.

### In one project manually

Run both commands from the project that will use the skills:

```bash
agent=codex # Or claude-code, opencode, or another skills CLI agent
npx --yes skills@latest add mattpocock/skills --skill '*' --agent "${agent}" --yes
npx --yes skills@latest add jonbaldie/skills --skill '*' --agent "${agent}" --yes
```

### Globally manually

Pass `--global` to both commands:

```bash
agent=codex # Or claude-code, opencode, or another skills CLI agent
npx --yes skills@latest add mattpocock/skills --skill '*' --global --agent "${agent}" --yes
npx --yes skills@latest add jonbaldie/skills --skill '*' --global --agent "${agent}" --yes
```

`/ship-spec` will not work until the `mattpocock/skills` prerequisite workflow
is installed for the same scope and harness.

Skill names below use the `/skill-name` form. In Codex, use `$skill-name`
instead.

## Skills

### The session died mid-task

**The problem.** Usage limits, crashes, and closed terminals kill agent sessions
mid-change. Starting over wastes the work already done. Handing the next agent a
vague summary loses the thread — what was in flight, which files mattered, and
what the next concrete step was.

**The fix.** Resume skills extract a brief from the interrupted session
transcript, ground it against the live workspace, and continue the work — not
report on it.

| Skill | Harness |
| --- | --- |
| [`resume-from-claude`](./skills/resume-from-claude/SKILL.md) | Claude Code |
| [`resume-from-pi`](./skills/resume-from-pi/SKILL.md) | Pi |
| [`resume-from-codex`](./skills/resume-from-codex/SKILL.md) | Codex CLI |
| [`resume-from-opencode`](./skills/resume-from-opencode/SKILL.md) | OpenCode |

```text
/resume-from-claude
/resume-from-pi
/resume-from-codex
/resume-from-opencode
```

Pass an optional session id (or harness-specific name/slug) when you don't want
the latest session for the current directory.

### A parent spec has many child issues to ship

**The problem.** A parent spec with a stack of child issues invites thrash:
picking the wrong ticket next, mixing work on one branch, or calling something
"done" before it's on the target branch. Agents drift; serial delivery stalls.

**The fix.** [`ship-spec`](./skills/ship-spec/SKILL.md) walks ready child issues
in dependency order, applies `/implement` to each on its own branch, and only
moves on once that issue is integrated and reachable on the remote target
branch.

```text
/ship-spec https://github.com/owner/repository/issues/123
```

Requires [`mattpocock/skills`](https://github.com/mattpocock/skills) (for
`/implement`) installed for the same scope and harness.

### The source is too large to summarise in one pass

**The problem.** Long docs, transcripts, and articles blow past context limits.
A single-shot summary either truncates, hallucinates coverage, or never starts.

**The fix.** [`to-summary`](./skills/to-summary/SKILL.md) reduces one source
through successive layers — chunk, summarise, repeat — until a final pass fits,
then writes the summary you asked for.

```text
/to-summary /path/to/large-source.txt
```

Accepts a file, URL, or pasted text. Optional focus, audience, format, or length.
