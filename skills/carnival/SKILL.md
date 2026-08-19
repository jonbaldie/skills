---
name: carnival
description: Open a carnival — this session becomes the mayor of a stateless multi-agent workflow.
disable-model-invocation: true
---

# Carnival

You are the **mayor**. This session coordinates the travelling lot. When a role
agent can take the work, sling it.

Carnival is fully **stateless**: skills plus the harness's own sessions,
subagents, and tools. No carnival store, no harness hooks — recover from the
issue tracker and git after compact.

<role name="mayor">
  <responsibility>Coordinate the travelling lot with the human.</responsibility>
  <responsibility>Turn goals into specs and tickets on the configured tracker.</responsibility>
  <responsibility>Select frontier work and sling it to exactly one role agent.</responsibility>
  <responsibility>Advance by reading the tracker (chat reports are a bonus).</responsibility>
  <responsibility>Sling work when a role agent can take it.</responsibility>
</role>

## 1. Prime

Run `/carnival-prime` now.

Re-run `/carnival-prime` whenever you detect this session was summarised or
compacted and the standing rules may have dropped.

<if>
  <when>This session was summarised or compacted, or standing rules may have dropped</when>
  <then>Run `/carnival-prime` again</then>
</if>

<if>
  <when>About to sling or about to advance</when>
  <then>Run `/carnival-prime` again so prime stays sticky</then>
</if>

Done when prime is in force.

## 2. Coordinate

Talk to the human. Turn goals into tickets on the configured tracker:

- Spec / parent → Follow `/to-spec`'s SKILL.md rigorously (via prime).
- Child tickets / individual tickets → Follow `/to-tickets`'s SKILL.md rigorously (via prime).

Work the **frontier**: open, unblocked tickets. The slung role claims the
ticket — you select and sling.

<if>
  <when>Need a parent spec</when>
  <then>Follow `/to-spec`'s SKILL.md rigorously (via prime)</then>
</if>

<if>
  <when>Need child tickets or individual tickets</when>
  <then>Follow `/to-tickets`'s SKILL.md rigorously (via prime)</then>
</if>

<if>
  <when>Tracker from `/setup-matt-pocock-skills` is missing or unusable</when>
  <then>Stop and tell the human to configure it — do not invent local status</then>
</if>

Done when the next action is clear — sling, wait, spot, or ask the human.

## 3. Sling

Raise one subagent or fresh session per ticket (or patrol), using the harness's
own machinery.

Role briefs live on `/carnival-prime`. Read the matching brief from prime and
include that file's full contents in the agent's first instructions.

In that agent's first instructions, tell it — in order — to:

1. Run `/carnival-prime`
2. Follow the included role brief exactly
3. Work only that assignment
4. Finish with `/carnival-done` or `/carnival-blocked`

Pass the ticket identity (or patrol scope) and enough tracker context to start.
One assignment, one role brief.

Paste this shape as their first instructions:

```text
1. Run /carnival-prime
2. Follow this role brief exactly:
<full contents of the matching role brief from carnival-prime>
3. Work only this assignment: <TICKET_OR_PATROL_SCOPE>
4. Finish with /carnival-done or /carnival-blocked
```

<if>
  <when>Choosing which role brief to include</when>
  <then>Follow the Role briefs If→Then rules on `/carnival-prime`</then>
</if>

Done when every live sling has been raised with that prompt shape.

## 4. Advance

When an agent reports via `/carnival-done` or `/carnival-blocked`, update your
picture from the tracker. Sling the next frontier ticket, raise a spotter when
progress is unclear, or stop when the spec's acceptance criteria are met.

Refresh the configured tracker. Chat `/carnival-done` / `/carnival-blocked`
reports help; the tracker is authoritative.

<if>
  <when>Frontier has an open, unblocked ticket</when>
  <then>Sling it (step 3)</then>
</if>

<if>
  <when>Progress is unclear</when>
  <then>Sling with the spotter brief from `/carnival-prime`</then>
</if>

<if>
  <when>Spec acceptance criteria are met on the tracker, or the human ends the carnival</when>
  <then>Stop</then>
</if>

Done when the human's goal is satisfied on the tracker, or they end the carnival.
