# Skills

A small, curated subset of my coding agent skills.

## Prerequisite

Some skills extend the engineering workflow from
[`mattpocock/skills`](https://github.com/mattpocock/skills). `/ship-spec` and
other dependent skills will not work without that collection.

## Install

These instructions require Bash, Git, curl, and network access on macOS, Linux,
or WSL. **No Node.js or npm.**

### One-line global install

```bash
curl -fsSL https://raw.githubusercontent.com/jonbaldie/skills/main/install.sh | bash
```

Installs this collection into your user skill directories and asks before also
installing the `mattpocock/skills` prerequisite set. Pass flags after
`bash -s --`:

```bash
curl -fsSL https://raw.githubusercontent.com/jonbaldie/skills/main/install.sh | bash -s -- --agent codex --with-prereqs
```

### Just ask your agent

These steps look like a lot? Paste this into your agent:

```text
Install jonbaldie/skills for me. It needs mattpocock/skills, so install that
too. First ask: this project, or my user (global)? Use the same scope and agent
for both, then check /ship-spec can find /implement.
```

<details>
<summary><strong>Manual install</strong></summary>

### Globally with the installer

Clone this repository and pass `--global` so the skills are available across
projects:

```bash
git clone https://github.com/jonbaldie/skills.git jonbaldie-skills
cd jonbaldie-skills
agent=codex # Or claude-code, opencode, pi, or cursor
./install.sh --global --agent "${agent}" --yes
```

### In one project with the installer

Run the cloned installer while the project is the working directory:

```bash
cd "/path/to/your-project"
git clone https://github.com/jonbaldie/skills.git ../jonbaldie-skills
agent=codex # Or claude-code, opencode, pi, or cursor
../jonbaldie-skills/install.sh --agent "${agent}" --yes
```

The installer asks before installing the full `mattpocock/skills` prerequisite
set. Any options, including agent selection, apply to both collections.
If the collection is already cloned, skip the `git clone` command and rerun
`install.sh` from the documented working directory.

### In one project manually

Run from the project that will use the skills. Clones this repo to a temp dir and
installs both collections into the current project:

```bash
agent=codex # Or claude-code, opencode, pi, or cursor
repo="$(mktemp -d)/jonbaldie-skills"
git clone --depth 1 https://github.com/jonbaldie/skills.git "${repo}"
printf 'y\n' | "${repo}/install.sh" --agent "${agent}" --yes
```

### Globally manually

```bash
agent=codex # Or claude-code, opencode, pi, or cursor
curl -fsSL https://raw.githubusercontent.com/jonbaldie/skills/main/install.sh | bash -s -- --global --agent "${agent}" --with-prereqs
```

`/ship-spec` will not work until the `mattpocock/skills` prerequisite workflow
is installed for the same scope and harness.

Skill names below use the `/skill-name` form. In Codex, use `$skill-name`
instead.

</details>

## Skills

### I ran out of Claude usage and need to continue!

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

Pick the skill for the harness that died. With no argument, each uses the latest
session for the current directory. Pass an id when you need a specific one:

```text
# Claude Code — optional full session UUID
/resume-from-claude
/resume-from-claude 5d4a2d3b-121a-435a-beb0-2ec0d54dc859

# Pi — optional full or partial session UUID
/resume-from-pi
/resume-from-pi 019fd33e-ae16

# Codex — optional full/partial session UUID or thread name
/resume-from-codex
/resume-from-codex 019fb9a9-4c3f
/resume-from-codex "fix auth middleware"

# OpenCode — optional full/partial ses_ id, slug, or title
/resume-from-opencode
/resume-from-opencode ses_02cd32efbffeNwXYERC4uDu7OD
/resume-from-opencode clever-canyon
/resume-from-opencode "Resume Claude session skill"
```

### I have a whole parent spec and I just want it shipped

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

### I finished an implement and the PR is up — just land it

**The problem.** After `/implement` raises a PR, the last mile is rote and
easy to half-do: merge before CI is green, forget the closes-issue trailer, or
push locally instead of merging through the PR.

**The fix.** [`ship-pr`](./skills/ship-pr/SKILL.md) waits for required checks
to go green, merges through the PR onto the target branch (`main` by default,
or the PR base / a branch you name), and adds `Closes #<n>` when an issue is
attached.

```text
/ship-pr
/ship-pr 42
/ship-pr https://github.com/owner/repository/pull/42
```

### I need an accurate summary of a massive amount of text

**The problem.** Long docs, transcripts, and articles blow past context limits.
A single-shot summary either truncates, hallucinates coverage, or never starts.

**The fix.** [`to-summary`](./skills/to-summary/SKILL.md) reduces one source
through successive layers — chunk, summarise, repeat — until a final pass fits,
then writes the summary you asked for.

```text
/to-summary /path/to/large-source.txt
```

Accepts a file, URL, or pasted text. Optional focus, audience, format, or length.
