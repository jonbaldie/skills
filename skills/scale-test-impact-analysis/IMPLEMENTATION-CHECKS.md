# Implementation checks

Use these checks when implementing or redesigning the result pipeline. Record the chosen behavior and evidence for every applicable case. Mark a case inapplicable only with a reason.

## Result contract and recovery

Define these semantics before coding; field names and storage technology belong to the repository:

| Concern | Required decision |
| --- | --- |
| Identity | Stable identity for a result, including job/run, test, and attempt. A retry delivery is distinguishable from a genuine test rerun. |
| Relevance | Revision and package/test identity sufficient to associate results with the intended history. |
| Ordering | The ordering key and authoritative sequence or timestamp; tie-breaking and late-arrival behavior. Arrival order is valid only if the source guarantees it. |
| Acknowledgement | The point where an input becomes recoverable after worker failure. Acknowledge after the journal write satisfies that recovery contract. |
| Idempotency | Replayed or concurrently delivered results affect history once. Bound deduplication retention against the replay window. |
| Materialization | Applying history and advancing a checkpoint cannot skip an update after a crash. Use atomic commit or replay-safe updates. |
| Retention | Journal and upstream retention cover outage, catch-up, and replay. Preserve pending records until materialization is recoverable. |
| Freshness | Selector-visible watermark exposes lag; missing and stale histories invoke the approved fallback. |
| Isolation | Independent keys can progress concurrently. Define behavior for a hot key, unavailable store, and malformed event. Account for quarantined events. |

## Correctness matrix

Use known result sequences and policy expectations. Assert observable history, checkpoints, reconciliation, and selected tests—not just that a worker returned successfully.

| Exercise | Evidence required |
| --- | --- |
| Ordered and out-of-order results | Same intended history according to the ordering contract, including ties and late events. |
| Duplicate delivery and genuine rerun | Duplicate has one effect; a genuine rerun remains a distinct result. |
| Listener crash around append/acknowledgement | Recovery loses no accepted result and replay adds no duplicate history effect. |
| Materializer crash around update/checkpoint | Restart neither skips nor double-applies a result. |
| Multiple workers and rebalance | Concurrent processing preserves per-key order and complete history. |
| New or repaired test | Becomes eligible according to policy within the freshness budget; unknown history takes the safe fallback. |
| Flaky or widespread-failing test | History transitions produce the approved selection behavior without silently removing mandatory gates. |
| Missing history or source-retention gap | Gap is visible, reconciliation identifies it, and selection falls back safely. |
| Store outage and malformed input | Recovery is bounded; valid inputs continue where isolation allows; every pending/quarantined result remains accounted for. |

## Load and shadow checks

Generate load through the supported ingestion path with realistic job-to-test fan-out, event sizes, package skew, and selection-query traffic. Run long enough to expose memory growth and repeated rollups; record duration and limitations.

Exercise current, 10–20×, and 25× load, plus bursts, a hot package, and an outage followed by catch-up. Measure end-to-end freshness, backlog growth, memory, selector latency, reconciliation, and cost. A short peak-throughput test does not establish sustained capacity.

Replay equivalent input into old and new pipelines. Compare history and selection at equivalent input watermarks, so listener lag does not masquerade as an algorithm difference. Explain every mismatch.

Validate selection safety independently with known affected tests, dependency/package rules, and periodic full-suite runs or an approved equivalent. Classify failures outside the selected set: a passing full suite alone cannot prove future selection completeness.

## Cutover and rollback

Before canarying, record:
- Numeric promotion and rollback thresholds for lag, missing results, unexplained selection differences, memory, latency, and cost.
- A representative observation window and bounded canary population.
- How to restore a fresh prior selector or activate conservative selection; stale prior state is not a safe rollback by default.
- How journal/checkpoint compatibility and any state migration permit replay or rollback.
- Alerts for oldest-event age, selector-history age, reconciliation gaps, and projected retention exhaustion.
- The operator, commands, and evidence needed to confirm recovery.

Keep the prior recovery path and required journal data until the rollout observation window closes and rollback has been exercised.
