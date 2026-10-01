---
name: user-journeys
description: Identify the user journeys accounting for 95% of an app or system's activity, distinguishing measured coverage from a hypothesis.
argument-hint: "[app, system, or repository]"
disable-model-invocation: true
---

# User journeys

Find the smallest set of goal-level journeys that accounts for 95% of user
activity. A **journey** runs from a user's trigger to an observable outcome;
features, screens, and endpoints are evidence for journeys, not substitutes.

## 1. Bound the activity

Use the supplied app or system, or the current project when none is named.
Establish the user roles and supported interfaces from the request and available
project documentation. Ask only when ambiguity would materially change the set.

Default to frequency of **user goal attempts**, including failed and abandoned
attempts. Follow an explicitly requested measure instead, such as time spent,
and keep that measure consistent throughout. Record the target, population,
interfaces, activity unit, and observation window; mark unknowns explicitly.

## 2. Gather the candidates

Use available analytics, usage logs, or user research for evidence of frequency.
Read documentation and trace the supported interface into source where available
to establish what users can actually do. For a system described only in prose,
separate supplied facts from assumptions.

Account for every discovered role and user-facing capability in a candidate
journey or a stated exclusion. Include returning use as well as first use.
Source structure and test coverage establish capabilities, not usage shares.
Finish with a candidate inventory and a record of the evidence available for
ranking it, including access or instrumentation gaps.

## 3. Shape complete journeys

For each candidate, capture:

- Actor, goal, trigger, and necessary starting state.
- The ordinary action sequence through the supported interface.
- The observable outcome that satisfies the goal.
- Sources supporting the path and, separately, its expected frequency.

Group variants serving the same goal; split distinct goals even when they share
screens. Keep shared steps such as sign-in inside the journeys they enable,
unless they are themselves the user's goal. Preserve frequent recovery paths
within their journey. Each journey must be concrete enough for someone to
attempt from its description, with a checkable outcome.

## 4. Find the 95% boundary

**With usable frequency data:** map activity to the candidate journeys using a
stated attribution rule. Count each activity unit once; split multi-goal sessions
into attempts when attempts are the unit. Keep unmapped activity in the denominator
and disclose excluded traffic, sampling, and missing populations. Calculate each
journey's share, rank descending, and take the shortest prefix whose cumulative
share reaches at least 95%. Use unrounded values for the cutoff and report the
actual total. If mapped journeys fall short of 95%, report the achieved coverage
and the unmapped gap. If the data cannot establish coverage of the scoped
population, label the result partial rather than extending an observed share
to all users.

**Without usable frequency data:** rank a proposed core by evidence of recurring
goals, role mix, and the normal operating cycle. Explain the frequency inference
for each journey and why excluded candidates plausibly form a low-frequency
long tail. Label the set a **95% coverage hypothesis**, with coverage unverified.
Use numeric estimates only when backed by an explicit estimation basis, labelled
as estimates; otherwise report shares as unknown. Name the smallest missing
measurement or user answer that could confirm or change the boundary.

The cutoff determines the list length. Keep rare but consequential journeys
visible as risk notes outside the core set; frequency and importance are separate.

## 5. Return the journey map

Lead with the scope, activity measure, and coverage status: measured, partial,
or hypothesised. Return the ranked journeys with the details from step 3 and
individual and cumulative shares where supported. Cite the frequency evidence
beside the ranking so the user can audit it.

Close with the excluded long tail, consequential exceptions, and unresolved
coverage gaps. Return the map directly; testing journeys or changing the system
is a separate task.
