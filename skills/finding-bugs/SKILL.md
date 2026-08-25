---
name: finding-bugs
description: Find bugs using coverage-guided, property-based testing.
---

Your task is to find reproducible bugs using **coverage-guided, property-based testing** (CGPT).

1. Specify every API behavior and domain rule as executable properties. Instrument properties and targets only.
2. Seed randomly. Keep inputs that add coverage; favor precondition passes, keep novel discards. Apply type-aware mutations; restart randomly when coverage stalls.
3. Use /diagnosing-bugs on each finding and keep only the tightly reproducible bugs. Report them to the user in really simple (but domain-accurate) language.

Follow this logic: "Rather than just generating a fresh random input at each iteration, CGPT can also produce new inputs by mutating previous ones using type-aware, generic mutation operators. The target program is instrumented to track which control flow branches are executed during a run and inputs whose runs expand control-flow coverage are retained for future mutations. This means that, when sparse conditions in the target are satisfied and new coverage is observed, the input that triggered them will be retained and used as a springboard to go further."
