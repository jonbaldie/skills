# Reliable bug-finding methodologies for `finding-bugs`

Research date: 2026-08-26

## Question and scope

Which repeatable methodologies should sit alongside the skill's existing coverage-guided, property-based testing (CGPT) loop?

Here, a method is **reliable** only to the extent that it does one or more of the following:

- produces a sustained yield of real bugs;
- keeps false positives and developer triage low;
- leaves a concrete input or action sequence that deterministically reproduces the failure;
- applies across a useful range of codebases and bug classes.

Those properties do not have a single ordering. A memory detector can be extremely precise but narrow; a static analyzer can be broad and cheap to run but report a path that is difficult to realize; a differential test can leave an excellent reproducer but only when an independent comparator exists. The industrial evidence therefore supports a portfolio rather than a universal winner.

## Recommendation

| Priority | Method | Recommendation | Why |
| --- | --- | --- | --- |
| Existing core | Coverage-guided, property-based testing | Keep and strengthen; do **not** add a second standalone coverage-guided fuzzing section | The current loop already is the libFuzzer-style algorithm: mutate a corpus, retain inputs that expand coverage, and minimize failures. Add crash, sanitizer, and other runtime-detector oracles to it. |
| 1 | Static-analysis-guided reproduction | Add | Static analysis has the broadest evidence of routine, large-scale use, but its diagnostics should be treated as hypotheses until reproduced against the real system. |
| 1 | Runtime-instrumented testing | Add | Sanitizers and related dynamic detectors provide unusually actionable runtime witnesses for supported bug classes and compose directly with both existing tests and CGPT. |
| 1 | Stateful action-sequence testing | Add | It reaches failures caused by histories of user or API actions rather than a single input, and Meta reports a strong actionability rate from sustained deployment. |
| 2, conditional | Concolic path exploration | Add only where a mature tool supports the language and entry point | Microsoft reports exceptional yield at scale, and every solver-produced case can be replayed concretely, but path explosion and environment modelling make the method costly and unevenly available. |
| 2, conditional | Differential testing | Add as a short method or oracle pattern | It produces simple, reproducible discrepancies when two independent implementations, versions, or backends have a shared contract. Its applicability depends on having a trustworthy comparator, and a discrepancy alone does not identify the wrong side. |
| Fold into CGPT | Metamorphic testing | Add as an oracle pattern, not a full parallel methodology | It supplies test oracles where the exact answer is unknown, but it is fundamentally a way to express properties over related inputs and therefore fits the current property-based section. |
| Exclude | Mutation testing | Do not present as a bug-finding methodology | A surviving artificial mutant demonstrates a gap in the tests; it is not itself evidence of a production defect. Use mutation testing to assess the adequacy of a bug-finding campaign, if at all. |

The three Priority 1 additions are not ordered against one another. Choose them from the codebase: static analysis for broad pre-execution discovery, runtime instrumentation for detector-supported failures, and stateful sequences for workflow- and history-dependent behavior.

## Industrial evidence

### Coverage-guided fuzzing remains part of CGPT

LLVM's in-process coverage-guided fuzzer mutates a seed corpus and retains inputs that reach new code; when it finds a failure, it writes the responsible input to disk. Its documentation recommends composing the fuzzer with AddressSanitizer, UndefinedBehaviorSanitizer, and related detectors. That is the same search loop already described by CGPT, so a separate section would be redundant. ([LLVM libFuzzer documentation](https://llvm.org/docs/LibFuzzer.html))

The scale and yield are strong. Google's ClusterFuzz documentation reported, as of May 2022, more than 25,000 bugs found in Google and more than 36,000 bugs in over 550 open-source projects, and describes automated testcase minimization, regression bisection, and fix verification. ([ClusterFuzz overview](https://google.github.io/clusterfuzz/), [ClusterFuzz architecture](https://google.github.io/clusterfuzz/architecture/)) OSS-Fuzz later reported verified fixes for more than 10,000 vulnerabilities across more than 1,000 projects. It also reported average code coverage of about 30%, an important warning that deployment scale does not imply complete exploration. ([Google Security Blog](https://security.googleblog.com/2023/08/ai-powered-fuzzing-breaking-bug-hunting.html))

Fuzzing's reproducibility comes from retaining the triggering testcase, not from coverage alone. ClusterFuzz defines a reliable crash as one that repeatedly produces the same crash state, minimizes reliable cases, and deprioritizes unreliable ones; its workflow reruns cases and verifies fixes. ([ClusterFuzz glossary](https://google.github.io/clusterfuzz/reference/glossary/), [fixing a ClusterFuzz bug](https://google.github.io/clusterfuzz/using-clusterfuzz/workflows/fixing-a-bug/))

