---
name: sync-jonbaldie-skills
description: Install or update the jonbaldie/skills and mattpocock/skills collections in a project.
disable-model-invocation: true
---

Install both collections into one project's canonical Agent Skills directory.

1. Use the directory named by the user, or the current working directory when none is named. Resolve it to an absolute path.

2. Resolve the bundled script relative to this `SKILL.md`, then run it immediately:

```bash
"<this-skill-directory>/scripts/sync-skills.sh" "/absolute/path/to/project"
```

It installs both collections into `<project>/.agents/skills`, replaces previously managed skills with their current versions, and leaves unrelated skills alone. Use its output to report the two source commit IDs and the canonical destination. Do not inspect agent harness folders or reconstruct the installation yourself.

3. Only after the canonical install succeeds, ask whether the user also wants the managed skills copied for other agents, such as Claude Code (`.claude/skills`) or Gemini CLI (`.gemini/skills`), or into any other skill directories. Stop and wait for their answer.

4. If they choose additional destinations, run:

```bash
"<this-skill-directory>/scripts/copy-to-skill-dirs.sh" "/absolute/path/to/project" --agent claude-code --agent gemini
```

Pass only the destinations they chose: `--agent <name>` for an agent, or a directory path for anything else. An unknown agent name fails before anything is copied and lists the supported names. Relative paths resolve beneath the project; absolute paths remain absolute. Agents that read `.agents/skills` need no copy. The script copies only skills managed by the canonical installer and leaves unrelated entries alone.

## Installation states

Start in `Resolve`. The scripts own filesystem changes; the agent owns the destination choice and reports their result.

| State | Event and guard | Next state / action |
| --- | --- | --- |
| Resolve | One project resolves to an existing absolute directory | Canonical preflight. Run `sync-skills.sh`. |
| Canonical preflight | Both source snapshots, skill names and collisions validate | Applying canonical. Each tree is staged before replacement. |
| Applying canonical | Every tree copy and retirement succeeds, then the manifest publishes | Await destinations. Report source commits and destination; ask once and wait. |
| Await destinations | The user declines additional copies | Complete. |
| Await destinations | The user selects destinations | Copy preflight. Pass exactly those destinations. |
| Copy preflight | All paths and agent names validate; every managed canonical skill exists | Applying copies. Process selected destinations in order. |
| Applying copies | Every selected destination has its trees and published manifest | Complete. Report the completed destinations. |
| Either preflight | Validation or fetch fails | Failed. Report the error; repair the input before retrying. Do not ask about additional copies after a failed canonical install. |
| Either applying state | Copy, retirement or manifest publication fails | Partial. Report the error and completed destinations; do not report completion. Repair the cause, then rerun the failed stage for its intended destinations. |

A failed tree copy leaves its previous installation intact. A failed replacement restores the previous tree; if restoration also fails, the script prints the retained backup path. Restore that backup before retrying. Process termination between replacement moves can also leave a `.skill-copy.*` backup beside the destination. Inspect and recover it before another run.

The operation spans multiple trees and destinations. Earlier successful changes can remain after a later failure. A manifest records managed names and source commits, not a transaction checkpoint or proof that every current tree has those bytes. Revalidate the canonical install before copying after an interrupted sync. A retry fetches fresh source snapshots; report the commits from the successful run.
