---
name: outpost-edict
description: >
  Outpost mode only. Edict standing rules and role briefs; re-edict after
  summary.
---

# Outpost edict

Load these standing rules for the rest of this session.

<role name="edict-agent">
  <responsibility>Obey the If→Then standing rules below for the rest of this session.</responsibility>
  <responsibility>Use the issue tracker `/setup-matt-pocock-skills` configured for this repo, unless context already makes the tracker obvious.</responsibility>
  <responsibility>When dispatching as prefect, read the matching role brief below and include its full contents in that agent's first instructions.</responsibility>
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

When you dispatch, read the matching brief and include its full contents in that
agent's first instructions:

- Labor (production code or bug) — [labor.md](labor.md)
- Splicer (merge or conflict-resolution) — [splicer.md](splicer.md)
- Patrol dog (perimeter patrol) — [patrol-dog.md](patrol-dog.md)

<if>
  <when>Ticket is production code or a bug</when>
  <then>Read and include [labor.md](labor.md)</then>
</if>

<if>
  <when>Ticket is merge or conflict-resolution</when>
  <then>Read and include [splicer.md](splicer.md)</then>
</if>

<if>
  <when>Progress is unclear, or the perimeter may have stalled work</when>
  <then>Read and include [patrol-dog.md](patrol-dog.md) (patrol scope, not a code ticket)</then>
</if>

## Tracker

Use the issue tracker `/setup-matt-pocock-skills` configured for this repo, unless
context already makes the tracker obvious.

## Config

If `.ration.json` exists in the cwd, read it per
[ration.json-FORMAT.md](ration.json-FORMAT.md). Honour `maxLabor` /
`maxSplicers` / `maxPatrolDogs` when dispatching. Pass `model` and `thinking`
into dispatch instructions when the harness accepts them. Missing file →
defaults. Do not invent harness features.

<if>
  <when>`.ration.json` exists in the cwd</when>
  <then>Read it per [ration.json-FORMAT.md](ration.json-FORMAT.md) and apply caps/preferences when dispatching</then>
</if>

<if>
  <when>`.ration.json` is missing</when>
  <then>Use FORMAT defaults</then>
</if>

## Done when

These five rules are in force for this session, the role briefs above are
reachable, and any cwd `.ration.json` has been applied or defaulted. Re-run
this skill after any session summary that may have dropped them.

<if>
  <when>Any session summary may have dropped them</when>
  <then>Re-run this skill</then>
</if>
