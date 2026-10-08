---
name: mutation-testing
description: Manually introduce small faults and check whether the existing tests catch them, with an optional automated-tool index.
---

# Mutation testing

Ask: **if this behaviour were wrong, would the tests fail?** Perform the manual
green–mutant–green loop below yourself, one mutant at a time, using direct source
edits and existing test/build commands. Reading tests or proposing mutations is
not a run.

**Procedure failure:** replacing the manual loop with a mutation framework or
custom driver, such as immediately writing a Python script to apply mutants and
collect results. Keep mutation decisions, edits, and evidence inspection in the
agent's hands; existing test/build scripts execute the checks.

## 1. Establish the target and baseline

Use the codebase, files, diff, or behaviour named by the user. Otherwise use the
codebase established in the conversation, then the current repository. Ask when
these leave multiple plausible targets. Read its agent instructions, relevant
contracts, production paths, tests, and test commands.

Record the starting revision and working-tree state, including staged, unstaged,
and relevant untracked files. Prefer a disposable copy of that exact state;
a worktree at HEAD alone omits uncommitted work. Keep evidence outside the
mutation workspace. For in-place work, save original file contents before editing
and restore only your own changes. Never use a blanket Git reset or restore.
Stop if concurrent edits make restoration ambiguous.

Use isolated test data and services. Mutants must not deploy, change live
infrastructure, contact real customers, or write to production data. For SQL,
CI, containers, or infrastructure code, use a local sandbox or disposable stack.

Before starting builds, tests, or sandbox services, inspect host CPU/load,
available memory, swap pressure, and free workspace/evidence disk space. Record a
**host budget** with measurable limits, a sampling interval, and breach durations
that trigger a stop. Base it on observed headroom, leaving capacity for existing
workloads. Default to one build/test worker, including runner-internal parallelism.
Set a finite timeout for every command, including the baseline. Defer execution
and report the blocker if the host is already outside budget.

Monitor at that interval during commands and recheck between mutants; retain
readings and stops as evidence. On a breach, stop launching work, terminate only
this pass's processes and descendants, and restore the source. Resume within the
host budget, reducing workers or narrowing checks as needed; establish a passing
baseline for any changed configuration.

Run the applicable unchanged-source checks. Record commands, working directory,
configuration, exit codes, test discovery/counts where available, and logs. Verify
that they exercise the intended implementation rather than an installed copy or
stale build. A failing, flaky, empty, or unavailable baseline blocks that scope;
report the blocker rather than count subsequent failures as kills.

**Ready:** the target state is recoverable, host headroom meets the recorded
budget, and the selected checks actually run and pass on it.

## 2. Select plausible faults

Follow the user's scope and budget. Otherwise select up to eight small mutants
across the highest-risk behaviours in scope; label this a sample. Prefer distinct
faults over many easy kills in one function. Include applicable boundaries,
negative/error paths, and observable side effects.

For each mutant, record an ID, source location, exact proposed change, intended
behaviour and its contract source, and the check expected to catch it. Name an
input or scenario that should distinguish original from mutant. Useful changes:

- Shift a boundary (`<` to `<=`), flip a condition, or replace `and` with `or`.
- Return a wrong value, drop a result field, or change a default.
- Bypass validation, swallow an error, or remove a write or cleanup action.
- Break ordering, deduplication, retry limits, or propagation between components.
- Remove a meaningful SQL predicate, container setting, or CI gate in a sandbox.

Keep each mutant to one fault and syntactically valid where possible. Mutate the
implementation, not its tests or expected values. Avoid changes already known to
be behaviourally equivalent. Calibrate per-command timeouts and the total run
budget from baseline duration, within the host budget.

**Ready:** each selected mutant has a fault hypothesis, an observation to test it,
and a bounded command. Record relevant behaviours left outside the sample.

## 3. Run the green–mutant–green loop

For each mutant, starting from the saved baseline:

