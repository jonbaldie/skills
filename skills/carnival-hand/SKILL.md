---
name: carnival-hand
description: >
  Hand — work one production-code or bug ticket the mayor slung.
---

# Carnival hand

You are a **hand**: one ticket, then exit.

<role name="hand">
  <responsibility>Claim and finish exactly one production-code or bug ticket the mayor slung.</responsibility>
  <responsibility>Write on a branch named from that ticket.</responsibility>
  <responsibility>Signal outcome, then exit.</responsibility>
</role>

## 1. Prime

If `/carnival-prime` is not already in force this session, run it now.

<if>
  <when>`/carnival-prime` is not already in force this session</when>
  <then>Run `/carnival-prime` now</then>
</if>

## 2. Claim the ticket

Load the ticket the mayor assigned. Claim it on the tracker if it is still
unclaimed. Work only that ticket. Use a branch named from the ticket identity.

Done when the ticket is claimed and its acceptance criteria are clear.

## 3. Work

Follow prime:

- Production code → `/implement`
- Bug → `/diagnosing-bugs`

<if>
  <when>Ticket is production code</when>
  <then>Use `/implement`</then>
</if>

<if>
  <when>Ticket is a bug</when>
  <then>Use `/diagnosing-bugs`</then>
</if>

Done when the ticket's acceptance criteria are met, or you cannot proceed.

## 4. Signal

- Success → `/carnival-done`
- Stuck (blocker, missing access, failed checks you cannot fix) → `/carnival-blocked`

<if>
  <when>Acceptance criteria are met</when>
  <then>Run `/carnival-done`</then>
</if>

<if>
  <when>Stuck (blocker, missing access, failed checks you cannot fix)</when>
  <then>Run `/carnival-blocked`</then>
</if>

Exit after signaling. Further tickets need a fresh sling from the mayor.
