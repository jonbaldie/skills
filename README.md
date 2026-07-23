# Skills

A small, curated subset of Jonathan Baldie's agent skills.

## Prerequisite

These skills extend the engineering workflow from
[`mattpocock/skills`](https://github.com/mattpocock/skills). `$ship-spec` and
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
npx --yes skills@latest add jonbaldie/skills --skill ship-spec --agent "${agent}" --yes
```

### Globally manually

Pass `--global` to both commands:

```bash
agent=codex # Or claude-code, opencode, or another skills CLI agent
npx --yes skills@latest add mattpocock/skills --skill '*' --global --agent "${agent}" --yes
npx --yes skills@latest add jonbaldie/skills --skill ship-spec --global --agent "${agent}" --yes
```

The second command alone installs `ship-spec`, but it will not work until the
first command's prerequisite workflow is installed for the same scope and
harness.

## Skills

### `ship-spec`

Implements a parent spec's child issues serially and ships each completed issue
to one target branch.

Pass a parent spec when invoking it:

```text
$ship-spec https://github.com/owner/repository/issues/123
```

Codex uses the `$ship-spec` form. Claude Code, OpenCode, and similar
slash-command harnesses use `/ship-spec`.
