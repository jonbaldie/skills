---
name: bmf
description: Derive or audit a computational design with a practical, developer-readable Bird–Meertens calculation.
argument-hint: "[idea-or-spec]"
disable-model-invocation: true
---

# BMF

Turn an idea, specification, or accepted conversation into an auditable
computational design. Start from an obviously correct **reference version** and
reach an implementation shape through small, justified transformations.

This is a read-only design skill. End at the derived design; implementation
begins only after a separate user request.

## 1. Resolve the source

Use the source in this order:

1. An idea, specification, path, or URL passed with the invocation.
2. The user's artifacts and explicit statements in the conversation.
3. Assistant proposals the user explicitly accepted.

Treat other assistant material as context, not specification. Read a referenced
source in full. When no readable source exists, ask for one.

In a codebase, inspect relevant domain docs, ADRs, source, types, and tests.
Treat the supplied specification as authoritative and record disagreements
with the implementation as discrepancies.

Complete this step when the source boundary and every known discrepancy are
explicit.

## 2. Establish the contract

Extract the computational core:

- inputs and outputs;
- invariants and required relationships;
- ordering, duplicates, ties, and empty cases;
- errors, effects, and observable evaluation order;
- finite-input and termination expectations;
- the **optimization target**: time, space, traversals, streaming, parallelism,
  or conceptual simplicity.

Tag each contract claim **Stated**, **Derived**, **Assumed**, or **Open**. When
normalizing the user's vocabulary, show the original and normalized terms
together once.

Collect every **blocking ambiguity** whose plausible answers produce different
computations. Ask them as one numbered batch and wait. Carry harmless
assumptions visibly.

When the source has no sufficiently precise data transformation, return a
**Fit report** and stop:

<fit-report>

## BMF fit

**Decision in view:** What the user appears to be deciding.

**Why calculation cannot start:** Why there is no precise computational core.

**Missing semantics:** The inputs, outputs, invariants, data meaning, effects,
or edge cases still needed.

**Questions:** The smallest numbered set of answers that would make a BMF pass
possible.

</fit-report>

Complete this step when every contract claim has provenance, no blocking
ambiguity remains, and either a computational core or a complete Fit report
exists. When no optimization target is stated, target the most direct idiomatic
implementation and make no claim of global optimality.

## 3. Write the reference version

Choose the **carrier** from the data's meaning: list, bag, set, tree, stream, or
another explicit shape. State which properties that choice licenses. Order,
multiplicity, and idempotence are semantic decisions, not implementation
details.

Model effects, exceptions, floating-point behavior, evaluation order, laziness,
divergence, infinite inputs, and concurrency wherever they are observable.
Assume pure, total, deterministic operations over finite data only when the
contract supports it. Isolate a pure core when possible.

Write the simplest obviously correct reference version. Efficiency and direct
executability can wait. Mirror the project's language when one is established;
otherwise use typed, language-neutral pseudocode with explicit semantics.

Complete this step when every part of the reference version traces to the
contract and every semantic hazard is modeled or recorded as an assumption.

## 4. Calculate

Read [`LAWS.md`](./LAWS.md) now. Use it as the source of laws, premises, and
counterexamples; consult only laws relevant to the chosen carrier and reference
version.

Normalize the reference version into familiar operations such as `map`,
`filter`, `fold`, `scan`, and composition. Transform one thing at a time. Record
every step in the **Derivation ledger** as one of:

- **Definition**: expands or introduces a name without adding behavior.
- **Equality**: preserves observable meaning in both directions under proved
  premises.
- **Refinement**: selects or strengthens behavior while satisfying the
  contract.
- **Heuristic**: an engineering judgment the calculation does not establish.

For every step say what changed, why it is safe here, and why it is useful. Name
the familiar move first and the formal law second. Expose every premise beside
the step; an unmet premise is a **proof obligation**, not an equality.

Derive one primary path against the optimization target. Include another path
only when it reveals a material trade-off.

Complete calculation only when the implementation shape satisfies the
contract, every ledger step is justified, and the optimization target is met,
shown unattainable under the stated constraints, or retained as a proof
obligation.

## 5. Check and present

Check concrete edge cases and properties corresponding to the contract and the
laws used. Run relevant existing tests when executable code is available;
otherwise propose checks. A sampled check supplies evidence, not an equality.
Assess time, space, traversal count, and operational consequences separately
from semantic correctness.

Return this artifact in order:

<derivation-artifact>

## Result

State the derived design in ordinary engineering language. A reader should
understand this section without reading the ledger.

## Contract

List inputs, outputs, invariants, edges, effects, the optimization target, and
claim provenance.

## Data shape

Name the carrier, explain why it matches the meaning, and list the algebraic
properties used later.

## Reference version

Show the obviously correct starting point.

## Derivation ledger

| Kind | Before | Move | Why it applies | After |
| --- | --- | --- | --- | --- |
| Definition / Equality / Refinement / Heuristic | Short expression | What changed; why it is useful | Premises and why it is safe here | Short expression |

Keep one transformation per row. Put longer code immediately below its row.

## Implementation shape

Show idiomatic code-shaped design, not a production implementation.

## Checks

Give edge examples, properties, repository test evidence, discrepancies, and
remaining proof obligations.

## Cost

Report time, space, traversals, streaming or parallel behavior, and any change
from the Reference version.

## Law notes

Explain only the laws used. Use conventional developer notation; include
historic BMF notation only when the user requests it.

</derivation-artifact>

Complete the pass only when the artifact accounts for every contract claim,
ledger premise, semantic edge, discrepancy, check, cost claim, and proof
obligation.

Return the artifact in chat. When the user requested a file, show the complete
artifact first and wait for confirmation, then write that approved artifact to
the requested destination. Stop at the design.
