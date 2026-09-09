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
