---
name: fix-one-thing
description: Fix one CODING_STANDARDS.md violation in a small PR.
disable-model-invocation: true
---

Read `CODING_STANDARDS.md`. If the repo has none, stop and say so.

Find one violation of it in the codebase. Choose the one with the smallest
blast radius: fewest lines and files touched, fewest callers affected.

Fix that one violation. Every changed line traces to it; note any other
violations you see in the PR body.

Open a PR from a new branch. Its body quotes the rule broken and names the
file and line.

Done when one PR is open, it fixes exactly one violation, and its CI is green.
