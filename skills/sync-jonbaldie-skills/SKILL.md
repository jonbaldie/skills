---
name: sync-jonbaldie-skills
description: Sync jonbaldie/skills into the user's agent skill directories.
disable-model-invocation: true
---

Mirror each skill directory under `github.com/jonbaldie/skills/skills/` into every user-level agent skill directory; preserve unrelated skills, remove stale files only inside matching destinations, and verify each mirrored directory byte-for-byte.
