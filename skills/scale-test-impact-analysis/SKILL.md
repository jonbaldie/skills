---
name: scale-test-impact-analysis
description: Scale test impact analysis when CI growth causes listener backlog, stale test selection, or memory pressure. Use when designing a test-selection service for agent-driven CI growth.
---

# Scale test impact analysis

Make test-selection state fresh enough to trust under growing CI load. Treat listener throughput, history freshness, and selection correctness as separate requirements: faster ingestion alone does not make selection safe.

Work within the requested scope. For an assessment, produce an evidence-backed plan. For implementation, work through validation and cutover. Get approval before changing production resources, selection policy, or CI gates.

## 1. Trace one result through the system

Inspect the CI configuration, listener, history storage, selector, and operational telemetry. Follow a real job result from completion to its effect on a later selection decision.

Record:
- **Listener:** how results arrive, how far back they can be fetched, and when they are acknowledged.
- **History:** where per-test state lives, who writes it, and which ordering rules affect selection.
- **Selector:** how changed packages and past results determine the selected tests; how it treats new, fixed, flaky, and widespread-failing tests.
- **Recovery:** what happens after a restart, duplicate delivery, missing result, or stale history.
- **Ownership:** who can approve policy changes, operate the service, and respond to alerts.

**Done:** each stage has a concrete code/configuration pointer or an explicit unknown. Every unknown affecting correctness or recovery has a way to resolve it. Keep documented invariants separate from assumptions.

## 2. Instrument and reproduce the bottleneck

Use a window covering peak traffic, overnight/weekend activity, and at least one restart or incident when records exist. Record the window and data source for every measurement:
- Arrival and completion rates, in the same units; distinguish jobs from individual test results.
- Backlog size and oldest pending-event age.
- Time from CI completion to listener capture, and from capture to selector-visible history.
- Dropped/missing results, retries, duplicates, and unrecoverable source-history gaps.
- CPU, memory growth, restart frequency, selector latency, and operating cost.

Reconcile **unique results** across each stage:

`opening backlog + arrivals = completions + closing backlog + explicitly accounted losses`

An acknowledged result awaiting history rollup is still pending at the next stage. Count retries separately so repeated processing cannot conceal missing results.

Agree on numeric budgets for history freshness, selector latency, recovery time, acceptable loss, and cost. For implementation, add missing metrics and verify that the agent can query them and reconcile the flow. Reproduce the backlog or memory-growth failure with representative traffic in an isolated environment; retain the workload for before/after comparisons. Profile an isolated worker or approved canary rather than risking the only production instance.

For assessment-only work, name missing instrumentation and mark unsupported conclusions unverified. If implementation is blocked by access or approval, report the blocker instead of treating a telemetry plan as working instrumentation.

**Done:** the agent can retrieve the measurements, the workload exposes the limiting stage, every discrepancy is explained or tracked as a correctness defect, and each budget has an owner. An assessment may finish with explicit evidence gaps; an implementation cannot claim this gate passed while those measurements are missing.

## 3. Choose the durable fix and release target

Model sustained traffic, peak bursts, and backlog recovery separately. Agent activity raises the overnight floor while human approvals still create bursts.

Plan capacity and its expansion path against these growth scenarios:
- Current load.
- 10–20× current load for a new design, within the agreed budget.
- 25× current load within two quarters, including a path to add capacity.

For a backlog of `B` results and recovery budget `T` seconds:

`required processing rate >= arrival rate + B / T`

Use measured throughput at the acceptable latency and memory limits, not core count or theoretical capacity. Identify the next bottleneck after the proposed change.

When process-owned history blocks horizontal scaling, externalize it. Treat larger instances, package workers, and restarts as bridges only when needed to finish that redesign. For other bottlenecks, choose the fix supported by the measurements. Compare total cost: infrastructure, repeated engineering, and incidents. Higher running cost can be justified by a durable scaling path.

A bridge needs an owner, an expiry, and enough runway to finish and validate the durable fix. With exponential growth and a known doubling time:

`capacity runway = doubling time × log2(capacity / current load)`

Label unsupported estimates. Restarts count as mitigation only if recovery does not compound the backlog or lose results.

Set a numeric release-load target, including burst and recovery requirements, within the approved budget. Measure capacity at that target; use higher-load tests where practical to validate the expansion path. The 10–25× scenarios are planning horizons, not unconditional release gates.

**Done:** select a durable fix and measurable release target; identify the next scaling limit and how to add capacity toward the growth scenarios. Any bridge has enough estimated runway. Escalate an unaffordable target rather than silently weakening correctness.

## 4. Design around the smallest ordering boundary

