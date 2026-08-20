---
name: finding-bugs
description: Find reproducible bugs in existing code. Use for bug-finding audits and automated exploratory testing. Known bugs go to diagnosis; established fixes go to implementation.
---

# Find bugs

Return a minimized reproducer, or a bounded report of what you searched and what to try next.

## 1. Pick a target

Inspect tests, public interfaces, recent changes, and domain rules. Pick a small, high-impact target with a clear automated check. Name the expected behaviour and visible failure.

## 2. Build a repeatable test

Reuse a focused test or build the smallest deterministic test harness. Record inputs, seeds, schedules, and external responses. Reset state; limit time and memory. The same case must produce the same result in a fresh process.

## 3. Decide what counts as a bug

A result is a bug only when it breaks expected behaviour supported by documentation, an existing regression, or an independent reference case. Use the strongest available check: sanitizer, crash, assertion, timeout, invariant, state model, round trip, reference comparison, deadlock, bounded liveness rule, or end-to-end invariant.

Treat an unproven result as a lead. Check every ignored case, report it as a blind spot, and tighten the check when it conflicts with expected behaviour.

## 4. Search

Set a time or execution budget. Choose one primary method:

- Use coverage-guided fuzzing with structured seeds and runtime detectors for input boundaries.
- Generate properties and command sequences for stateful logic; shrink failures.
- Use differential or metamorphic testing when results or transformations can be compared.
- Control schedules, time, failures, and message order for concurrent code.
- Use static analysis for rules that span the codebase.
- Use symbolic or concolic execution for a hard-to-reach branch.
- Use mutation testing to find missing properties and assertions.

Record the exact command, duration, executions, input or coverage growth, and failures. Use feedback to guide the search. If it stalls, strengthen the check or improve the inputs and models. Add a second method only when it reaches different cases. Stop when the budget is spent or a failure reproduces.

## 5. Confirm each result

Reproduce every failure in a fresh process. Minimize the input or trace. Group failures with the same cause. Identify the broken behaviour and source location. Classify each result as a confirmed bug, intended behaviour, test-harness bug, or unclear requirement.

## 6. Preserve confirmed bugs

For each confirmed bug, define a deterministic regression and improve the relevant input set, generator, model, schedule suite, or static-analysis rule. When changes are authorized, add and verify them. Otherwise report exactly what to add.

## Report

Report the target and expected behaviour; test harness and commands; check and blind spots; search method, budget, and results; minimized bugs; and next improvement.

For every confirmed bug, write a **Bug explanation** in ASD-STE100 Simplified Technical English. Say what the bug means to an end-user.

A clean search proves only that no bug appeared within the stated target and budget.
