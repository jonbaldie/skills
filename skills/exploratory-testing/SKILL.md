---
name: exploratory-testing
description: Find reproducible bugs by using software for realistic tasks through its supported interface. Use when asked to try software as a user or explore what breaks during actual use.
---

# Exploratory testing

Run an **exploratory pass**: attempt real user goals through the software's supported
interface, check their observable outcomes, and let unexpected behaviour guide
the next experiment.

## 1. Use the supported interface

Read enough documentation and source to set up the software and understand its
intended user goals. Reuse a project-local verification skill or existing driving
tools when available; otherwise choose tools suited to the interface.

Use the surface the user actually touches: a browser for a web UI, an interactive
terminal for a TUI, or the public commands or API when those are the product.
For a library, use its public API in a small, realistic consuming program.
Internal calls can help observe a UI journey, but cannot substitute for driving it.

Start with ordinary user configuration and isolated data or instances. Record the
build, configuration, starting state, and evidence directory.

Before starting resources, set up one cleanup harness or exit trap for the pass.
Register every background process, browser, or container with that owner as it
starts. Record its identifiers, ports, and teardown commands alongside the
starting state. Use a pass-specific project identifier for container groups.
Make teardown run on normal completion and early exit.

Establish that the software is ready to use. If setup or access is blocked, report
the concrete blocker and what was attempted.

## 2. Attempt complete journeys

Follow the user's scope and any explicit budget. Otherwise select up to three
user-critical journeys and explore each thoroughly.

For each journey, name the user's goal and the observable result that would
satisfy it. Ground that expectation in the request, documentation, or promises
made by the interface. Attempt the ordinary path, then a relevant variation such
as correcting input, retrying, reopening, or cancelling.

Capture actions and resulting screens, terminal output, or returned values. Check
relevant lasting effects too: saved data, generated files, outgoing requests, or the result after
reopening. A success message alone does not establish that the goal was achieved.
For a coding app, submitting an implementation request is the beginning; inspect
the resulting change and independently run its checks.

## 3. Follow surprises

Let interaction lead. Use source, logs, and state probes to explain and verify
what happened. Distinguish a software failure from a broken driver, observation
timeout, or unmet prerequisite. Repair observation problems and repeat the
interaction before drawing a conclusion.

When changing configuration or adding instrumentation to investigate, retain the
original observations and disclose the intervention. A successful comparison
under different conditions does not erase a failure in the ordinary user setup.

Reduce a suspected bug to the smallest practical action sequence and replay it
from a known starting state. Track each candidate with this lifecycle:

| State | Event and guard | Next state and action |
| --- | --- | --- |
| Observed | The driver, observation, or prerequisite is faulty. | Repair observation, retain the original evidence, and replay. |
| Observed | The observation is reliable and conflicts with a grounded expectation. | Suspected. Minimize and replay from the recorded starting state. |
| Suspected | The same failure recurs and violates the expectation. | Confirmed. Preserve the reproducer. |
| Observed or suspected | Evidence explains why the observation satisfies the expectation. | Rejected. Record that evidence. |
| Observed or suspected | Replay is ambiguous, intermittent, or blocked when the budget ends. | Unresolved. Record the missing check and next replay. |

If the build, configuration, or starting state changes, retain the old result
under its original conditions and replay before claiming it applies to the new
conditions. A passing run under altered conditions does not reject the original
candidate.

## 4. Preserve findings and continue

Capture the reproducer, then continue the selected journeys where possible.
Record a blocked journey with its failed step and prerequisite. Keep product
fixes for a subsequent task; `/diagnosing-bugs` can take the confirmed reproducer
into root-cause investigation and fixing.

Start every selected journey at **Selected** and track it independently from its
bug candidates:

| State | Event and guard | Next state and action |
| --- | --- | --- |
| Selected | Its grounded goal and starting state are recorded. | Exploring. Attempt the ordinary path and a relevant variation. |
| Exploring | Observable outcomes and lasting effects are checked, and suspected failures have been replayed. | Explored. Preserve candidate outcomes and evidence. |
| Selected or exploring | A prerequisite prevents progress. | Blocked. Record the failed step and concrete prerequisite. |
| Blocked | The prerequisite becomes available within budget. | Exploring. Resume from a known starting state. |
| Selected, exploring, or blocked | The explicit user budget ends. | Unfinished. Record the remaining work. |

Finish exploring when every selected journey is explored or has a concrete
blocker, or the explicit budget ends. Account for each candidate using step 3.
Preserve useful driving scripts when they help replay; a reusable harness is
optional.

## 5. Report the evidence

Save a report alongside the evidence. For each confirmed bug, give its user
impact, starting conditions, replay steps, expected and actual outcomes, repeat
observations, and links to captured evidence. Separate unresolved candidates
from confirmed findings.

Include the journeys exercised, blocked and unexplored areas, and any limitations
introduced by the environment or instrumentation. Include usability observations
grounded in the attempted journeys, distinguishing observations from suggested
improvements. A pass with no confirmed bugs still reports what was exercised
and observed.

File confirmed bugs in the project's issue tracker, following its conventions
and including the replay steps and evidence. If filing is blocked, record the
blocker and preserve ready-to-file bug reports.

Finish through the resource lifecycle below, including on early exit. Preserve
the report and evidence, and stop only resources owned by this pass.

| State | Event and guard | Next state and action |
| --- | --- | --- |
| Unprepared | The cleanup owner exists. | Ready. Register each resource and its teardown as it starts. |
| Ready or active | An owned resource starts and its identifiers are registered. | Active. Keep its teardown with the cleanup owner. |
| Ready or active | Exploration finishes, fails, or stops early. | Cleaning. Run the registered teardown and remove owned scratch state. |
| Cleaning | Recorded identifiers and ports show no owned resource remains active. | Clean. Link the report in the final response. |
| Cleaning | A resource survives or its absence cannot be verified. | Cleanup blocked. Report its identifier and blocker. Preserve the teardown record and retry safe cleanup. |
| Cleanup blocked | The blocker clears. | Cleaning. Retry teardown and the absence check. |

A blocked cleanup is an incomplete pass. Report that status even if all journeys
finished. Journey exploration itself ends when every selected journey meets the
criteria in step 4 or the explicit budget ends.

Offer to preserve the report as exploratory feedback under `docs/`, naming a
concrete destination. Reuse the project's existing feedback or testing report
convention; otherwise propose `docs/exploratory-testing/YYYY-MM-DD-<scope>.md`.
If the user accepts or already requested this, save the report there with working
evidence and issue links. Add a pointer from a relevant existing docs index or
feature document so future work on that area can find the feedback.
