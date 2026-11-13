---
name: promote-fork-pr-upstream
description: Promote or repair changes from a GitHub fork as a clean upstream pull request. Use for fork branches, fork-local pull requests, commit sets, or upstream pull requests carrying fork-only history.
---

# Promote a fork PR upstream

## Promotion states

Start in `Resolve route`. Track the exact fork branch and captured SHA,
upstream base, ordered intended patches, candidate SHA, and selected PR.

| State | Event and guard | Next state / action |
| --- | --- | --- |
| `Resolve route` | The route and intended patch set are established. | `Select PR`. Match by exact head and base in step 2. |
| `Resolve route` | Either cannot be established. | `Stopped`. Report the missing evidence. |
| `Select PR` | An exact merged match already contains every intended patch on the remote target. | `Complete`. Report the existing merged PR and verified result. |
| `Select PR` | The intended changes remain unmerged. | `Audit`. Reuse an open match, reopen a closed unmerged match, or create a replacement after the audit. |
| `Audit` | The head contains only intended changes. | `Check candidate`. Check the existing head. |
| `Audit` | The head is contaminated. | `Rebuild`. Cherry-pick the intended commits onto the fetched base. |
| `Rebuild` | Source evidence cannot resolve a semantic conflict. | `Stopped`. Report the conflict and retain necessary recovery evidence. |
| `Rebuild` | The rebuilt patch set is equivalent and intended-only. | `Check candidate`. Run required checks. |
| `Check candidate` | Checks pass and the fork head still equals the captured SHA. | `Publish`. Use the lease for a rebuild, then publish the PR. |
| `Check candidate` or `Publish` | The fork head changes or the lease fails. | `Audit`. Refetch, recapture the head, and re-establish the intended patch set. Prior checks do not authorize overwriting the new head. |
| `Check candidate` | Checks fail. | Return to `Rebuild` to fix the candidate, or `Stopped` with the failure. |
| `Publish` | Read-back matches the candidate SHA and the PR's base, commits, and files match the route. | `Complete`. Remove disposable state and report the verified PR. |
| `Publish` | Read-back differs. | `Audit` if refs changed; otherwise report the publication error as `Stopped`. |

A merged PR cannot be reopened. If it does not cover the current intended
changes, audit those changes and create a replacement PR for what remains.
On a later invocation, resolve and audit again before publishing.

## 1. Resolve the route

Resolve with `gh`:

- ordered intended commits: source PR first, otherwise the supplied commit set;
- exact fork `<owner>:<branch>@<SHA>`;
- upstream parent and target base.

Read the parent with `gh repo view`. Never infer it from names or remotes.
If the route or intended patch set cannot be established, stop and report the
missing evidence.

## 2. Find the upstream PR

Search all upstream PR states for the exact `<fork-owner>:<head-branch>`, then
validate the target base. Follow the matching state in the table. Compare a
merged match against intended patches on the fetched target, accounting for
squash or rebase merges. Titles are not identity.

## 3. Audit and rebuild

Fetch the exact base and head without changing the working tree. Compare the
commit patches and final diff with the intended changes. Any extra
upstream-visible commit, patch, or path is contamination.

For a contaminated head, create a disposable worktree at the fetched upstream
base and cherry-pick only the intended commits in order. Resolve conflicts from
source evidence; report any semantic conflict the evidence cannot resolve.

Before publishing, verify:

- rebuilt patches match their source patches, with inspected conflict
  resolutions accounting for any difference;
- the final diff contains only intended changes;
- affected and repository-required checks pass;
- the remote fork head still equals the captured SHA.

Push the rebuilt SHA to the exact branch with:

```bash
git push --force-with-lease=refs/heads/<branch>:<captured-sha> \
  <fork> <rebuilt-sha>:refs/heads/<branch>
```

Read the remote ref back and require the rebuilt SHA. Keep the disposable
worktree until PR verification also succeeds.

## 4. Publish and verify

Use the upstream PR template. Create or update the selected PR with verified
scope and observed test results only. Read it back and require its base, head SHA,
commits, and changed files to match the route. Follow the recovery path in the
table when they differ.

Report the PR URL, mergeability, and observed checks.