1. Apply only that mutation. Save its diff and verify no other mutant is active.
2. Rebuild/reload as required and run the selected existing checks with the same
   configuration as the baseline. Capture exit status and actual test output;
   bypass stale test-result caches. Keep tests unchanged during this measurement.
3. Inspect the failure or pass. If focused checks pass, widen to relevant callers
   or integration checks within budget. First establish an unchanged-source pass
   for any newly selected command, then replay the same mutant. Report a result
   only against the checks actually run.
4. Restore the exact pre-mutation contents, including on error or interruption.
   Verify the restored diff/content and rerun the applicable checks. A restoration
   failure stops the pass; preserve recovery information and tell the user.
   If host headroom prevents verification tests, keep the source restored and
   report verification as blocked until the host budget permits a rerun.

Classify each result from evidence, not just a non-zero exit:

| Outcome | Required evidence |
| --- | --- |
| **Killed** | A test detects the intended behavioural fault; the same checks pass before and after restoration. Name the detecting test and observation. |
| **Survived** | The mutation is present in the tested implementation and the selected checks pass. State which checks; survival alone does not prove a missing test. |
| **Invalid** | The mutant cannot build, parse, or start because the edit is invalid. Compiler rejection is not a test kill. |
| **Inconclusive** | Timeout, resource exhaustion/budget stop, flakiness, infrastructure failure, stale build, no tests discovered, or an unrelated failure prevents attribution. |
| **Not run** | Safety, budget, or another stated blocker prevented execution. |

Keep timeouts separate unless a repeatable, mutation-caused violation of an
explicit termination/latency contract is established; explain any such kill.
A linter or static gate rejecting the edit is separate evidence, not a behavioural
test kill. For a CI gate itself under test, its expected exit status can be the
behaviour—but verify that through a test of the gate.

**Done:** every selected mutant has a recorded outcome and the baseline is restored.

## 4. Investigate survivors

Replay a survivor when needed to establish that the mutation was active. Trace
whether tests reach the changed path and observe its result. Classify the cause:
missing input/path coverage, weak assertion, mocked-away behaviour, insufficient
test selection, equivalent behaviour, or unresolved. Claim equivalence only with
a reason grounded in the supported inputs and contract; passing tests are not
proof of equivalence.

For each confirmed test gap, give a concrete distinguishing input and the expected
output or effect a test should assert. Ground expectations in the contract, not
just the current implementation. Keep test improvements as recommendations unless
the user also requested fixes. When fixing, prove the new test passes on original
code, fails on the same mutant, and passes after restoration. Preserve the original
survival result separately from the improved suite's result.

**Done:** each survivor has an evidenced cause or an explicit unresolved question.

## 5. Report and finish

Save a concise report and replayable mutation diffs/logs using the repository's
report convention, or a clearly named scratch directory if none exists. Include:

- Target revision plus working changes, scope, baseline commands, run/host budgets,
  resource readings and stops, and limits.
- An indexed ledger: ID, file/line, fault, checks run, outcome, evidence links.
- Confirmed gaps ranked by behavioural impact, with concrete test recommendations.
- Counts for every outcome, equivalent survivors identified separately, and
  untested/blocked areas. These are sample results, not a codebase-wide score.
- Final restoration and unchanged-source test results; any intentional test edits.

Completion requires all selected mutants accounted for, recoverable evidence,
and verified removal of every temporary mutation. Clean up only scratch resources
created by this pass, preserving its report and evidence. Link the report in the
final response and offer automation as a supplement.

## Optional automation

When the user asks for tool recommendations, automated mutation, or a CI follow-up,
read [AUTOMATED-TOOLS.md](AUTOMATED-TOOLS.md). It indexes Quality Gates tools first
and alternatives by ecosystem. Recommend the matching entry; install or run a
mutation tool only when requested. Automation supplements this manual pass rather
than silently replacing it.
