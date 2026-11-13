---
name: land-the-plane
description: "Land the plane: finish the current task, verify it, merge into the default branch, and sync local and remote."
---

# Land the plane

## Landing states

Start in `Finish`. Track assigned work, the fetched default tip, the verified
candidate tree, and the actual integrated commit. Verification belongs to that
candidate, not to the task indefinitely.

| State | Event and guard | Next state / action |
| --- | --- | --- |
| `Finish` | Assigned work is complete and unrelated work is preserved. | `Verify candidate`. Prepare and check the candidate in step 2. |
| `Verify candidate` | Required checks pass. | `Integrate`. Choose the route in step 3. |
| `Verify candidate` | A check fails. | Stay in `Verify candidate` while fixing it. If it cannot pass, `Stopped` and report the failure. |
| `Integrate` | Assigned work or the remote default tip changes, or a direct push loses a race. | `Verify candidate`. Update the candidate and invalidate earlier results. |
| `Integrate` | The remote already contains the work or integration succeeds. | `Verify result`. Inspect the actual remote tree. |
| `Verify result` | The tree differs from the candidate. | Stay in `Verify result`. Run the checks on that tree. |
| `Verify result` | The tree matches the candidate or its checks pass. | `Sync`. Follow step 4. |
| `Verify result` | A required check fails on the integrated tree. | `Integrated with failure`. Report the commit and failure. Preserve evidence needed for recovery; do not claim a successful landing or silently roll back shared history. |
| `Sync` | The remote contains the work and local and remote tips match safely. | `Cleanup`. Follow step 5. |
| `Sync` | A safe local update is impossible. | `Stopped`. Preserve existing work and report the sync blocker. |
| `Cleanup` | Associated temporary files, worktrees, and processes no longer needed are removed. | `Complete`. Report the verified result and cleanup. |

If a recovery changes the work or candidate, return to `Verify candidate`.
After a failed integrated-tree check, an authorized fix must pass verification
and integration before the landing can be complete.

## 1. Finish

Complete the current assigned task. Include only the assigned work and preserve
unrelated changes and commits. Follow the remaining steps for each affected
repository.

## 2. Verify

Identify the default branch and its remote. Fetch the remote default branch and
prepare an integration candidate containing its current tip and the assigned
work. Run the repository's required checks and the tests relevant to the task on
that candidate. Fix failures and rerun the checks. If a check or test cannot
pass, stop and report the failure.

If the work or the remote default branch changes before integration, update the
candidate and repeat verification.

## 3. Merge

If the remote default branch already contains all assigned work, continue to
sync.

When the repository uses pull requests, read and follow
[`ship-pr`](../ship-pr/SKILL.md), naming the default branch as the target. If the
linked skill is absent, locate an installed copy. If none exists, stop and report
the missing dependency.

Otherwise, merge the verified work into the default branch and push it to its
remote. Respect branch protections and use a non-force push. If the remote moves,
update the candidate and repeat verification before pushing.

If the merged tree differs from the verified candidate, run the checks on the
merged tree. A failure takes the `Integrated with failure` path above.

## 4. Sync

Fetch the remote default branch. Confirm that it contains the assigned work and
update the local default branch to the same commit without discarding existing
work. Verify that both tips match. If the local branch cannot be updated safely,
stop and report why.

## 5. Clean up and report

Remove the work's associated worktree and clean up session cruft, including
temporary files and processes that are no longer needed.

Report the checks and their results, the merged commit, the PR if used, the local
and remote sync status, and the cleanup completed.
