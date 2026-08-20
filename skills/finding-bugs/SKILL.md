---
name: finding-bugs
description: Find reproducible defects in an existing codebase with a tight, guided counterexample loop. Use for bug-finding audits and selecting automated test or analysis loops; use diagnosis or implementation workflows when the defect and fix are already established.
---

# Counterexample loop

Produce **counterexamples**, not suspicions.

**TIGHT** means a fast, deterministic, isolated experiment. **RED** means an observable contract violation. **GUIDE** means each execution informs the next. **COMPOUND** means every confirmed finding improves future detection.

Return either a minimal, reproducible case that goes **RED**, or a bounded result: targets searched, oracle, budget, and the next stronger loop.

## MAP

Inspect existing tests, scripts, public boundaries, recent changes, and domain contracts. Rank candidate targets by:

`risk × exposure × change rate × oracle strength ÷ execution cost`

Choose the highest-ranked target with a credible oracle. Prefer a narrow public boundary over a whole-system test.

Complete when the target, contract, and expected **RED** signal are named.

## TIGHT

Reuse an existing focused harness when it covers the target. Otherwise build the smallest harness that records inputs, seeds, schedules, and external responses. Reset state and bound time and memory.

Complete when a case runs cheaply and produces the same observation in a fresh process.

## RED

Choose the strongest available oracle:

| Target shape | Oracle |
|---|---|
| Native or runtime-sensitive code | Sanitizer, crash, assertion, timeout |
| Domain or stateful logic | Invariant, conservation law, state-machine model |
| Parser, serializer, codec | Validity, round trip, reference parser |
| Independent versions or implementations | Differential result |
| Concurrent or async component | Safety invariant, deadlock, bounded liveness |
| Security or API flow | Source-to-sink rule with project-specific barriers |
| Narrow guard-heavy code | Assertion or property at the boundary |

Prove the oracle against a documented contract, existing regression, or independently derived reference case. Classify an unproven oracle as a lead.

**Audit every oracle exemption against the target contract.** Each exemption is a declared blind spot. Report it and add a stricter property when the contract disagrees.

Complete when the harness visibly goes **RED** for a contract-violating case.

## GUIDE

Choose one primary loop for the target:

- Input boundary: coverage-guided fuzzing with structured seeds and applicable runtime detectors.
- Semantic or stateful logic: generated properties and command sequences, shrunk on failure.
- Independent implementations or valid transformations: differential or metamorphic testing.
- Concurrent code: controlled schedule, time, failure, and message-order exploration.
- Whole-codebase flow: static data-flow analysis with project-specific sources, sinks, and barriers.
- Hard-to-reach narrow branch: symbolic or concolic execution.
- Weak test suite: mutation testing to select missing properties and assertions.

Use coverage, constraints, schedule choices, or surviving mutants as **GUIDE**. Coverage is search telemetry; **RED** is defect evidence.

Complete when the selected loop runs against the **TIGHT** target with the **RED** oracle active.

## SEARCH

Run a short bounded campaign first. Record the exact command, duration, executions, corpus or coverage growth, and each **RED** result.

At a plateau, strengthen the oracle when explored behaviour lacks a meaningful failure signal; improve seeds, generators, dictionaries, or models when valid states remain unreachable; select a secondary loop only when it searches a distinct missing state space.

Complete when the budget is spent or a **RED** result reproduces.

## REDUCE

For every **RED** result, reproduce it in a fresh process, minimize its input or trace, deduplicate by root cause, and identify the violated contract and relevant source location.

Classify each result as a confirmed defect, intended behaviour, harness defect, or unresolved contract ambiguity.

Complete when another engineer can run and understand the finding without the search infrastructure.

## COMPOUND

For each confirmed defect, preserve the minimized reproducer as a deterministic regression and add it to the relevant corpus, property generator, model, schedule suite, or static-analysis rule.

For discovery-only work, report the proposed regression and detector improvement. When implementation is authorized, add and verify the regression before closing the finding.

## Report

Report the target and contract; **TIGHT** harness; **RED** oracle and exemption audit; **GUIDE** loop and exact commands; budget and telemetry; minimized findings; detector blind spots; and the next improvement.

A passing campaign means no defect was found under its oracle and budget. It does not establish correctness.
