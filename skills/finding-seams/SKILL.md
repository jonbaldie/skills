---
name: finding-seams
description: Find architectural seams where application capabilities could move behind shared interfaces.
---

# Finding Seams

Find application capabilities that belong behind clear, shared interfaces. Aim for **deep modules**: simple interfaces that hide substantial complexity. The UI, API, jobs, and scripts should **dogfood** those interfaces, using capabilities that could also serve external consumers.

## Review

1. **Trace capabilities across callers.** Follow what the application does from its entry points to the business logic and storage. Identify which callers share each capability and how they reach it.
2. **Find the friction.** Look for duplicated business logic, callers bypassing domain rules through database access or private imports, capabilities trapped in UI or transport code, and interfaces that force callers to understand implementation details. Ground each finding in exact code paths and its consequences.
3. **Propose the smallest useful seam.** Describe a shared interface, the logic it would own, and how existing callers would use it. Prefer changes within the existing process. Each proposed step should leave the capability easier to use and its implementation better hidden.

## Output

Return a single ranked list of proposals. Prioritise shared capabilities, bypassed domain rules, and interfaces causing active friction; weigh the benefit against implementation cost and risk.

For each item include:

- **Evidence:** the callers, code paths, and concrete problem.
- **Change:** the capability, proposed interface, and how callers would adopt it.
- **Payoff:** what becomes simpler or more reliable, with the cost and risk that justify its rank.
