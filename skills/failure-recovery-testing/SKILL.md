---
name: failure-recovery-testing
description: Test failure recovery by injecting faults into a disposable environment — timeouts, HTTP 429/500 errors, dropped connections, duplicate webhooks, restarts, interrupted writes — then checking durable state and retries after recovery. Use when operations must survive failures without duplicate charges, missing data, or stuck operations.
argument-hint: "[workflow] [budget]"
disable-model-invocation: true
---

# Failure recovery testing

Deliberately corrupt the **conditions** under which operations execute,
not the operations themselves. Stateful testing
([finding-bugs](../finding-bugs/SKILL.md#stateful-action-sequence-testing))
generates sequences of operations under healthy conditions; this skill takes
those sequences and runs them while the network, the provider, and the
process misbehave. The question is never "does the happy path work" but
"does the system recover without violating its promises".

Inject faults only into a disposable environment you own, and confirm
provider credentials are test-mode before injecting — a disposable app
can still hold live payment keys. Never fault a production system, a
real customer account, or a shared provider without explicit
authorization. Produce evidence and reproducers; implement product fixes
only when the user requests them.

## 1. State the invariants

For the workflow under test, name the promises that must survive any
fault, in checkable form. Typical invariants:

- no duplicate charges, side effects, or outbound messages for one
  logical operation;
- no missing committed data: once an operation reports success, its
  effects are durable and visible to the next reader;
- no permanently stuck operations: every interrupted operation eventually
  reaches a terminal state (completed, safely retried, or recorded as
  failed);
- correct retry behavior: retries reuse the original idempotency key,
  back off under rate limits, and converge instead of amplifying load.

For each invariant, name the independent check that verifies it — a
direct read of the database, ledger, event log, or provider state through
a path other than the one under test. An API response is never its own
check.

Complete this step with an invariant list, each with a named independent
check and the state it reads.

## 2. Build the fault schedule

Choose the faults and when each fires during the workflow. Cover at
minimum, as applicable to the system:

- latency and timeouts (slow provider, hanging request, exhausted pool);
- HTTP 429 (with and without a retry hint) and 500-class errors;
- dropped or reset connections (before the request, after the server
  committed, after the response was sent);
- duplicate webhook or event deliveries, including replays with the same
  and with conflicting payloads;
- process restarts and deploys at each workflow phase, including mid-write;
- interrupted writes (crash or kill between the commit and the
  acknowledgement, partial multi-record writes).

A fault is defined by its position: before the operation, after the
commit but before the acknowledgement, during retry, during recovery.
The same fault at a different position is a different test.

Write the schedule as a reproducible document: operation, fault, trigger
condition (request count, clock, or sequence position), expected
behavior, and a recovery deadline — the latest time by which recovery
must complete before the run is called stuck. Record the workload and
starting state the schedule assumes.

## 3. Inject the faults

Run the workflow from its recorded starting state. Inject each fault at
its scheduled point using a local fault proxy, chaos tool, test double,
or replay harness — the smallest mechanism that reaches production code.
Record the exact injection commands and their observed behavior (did the
fault actually fire, and did the operation see it?).

For each run, capture the operation's outcome: success, expected error,
retry, or unexpected error. An unexpected error is a result to classify,
not a harness failure to retry until it disappears.

If a fault cannot be injected (the proxy cannot reach the provider, the
system masks the fault), record it as blocked with the missing mechanism
and move to the next fault. Never substitute the unaided run and report
it as faulted.

## 4. Verify durable state after recovery

Wait for recovery — retries exhausted, background workers drained, the
restarted process warm — then check each invariant through its independent
read path from step 1.

A fault run is only complete when every invariant has an observed
decision: holds, violated, or unverifiable (the check itself failed).
Violations are named with the durable-state evidence: the duplicate
charge, the missing record, the operation still pending long after its
recovery deadline.

Distinguish the fault's own blast radius from an invariant violation. A
429 that surfaces as a clean "try again" error is the system working;
a 429 retried without backoff until the provider blocks the account is
not.

## 5. Classify and preserve

Classify each fault run as:

- **Recovered** — all invariants hold through the independent checks;
- **Violated** — at least one invariant fails, with the durable-state
  evidence preserved;
- **Unresolved** — the fault did not fire, recovery never completed, or
  a check could not run;
- **Blocked** — the fault mechanism never reached the operation, so no
  recovery was exercised at all. A blocked fault is not recovered and
  is not counted as a pass.

Minimize each violation to the smallest schedule that reproduces it, then
replay it from the recorded starting state. Keep the injection schedule,
the observed outcome, and the durable-state result as three separate
records: a violated invariant with a missing schedule is not replayable,
and a schedule with no durable-state check proves nothing.

## Fault-run states

Start each scheduled fault at **Unscheduled** and track it independently.

| State | Event and guard | Next state and action |
| --- | --- | --- |
| Unscheduled | Step 2 fixes the operation, fault, and trigger position. | Scheduled. Run from the recorded starting state. |
| Scheduled | The fault fires at its trigger and the operation's outcome is captured. | Running. Execute recovery to its end. |
| Scheduled | The injection is attempted but the fault does not fire. | Unresolved. Record that the conditions were healthy for this run. |
| Scheduled | The fault mechanism cannot reach the operation. | Blocked. Record the missing mechanism. |
| Running | Recovery completes and every invariant has an independent check result. | Classified. Apply step 5. |
| Running | Recovery does not complete within the recovery deadline. | Unresolved. Record the stuck operation. |
| Classified | Every invariant holds through its independent check. | Recovered. Preserve the schedule, outcome, and checks. |
| Classified | At least one invariant fails. | Violated. Minimize and replay before preserving the report. |
| Classified | A check cannot run or recovery misses its deadline. | Unresolved. Record the missing check. |
| Violated | Minimization fails to reproduce the failure. | Unresolved. Record the flaky observations; do not report a defect. |
| Blocked | The fault mechanism becomes available. | Scheduled. Run from the recorded starting state. |
| Scheduled or later | The build, workflow, or check path changes. | Unscheduled. Rebuild the schedule from step 2 before reusing the outcome. |

## 6. Preserve the result

Write a report alongside the schedules and captures. Include:

- the invariant list with their independent checks;
- each fault's reproducible injection schedule and observed outcome;
- the independently checked durable-state result per invariant;
- recovered, violated, unresolved, and blocked runs, with minimized
  replays for the violations and the missing mechanism or check for
  each blocked or unresolved run;
- exact injection, recovery, and verification commands and the
  environment they ran in.

Done when each fault has a reproducible injection schedule, an observed
outcome, and an independently checked durable-state result. A run that
ends with unresolved or blocked faults is a partial result; report them
with their missing check or mechanism. Tear down every fault proxy,
replay harness, and
test-owned process created by the pass, and verify nothing remains.
