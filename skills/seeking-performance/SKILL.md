---
name: seeking-performance
description: Audit performance and rank bottlenecks by Big O complexity.
---

Audit every subsystem in scope. Change code only if the user requests fixes.

1. Map entry points and trace costly paths: loops, recursion, collection
   pipelines, queries, I/O, allocations, and repeated work.

2. For each suspected bottleneck, define input variables, derive worst-case
   time and space complexity, and verify reachability with realistic inputs.
   Profile or benchmark where practical; distinguish potential costs from
   measured bottlenecks.

3. Report findings in descending order of time-complexity growth. State
   scaling assumptions when comparing multiple input variables. Break ties
   using space, call frequency, input size, and measured impact. Use those
   tie-breakers when growth rates cannot be compared, and say why.

Each finding must include:

- Rank, asymptotic severity, source location, and caller path.
- Input variables and current time and space complexity.
- Cause and source evidence.
- For measurements: workload, command, runtime/compiler version, and
  relevant machine/OS details needed to reproduce them.
- Proposed fix and expected complexity.
- Confidence and missing evidence.

Finish with a coverage summary accounting for every subsystem in scope.
Support every finding with source analysis. If none qualify, report what
you inspected and ruled out.
