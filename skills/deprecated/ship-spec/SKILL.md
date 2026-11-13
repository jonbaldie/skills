---
name: ship-spec
description: Implement a parent spec's child issues serially and ship each to one target branch.
---

# Ship a spec

Require a parent spec.

This skill is deprecated and is not distributed by the installer.

## Shipping states

Start in `Resolve target`. Track the parent, dependency-ready unfinished
children, selected child, verified commit, and remote target tip.

| State | Event and guard | Next state / action |
| --- | --- | --- |
| `Resolve target` | The target is established. | `Select child`. Refresh the parent and child issues. |
| `Resolve target` | The target is ambiguous. | `Await target`. Ask once with the proposed target and wait. |
| `Await target` | The user names the target. | `Select child`. |
| `Select child` | A ready unfinished child exists. | `Implement child`. Use a dedicated branch from the latest target. |
| `Select child` | Unfinished children exist but none is dependency-ready. | `Blocked`. Report the unmet dependencies. |
| `Implement child` | Acceptance criteria, review resolution, and required checks all pass. | `Integrate child`. Merge and push to the target. |
| `Implement child` | A criterion or check fails. | Stay in `Implement child` to fix it, or report the blocker. |
| `Integrate child` | The target moves or integration fails. | `Implement child`. Update against the latest target and repeat affected verification. |
| `Integrate child` | The completed commit is reachable from the remote target. | `Select child`. Mark the child complete and refresh the issues. |
| `Select child` | Every child is complete on the remote target. | `Verify parent`. Check the parent criteria and full suite there. |
| `Verify parent` | Parent criteria and the full suite pass on the current remote target. | `Complete`. Report the result. |
| `Verify parent` | Criteria fail or the target changes. | Re-enter `Implement child` for remaining work or repeat `Verify parent` on the changed target. |

Resolve the target branch before starting:

1. Use the branch provided by the user.
2. Otherwise, use the repository's obvious default or development branch.
3. If ambiguous, ask the user once, proposing `origin/main`.

Then repeat:

1. Refresh the parent spec and its linked child issues.
2. Select one ready, unfinished child issue. Order by dependencies, then issue
   number.
3. Create a dedicated branch from the latest target branch.
4. Implement that issue only, following its acceptance criteria and the
   repository's development and review instructions.
5. Verify the child before integration. Require:
   - its acceptance criteria are satisfied;
   - review findings are resolved;
   - required checks pass.
6. Integrate the completed branch into the latest target branch and push it.
7. Confirm the completed commit is reachable from the remote target branch
   before selecting another issue.

Complete only when every linked child issue and the parent spec's acceptance
criteria are satisfied on the remote target branch, with the full test suite
passing there.
