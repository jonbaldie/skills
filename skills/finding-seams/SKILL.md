---
name: finding-seams
description: Find architectural seams, backdoors, and un-dogfooded logic to move code toward deep, capability-oriented modules.
---

# Capability-Oriented Architecture Review

Review the existing codebase for opportunities to move toward a capability-oriented modular architecture: deep modules, explicit stable service interfaces, and peer consumers dogfooding the same underlying application capabilities.

## Task

Inspect the codebase and identify architectural seams where:

* domain capabilities are coupled to UI, transport, persistence, or orchestration details;
* important logic is duplicated across UI, API, jobs, scripts, or services;
* modules expose too much complexity or have shallow, leaky interfaces;
* callers use backdoors (direct database reads, private imports, bypassed domain logic) rather than explicit service interfaces;
* internal capabilities are not externalizable—the UI or internal tools use private capabilities unavailable through clean boundaries;
* implicit seams could become explicit in-process module or service boundaries;
* unstable, slow, unreliable, or awkward interfaces indicate poor underlying boundaries.

Prefer architectural improvements that increase information hiding, capability reuse, interface stability, testability, and dogfooding.

Prefer in-process modular boundaries over distributed microservices. Propose the smallest architectural change that creates a deep module with a stable interface.

## Output

Produce a single ranked list of proposed enhancements.

For each item include:

1. **Change** — the concrete architectural change.
2. **Evidence** — exact code paths, dependencies, duplication, backdoors, or failure modes that justify it.
3. **Target boundary** — the capability and proposed interface.
4. **Why it matters** — architectural and user/developer benefit.
5. **Priority** — impact relative to implementation cost and risk.

Rank highest the changes that eliminate the most architectural backdoors, extract the most important shared capabilities, or fix interfaces already causing active friction.

Propose incremental partition changes that leave the codebase better factored after each step.
