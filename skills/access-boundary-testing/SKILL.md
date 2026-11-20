---
name: access-boundary-testing
description: Test access boundaries by acting as different real users. Create isolated accounts, tenants, roles, and subscription states; try other users' resource IDs, prohibited writes, direct API calls bypassing the UI, and access after downgrade or expiry. Use when checking object-level or function-level authorization (IDOR/BOLA, role isolation).
---

# Access boundary testing

Test **as different real users**, not just against invalid inputs. A
malformed request proves nothing about authorization; a valid request from
the wrong principal proves everything. This addresses object-level and
function-level authorization risks identified by OWASP: [API1:2023 Broken
Object Level Authorization](https://owasp.org/API-Security/top-10/2023/#api1broken-object-level-authorization)
(BOLA, often called IDOR) and [API5:2023 Broken Function Level
Authorization](https://owasp.org/API-Security/top-10/2023/#api5broken-function-level-authorization).
A hidden button is not a boundary; a server that enforces it is.

Run only in a disposable environment against test-owned accounts. Never
probe production data or real customer accounts, and never attempt access
you are not authorized to attempt. Produce evidence and reproducers;
implement product fixes only when the user requests them.

## 1. Map the boundaries

Use the routes, handlers, data schema, and authorization checks in the
repository to list every operation that is protected by who owns or may
act on a resource. For each, record:

- the actor class (owner, other user, tenant member, role, administrator,
  anonymous, expired or downgraded principal);
- the protected resource and how its identifier is obtained;
- the expected decision for each actor class (allow, deny, or
  out-of-scope), grounded in documentation or the authorization code — not
  in what the UI shows.

Trace the UI to the API: a control the UI hides or disables is a probe
candidate, not evidence of enforcement.

Complete this step with a boundary inventory: one row per operation and
actor class, each with its expected decision. A boundary with no recorded
expectation cannot be classified later.

## 2. Create isolated principals

Create isolated test accounts, tenants, roles, and subscription states on
the disposable environment. Seed each principal with its own resources so
that any cross-principal effect is attributable. Include:

- at least one ordinary owner per resource under test;
- one principal per privileged role the system defines;
- one downgraded, cancelled, and expired principal for every
  subscription-gated operation;
- an unauthenticated client where the operation is reachable without
  credentials.

Where the system does not let you create these principals directly (for
example, an approval-gated role), record that as a blocked setup step with
the concrete prerequisite, and continue with the principals that exist.

Record the build, configuration, and starting state. These principals are
the test fixtures: every probe below names its actor and its target.

## 3. Probe across the boundaries

For each boundary row, attempt the operation with every actor class whose
expected decision differs from the owner's. Use the real client path —
the public API or another supported interface — with the actor's genuine
credentials or session, not a hand-built request that skips the client's
own behavior.

Vary the attack, not just the actor:

- another principal's resource identifier in an otherwise valid request;
- a prohibited write (delete, transfer, refund, role change) with valid
  credentials but the wrong role;
- the operation directly against the API, bypassing the UI that hides it;
- the same request after downgrade, cancellation, or expiry, reusing the
  previous session or token;
- enumeration: collect identifiers from list endpoints, error messages,
  or shared links, then use them as another principal.

Run a positive control for every boundary: the authorized principal must
succeed on the same operation, proving the probe is capable of succeeding
when it should. A denied control means the harness cannot distinguish a
boundary from a broken setup.

Check the server's response **and** the lasting effect: re-read the
resource as its owner and inspect the audit log where one exists. A 200
that changes nothing and a 403 that still changed something are both
findings to record, not to smooth over.

Treat a cross-boundary success as a candidate and replay it (step 4).
Treat a denial as evidence, not as a pass, until the positive control
confirms the operation works for the right actor.

## 4. Classify, minimize, and replay

Classify every boundary row as:

- **Blocked** — the probe ran and the boundary held: the unprivileged
  actor is denied and no lasting effect occurs, with a passing positive
  control;
- **Tested** — the probe ran and demonstrated a boundary failure: a
  cross-principal read or write succeeded, confirmed by replay;
- **Untested** — a setup blocker or missing principal prevented the probe
  from running.

Keep the vocabulary exact: blocked means the probe ran and was denied,
tested means the probe broke it, untested means it did not run. Never
merge them into a single "pass".

Minimize each confirmed violation to the smallest actor, resource, and
action that reproduces it, then replay from the recorded starting state.
Keep unauthorized successes and unauthorized changes as distinct findings:
reading another user's data and writing it carry different impact.

## Boundary states

Start each boundary row at **Unmapped** and track it independently, so a
blocked principal does not stop probes on other rows.

| State | Event and guard | Next state and action |
| --- | --- | --- |
| Unmapped | Step 1 records an expected decision for this actor class. | Mapped. Create the principals for step 2. |
| Mapped | The principals exist and each owns its seeded resources. | Probing. Run every differing actor class, each with its positive control. |
| Probing | The unprivileged actor is denied, no durable effect occurs, and the positive control passes. | Blocked. Record the response and effect check. |
| Probing | The unprivileged actor reads or changes the resource. | Candidate. Minimize before calling it a violation. |
| Probing | The principal or prerequisite cannot be created. | Untested. Record the blocker and next check. |
| Candidate | The minimized replay from the starting state reproduces the access. | Tested. Preserve the reproducer. |
| Blocked or candidate | The build, authorization code, or account state changes. | Mapped. Replay under the new conditions before reusing the outcome. |

## 5. Preserve the result

Write a report alongside the harness and captures. Include:

- the boundary inventory, each row's classification, and the actor and
  operation for every probe;
- for each violation, the principal, resource, action sequence, expected
  and actual outcomes, repeat observations, and the minimized replay;
- the blocked rows with their effect checks, the untested rows with their
  missing principals or prerequisites, and the positive controls;
- exact setup, build, and replay commands and the environment they ran in.

Done when every discovered boundary is classified as tested, blocked, or
untested, with successful authorized controls and replayable failures.
A run that ends with untested rows is a partial result; report them with
their next check rather than calling the boundary set covered. Remove
only test-owned accounts, data, and sessions, and verify nothing the pass
created remains.
