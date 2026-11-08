---
name: land-the-plane
description: "Land the plane: finish the current task, verify it, merge into the default branch, and sync local and remote."
---

# Land the plane

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
merged tree and report any failure.

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
