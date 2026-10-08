# Automated mutation tools

Optional supplement to the manual pass. Start with the Quality Gates tool for
the language when it fits; retain a project's existing runner when it already
serves the task. These are discovery pointers, not a promise of compatibility.
Read the selected tool's current documentation and installed `--help` before
choosing commands, test adapters, or score gates.

## Index

| # | Ecosystem | Tool | Starting point |
| --- | --- | --- | --- |
| 1 | Go | **Quality Gates mutago** | [Details](#1-mutago--go) |
| 2 | Rust | **Quality Gates mutarust** | [Details](#2-mutarust--rust) |
| 3 | Haskell | **Quality Gates mutaskell** | [Details](#3-mutaskell--haskell) |
| 4 | JavaScript / TypeScript | StrykerJS | [Quickstart](https://stryker-mutator.io/docs/stryker-js/getting-started/) · [Repository](https://github.com/stryker-mutator/stryker-js) |
| 5 | .NET | Stryker.NET | [Getting started](https://stryker-mutator.io/docs/stryker-net/getting-started/) · [Repository](https://github.com/stryker-mutator/stryker-net) |
| 6 | PHP | Infection | [Documentation](https://infection.github.io/) · [Repository](https://github.com/infection/infection) |
| 7 | Java / JVM | PIT | [Documentation](https://pitest.org/) · [Repository](https://github.com/hcoles/pitest) |
| 8 | Python | mutmut | [Documentation](https://mutmut.readthedocs.io/en/latest/) · [Repository](https://github.com/boxed/mutmut) |
| 9 | C / C++ | Mull | [Documentation](https://mull-project.com/) · [Repository](https://github.com/mull-project/mull) |

The [Quality Gates mutation-testing hub](https://github.com/quality-gates/mutation-testing)
is documentation, not a fourth runner. Its `mess*` siblings and `assumpgo` perform
static analysis; they do not establish that tests detect mutations.

## 1. mutago — Go

[Repository](https://github.com/quality-gates/mutago) ·
[Install](https://github.com/quality-gates/mutago/blob/main/docs/install.md) ·
[CLI source documentation](https://github.com/quality-gates/mutago/blob/main/docs/cli.md)

A Go mutation CLI with coverage and per-test selection, changed-line scope,
accepted-survivor baselines, score gates, and escaped-mutant JSON for agents.
Go-specific probes include error wrapping, error guards, deferred cleanup,
concurrency, and field/return-value removal—not just arithmetic substitutions.

For a requested run, select a package or subtree first. Use `--workers 1`, an
explicit `--exec-timeout`, and resource limits appropriate to the host. A private
`GOCACHE` makes cleanup safe; mutation builds can consume substantial disk space.
Use `--logger-agentic-json` to collect survivor evidence and `--run-mutant-id` to
replay one candidate. Verify the CLI's special replay-mode gate behaviour.

**Interpretation caveat:** at the audited revision, both MSI numerators include
killed **plus errored plus skipped** mutants. The per-mutator killed field also
includes errors. Inspect outcome counts and logs; MSI is not a pure observed-test
kill rate. Build/setup rejection is classified separately by the execution engine.

## 2. mutarust — Rust

[Repository](https://github.com/quality-gates/mutarust) ·
[Install](https://github.com/quality-gates/mutarust/blob/main/docs/install.md) ·
[CLI](https://github.com/quality-gates/mutarust/blob/main/docs/cli.md)

A Cargo-native runner with isolated mutation workspaces, changed-line selection,
baselines, score gates, and agent-ready reports. Inspect `--list-files` before a
run: target form affects recursive selection and exclusions.

Coverage and per-test modes need `cargo-llvm-cov` and `llvm-tools-preview`.
Use one worker initially, a finite `--exec-timeout`, and a resource-capped
container where appropriate. Keep automatic scratch cleanup enabled: worker
build directories can be large. `--logger-agentic-json` and `--run-mutant-id`
support survivor investigation.

**Interpretation caveat:** at the audited revision, MSI includes killed, errored,
and skipped mutants in its numerator. Build rejection is skipped; test-command
timeout is errored. Neither is automatically evidence that an assertion detected
a fault. Per-mutator killed summaries also include errors.

## 3. mutaskell — Haskell

[Repository and guide](https://github.com/quality-gates/mutaskell) ·
[Site](https://quality-gates.github.io/mutaskell) ·
[CI/config examples](https://github.com/quality-gates/mutaskell/tree/main/setups)

A GHC-parser mutation CLI. It probes Haskell operators, guards, patterns,
`Maybe`/`Either`, resource cleanup, and other language-specific constructs.

Choose the execution mode deliberately:

- **Directory/project mode:** discovers the project and drives its real Cabal or
  Stack build/tests. Appropriate for ordinary repositories with separate tests.
- **Single-file `--exec`:** drives explicit project build/test commands for one file.
- **Single-file interpreter mode:** expects discoverable tests in the module and
  an appropriate `hint` package environment. It is not a drop-in project test run.

Use one worker and one project job initially, an explicit `--timeout`, and a
project `--time-budget`. Coverage needs valid HPC `.tix`/`.mix` data;
`--coverage` discovers existing data rather than guaranteeing its collection.
`--logger-agentic-json FILE` takes a path, unlike the Go/Rust flag shape.

**Interpretation caveat:** the audited orchestrator skips failed builds but
classifies test-command timeouts and other non-zero test exits as killed.
Validate their cause before treating them as behavioural test evidence. The
README contains older single-module-only text alongside newer project-mode docs;
use the mode-specific guide and implementation when these disagree.

## Other ecosystems

For entries 4–9, first check the current language/runtime, test-runner, and build
integration requirements. Stryker's runners are separate products; check language
support within .NET rather than assuming every .NET language is supported. PIT's
JVM coverage also depends on the language and test-framework integration. mutmut
requires `fork` support (Windows users need WSL) and its current execution model
focuses on function bodies. Mull requires a compatible LLVM/build setup.

## Before an automated run

1. Confirm the user's requested scope, green baseline, execution mode, and
   runtime/disk budget. Reuse the manual pass's isolation and restoration rules.
2. Start with a narrow source scope and explicit timeouts/concurrency. Retain
   raw reports, logs, configuration, and tool version. Check that real tests ran.
3. Separate killed, survived, uncovered, invalid/skipped, errored, and timed-out
   outcomes. Keep tool-reported scores under their own names and formulas.
   Covered-MSI can help separate detection from reach, but also report uncovered
   code; excluding it does not make it tested.
4. Investigate survivors through the manual loop. Set CI floors only against
   measured, understood results. Accepting survivors or suppressions is a user
   policy decision, not an automatic way to make a gate pass.

For the source revisions and evidence behind these caveats, see the collection's
[repository audit](https://github.com/jonbaldie/skills/blob/main/docs/research/mutation-testing-audit.md).
