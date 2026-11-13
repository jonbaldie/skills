---
name: ship-pr
description: "Ship current work through a pull request: create or reuse it, pass required checks, merge it, close linked issues, and verify the remote result."
disable-model-invocation: true
---

# Ship a PR

## Shipping states

Start in `Resolve`. Track the exact PR, target, recorded head SHA, gate results,
closing issues, and host-reported merge commit. A merge request or queue entry
is not a merged PR.

| State | Event and guard | Next state / action |
| --- | --- | --- |
| `Resolve` | An open PR is selected or created. | `Gate`. Record its identity and head in step 1. |
| `Resolve` | The explicit PR is already merged. | `Verify`. Verify its actual target and merge commit without retargeting or merging again. |
| `Resolve` | The explicit PR is missing or closed without merging. | `Stopped`. Report that PR's state. |
| `Gate` | Required checks and protections pass for the recorded head. | `Merge`. Use the guarded merge in step 3. |
| `Gate` | Required checks are still pending. | Stay in `Gate`. Observe checks for the recorded head. |
| `Gate` | A required check fails or is canceled, or a protection blocks merging. | `Stopped`. Report the failed gate. |
| `Gate`, `Merge`, or `Queued` | The PR head changes or compare-and-merge reports a mismatch. | `Gate`. Capture the new head and invalidate the old gate results. |
| `Merge` | The host queues the merge. | `Queued`. Observe the same PR until its state changes. |
| `Merge` or `Queued` | The host reports `MERGED`. | `Verify`. Fetch and check the remote target. |
| `Merge` or `Queued` | The entry is canceled or ejected, or the PR closes unmerged. | `Stopped`. Report the host reason. Any retry must re-enter `Gate`. |
| `Merge` | The host rejects the merge for another reason. | `Stopped`. Report the host error and preserve the PR. |
| `Verify` | The merge commit is reachable and issues and branch are settled or restrictions reported. | `Complete`. Report the results from step 4. |
| `Verify` | Fetch or reachability verification fails. | `Unverified`. Report the failure; retry verification after the cause is resolved. |

## 1. Resolve or create

Use an explicitly supplied PR. Otherwise treat the current branch as the work to
ship.

Reuse the branch's open PR. When none exists, commit the intended work, push the
branch, and create a PR against the user-named target or the repository default
branch. Use the repository PR template.

An explicit PR is authoritative. Follow its state in the table rather than
selecting another PR.

Treat an existing PR's base as the target. When the user names another target,
retarget the PR before continuing.

Record the repository, base, head branch and SHA, draft and review state,
required checks, and host-native closing issue links.

## 2. Gate

Resolve linked issues from explicit arguments, otherwise the PR's host-native
closing links. Bare mentions do not count. Add missing closing links to the PR
body when it targets the default branch.

Mark a draft ready. Watch every required check on the recorded head SHA and fail
fast on failure or cancellation. If the head changes, repeat the gate on the new
SHA.

Require approvals, rulesets, and other branch protections. Never bypass them
with administrator privileges.

## 3. Merge

Use the user's merge method, otherwise the repository convention, otherwise
squash.

Merge through the host. On GitHub, pass `--match-head-commit <sha>` and
`--delete-branch`. A head mismatch restarts the gate.

Observe any merge queue using the transitions above. Continue to verification
only after the host reports `MERGED`.

## 4. Verify

Read the PR back. Fetch the target from the base repository and verify the
host-reported merge commit is reachable from that remote branch.

Close any selected issue still open, linking the merged PR. Verify the remote
head branch was deleted where permitted; otherwise report why it remains.

Report the PR URL, merge commit, target, issue results, and branch result.
