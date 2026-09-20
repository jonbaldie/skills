---
name: perffuzz
description: Find pathological inputs through performance-guided mutation and preserve reproducible hotspot evidence.
argument-hint: "[target or scope] [budget]"
disable-model-invocation: true
---

# PerfFuzz

Search for inputs that make production code do disproportionate work. Adapt
the harness to the repository's language and runtime; execute the real target
and retain inputs using measured performance feedback.

The defining mechanism is **independent maxima**: each instrumented location
has its own highest observed execution count and a witness input. This follows
[PerfFuzz (ISSTA 2018)](https://conf.researchr.org/details/issta-2018/issta-2018-Technical-Papers/1/PerfFuzz-Automatically-Generating-Pathological-Inputs).
The harness, budgets, and validation below are a portable workflow around that
mechanism. Produce evidence and reproducers; implement product fixes only when
the user requests them.

## 1. Bound the campaign

Use the requested target. Otherwise inspect entry points, tests, and existing
fuzzing or benchmark infrastructure, then select one input-driven operation
whose cost plausibly depends on input shape. Trace its production call path.

Record the input format, acceptance rules, size variables, starting state, and
an ordinary seed that reaches the operation. Include state setup or operation
sequences when they are part of the input. Use isolated local data and services.

Honor the user's budget. Otherwise use a ten-minute search with a separate
five-minute replay and reduction allowance after setup. Choose and record
numeric input-size, per-execution timeout, memory, and corpus-storage limits
from the target's normal workload and available resources. Enforce the limits
in the runner, including termination of child processes.

Complete this step with one named target, a reachable seed, an evidence
directory, and explicit limits. Record setup blockers against that target.

## 2. Establish trustworthy feedback

Reuse compatible fuzzing infrastructure or build the smallest local harness
that invokes the production operation. Reset target state and counters between
inputs. Save the build revision, runtime, configuration, random seed, and exact
build and run commands.

Collect a map from stable production locations to execution counts, using
runtime-supported instrumentation. Verify that counts retain magnitude beyond
boolean coverage and that overflow or saturation cannot masquerade as progress.
For C/C++ with compatible tooling, consult the
[original implementation](https://github.com/carolemieux/perffuzz) for its
instrumented compiler and performance mode; resolve commands against the
installed version.

If location counts are unavailable, use separate counters for meaningful work
such as comparisons, traversals, or queries. Label this **adapted feedback**
and name the blind spots. With only elapsed time available, label the run a
**timing-guided fallback**; establish repeatable timing before using it to
select inputs. Ordinary coverage alone cannot establish performance progress.

Replay the ordinary seed and a controlled variation at least three times each.
Check output validity, state reset, and that the feedback measures target work
and responds to the variation. Exclude harness setup from the measured region.
For timing, control warmup and cache state and record the observed spread.

Complete this step when the harness runs, feedback is repeatable enough to
distinguish improvement, and limits terminate an over-budget trial. If usable
feedback cannot be established, report the blocker and preserve the harness.

## 3. Mutate toward independent maxima

Start with a small corpus of accepted examples and relevant boundary cases.
Keep malformed-input rejection paths separate from successful-operation paths.
Initialize each location's maximum from the seed executions.

Run an automated loop until the search budget expires:

1. Select a corpus input, giving retained witnesses recurring mutation turns.
2. Mutate it within the size limit. Mix small edits, splicing, and structural
   changes appropriate to the input: repetition, ordering, nesting, shared
   prefixes, or operation sequences. Keep enough structure to reach the target.
3. Execute and collect status, validity, size, and the feedback map.
4. Retain an input if it improves any location's maximum, even when its total
   work decreases. Update those maxima and preserve their witnesses. Keep
   coverage-expanding seeds too when coverage is available.
5. Save the input, parent, mutation, measurements, and retention reason. Replay
   unstable improvements before promotion. Deduplicate corpus entries while
   preserving a witness for every current maximum.

Keep maxima comparable within a fixed build, configuration, and input-size
bound. If changing the bound, start a separately recorded campaign. For adapted
feedback use one maximum per work counter; for timing use repeated measurements
whose improvement exceeds the established noise.

Save crashes, timeouts, and memory-limit hits separately for replay. A timeout
is a censored observation, not a completed execution count or measured runtime.
Record executions, valid-input rate, corpus growth, and improvements over time.

Complete search at the declared budget or an enforced resource limit. Save the
corpus and stop reason even if no pathological input emerges. A plateau describes
this search; it does not prove that the target has no worse inputs.

## 4. Validate and reduce witnesses

Group promising witnesses by the production hotspot they exercise. Within the
remaining allowance, compare each group's strongest witness with ordinary
inputs of comparable size and semantic workload. Replay from the same starting
state at least five times and retain raw measurements and their spread.

Check actual runtime or resource impact in the ordinary build too. Trace the
observed work to reachable production code. Distinguish input-shape sensitivity
from simply supplying more data, instrumentation overhead, and environmental
noise. Use several controlled input sizes to investigate scaling; support any
Big-O claim with source analysis as well as measurements.

Reduce each confirmed witness by removing or simplifying input while preserving
validity, the implicated hotspot, and an explicit cost or slowdown threshold.
Replay every accepted reduction against that predicate. Preserve both the
original high-cost witness and the smallest confirmed reduction reached within
budget. A coverage-only minimizer may discard the expensive behaviour.

Complete validation when each candidate is confirmed, rejected with evidence,
or unresolved with the missing check recorded. Budget exhaustion leaves pending
candidates unresolved. A high counter alone is a search result; calling it a
performance defect requires demonstrated impact against a grounded expectation.

## 5. Preserve the result

Write a report alongside the harness, corpus, and measurements. Include:

- target, production call path, feedback mode, instrumentation blind spots,
  limits, actual search effort, and stop reason;
- confirmed findings ranked by demonstrated impact, with source locations,
  input sizes, baseline comparisons, repeat measurements, and likely cause;
- exact setup and replay commands, environment details, original witnesses,
  reduced inputs, and reduction predicates;
- rejected and unresolved candidates, unexercised paths, and the next useful
  experiment where evidence is incomplete.

For a run without confirmed findings, report the observed maxima and tested
scope. Check that saved replay commands resolve to preserved artifacts. Remove
only campaign-owned temporary processes and scratch data, keeping the evidence.
Finish with the report path and the strongest supported result.
