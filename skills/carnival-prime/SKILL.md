---
name: carnival-prime
description: >
  Prime carnival standing workflow rules and role briefs. Use when opening a
  carnival, priming a slung agent, slinging a role, or restoring adherence after
  the session was summarised.
---

# Carnival prime

Load these standing rules for the rest of this session.

<role name="primed-agent">
  <responsibility>Obey the If→Then standing rules below for the rest of this session.</responsibility>
  <responsibility>Use the issue tracker `/setup-matt-pocock-skills` configured for this repo, unless context already makes the tracker obvious.</responsibility>
  <responsibility>When slinging as mayor, read the matching role brief below and include its full contents in that agent's first instructions.</responsibility>
</role>

## Standing rules

1. Working on production code: Follow /implement's SKILL.md rigorously.
2. Looking at a bug: Follow /diagnosing-bugs's SKILL.md rigorously.
3. If you need to make a spec: Follow /to-spec's SKILL.md rigorously.
4. If you need to make child tickets or individual tickets: Follow /to-tickets's SKILL.md rigorously.
5. Working on resolving merge conflicts: Always follow /resolving-merge-conflicts's SKILL.md rigorously.

<if>
  <when>Working on production code</when>
  <then>Follow /implement's SKILL.md rigorously</then>
</if>

<if>
  <when>Looking at a bug</when>
  <then>Follow /diagnosing-bugs's SKILL.md rigorously</then>
</if>

<if>
  <when>Need to make a spec</when>
  <then>Follow /to-spec's SKILL.md rigorously</then>
</if>

<if>
  <when>Need to make child tickets or individual tickets</when>
  <then>Follow /to-tickets's SKILL.md rigorously</then>
</if>

<if>
  <when>Working on resolving merge conflicts</when>
  <then>Always follow /resolving-merge-conflicts's SKILL.md rigorously</then>
</if>

## Role briefs

When you sling, read the matching brief and include its full contents in that
agent's first instructions:

- Hand (production code or bug) — [hand.md](hand.md)
- Rigger (merge or conflict-resolution) — [rigger.md](rigger.md)
- Spotter (frontier patrol) — [spotter.md](spotter.md)

<if>
  <when>Ticket is production code or a bug</when>
  <then>Read and include [hand.md](hand.md)</then>
</if>

<if>
  <when>Ticket is merge or conflict-resolution</when>
  <then>Read and include [rigger.md](rigger.md)</then>
</if>

<if>
  <when>Progress is unclear, or the frontier may have stalled work</when>
  <then>Read and include [spotter.md](spotter.md) (patrol scope, not a code ticket)</then>
</if>

## Tracker

Use the issue tracker `/setup-matt-pocock-skills` configured for this repo, unless
context already makes the tracker obvious.

## Done when

These five rules are in force for this session, and the role briefs above are
reachable. Re-run this skill after any session summary that may have dropped
them.

<if>
  <when>Any session summary may have dropped them</when>
  <then>Re-run this skill</then>
</if>
