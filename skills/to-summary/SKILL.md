---
name: to-summary
description: Progressively summarise one large source.
disable-model-invocation: true
---

# To summary

Turn one source into a summary through successive reduction layers.

Hold the source **by reference** the whole way down: a path and a line range,
never its text. Subagents dereference; you read only the final pass.

## 1. Resolve the brief

Require one readable source and normalise it to a local file path:

- a file: use its path;
- a URL: `curl -sL <url> -o <path>`, converting HTML to text;
- pasted text: write it to a file.

Make a uniquely named work directory alongside it for the layer files.

Use Summary instructions supplied with the invocation. Otherwise ask once:

> Any particular focus, audience, format, or length? Say "no" for a general
> summary.

Complete this step when the source is one readable path on disk, the work
directory exists, and the Summary instructions are clear.

Copy the source into the work directory as an immutable input. Check the source
hash before and after copying and the copy's hash; they must match. Workers use
this copy. Keep an ordered lineage map in the work directory with the source
hash, Summary instructions, chunk ranges, parent paths and hashes, output paths
and hashes, and per-chunk and per-layer attempts. Record outputs only after a
worker finishes writing. Give each attempt a fresh output path.

### Reduction states

Start in **Resolve brief**. Size means the byte estimate in step 2.

| State | Event and guard | Next state / action |
| --- | --- | --- |
| Resolve brief | The source and Summary instructions are pinned. | **Probe**. |
| Probe | Input is at most 200,000 bytes. | **Final pass**. |
| Probe | Input exceeds 200,000 bytes. | **Reduce**. Partition with exact ordered coverage. |
| Reduce | A chunk output is missing, failed, or empty for nonempty input. | **Retry chunk**. Correct a concrete cause and retry that chunk once. If there is no correction or the retry fails, enter **Incomplete**. |
| Retry chunk | The replacement output is complete and bound to unchanged inputs. | **Reduce**. Retain exactly one output for the chunk. |
| Reduce | Every chunk has one verified output and lineage covers every input. | **Check layer**. Probe the ordered outputs together. |
| Check layer | The layer is smaller than its inputs and at most 200,000 bytes. | **Final pass**. |
| Check layer | The layer is smaller but still exceeds 200,000 bytes. | **Reduce**. Use it as the next layer's input. |
| Check layer | The layer fails to shrink. | Retry reduction from the same inputs once with a tighter target. If it still fails to shrink, enter **Incomplete**. |
| Final pass | Input hashes and complete lineage still match, and the summary satisfies the brief. | **Delivered**. Return the final summary. |
| Any active state | The requested source or Summary instructions change. | **Resolve brief**. Invalidate derived outputs and start a new run from the changed input. |
| Any active state | A layer input or output hash differs from its recorded value. | **Reduce**. Invalidate that output and its descendants, then rebuild from the nearest verified parents. Return to **Resolve brief** if none remain. |
| Any active state | The task budget is exhausted or work cannot continue. | **Incomplete**. Retain verified artifacts and report the missing coverage or failed guard. |

**Delivered** and **Incomplete** end the run. An incomplete run reports its
status instead of presenting partial coverage as a final summary. On resumption,
verify hashes before reusing artifacts and retain the recorded attempt counts.

## 2. Probe the size

Measure the file from the outside: `wc -lc <path>`. Read bytes ÷ 4 as tokens.

At most 50,000 tokens (200,000 bytes): go to step 5 and read the file there.

Larger: locate the heading lines with `grep -n '^#\+ ' <path>`, then cut lines
1..N into ordered chunks of roughly 25,000 tokens (100,000 bytes) or fewer,
landing each boundary on a heading line where one is near. Cut on line count
alone when the file has no headings.

Complete this step when every line of the file falls in exactly one chunk
range, each range computed from line numbers and byte counts alone.

## 3. Reduce

Spawn one subagent per chunk, up to available concurrency. Give each subagent:

- the source path, its line range, and its position in the source;
- an output path in the work directory, numbered by layer and position;
- the complete Summary instructions;
- a target of prose roughly 10% of its input or less.

Each subagent dereferences its own range (`sed -n 'A,Bp' <path>`), writes its
prose to the output path, and returns that path alone.

Complete a layer only through the **Check layer** guard. Use the lineage map's
ordered paths, rather than a directory glob that could include stale attempts.

## 4. Repeat

Probe only the ordered layer files recorded in the lineage map with `wc -c`.
Compare their total bytes with their inputs before accepting the layer. Group
an accepted layer that still exceeds 50,000 tokens in source order into batches
of roughly 25,000 tokens or fewer. Each subagent `cat`s its batch in order and
writes one file at the next layer under the same Summary instructions and
10:1 target. Apply the retry and progress guards above at each layer.

## 5. Write the final summary

Recheck the requested source hash and the lineage map before finalization.
Read the final-pass input, either the immutable source copy or the last layer's
verified files in source order.

Apply the Summary instructions. With none, write a broad-audience summary of at
most 1,000 words in continuous prose paragraphs. Use uncited prose by default;
add citations when requested.

Return the summary in chat. When the user requests a file, use their path or
create a uniquely named Markdown file in the operating system's temporary
directory.

Complete only when the final summary satisfies the requested focus, audience,
format, and length. Deliver only the final summary.
