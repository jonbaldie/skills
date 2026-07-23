# Agent Skills

Reusable agent instructions published by this repository.

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
