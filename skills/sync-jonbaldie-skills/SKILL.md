---
name: sync-jonbaldie-skills
description: Sync jonbaldie/skills and mattpocock/skills into the user's agent skill directories.
disable-model-invocation: true
---

Synchronize the two published collections into the current user's existing global agent skill directories.

## Destinations

Expand these candidate paths from the current environment, in this order:

1. `${HOME}/.agents/skills`
2. `${HOME}/.agent/skills`
3. `${CLAUDE_CONFIG_DIR:-${HOME}/.claude}/skills`
4. `${CODEX_HOME:-${HOME}/.codex}/skills`
5. `${HOME}/.cursor/skills`
6. `${HOME}/.gemini/skills`
7. `${HOME}/.pi/agent/skills`
8. `${XDG_CONFIG_HOME:-${HOME}/.config}/opencode/skills`

An existing directory, including a symlink to a directory, is a destination. A missing directory or broken symlink is not. This closed set excludes project-local directories, repository checkouts, and nested extension or plugin trees.

Canonicalize each destination directory itself with `realpath`; this also resolves symlinked parents. Group canonical paths with the same device and inode. For each group, mutate the lexicographically first canonical path once and retain every candidate path and canonical path in the group as aliases for the final report.

## Sources and identity

Create one throwaway root under the operating system's temporary directory with the equivalent of `mktemp -d`, and register unconditional exit cleanup before cloning. Into separate children, shallow-clone the current default branch of `https://github.com/mattpocock/skills.git` once and `https://github.com/jonbaldie/skills.git` once. Always use these fresh clones, including when the command is run from a checkout of either repository.

A source skill is any directory below a clone's top-level `skills/` directory that directly contains `SKILL.md`. Its collision key and destination directory name are the exact, trimmed `name` value in that file's YAML frontmatter; the source directory basename has no role. Require each name to be a non-empty single path component other than `.` or `..`, and unique within its repository. Finish source validation before changing a destination.

Build the winning map by adding every Matt Pocock skill and then every Jonathan Baldie skill by name. The second entry replaces the first on a collision.

## Mirror

For every deduplicated destination and every entry in the winning map, replace `${destination}/${name}` with a complete archive-preserving copy of the winning source directory. Create it when absent. “Replace only same-named” defines the boundary of replacement; it does not limit synchronization to skills already present. The resulting directory contains no destination-only files, directories, or symlinks.

Before the first replacement in a destination, record the sorted basenames of every top-level entry whose name is not in the winning map. Copy those entries together into a temporary `before` directory with the equivalent of `rsync --archive --hard-links --acls --xattrs`; this preserves entry types, symlink targets, hard-link relationships, contents, permissions, ownership, timestamps, ACLs, and extended attributes. After all replacements, record the same name set and make an `after` snapshot by the same method. Use the closest platform-equivalent only when its preservation and comparison contract covers every property just listed.

## Verification

For each mirrored skill, run the equivalent of:

```bash
rsync --archive --hard-links --acls --xattrs --checksum \
  --dry-run --itemize-changes --delete \
  "${winning_source}/" "${destination}/${name}/"
```

Require exit status zero and empty output. This proves that the copied tree has equal names, types, bytes, links, and filesystem metadata, with no destination extras.

Compare each destination's `before/` to its `after/` with the same command and require the recorded top-level name sets to be identical. Any difference is a failed sync.

Report the two source commit IDs and each mutated physical destination followed by all of its aliases. Report success only after every mirrored skill and every unaffected top-level entry passes verification.
