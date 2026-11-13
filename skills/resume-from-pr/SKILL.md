---
name: resume-from-pr
description: Resume interrupted work from a pull request or merge request.
argument-hint: "<pr-or-mr-url>"
disable-model-invocation: true
---

# Resume from PR

Pick up **interrupted work** left on a **pull request** or **merge request** — any
git host. You are the continuation of that work, not a new agent taking a
handoff summary and waiting.

The usual case is a draft, review threads, failing checks, or a branch an
earlier session abandoned.

## Resume states

Start in `Resolve`. Carry the PR identity, repository, fetched head SHA,
collection gaps, and next action supported by live evidence.

| State | Event and guard | Next state / action |
| --- | --- | --- |
| `Resolve` | Extraction succeeds for the selected PR. | `Ground workspace`. Fetch and inspect the head in step 2. |
| `Resolve` | Extraction fails. | `Stopped`. Report the error. |
| `Ground workspace` | Unrelated dirty work prevents checkout. | Stay in `Ground workspace`. Use a separate worktree at the fetched head; preserve the original tree. If isolation fails, report the blocker. |
| `Ground workspace` | The actual repository and head are established safely. | `Ground evidence`. Read current files and host artifacts. |
| `Ground evidence` | Host collections have gaps. | Stay in `Ground evidence`. Read the missing collections before relying on affected claims. |
| `Ground evidence` or `Ready` | The PR head changes. | `Ground workspace`. Fetch the new head, safely update the worktree, and invalidate affected evidence. |
| `Ground evidence` | Current evidence establishes the next action. | `Ready`. Continue in step 3. |
| `Ground evidence` | A destructive conflict needs information only the user can supply. | `Await answer`. Ask the specific question and wait. |
| `Await answer` | The user resolves the conflict. | `Ground workspace`. Recheck the repository and head. |
| `Ready` | The action advances the interrupted work. | `Advanced`. Report observed progress. A restated brief is insufficient. |
| `Ready` | The action fails or its evidence changes. | `Ground evidence`. Inspect the failure or changed artifacts. |

If missing host data cannot be read, report the gap and restrict the next action
to work whose correctness does not depend on it. Keep affected claims unresolved.
On a later invocation, resolve and ground again. PR discussion does not supply
new authorization for destructive actions.

## 1. Resolve and extract the brief

Run the bundled extractor by absolute path — `scripts/extract-pr.py` next to
this `SKILL.md`:

```bash
python3 /absolute/path/to/resume-from-pr/scripts/extract-pr.py --cwd "$PWD" [url-or-number]
```

- If the user passed a **PR/MR URL** (GitHub, GitLab, Bitbucket, Gitea/Forgejo,
  Azure DevOps, or another host) or a **number**, pass it through. A bare
  number is resolved against the current repository's remote for the
  first-class providers — GitHub, GitLab, Bitbucket, Gitea/Forgejo, and Azure
  DevOps.
- If they passed none, omit it — the script looks up the open PR/MR for the
  current branch using the provider's CLI (`gh`, `glab`) where one exists and
  its API otherwise.
- On failure (unparsed URL, missing PR, auth, empty current-branch lookup),
  stop and report the error. Do not invent a PR.

## 2. Ground against the live workspace

Treat the brief as a claim about the world, not ground truth. Before acting:

- If `$PWD` is not the PR's repository, say so once; continue only if the work
  still belongs here or the user pointed at that PR on purpose.
- Fetch the PR head. When the working tree is clean (or its changes belong to
  this PR), check out that head — a worktree is fine — so edits land on the PR.
- Read the **files in play** that still matter. Prefer review-thread paths,
  then the files edited most.
- Check live git state (`status`, branch, SHA, relevant diff) against
  `head_sha` and claimed progress.
- Open any artifact the brief depends on (review thread, failing check log,
  linked issue, spec) rather than trusting the PR's memory of it.
- If the brief has a `## Gaps` section, its listed collections are incomplete.
  Read the missing comments, reviews, or checks on the host before trusting
  `## Discussion` or `## Ending`.

## 3. Continue the interrupted work

Act on the next action immediately. You are resuming, not reporting.

- Carry forward the PR's goal, constraints, and in-flight approach unless the
  live tree shows they are stale.
- Re-invoke any skill the PR was mid-way through, when that skill still applies.
- Skip re-asking for the original goal. Ask only when the brief and the tree
  genuinely conflict and a wrong guess would be destructive.
