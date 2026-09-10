# Agent Skills

Reusable agent instructions published by this repository.

## Calculational design

**Practical BMF pass**:
A developer-facing application of Bird–Meertens calculation to the precise
computational core of an idea or specification. It derives or audits a design
with justified transformations and labels any heuristic judgment explicitly.
_Avoid_: BMF-inspired analysis, formal proof

**Derivation artifact**:
The layered result of a Practical BMF pass: a plain-language conclusion, an
auditable derivation, and the laws and premises that justify each step.
_Avoid_: Proof, math paper

**Computational core**:
The part of an idea or specification precise enough to express as inputs,
outputs, semantic constraints, and transformations over a stated data shape.
_Avoid_: Algorithm, whole specification

**Fit report**:
The result when a Practical BMF pass cannot yet identify a Computational core.
It names the missing semantics and the smallest questions needed to make
calculation possible.
_Avoid_: Failure, BMF-inspired analysis

**Reference version**:
An obviously correct expression of the Computational core used as the starting
point for calculation, regardless of its efficiency or executability.
_Avoid_: Final implementation, pseudocode

**Derivation ledger**:
An ordered record with one transformation per row, classified as a definition,
equality, refinement, or heuristic and accompanied by its premises.
_Avoid_: Proof

**Blocking ambiguity**:
An unresolved interpretation for which plausible answers produce materially
different computations. A Practical BMF pass asks the user to settle it before
continuing.
_Avoid_: Missing detail, assumption

**Optimization target**:
The stated quality a Practical BMF pass tries to improve after preserving the
contract, such as traversal count, memory use, streaming, parallelism, or
conceptual simplicity.
_Avoid_: Performance

**Proof obligation**:
A premise needed to justify a derivation step that available evidence has not
established. It remains visible in the Derivation artifact until discharged.
_Avoid_: Assumption, TODO

**Claim provenance**:
The status of a contract statement in a Derivation artifact: stated by the
source, derived from it, assumed to make progress, or still open.
_Avoid_: Confidence, citation

**Source material**:
The idea, specification, or accepted conversation a Practical BMF pass treats
as authoritative. Explicit user input takes precedence over earlier
conversation; assistant proposals count only after the user accepts them.
_Avoid_: Context, prompt

## Progressive summarisation

**Summary instructions**: Optional directions from the user about the summary's
focus, audience, format, or length. _Avoid_: Special instructions, particular
instructions

**General summary**: The concise, broad-audience summary produced when the user
provides no Summary instructions.

**Reduction layer**: One round of turning source chunks or earlier summaries
into shorter summaries. Every Reduction layer inherits the same Summary
instructions.

**Final summary**: The user-facing result of the last Reduction layer.
Intermediate summaries remain working material. _Avoid_: General summary

## Tutoring

**Tutor**: A user-invoked skill that teaches through a stateful, in-chat
conversation. It teaches one small idea, checks the user's understanding, and
waits before teaching another. _Avoid_: Lesson generator, course generator

**Teaching workspace**: The current directory used by Tutor to retain the
user's learning purpose, sources, preferences, understood terms, and proved
learning across sessions. _Avoid_: Course directory, lesson directory

**Learning record**: A short Markdown record of understanding that changes what
Tutor should teach next. It is evidence of learning, not a record of activity.
_Avoid_: Lesson log, session log

## Bug finding

**Exploratory pass**: A bug-finding investigation centred on a few complete user
journeys through the software's supported interface, judged by their observable
outcomes. Its scope includes which journeys were explored and which areas remain
unexplored.
