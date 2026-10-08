# Mutation-testing skill audit

## Scope and method

Purpose: derive a general-use, manual-first `/mutation-testing` skill from
Jonathan's Quality Gates repositories, with automation as an optional supplement.
This is a documentation and targeted source audit, not a full correctness review
or a mutation campaign against the tools themselves. No tool was installed or run,
and no audited repository was edited.

Canonical local checkouts were identified by their Git remotes under
`github.com/quality-gates/`. Alternate worktrees and legacy checkouts were not
counted as separate products. Audited snapshots:

| Repository | Revision | Role |
| --- | --- | --- |
| [mutation-testing](https://github.com/quality-gates/mutation-testing/tree/2d0e2d2deeb642267fd3883bf66c44a00e1e57cc) | `2d0e2d2` | Documentation hub; manual loop and language map |
| [mutago](https://github.com/quality-gates/mutago/tree/2d6bdd9f394241baf54ad91b2601aee8a403b8c6) | `2d6bdd9` | Go runner |
| [mutarust](https://github.com/quality-gates/mutarust/tree/d327c09769fbbfe0c1d1e46975c77f592e06bb1d) | `d327c09` | Rust runner |
| [mutaskell](https://github.com/quality-gates/mutaskell/tree/18fb9fade4cf5b4e3b3e6778ea7c5c9f6bfc7186) | `18fb9fa` | Haskell runner |

The mutago checkout had unrelated changelog/exploratory-report changes and scratch
files; mutaskell had an untracked performance audit. They were left untouched.
The findings below use tracked documentation and implementation, not those artifacts.

Read the hub and runner READMEs and agent instructions, Rust domain/CLI docs, and
selected execution, scoring, and test code. The mess-detection hub and assumpgo
README establish that those products are static analyzers, not mutation runners.
Distribution and demo repositories are not additional mutation engines.

## Findings that change the skill

### 1. The shared purpose is stronger evidence, not more green tests

The hub and all three runners distinguish execution coverage from fault detection.
Their examples target weak assertions, missing boundaries, over-mocking, and
broken propagation between individually tested components. The hub explicitly
extends manual mutation to SQL, Dockerfiles, Terraform, CI, and end-to-end checks.

**Draft decision:** the default is actual source mutation plus execution of existing
checks. Each mutant starts with a contract and distinguishing scenario. A static
review, coverage number, or proposed mutant list is not a completed pass.

### 2. Go and Rust scores are not pure test-kill rates

At these revisions, both tools calculate:

```text
MSI         = (killed + errored + skipped) / total
covered-MSI = (killed + errored + skipped) / (total - not-covered)
```

Sources:

- [mutago `Report.MsiScore`, `CoveredMsiScore`, and per-mutator aggregation](https://github.com/quality-gates/mutago/blob/2d6bdd9f394241baf54ad91b2601aee8a403b8c6/internal/models/report.go#L82-L132)
- [mutarust score methods](https://github.com/quality-gates/mutarust/blob/d327c09769fbbfe0c1d1e46975c77f592e06bb1d/src/execution.rs#L87-L108)
- [mutarust parity-state test](https://github.com/quality-gates/mutarust/blob/d327c09769fbbfe0c1d1e46975c77f592e06bb1d/src/execution.rs#L1409-L1433)

The Rust test feeds one of each outcome into production `MutationRun` methods and
asserts MSI `3/5` and covered-MSI `3/4`, although only one mutant is `Killed`.
Its evidence is production-grounded for **score arithmetic**, not for the runner's
ability to distinguish real test failures from other failures. Mutago's report
tests also exercise production calculations; their passing would not establish
end-to-end classification accuracy.

Mutago's README describes MSI as killed/total in places, without the qualification
that errors and skips contribute. Per-mutator killed summaries in both tools also
include errors. Thus even a high displayed score can overstate observed detection.
This audit confirms the implementation, not whether that scoring policy should be
changed; no fix was attempted.

**Draft decision:** report per-mutant evidence and outcome counts first. Keep
compiler rejection, tool failure, and timeouts distinct. Optional automation must
disclose the selected tool's score semantics rather than impose a universal MSI.

### 3. Outcome names require checking the execution mode

- [mutago's classifier](https://github.com/quality-gates/mutago/blob/2d6bdd9f394241baf54ad91b2601aee8a403b8c6/internal/engine/engine.go#L1666-L1675)
  separates Go build/setup failures from test failures despite both using exit 1.
- [mutarust's Cargo classifier](https://github.com/quality-gates/mutarust/blob/d327c09769fbbfe0c1d1e46975c77f592e06bb1d/src/execution.rs#L2998-L3013)
  skips compile failures and marks timeouts errored.
- [mutaskell's orchestrator classifier and restoration](https://github.com/quality-gates/mutaskell/blob/18fb9fade4cf5b4e3b3e6778ea7c5c9f6bfc7186/app/App/Orchestrator.hs#L190-L215)
  restores source with `finally`, skips failed builds, and labels test-command
  timeouts and other non-zero test exits killed.

These classifiers alone do not prove that a failure came from the intended
behavioural observation. A test-command error can have another cause.

**Draft decision:** use a green–mutant–green comparison, inspect the detecting test,
and retain inconclusive outcomes. Count a timeout as a kill only with repeatable
evidence of a violated termination/latency contract.

### 4. Haskell has multiple modes and stale descriptions

The [mutaskell README](https://github.com/quality-gates/mutaskell/blob/18fb9fade4cf5b4e3b3e6778ea7c5c9f6bfc7186/README.md)
contains an older “single module” restriction alongside newer directory/project
and single-file `--exec` modes. The interpreter expects discoverable tests in a
module; project mode drives the real Cabal/Stack suite. Some mutation examples
also call compile errors killed, contrary to the orchestrator classification.
Coverage requires usable HPC data; automatic discovery is not automatic collection.

**Draft decision:** the tool index recommends project mode for ordinary repositories,
explains interpreter prerequisites, and tells agents to check current mode-specific
documentation and CLI help. No universal Haskell quickstart is copied into the skill.

### 5. Isolation and budgets are part of trustworthy measurement

The runner instructions describe large Go caches and Rust worker build areas,
shared-host concurrency limits, and Haskell per-mutant/project budgets. The source
and docs use different isolation techniques; restoration cannot simply be assumed.

**Draft decision:** preserve the user's exact starting state, including uncommitted
work; prefer a disposable copy, run one fault at a time, limit resources, and verify
restoration. Mutations of infrastructure run only against disposable targets.

## Optional third-party index

Consulted upstream README introductions and setup sections to confirm tool purpose
and ecosystem; these alternatives were not source-audited or executed:

- [StrykerJS](https://github.com/stryker-mutator/stryker-js): JavaScript/TypeScript.
- [Stryker.NET](https://github.com/stryker-mutator/stryker-net): .NET; verify language support.
- [Infection](https://github.com/infection/infection): PHP.
- [PIT](https://github.com/hcoles/pitest): Java/JVM.
- [mutmut](https://github.com/boxed/mutmut): Python; requires fork support and has
  version-dependent mutation scope.
- [Mull](https://github.com/mull-project/mull): C/C++, LLVM-based.

Quality Gates receives the first three indexed entries and detailed operational
notes. Alternatives fill other ecosystem needs without adding an installation or
CI-configuration workflow to the manual path.

## Draft structure

- [`SKILL.md`](../../skills/mutation-testing/SKILL.md): user-invoked, manual-first
  steps with explicit completion criteria; findings and recommendations by default.
- [`AUTOMATED-TOOLS.md`](../../skills/mutation-testing/AUTOMATED-TOOLS.md): disclosed
  only for a requested tool recommendation, automated run, or CI follow-up.

This follows `/writing-for-agents`: keep the common execution path inline, disclose
the optional branch, and avoid caching installation commands and version floors.
No release, installation into home skill roots, or upstream issue filing is part
of this draft.

## Draft verification

Passed `tests/skill-tree.sh`, `tests/install-skill-filter.sh`, and
`tests/install-pycache-exclusion.sh`. Also checked frontmatter, local Markdown
links, whitespace, actual discovery of `mutation-testing`, and copying both skill
files through the production skill-tree helper into a temporary directory.

Document walkthrough: a dirty tree is preserved as the baseline; a red or empty
baseline blocks execution; compile rejection is invalid; an unexplained timeout
is inconclusive; a survivor needs investigation before becoming a test-gap finding;
a restricted test selection cannot support a whole-suite claim; automation is an
explicit optional branch. These are instruction checks, not an independent agent
trial. Behavioural validation of the skill on real target repositories remains
future work.