For an implementation or redesign, read [IMPLEMENTATION-CHECKS.md](IMPLEMENTATION-CHECKS.md) before changing the pipeline.

Identify what actually requires serialized updates: a test, a package, or another key. Prove that updates across different keys can proceed independently before partitioning them. Package sharding is useful only when package-local ordering is sufficient; it leaves process-held state and hot-package limits to address.

Prefer this shape when listener-owned history is the bottleneck:

```text
CI results → stateless listeners → shared append-only journal
                                         ↓
                              keyed history materializer
                                         ↓
                              per-test history → selector
```

Listeners append results and release local state. The materializer rolls the journal into selector-readable history on a cadence that fits the freshness budget. Workers scale independently of history ownership.

Use the repository's existing storage and messaging capabilities where they satisfy recovery and ordering requirements. An in-memory store is an option, not a requirement; its persistence or source-replay guarantees must cover the allowed outage window. Measure the materializer and store as potential next bottlenecks.

Keep the selection algorithm unchanged during a capacity redesign unless policy changes are explicitly in scope. Choose a conservative fallback for stale or incomplete history: expand to the affected package suite, then the full suite if package relevance is unknown. Keep mandatory gates intact.

**Done:** the design specifies ordering, acknowledgement, replay, recovery, fallback, and capacity for every stateful stage. Every production behavior change is identified for approval.

## 5. Build a working result-to-selection path

Implement the chosen design. For the journal-based redesign, build one vertical slice: listener append → journal rollup → per-test history → selector read. Feed it a real CI result and verify its effect on a later selection decision.

Run multiple listener workers against the shared journal. Route results for the same test/package through different workers, then restart or replace a worker. Verify that any listener can handle any result without owning persistent test history; enforce ordering at the history-update boundary instead.

**Done:** executable code carries the result through every stage, worker replacement preserves history, and tests demonstrate interchangeable listeners. A design document alone does not complete this step.

## 6. Prove correctness and horizontal scaling

Use the validation matrix in [IMPLEMENTATION-CHECKS.md](IMPLEMENTATION-CHECKS.md). Replay the retained workload against the new pipeline and compare its resulting history and selections with the approved behavior. Compare one listener with multiple listeners under the same offered load; show that adding workers increases processing capacity until the next measured bottleneck, while keeping memory bounded and results accounted for.

Separate two questions:
- **Parity:** does the new pipeline preserve the intended ordering and selection behavior?
- **Safety:** does selection include the tests required by policy? Agreement with an old, stale selector alone is insufficient evidence.

**Done:** correctness cases pass; release-target runs meet freshness, latency, recovery, and cost budgets; event reconciliation closes; horizontal scaling is demonstrated. Distinguish measured capacity from extrapolated growth headroom and record untested limits.

## 7. Canary and tune until stable

Prepare rollback before routing production selection through the new path. Shadow it first, then canary a bounded traffic slice with comparable baseline traffic. Advance only while reconciliation, freshness, and selection checks hold. On a threshold breach, restore the approved path or conservative fallback and preserve diagnostic evidence.

Agree on a tuning time budget, spending ceiling, and settings the agent may change. Within those bounds, repeat:
1. Query the metrics and identify the limiting stage.
2. Change one setting, starting with journal capacity or listener count when supported by the measurements; adjust rollup cadence/batch size or partitioning when those stages limit progress.
3. Compare equivalent traffic windows. Retain improvements and revert regressions before the next experiment.

Continue until backlog stops growing and freshness meets the target, or a budget or rollback threshold is reached. Journal retention must cover the measured outage and replay window; worker additions must improve end-to-end freshness, not merely move backlog downstream.

Persist each experiment's workload, settings, measurements, decision, and next action in a repository-local record so another session can resume. Configure ongoing monitoring and notifications only when authorized; otherwise hand over the metric queries and thresholds without claiming continued observation.

**Done:** the agreed observation window covers representative peak and overnight load; budgets hold without growing backlog; rollback is exercised; the experiment record, alerts, operating limits, runbook, and on-call ownership are recorded. If tuning stops at a budget or access limit, report the unresolved target and leave the approved safe path active.

## Deliverable

Return a short report with:
1. Baseline evidence and unresolved unknowns.
2. Chosen change, rejected alternatives, and estimated runway.
3. Validation results against the release target and budgets; measured versus projected growth capacity.
4. Cutover/rollback status, remaining risks, and owner actions.

## Source

Derived from [Anthropic's test impact analysis scaling account](https://claude.com/blog/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic). The article supplies the growth scenarios, shrinking patch runway, listener/selector freshness problem, and journal-based redesign. Reconciliation equations, rollout gates, and failure checks here operationalize those lessons; they are not claims about Anthropic's unpublished implementation.