**Conclusion:** keep one CGPT section. Broaden its oracle step to include crashes, assertions, hangs, sanitizer findings, and domain properties, and make stable replay of the saved testcase part of its completion criterion.

### Static analysis: high yield, but validate before calling it a bug

Google reports that its Tricorder static-analysis infrastructure is used daily by most engineers and that developers voluntarily fix thousands of issues before check-in each day. ([Google, “Lessons from Building Static Analysis Tools at Google”](https://research.google/pubs/lessons-from-building-static-analysis-tools-at-google/)) Meta reports that Infer has led to hundreds of potential bugs being fixed each month before commit in Facebook's mobile codebases, and that its interprocedural analyses have resulted in thousands of fixes while operating over millions of lines and thousands of daily modifications. ([Meta on open-sourcing Infer](https://engineering.fb.com/2015/06/11/developer-tools/open-sourcing-facebook-infer-identify-bugs-before-you-ship/), [Meta on interprocedural Infer](https://engineering.fb.com/2017/09/06/android/finding-inter-procedural-bugs-at-scale-with-infer-static-analyzer/))

That is compelling evidence for yield and breadth, not proof that every diagnostic is a real, reachable defect. Clang's own analyzer documentation says false-positive rates vary by check and that static analysis only finds bug classes its checks were designed to recognize. ([Clang Static Analyzer](https://clang.llvm.org/analyzer/)) Meta similarly explains why it measures developer fix rate rather than assuming a simple false-positive classification for findings whose reachability may be hard to establish. ([Meta on interprocedural Infer](https://engineering.fb.com/2017/09/06/android/finding-inter-procedural-bugs-at-scale-with-infer-static-analyzer/))

**Conclusion:** static analysis deserves a section, but “run a linter and list warnings” does not meet this skill's reproducibility standard. The method should use diagnostics to direct a concrete reproduction attempt.

### Runtime instrumentation: precise oracles for supported bug classes

AddressSanitizer's Google-authored paper reports that, during its first ten months of use in Chromium, it found more than 300 previously unknown bugs through regular tests and targeted fuzzing. ([AddressSanitizer paper](https://research.google.com/pubs/archive/37752.pdf)) LLVM documents concrete detector classes including out-of-bounds access and use-after-free for AddressSanitizer, arithmetic, pointer, shift, and other undefined behavior for UndefinedBehaviorSanitizer, and data races for ThreadSanitizer. ([AddressSanitizer](https://clang.llvm.org/docs/AddressSanitizer.html), [UndefinedBehaviorSanitizer](https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html), [ThreadSanitizer](https://clang.llvm.org/docs/ThreadSanitizer.html))

Sustained production use supports the broader detector family: Google's GWP-ASan deployment reports more than 300 server-side bugs fixed in 2019 and more than 450, 450, 500, and 550 in each year from 2020 through 2023; in one Chrome prescreening workflow, 71% of sampled reports were filed and 69% of resolved reports were marked fixed. ([Google-authored GWP-ASan paper](https://raw.githubusercontent.com/google/sanitizers/master/gwp-asan/icse2024/paper.pdf)) These figures are for a sampled production detector rather than a test-only sanitizer, so they support detector actionability, not an instruction to deploy production instrumentation from this skill.

The limits are material. Detectors only observe executed paths, require compatible build/toolchain support, and differ in overhead and completeness; for example, LLVM documents a typical 5–15× slowdown for ThreadSanitizer and warns that incomplete instrumentation can lead to missed races or false reports. ([ThreadSanitizer](https://clang.llvm.org/docs/ThreadSanitizer.html))

**Conclusion:** add a standalone runtime-instrumented method because it defines an oracle, not an input generator. It should feed existing tests, representative workflows, or CGPT inputs through the best detector available for the codebase.

### Stateful action-sequence testing: strong for workflow bugs

Meta's Sapienz deployment generated tens of thousands of test cases each day across large pools of emulators, and Meta reports that about 75% of its reports were actionable and resulted in fixes. ([Meta on Sapienz at scale](https://engineering.fb.com/2018/05/02/developer-tools/sapienz-intelligent-automated-software-testing-at-scale/)) A companion account says the system produced hundreds of bug reports per month and that roughly three quarters resulted in fixes. ([Meta on Sapienz and SapFix](https://engineering.fb.com/2018/09/13/developer-tools/finding-and-fixing-software-bugs-automatically-with-sapfix-and-sapienz/)) The original study found 558 unique crashes in the top 1,000 Android applications and emitted replayable test scripts, though only a much smaller set had been developer-confirmed at publication time. ([Sapienz paper](https://www0.cs.ucl.ac.uk/staff/k.mao/archive/p_issta16_sapienz.pdf))

This evidence is strongest for mobile user interfaces, so it should not be generalized to every stateful system without qualification. The method itself generalizes: state-machine property-testing tools generate sequences of primitive operations whose effects interact over time. ([Hypothesis stateful testing documentation](https://hypothesis.readthedocs.io/en/latest/stateful.html))

**Conclusion:** add a stateful action-sequence method for codebases with workflows, protocols, lifecycle operations, or persistent state. Its artifact is a resettable, minimized sequence, not just the last input in the sequence.

### Concolic execution: excellent evidence, conditional applicability

Microsoft's SAGE whitebox fuzzer accumulated more than 400 machine-years of testing across hundreds of applications and found about one third of the file-fuzzing bugs discovered during Windows 7 development. ([Microsoft Research on SAGE](https://www.microsoft.com/en-us/research/?p=162940)) An earlier Microsoft account reports that SAGE found more than 30 bugs in already-shipped Windows applications, including a vulnerability missed by blackbox fuzzing and static analysis. ([Microsoft Research, “Automated Whitebox Fuzz Testing”](https://www.microsoft.com/en-us/research/publication/automated-whitebox-fuzz-testing/))

The algorithm is neat: run a concrete input, collect path constraints, negate an unexplored branch, solve for a new input, and replay that input concretely. Microsoft's DART work describes this feedback loop, while the KLEE paper demonstrates concrete replay on unmodified programs and reports 56 serious defects across several systems utilities and operating-system components. ([DART paper](https://osl.cs.illinois.edu/publications/conf/pldi/GodefroidKS05.html), [KLEE paper](https://www.usenix.org/legacy/events/osdi08/tech/full_papers/cadar/cadar.pdf)) Both lines of work also expose the practical limitations: path explosion, solver cost, and modelling of environment interactions.

**Conclusion:** include only as a conditional method, or omit it from the first revision if the skill should remain tool-agnostic. It is highly reliable where supported, but not broadly turnkey.

### Differential and metamorphic testing: strong oracle patterns, less universal evidence

Differential testing sends the same generated cases to comparable implementations and treats divergent results, crashes, or hangs as candidates. The original method is simple and produces compact witnesses, and KLEE used cross-checking between independently implemented utilities to find functional inconsistencies. ([McKeeman, “Differential Testing for Software”](https://www.cs.tufts.edu/comp/150FP/archive/bill-mckeeman/DifferentailTesting.pdf), [KLEE paper](https://www.usenix.org/legacy/events/osdi08/tech/full_papers/cadar/cadar.pdf)) A difference does not establish which implementation violates the contract, so the method still needs specification-based adjudication.

Metamorphic testing derives a follow-up input from a source input and checks a required relation between the two results; it was introduced specifically for cases where the correct output of an individual test is difficult to know. ([Chen, Cheung, and Yiu, “Metamorphic Testing: A New Approach for Generating Next Test Cases”](https://arxiv.org/abs/2002.12543)) This is an especially useful way to formulate CGPT properties, such as invariance under serialization round-trips, reordering independent operations, or applying an identity-preserving transformation.

**Conclusion:** differential testing can be a small conditional section because its setup and stopping rule are distinct. Metamorphic testing belongs in the property/oracle material of CGPT rather than as a duplicate end-to-end loop.

### Mutation testing: adequacy evidence, not a production bug

PIT describes mutation testing as changing production bytecode and checking whether the existing tests detect the artificial change. A surviving mutant identifies weak test evidence, but it does not demonstrate that the original code is defective. ([PIT documentation](https://pitest.org/))

**Conclusion:** do not add it as a bug-finding methodology. It can be used later to assess whether tests are sensitive to plausible faults.

## Proposed repeatable algorithms

These are outlines for skill sections, not final skill prose.

### 1. Static-analysis-guided reproduction

1. Identify the repository's configured compiler checks, type checker, security analyzers, and path-sensitive analyzers; prefer the project's own commands and configuration.
2. Run them on the relevant production code and record tool version, configuration, and exact diagnostic path.
3. Deduplicate findings and rank them by reachable entry point, severity, confidence, and closeness to changed or user-facing code.
4. For the highest-ranked diagnostic, derive the input, state, and control-flow preconditions required to reach it.
5. Exercise those preconditions through a real entry point. Treat the diagnostic as a hypothesis until the system exhibits an observable contract violation, crash, corruption, leak, or security boundary failure.
6. Minimize the input and environment while preserving the behavior, then replay it from a clean state.
7. Repeat until each selected diagnostic is reproduced, rejected with evidence, or explicitly deferred.

**Completion criterion:** every reported bug has a stable system-level reproducer and its originating diagnostic; the chosen diagnostic set has been exhausted or the declared time/finding budget has been reached. Analyzer warnings without a reproducer remain leads, not bugs.

### 2. Runtime-instrumented testing

1. Map the repository's languages and failure risks to supported detectors: memory safety, undefined behavior, races, leaks, deadlocks, taint, or another runtime invariant.
2. Build the system and relevant dependencies with the selected detector enabled, preserving symbols and a documented invocation.
3. Run the existing test suite, then representative user/API workflows; where CGPT exists, run its corpus under the detector as well.
4. Group reports by root stack and detector class rather than raw occurrence count.
5. For each unique report, save the exact input, action sequence, build, environment, and detector options.
6. Reproduce from a fresh instrumented build, minimize the input or sequence, and confirm any externally observable effect on a normal build where feasible.
7. Continue through the selected detector/test matrix or until the declared execution budget expires.

**Completion criterion:** each retained finding repeats with the same root failure under the recorded invocation and has a minimized artifact; all selected detector/test combinations have run or the declared budget is exhausted.

### 3. Stateful action-sequence testing

1. Choose a user-critical workflow, protocol, lifecycle, or API whose failures can depend on prior actions.
2. Define observable abstract state, valid actions with preconditions, reset/cleanup behavior, and invariants that must hold after each action.
3. Generate or search sequences of actions and data, weighting unexplored actions, state transitions, control-flow coverage, and previously productive motifs.
4. Reset the system, execute a sequence through its real boundary, and check invariants and observable state after every step.
5. On failure, replay from a clean reset several times to separate deterministic failures from environmental flakes.
6. Shrink actions and their data while preserving the same failure and record the smallest setup-to-failure script.
7. Continue until transition/state coverage plateaus or the declared sequence/time budget expires.

**Completion criterion:** report only stable, resettable, minimized failure sequences; otherwise finish when the declared budget or state/transition target is met.

### 4. Concolic path exploration (conditional)

1. Select a bounded entry point, symbolic input fields, and a mature concolic or symbolic executor compatible with the build.
2. Run seed inputs concretely while collecting branch constraints and environmental assumptions.
3. Negate an unexplored feasible branch, solve the resulting constraints, and obtain a concrete new input.
4. Execute the new input, retain it if it reaches a new path or a failure oracle, and prioritize unexplored paths within the budget.
5. Replay failures against an unmodified or normally instrumented system to rule out executor-model artifacts.
6. Minimize the concrete input and record tool version, bounds, assumptions, and replay command.

**Completion criterion:** a retained bug has a stable concrete reproducer outside the symbolic engine; otherwise the declared path, solver-time, or wall-clock budget is exhausted.

### 5. Differential testing (conditional)

1. Identify two genuinely independent implementations, versions, backends, or execution modes governed by a shared contract.
2. Define their common input domain and normalize only contract-irrelevant output differences.
3. Generate inputs and run each side under equivalent resource limits.
4. Capture disagreements, one-sided crashes, and one-sided hangs.
5. Use the specification or an independent invariant to determine which side, if either, is defective.
6. Shrink the input while retaining the adjudicated difference, then replay both sides from clean state.

**Completion criterion:** every reported bug is an adjudicated, stable, minimized divergence; otherwise the declared input/coverage budget is exhausted.

### Metamorphic oracle pattern for CGPT

1. Define a source-input precondition, a transformation `T`, and the required relation `R(output(x), output(T(x)))`.
2. Generate a valid `x`, execute both cases, and check `R`.
3. Shrink `x` and any parameters of `T` together while preserving the violated relation.
4. Replay the pair from clean state and retain both inputs plus the violated relation.

**Completion criterion:** each report is a stable minimized input pair that violates a named relation; otherwise the declared relation/input budget is exhausted.

## Direct answers

- **Static analysis?** Yes, provided the skill turns warnings into system-level reproduction attempts. Industrial evidence supports its yield, but a diagnostic alone is not a reproducible bug.
- **Coverage-guided fuzzing?** Yes in substance, but no new standalone section. It is already the coverage-guided half of CGPT. Make its crash/runtime oracles and saved-testcase replay explicit.
- **What should be added first?** Static-analysis-guided reproduction, runtime-instrumented testing, and stateful action-sequence testing. They are complementary and each has measured, sustained company deployment evidence.
- **What is useful but conditional?** Concolic exploration and differential testing.
- **What should be folded into the current section?** Metamorphic relations.
- **What should not be presented as direct bug finding?** Mutation testing.
