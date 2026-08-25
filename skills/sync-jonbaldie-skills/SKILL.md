---
name: sync-jonbaldie-skills
description: Sync jonbaldie/skills and mattpocock/skills into the user's agent skill directories.
disable-model-invocation: true
---

Mirror every skill directory from the current default branches of `github.com/mattpocock/skills` and `github.com/jonbaldie/skills` into every user-level agent skill directory. Install Matt Pocock's collection first, then Jonathan Baldie's so Jonathan-owned name collisions win. Preserve unrelated skills, remove stale files only inside matching destinations, and verify every mirrored directory byte-for-byte against its source.
