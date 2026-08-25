---
name: finding-bugs
description: Coverage-guided API and domain bug finding.
---

Intent: Find bugs hidden from random testing by sparse preconditions.

1. Specify every API behavior and domain rule as executable properties. Instrument properties and targets only.
2. Seed randomly. Keep inputs adding coverage; favor precondition passes, keep novel discards. Apply type-aware mutations; restart randomly when coverage stalls.
3. Shrink failures. Rerun to confirm. Plainly report user-impacting counterexamples.
