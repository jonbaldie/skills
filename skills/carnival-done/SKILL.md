---
name: carnival-done
description: >
  Carnival mode only. Signal this assignment complete to the mayor.
---

# Carnival done

Signal completion for the assignment this agent was slung.

<role name="signaling-agent">
  <responsibility>Write completion to the tracker first (authoritative signal).</responsibility>
  <responsibility>Briefly report to the mayor or parent session if a channel exists.</responsibility>
  <responsibility>Exit — no further assignment without a fresh sling.</responsibility>
</role>

## 1. Update the tracker

For a ticket assignment: close or complete it on the configured tracker. Record
what landed (branch, PR, commit, artifact path — whatever the harness and
tracker use).

For a spotter patrol: leave ticket states as found; put the report where the
mayor will see it.

<if>
  <when>Assignment was a ticket</when>
  <then>Close or complete it on the configured tracker; record what landed (branch, PR, commit, artifact — whatever the harness and tracker use)</then>
</if>

<if>
  <when>Assignment was a spotter patrol</when>
  <then>Leave ticket states as found; put the report where the mayor will see it</then>
</if>

Done when the tracker (and report) give the mayor enough to advance.

## 2. Report

Tell the mayor (or parent session), briefly:

- which assignment finished
- what landed or what the patrol found
- anything the next sling must know

Then exit.
