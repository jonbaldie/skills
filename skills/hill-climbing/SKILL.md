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
