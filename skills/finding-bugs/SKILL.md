---
name: finding-bugs
description: Find bugs by coverage-guided, property-based testing of the system under test.
---

Find reproducible bugs by running **coverage-guided, property-based testing** (CGPT) against the actual system under test (SUT).

1. **Invariant.** Specify predicates over SUT observations: return values, exceptions, and visible effects. The invariant is the oracle. Done when each invariant is decidable from a single SUT run.
2. **Entry point.** Run generated and mutated inputs through the SUT's real entry points. Instrument the SUT for control-flow coverage. Keep behavior-affecting state and effects on the execution path; make them repeatable and resettable between runs. Done when every execution observes the SUT.
3. **Corpus.** Seed randomly. Retain SUT executions that add coverage; favor precondition passes and retain novel discards. Apply type-aware mutations to the corpus. A stall widens the surface — a new SUT entry point or process — then mutates again. Done at saturation: a widened surface that adds no SUT coverage.
4. **Counterexample.** Minimise, then use /diagnosing-bugs. Keep only the tight bugs. Report them to the user in really simple, domain-accurate language.

Each execution must test the SUT. Coverage guides the search; a violated invariant is the bug signal.
