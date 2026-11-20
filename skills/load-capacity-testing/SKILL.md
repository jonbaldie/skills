---
name: load-capacity-testing
description: Test load capacity by running representative user journeys under increasing concurrency, bursts, and sustained traffic, measuring p95/p99 latency, error rates, queues, throughput, and resource saturation. Use when finding the boundary where the service degrades or remains healthy.
argument-hint: "[journey or service] [budget]"
disable-model-invocation: true
---

# Load capacity testing

Find the **operating boundary** of a service: the load beyond which it
degrades, and the load up to which it remains healthy. This complements
[`perffuzz`](../perffuzz/SKILL.md), which searches for costly input
shapes, and [`hill-climbing`](../hill-climbing/SKILL.md), which optimizes
one journey's latency. Those ask "which inputs or changes are slow";
this asks "how much load can the system carry, and what happens past it".

Run only in an environment you own with an explicit resource budget.
Never load-test production or a shared service without authorization.
Produce evidence and a boundary measurement; implement fixes only when the
user requests them.

## 1. Define the workload

Use the requested service or journey. Otherwise select one by usage and
consequence (see [`user-journeys`](../user-journeys/SKILL.md) for the
ranking method). Define the workload as a script a second engineer can
run unchanged:

- the journeys and their mix, grounded in observed or estimated traffic;
- the data volume, account count, and working-set size per journey;
- arrival behavior: steady concurrency, burst shape, and sustained rate
  as separate phases, not one blended number;
- the success criteria for one journey attempt (status, check, and
  durable effect), so error rates count real failures.

Record the workload's assumptions and what it omits (background jobs,
scheduled work, other tenants). A workload that never exercises a known
traffic component cannot bound the system that carries it.

Complete this step with a runnable workload, its mixture, and its known
omissions.

## 2. Establish the baseline and the budget

Pin the build, configuration, dataset, and instance sizes. Record the
environment and the resource budget: CPU, memory, instances, connection
pools, queue depths, and third-party quotas that bound the system.

Before ramping, run the workload at ordinary load and record the
baseline: throughput, p50/p95/p99 latency, error rate, and the
saturation gauges that will be watched (CPU, memory, connections, queue
lag, disk, lock contention). Warm up caches and JIT before measuring and
exclude warmup from the numbers.

Verify the harness measures the system, not itself: the load generator
must not be the bottleneck (its own CPU, connections, or ports), the
clock and percentiles must be computed over completed attempts only, and
a rerun at baseline must reproduce the baseline within recorded spread.

Complete this step when the baseline repeats within noise and every
metric has a named source.

## 3. Ramp to the boundary

Increase load in fixed steps — concurrency, burst size, then sustained
rate — holding each step steady long enough for queues and caches to
reach equilibrium (at least the longest expected queue drain). At each
step record:

- offered load versus achieved throughput;
- p50/p95/p99 latency and error rate;
- queue depths and oldest-item age, connection and thread saturation,
  memory and CPU headroom;
- recovery behavior once the step ends: how long to return to baseline.

Continue past the first sign of degradation until the failure mode is
identified: latency collapse, error-rate rise, queue growth without
bound, resource exhaustion and restart, or cascading retry load. A knee
in latency is a boundary only if it repeats; an isolated spike is noise
until proven otherwise.

If load must stop early (host budget, error runaway, provider quota),
record the step reached, the stop reason, and that the boundary is
unmeasured above it. An incomplete ramp describes where testing stopped,
not where the system fails.

## 4. Validate the boundary

Return to the candidate boundary and repeat it from a clean state. The
boundary holds only if the degradation mode and approximate load repeat.
Vary one factor at a time where it matters — concurrency with loose
locking versus a contended key, burst versus sustained — to say whether
the boundary is load-shaped or contention-shaped.

Check recovery after each validation: the system returns to baseline
behavior within a recorded time, queues drain, and no stuck operations,
leaked connections, or durable-state corruption remain. Recovery is part
of the boundary claim; a service that degrades gracefully and heals is a
different result from one that must be restarted.

Distinguish capacity from correctness: restore durable state to the known
starting point and verify counts, balances, and idempotency where the
workload touches them (see
[`failure-recovery-testing`](../failure-recovery-testing/SKILL.md) for the
invariant method). A capacity pass that silently corrupts state has
found a defect, not a boundary.

## Load-run states

Start each ramp at **Baseline** with the pinned build, workload, and
budget from step 2.

| State | Event and guard | Next state and action |
| --- | --- | --- |
| Baseline | The baseline repeats within recorded noise and harness saturation is ruled out. | Ramping. Increase load in held steps. |
| Ramping | Degradation repeats at a load step and its failure mode is identified. | Candidate boundary. Validate by clean-state repeat. |
| Ramping | The host or provider budget ends before degradation. | Blocked. Record the step reached and the stop reason. |
| Candidate boundary | The clean-state repeat reproduces the mode near the same load. | Bounded. Record the measured boundary and recovery time. |
| Candidate boundary | The repeat does not reproduce it. | Ramping. The spike was noise; continue stepping. |
| Bounded | Recovery to baseline is verified and durable state is checked. | Finished. Preserve the report in step 5. |
| Blocked | The budget or authorization extends. | Baseline. Re-verify the baseline before ramping again. |

## 5. Preserve the result

Write a report alongside the workload, harness, and measurements.
Include:

- the workload script and mixture, its assumptions, and its omissions;
- the pinned environment, resource budget, and baseline with spread;
- the ramp table: offered and achieved load, latency percentiles, error
  rates, queue and saturation gauges at each step, and recovery times;
- the measured boundary, its failure mode, the validation repeats, and
  the durable-state check;
- the exact run commands, so an independent engineer can reproduce the
  workload on the same environment.

Done when there is an independently reproducible workload, a documented
environment and resource budget, and a measured boundary at which the
service degrades or remains healthy. A run that stops before the boundary
is partial: report the highest load measured healthy and the missing
step. Tear down load generators, test accounts, and scratch data, and
verify the environment is back within its recorded budget.
