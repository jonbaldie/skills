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

Once installed successfully, use `/sync-jonbaldie-skills` to update them.
The skill installs both collections into the requested project's
`.agents/skills` directory first, then asks whether to copy them into
`.claude/skills`, `.gemini/skills`, or another skill directory.

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

**The problem.** Usage limits, crashes, and closed terminals interrupt agent work
mid-change, leaving its useful context stranded in a transcript. Starting over
wastes completed work. An informal handoff loses the thread—what was in flight,
which files mattered, and what needed to happen next.

**The fix.** Resume skills extract a brief from the interrupted session
transcript, ground it against the live workspace, and continue the work — not
report on it.

| Skill | Harness |
| --- | --- |
| [`resume-from-agent`](./skills/resume-from-agent/SKILL.md) | **Any known agent** (cross-agent discovery) |
| [`resume-from-claude`](./skills/resume-from-claude/SKILL.md) | Claude Code |
| [`resume-from-pi`](./skills/resume-from-pi/SKILL.md) | Pi |
| [`resume-from-codex`](./skills/resume-from-codex/SKILL.md) | Codex CLI |
| [`resume-from-opencode`](./skills/resume-from-opencode/SKILL.md) | OpenCode |

Prefer `/resume-from-agent` when you don't know which harness ran last — it ranks
sessions for the current directory across Hermes, Dirac, Goose, Cursor, Gemini
CLI, Antigravity/agy, Claude, Pi, Codex, and OpenCode. Use a per-harness skill
when you already know which agent died.

With no argument, each skill uses the latest session for the current directory.
Pass an id (or agent name for the generic skill) when you need a specific one:

```text
# Any agent — latest for $PWD, or pin agent / id
/resume-from-agent
/resume-from-agent hermes
/resume-from-agent goose 20251016_150658

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

### I have a pull request I need to pick up

**The problem.** The work already lives on a pull or merge request — review
threads, failing checks, a draft, a branch an earlier agent (or a teammate)
left mid-change. Opening a fresh session without that thread loses the goal,
the files, and the next action.

**The fix.** [`resume-from-pr`](./skills/resume-from-pr/SKILL.md) extracts a
brief from the PR/MR on any git host, grounds it against the live workspace,
and continues the work — not report on it.

```text
/resume-from-pr https://github.com/owner/repository/pull/42
/resume-from-pr https://gitlab.com/group/project/-/merge_requests/7
/resume-from-pr https://bitbucket.org/owner/repository/pull-requests/3
/resume-from-pr https://codeberg.org/owner/repository/pulls/9
/resume-from-pr 42
```

Pass a URL from GitHub, GitLab, Bitbucket, Gitea/Forgejo, Azure DevOps, or
another host. A number uses the current repository. No argument uses the open
PR/MR for the current branch.

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

### I finished the work — ship it through a PR

**The problem.** Finished work may still be only a local branch. The last mile
is easy to half-do: forget to open the PR, merge the wrong head, or stop at the
merge queue instead of the target branch.

**The fix.** [`ship-pr`](./skills/ship-pr/SKILL.md) creates or reuses the PR for
the current branch, waits for required checks on its exact head, merges it onto
the target branch, closes linked issues, and verifies the remote result.

```text
/ship-pr
/ship-pr 42
/ship-pr https://github.com/owner/repository/pull/42
```

### I have changes on a fork that belong upstream

**The problem.** A fork branch can carry extra merges, setup commits, or other
fork-only history. Opening it upstream as-is either creates a duplicate PR or
asks maintainers to review changes that were never meant for them.

**The fix.** [`promote-fork-pr-upstream`](./skills/promote-fork-pr-upstream/SKILL.md)
finds the real upstream repository and any existing PR, audits the fork head,
rebuilds contaminated history from the upstream base, and creates or updates
one clean upstream PR.

```text
/promote-fork-pr-upstream https://github.com/fork-owner/repository/pull/42
```

### I need an accurate summary of a massive amount of text

**The problem.** Long documents, transcripts, and articles can be too large for
one summarisation pass. Ad hoc chunking risks omitting sections, losing their
order, or applying the requested focus inconsistently, leaving a final summary
that does not faithfully cover the whole source.

**The fix.** [`to-summary`](./skills/to-summary/SKILL.md) reduces one source
through successive layers — chunk, summarise, repeat — until a final pass fits,
then writes the summary you asked for.

```text
/to-summary /path/to/large-source.txt
```

Accepts a file, URL, or pasted text. Optional focus, audience, format, or length.

### I need to know whether my tests observe production behavior

**The problem.** A passing test can assert values made entirely by fixtures,
mocks, helpers, or the test itself. The test is green, but its result may say
nothing about the production system.

**The fix.** [`deintrovert-tests`](./skills/deintrovert-tests/SKILL.md) traces
every assertion back to its source, classifies its evidence, and highlights
tests whose results never reach the system under test.

Credit: [`unclebob/deintroverter4clj`](https://github.com/unclebob/deintroverter4clj?utm_source=chatgpt.com).

### I want to find real bugs before my users do

**The problem.** Agents wrote the code. TDD says the behavior you anticipated
works, so you are reasonably confident—but you will not really know until
people use it. Their time is the expensive part. Before asking humans to test
the software, you want automation to explore beyond the examples you thought
to write and find as many of the remaining bugs as it can.

**The fix.** [`finding-bugs`](./skills/finding-bugs/SKILL.md) gives the code an
automated shakedown before it reaches human testers. It checks invariants over
SUT observations, drives generated and mutated inputs through the actual system
under test, and grows a corpus from coverage until saturation. Every
counterexample is diagnosed and kept only when it is tightly reproducible.

You enter human testing with fewer avoidable defects and a clear account of
what coverage-guided testing found.

```text
/finding-bugs
```

### I need to make slow code faster

**The problem.** Performance work can point at the wrong code or produce a
benchmark win that disappears in real use. A profiler only shows where time was
spent in one run, a benchmark is only as good as its workload, and some
algorithms fail only when their input gets large.

**The fix.** [`seeking-performance`](./skills/seeking-performance/SKILL.md)
audits every production subsystem, traces reachable bottlenecks, and ranks them
by time complexity. Its report includes reproducible runtime evidence, space
costs, remediation directions, and the expected Big-O improvement without
changing the code unless you also ask for fixes.

```text
/seeking-performance
```
