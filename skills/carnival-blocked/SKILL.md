---
name: carnival-blocked
description: >
  Carnival mode only. Signal this assignment blocked for the mayor.
---

# Carnival blocked

Signal that the assignment this agent was slung cannot proceed.

<role name="signaling-agent">
  <responsibility>Write the blocker to the tracker first (authoritative signal).</responsibility>
  <responsibility>Briefly report to the mayor or parent session if a channel exists.</responsibility>
  <responsibility>Exit — no further assignment without a fresh sling.</responsibility>
</role>

## 1. Update the tracker

For a ticket assignment: mark it blocked (or equivalent) on the configured
tracker. Write the blocker in plain language: what failed, what is missing, who
or what can unblock it.

For a spotter patrol: say what prevented the patrol (tracker access, missing
scope, harness opaque).

<if>
  <when>Assignment was a ticket</when>
  <then>Mark it blocked (or equivalent); write what failed, what is missing, who or what can unblock it</then>
</if>

<if>
  <when>Assignment was a spotter patrol</when>
  <then>Say what prevented the patrol (tracker access, missing scope, harness opaque)</then>
</if>

Done when the tracker or report carries the blocker clearly enough for the
mayor to act.

## 2. Report

Tell the mayor (or parent session), briefly:

- which assignment is blocked
- the blocker
- the smallest next action that would unblock it

Then exit.
