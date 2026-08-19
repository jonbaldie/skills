---
name: carnival-prime
description: >
  Prime carnival standing workflow rules. Use when opening a carnival, starting
  a role assignment, or restoring adherence after the session was summarised.
---

# Carnival prime

Load these standing rules for the rest of this session. Prefer an autocompact
window of 150k tokens or less so this prime stays sticky.

<role name="primed-agent">
  <responsibility>Obey the If→Then standing rules below for the rest of this session.</responsibility>
  <responsibility>Use the issue tracker `/setup-matt-pocock-skills` configured for this repo, unless context already makes the tracker obvious.</responsibility>
</role>

## Standing rules

1. Working on production code: use /implement's SKILL.md rigorously.
2. Looking at a bug: use /diagnosing-bugs's SKILL.md rigorously.
3. If you need to make a spec: use /to-spec's SKILL.md rigorously.
4. If you need to make child tickets or individual tickets: use /to-tickets's SKILL.md rigorously.
5. Working on resolving merge conflicts: always use /resolving-merge-conflicts's SKILL.md rigorously.

<if>
  <when>Working on production code</when>
  <then>Use /implement's SKILL.md rigorously</then>
</if>

<if>
  <when>Looking at a bug</when>
  <then>Use /diagnosing-bugs's SKILL.md rigorously</then>
</if>

<if>
  <when>Need to make a spec</when>
  <then>Use /to-spec's SKILL.md rigorously</then>
</if>

<if>
  <when>Need to make child tickets or individual tickets</when>
  <then>Use /to-tickets's SKILL.md rigorously</then>
</if>

<if>
  <when>Working on resolving merge conflicts</when>
  <then>Always use /resolving-merge-conflicts's SKILL.md rigorously</then>
</if>

## Tracker

Use the issue tracker `/setup-matt-pocock-skills` configured for this repo, unless
context already makes the tracker obvious.

## Done when

These five rules are in force for this session. Re-run this skill after any
session summary that may have dropped them.

<if>
  <when>Any session summary may have dropped them</when>
  <then>Re-run this skill</then>
</if>
