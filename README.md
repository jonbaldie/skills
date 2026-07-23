# Skills

A small, curated subset of Jonathan Baldie's agent skills.

## Prerequisite

These skills extend the engineering workflow from
[`mattpocock/skills`](https://github.com/mattpocock/skills). `$ship-spec` and
other dependent skills will not work without that collection.

## Install

Clone this repository and run the installer:

```bash
git clone https://github.com/jonbaldie/skills.git jonbaldie-skills
cd jonbaldie-skills
./install.sh
```

The installer asks before installing the full `mattpocock/skills` prerequisite
set. Choose the same agents or harnesses for the prerequisite and this
collection.

To install manually:

```bash
npx skills@latest add mattpocock/skills --skill '*'
npx skills@latest add jonbaldie/skills --skill ship-spec
```

The second command alone installs `ship-spec`, but it will not work until the
first command's prerequisite workflow is installed for the same harness.

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
