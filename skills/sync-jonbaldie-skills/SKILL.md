---
name: sync-jonbaldie-skills
description: Sync jonbaldie/skills and mattpocock/skills into the user's agent skill directories.
disable-model-invocation: true
---

Clone the current default branches of `github.com/mattpocock/skills` and `github.com/jonbaldie/skills` once each. Discover every existing user-level agent skill path, resolve it to a physical directory, and deduplicate aliases. Mirror every Matt Pocock skill into each directory, then every Jonathan Baldie skill so Jonathan-owned name collisions win. Replace only same-named skill directories. Verify each mirror byte-for-byte against its winning source and verify all other top-level entries are unchanged.
