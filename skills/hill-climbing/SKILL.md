---
name: hill-climbing
description: Improve user-perceived performance through measured experiments and regression ratchets.
argument-hint: "[journey or hot path] [budget]"
disable-model-invocation: true
---

Turn a slow user journey into a repeatable optimization loop.

1. **Choose the hill.** Use the requested journey; otherwise select one by
   usage and time lost. Record its scope, target, and work budget. Measure from
   user action to usable result, separating client and server work. Establish
   comparable baselines by platform, workload, and percentile.

2. **Build feedback.** Trace the slow stretch and reproduce it in a benchmark.
   Save the workload, environment, commands, and baseline. Prefer repeatable
   work counts—such as instructions, renders, or layout recalculations—for
   rapid iteration. Before adopting a counter, demonstrate that reducing it
   also reduces wall-clock latency on the same representative workload. Replace
   flaky or misleading benchmarks.

3. **Climb.** Profile, change one bottleneck, and rerun the benchmark and
   correctness checks. Establish tests for affected behaviour before optimizing
   it. Keep changes whose gains exceed measurement noise and justify their
   maintenance cost. Preserve before-and-after evidence for each retained change.
   Save the exact pre-experiment state before each edit, including existing work.
   Use the experiment lifecycle below before starting another edit.

4. **Roll out.** Follow the project's review and deployment process within the
   user's authorization. Keep patches small enough to review. Present
   user-perceptible tradeoffs with screenshots or recordings for the owner to
   decide. Protect risky changes with a temporary flag and staged rollout.

5. **Verify in the field.** Compare real-user measurements by build and platform
   under comparable conditions. Check correctness and visual behaviour alongside
   latency. Disable or revert a regression through the authorized rollout
   process, then iterate. When deployment or telemetry is unavailable, label the
   result lab-only and record the pending check.

6. **Ratchet.** Protect confirmed wins with stable CI ceilings that fail on
   regression and tighten when measurements improve. Keep noisy timing in
   monitoring. Retire rollout flags once verification is complete.

7. **Repeat within scope.** Find the next slow stretch, adding instrumentation
   where current metrics miss user-visible delays. A target is a checkpoint;
   continue until the budget expires, progress is blocked, or further gains no
   longer justify complexity. Report measured gains, retained guardrails,
   pending field checks, and the stopping reason.

## Experiment and rollout states

Start at **Baseline**. Keep the measured revision, workload, environment, and
check configuration with every result. If unrelated code, the workload,
environment, or check configuration changes, establish a comparable baseline
before evaluating another experiment.

| State | Event and guard | Next state and action |
| --- | --- | --- |
| Baseline | Feedback tracks user latency and the baseline checks pass. | Experiment. Change one bottleneck. |
| Experiment | Checks pass, the gain exceeds noise, and maintenance cost is justified. | Retained. Save the comparison. |
| Experiment | Any acceptance condition fails or the experiment stops early. | Restoring. Remove only this experiment's edits. |
| Restoring | Exact pre-experiment contents and baseline checks are verified. | Baseline. Try another hypothesis within budget. |
| Restoring | Restoration is ambiguous or verification fails. | Blocked. Preserve recovery evidence and resolve the failure before another experiment. |
| Retained | Review and rollout authorization permit deployment. | Field check. Follow steps 4 and 5. |
| Retained or field check | Deployment or telemetry is unavailable. | Lab-only. Record the pending field check without claiming a field win. |
| Lab-only | Deployment and comparable telemetry become available. | Field check. Run the pending check. |
| Field check | A regression appears. | Rollback. Disable or revert through the authorized process and verify recovery before iterating. |
| Rollback | Recovery is verified. | Baseline. Reproduce and investigate the regression. |
| Rollback | Recovery fails or authorization blocks recovery. | Blocked. Report the active rollout state and required action. |
| Field check | Comparable field data confirms the win and correctness. | Confirmed. Apply step 6, then choose the next stretch within scope. |

End the pass only at the stopping conditions in step 7, with every experiment
retained or restored. A blocked recovery remains incomplete and must be reported.
