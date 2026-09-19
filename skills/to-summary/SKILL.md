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

Make a work directory alongside it for the layer files.

Ask once:

> Any particular focus, audience, format, or length? Say "no" for a general
> summary.

Use Summary instructions supplied with the invocation and proceed. Complete
this step when the source is one readable path on disk, the work directory
exists, and the Summary instructions are clear.

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

Retry a missing or failed chunk. Complete the layer only when every chunk range
has exactly one layer file, and you hold the ordered list of their paths.

## 4. Repeat

Probe the layer files together (`wc -c <workdir>/<layer>-*`). While they exceed
50,000 tokens, group them in source order into batches of roughly 25,000
tokens or fewer and run another reduction layer: each subagent `cat`s its batch
in order and writes one file at the next layer, under the same Summary
instructions and 10:1 target.

Complete reduction when one layer's files total at most 50,000 tokens and
every original chunk reaches that layer through an unbroken line of files.

## 5. Write the final summary

Read the final-pass input: the source file, or the last layer's files in source
order.

Apply the Summary instructions. With none, write a broad-audience summary of at
most 1,000 words in continuous prose paragraphs. Use uncited prose by default;
add citations when requested.

Return the summary in chat. When the user requests a file, use their path or
create a uniquely named Markdown file in the operating system's temporary
directory.

Complete only when the final summary satisfies the requested focus, audience,
format, and length. Deliver only the final summary.
