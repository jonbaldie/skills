# Skills

A small, curated subset of my coding agent skills.

## Prerequisite

Some skills extend the engineering workflow from
[`mattpocock/skills`](https://github.com/mattpocock/skills) and hand off to its
skills, such as `/diagnosing-bugs`. Install that collection for the full flow.

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

### Cursor plugin

This repository is also a Cursor plugin marketplace
(`.cursor-plugin/marketplace.json`) with a single `jonbaldie-skills` plugin.
Add `https://github.com/jonbaldie/skills` as a plugin marketplace in Cursor, then
install `jonbaldie-skills`. The plugin ships every skill under `skills/<name>/`;
skills under `skills/in-progress/` and `skills/deprecated/` are left out. It does
not install `mattpocock/skills`.

### Just ask your agent

These steps look like a lot? Paste this into your agent:

```text
Install jonbaldie/skills for me. It needs mattpocock/skills, so install that
too. First ask: this project, or my user (global)? Use the same scope and agent
for both.
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

Skills that hand off to the `mattpocock/skills` workflow need it installed for
the same scope and harness.

Skill names below use the `/skill-name` form. In Codex, use `$skill-name`
instead.

</details>

## Test

Run every shell and Python test suite with one command:

```bash
tests/run-all.sh
```

The runner skips `install-ship-spec.sh` with a warning when Docker or
`sandbox-exec` is unavailable. Set `RUN_ALL_SKIP` to a comma-separated list of
suite names to skip a suite explicitly.

## Skills

### I want to understand how something works and why it helps

[`worked-example`](./skills/worked-example/SKILL.md) traces a concrete example
step by step, showing what changes and what is retained. It compares the same
example with a simple baseline to make the benefit visible.

```text
/worked-example Coverage-guided property-based testing
```

---

### I want options and a recommendation

[`options`](./skills/options/SKILL.md) summarises the situation, gives 2–3 choices,
then recommends one. The whole response stays under 240 words.

```text
/options
```

---

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

---

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

---

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

---

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

---

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

---

### I need an LLM to improve an important spec without changing what it means

**The problem.** You have an important specification and want an LLM's help
turning it into a clean, implementable design. A fluent rewrite can quietly
change behavior, drop an edge case, or smuggle in an assumption—and still sound
completely convincing. With correctness at stake, "looks reasonable" is not
enough.

**The fix.** [`bmf`](./skills/bmf/SKILL.md) uses the Bird–Meertens formalism, a
calculational method for deriving programs from specifications. It starts from
the obviously correct version and changes one thing at a time, showing why each
step preserves the meaning you care about. You get the practical design first,
followed by an audit trail of every transformation, assumption, and unresolved
obligation—written for developers, not mathematicians.

```text
/bmf
/bmf path/to/spec.md
```

Pass an idea or specification, or invoke it without an argument to use the
accepted conversation so far. In Codex, use `$bmf`.

---

### I need to know whether my tests observe production behavior

**The problem.** A passing test can assert values made entirely by fixtures,
mocks, helpers, or the test itself. The test is green, but its result may say
nothing about the production system.

**The fix.** [`deintrovert-tests`](./skills/deintrovert-tests/SKILL.md) traces
every assertion back to its source, classifies its evidence, and highlights
tests whose results never reach the system under test.

Credit: [`unclebob/deintroverter4clj`](https://github.com/unclebob/deintroverter4clj?utm_source=chatgpt.com).

---

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

---

### I want an agent to actually use my software

**The problem.** Individual operations can work while a complete user journey
fails. You want an agent to attempt real tasks through the interface and check
whether the intended outcomes actually happen.

**The fix.** [`exploratory-testing`](./skills/exploratory-testing/SKILL.md) drives
a few user-critical journeys, follows unexpected behaviour, and records
reproducible bugs with evidence. It reports what was explored and what remains
unexplored, leaving product fixes for a subsequent task.

```text
/exploratory-testing
/exploratory-testing Try implementing a small feature through the TUI
```

---

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

---

### I want to make a slow user journey faster

[`hill-climbing`](./skills/hill-climbing/SKILL.md) turns one journey into a
measured optimization loop: establish a baseline, prove benchmark feedback
tracks latency, improve the code, verify the result, and protect the gain with
a regression ceiling. It keeps work within a budget and distinguishes local
benchmark wins from improvements verified with real users.

```text
/hill-climbing Feedback export — 25 minutes
```

---

### I want to find inputs that make my code slow

**The problem.** Ordinary benchmarks can miss expensive input shapes. You need
concrete inputs that expose hotspots and can be replayed to investigate them.

**The fix.** [`perffuzz`](./skills/perffuzz/SKILL.md) mutates inputs using
independent performance maxima, adapts instrumentation to the codebase, and
validates and reduces expensive witnesses. It preserves the harness, corpus,
measurements, and a report within a bounded search budget.

```text
/perffuzz
/perffuzz parser — search for 20 minutes
```

---

### I need to find clean modular boundaries in a tangled codebase

**The problem.** Codebases grow tangled when domain capabilities couple directly
to UI, database, or transport details. Logic gets duplicated across frontends and
background jobs, callers reach through backdoors instead of stable interfaces,
and public APIs diverge from internal capabilities.

**The fix.** [`finding-seams`](./skills/finding-seams/SKILL.md) audits the
codebase for capability-oriented boundaries, deep modules, and architectural
backdoors. It produces a ranked list of incremental, in-process enhancements to
help UI and API consumers dogfood the same underlying capabilities.

```text
/finding-seams
```

---

### I need to find what a spec hasn't thought of yet

**The problem.** Specs read as complete until someone starts building them. The
gaps only show up mid-implementation, when they are expensive.

**The fix.** [`walk-the-spec`](./skills/walk-the-spec/SKILL.md) walks the spec
one tiny step at a time from now to closed, as the implementer, to surface
unknown-unknowns before work starts.

```text
/walk-the-spec
```
