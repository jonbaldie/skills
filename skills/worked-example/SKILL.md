---
name: worked-example
description: Explain a mechanism through a concrete trace and a comparison that shows why it helps.
disable-model-invocation: true
---

Explain the current topic through a worked example. Start with the example; introduce terminology beside the action it names.

1. **Make the mechanism visible.** Choose a small input and a short piece of code, pseudocode, or everyday process whose relevant decisions the reader can inspect. State the desired outcome or rule being checked. Include enough of the mechanism to explain every step of the trace.
2. **Trace the changes.** Walk the example through successive steps in a compact table or annotated text block. Show the input or state, the decision taken, and the result. For feedback loops, show what is retained and how it affects the next attempt. Continue through at least one consequential decision and its outcome.
3. **Show why it helps.** Run a simple baseline against the same example. Identify the specific work avoided or outcome improved, and connect it to the mechanism in the trace. Keep the comparison concrete: repeated rejected inputs, repeated calculations, extra reads, or another observable cost.
4. **Bound the lesson.** State the general principle in one sentence and one relevant condition where the benefit may disappear. Label invented traces as illustrative; distinguish a possible sequence from a guaranteed outcome.

Keep prose beside the step it explains. Use the smallest visual that exposes the decisions; a diagram should add information beyond the trace.

If the user remains confused, isolate the unclear decision and trace it in smaller steps. If they ask for more examples, choose a second case that reveals a different consequence of the same mechanism. Once they restate the mechanism accurately, confirm briefly and correct only material misunderstandings.
