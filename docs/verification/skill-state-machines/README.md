# Verification record

The [inventory](../../skill-state-machines.md) covers all 27 skill definitions.
Twenty-one now have operative transition tables. Six remain procedures or
classifiers. Skill frontmatter is unchanged, including invocation controls.
Tutor remains in progress and ship-spec remains deprecated and excluded from
installation.

## Reproduced defects

The [before-and-after transcript](regressions.txt) records two injected failure
cases against the actual shell helpers:

- A failed source copy previously deleted an installed tree. Replacement now
  stages the source first. A failed publication restores the previous tree.
- A missing later canonical skill previously changed earlier destination entries
  and removed retired skills. All managed sources now validate before copying.

Existing tests exposed two Bash 3.2 defects. A helper local variable shadowed a
readonly caller variable. Empty-set retirement expanded an unset array. Agent
resolution and comment-only manifest retirement now pass on Bash 3.2.

Independent probes also verified replacement of a destination symlink without
changing its target, restoration of that link after failed publication, and
retention of the backup path when publication and restoration both fail.

The helper protects individual tree replacements. It does not provide an atomic
transaction across trees or destinations. The skill documents partial results
and recovery from interruption between replacement moves.

## Instruction review

Independent readers applied the edited skills to 26 supplied situations without
performing the underlying operations. Ten covered learning and reduction,
seven covered resumption and shipping, and nine covered testing and performance.
They identified two conflicts that were corrected: merged PRs cannot be
retargeted, and incomplete summary lineage must explicitly return to rebuilding.

The cases covered used tutor repair attempts, understanding without continuation
permission, changed BMF premises, failed and nonshrinking reductions, stale PR
heads, queue ejection, failed leases, failed post-merge checks, dirty checkouts,
mutation rebaselining, blocked cleanup, deferred findings, incompatible fuzzing
measurements, rejected experiment restoration, result replay, and stale rollback
selectors.

This is instruction review. It does not prove real tutoring, summary quality,
performance findings, pipeline recovery, production rollback, or forge behavior.
No real merges or production operations were performed for these cases.

## Repeatable checks

Run the repository checks with Python's `pytest` dependency installed:

```bash
bash -n install.sh tests/*.sh skills/sync-jonbaldie-skills/scripts/*.sh skills/sync-jonbaldie-skills/scripts/lib/*.sh
shellcheck -e SC2016 install.sh $(find tests -type f -name '*.sh' ! -name 'install-ship-spec.sh' -print) skills/sync-jonbaldie-skills/scripts/*.sh skills/sync-jonbaldie-skills/scripts/lib/*.sh
TMPDIR=/private/tmp bash tests/run-all.sh
```

The isolated installer suite needs Docker and macOS `sandbox-exec`. It was run
from a standalone clone because its containers cannot resolve a linked worktree's
Git metadata outside the mounted checkout. `/private/tmp` avoids macOS temporary
path aliases in exact-path assertions. The suite was not skipped in the final
run. Sanitized results are attached in [checks.txt](checks.txt).

The artifact check also verified unchanged parsed frontmatter, all 21 workflow
tables, all 27 inventory entries, and every local Markdown link in the changed
documents. These structural checks cannot establish the meaning of a transition.
