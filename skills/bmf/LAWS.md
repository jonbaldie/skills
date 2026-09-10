# BMF law catalogue

Use this catalogue only after the contract, carrier, and Reference version are
explicit. A rule licenses an **Equality** row only when every premise holds for
the program in view. Otherwise keep the premise as a proof obligation or label
the move a Refinement or Heuristic.

The notation is intentionally conventional:

- `f ∘ g` means apply `g`, then `f`.
- `id` returns its input unchanged.
- `xs ++ ys` concatenates lists.
- `map(f, xs)` applies `f` to every element.
- `filter(p, xs)` retains the elements satisfying `p`.
- `foldr(step, z, xs)` replaces `[]` with `z` and each list constructor with
  `step`.
- `scanl(step, z, xs)` returns the initial state and every successive prefix
  state.

In a Derivation artifact, explain a move in plain language before giving its
formal name.

## Semantic baseline

The equations below compare observable values under pure, total, deterministic
evaluation. Check effects, exceptions, floating-point rounding, evaluation
order, strictness, divergence, infinity, and concurrency separately. A rewrite
that changes one of those observations needs a narrower contract or a different
classification.

### Choose the carrier first

| Carrier | Operation | Laws available by default | Meaning retained |
| --- | --- | --- | --- |
| List | concatenation | associative; empty identity | order and duplicates |
| Bag | bag union | associative; commutative; empty identity | duplicates, not order |
| Set | set union | associative; commutative; idempotent; empty identity | membership only |
| Tree | declared constructor or combine | only the laws established for that tree | branching shape unless abstracted away |
| Stream | declared stream operation | productivity-sensitive | order; possibly infinite production |

Moving from a list to a bag permits reordering but loses order. Moving from a
bag to a set permits deduplication but loses multiplicity. Those moves are
Refinements only when the contract makes the lost distinction unobservable.

## Composition

### Identity

**Plain statement:** Doing nothing before or after a function changes nothing.

```text
id ∘ f = f
f ∘ id = f
```

**Premises:** The two sides have matching types and the semantic baseline
holds.

**Tiny example:** Parsing and then applying `id` returns the parsed value.

**Counterexample:** An apparent identity that logs, copies, validates, throws,
or changes object identity is not `id` under a contract that observes that
behavior.

### Associativity

**Plain statement:** Regrouping a pipeline does not change which functions run
or their order.

```text
(f ∘ g) ∘ h = f ∘ (g ∘ h)
```

**Premises:** Functions are composable and the semantic baseline holds.

**Tiny example:** `render ∘ (validate ∘ parse)` equals
`(render ∘ validate) ∘ parse` as a value-producing pipeline.

**Counterexample:** Regrouping resource acquisition or asynchronous effects may
change timing, cleanup, or failure behavior.

## Map

### Map identity

**Plain statement:** Mapping the identity function leaves a collection alone.

```text
map(id, xs) = xs
```

**Premises:** The carrier's map preserves its structure and `id` is observable
identity.

**Tiny example:** Mapping `x => x` over `[2, 3]` yields `[2, 3]`.

**Counterexample:** A mapping API that clones elements can change observable
identity even when values compare equal.

### Map fusion

**Plain statement:** Two consecutive element-wise passes can become one pass.

```text
map(f, map(g, xs)) = map(f ∘ g, xs)
```

**Premises:** `f` and `g` are pure and total, and the carrier obeys the map
laws.

**Tiny example:** Incrementing and then doubling `[1, 2]` is the same as mapping
`x => 2 * (x + 1)` once.

**Counterexample:** If either function logs, counts calls, throws, or mutates,
fusion can change observable behavior or failure timing.

### Map over concatenation

**Plain statement:** Mapping after joining two lists equals mapping each list
before joining them.

```text
map(f, xs ++ ys) = map(f, xs) ++ map(f, ys)
```

**Premises:** List concatenation is the carrier operation and `f` is pure and
total.

**Tiny example:** Doubling `[1] ++ [2, 3]` equals `[2] ++ [4, 6]`.

**Counterexample:** The equation does not license reordering the two lists.

## Filter

### Filter over concatenation

**Plain statement:** Filtering a joined list equals filtering both parts and
then joining them.

```text
filter(p, xs ++ ys) = filter(p, xs) ++ filter(p, ys)
```

**Premises:** `p` is pure, total, and deterministic.

**Tiny example:** Keeping even values from `[1, 2] ++ [3, 4]` yields
`[2] ++ [4]`.

**Counterexample:** A predicate based on call count or mutable state can select
different elements when the work is partitioned.

### Filter idempotence

**Plain statement:** Applying the same stable filter twice changes no values.

```text
filter(p, filter(p, xs)) = filter(p, xs)
```

**Premises:** `p` is pure, total, and deterministic.

**Tiny example:** Keeping positive numbers twice gives the same list as keeping
them once.

**Counterexample:** A predicate that toggles state may accept an element on one
call and reject it on the next.

### Map–filter interchange

**Plain statement:** A filter after a map can move before the map when its
predicate is translated back to the input type.

```text
filter(p, map(f, xs)) = map(f, filter(p ∘ f, xs))
```

**Premises:** `f` and `p` are pure and total; filtering observes only the mapped
value; order is retained.

**Tiny example:** Filtering doubled values by `value > 10` is equivalent to
filtering inputs by `2 * value > 10` and then doubling them.

**Counterexample:** Reusing `p` unchanged on the input side is generally wrong
when `f` changes the predicate's meaning or type.

## Folds and homomorphisms

### Fold evaluation

**Plain statement:** A right fold is completely characterized by its empty and
non-empty cases.

```text
foldr(step, z, []) = z
foldr(step, z, x : xs) = step(x, foldr(step, z, xs))
```

**Premises:** `foldr` has the stated right-associative semantics.

**Tiny example:** `foldr(+, 0, [1, 2, 3])` expands to `1 + (2 + (3 + 0))`.

**Counterexample:** A left fold has different nesting and may differ for
non-associative operations, stack use, laziness, or floating-point arithmetic.

### List homomorphism

**Plain statement:** A computation can run on chunks and combine their results
when it preserves concatenation.

```text
h([]) = e
h(xs ++ ys) = h(xs) ⊗ h(ys)
```

**Premises:** `⊗` is associative with identity `e`, and both equations hold
for every valid list.

**Tiny example:** `length(xs ++ ys) = length(xs) + length(ys)`, so lengths can
be computed per chunk and added.

**Counterexample:** Combining two chunk averages with `(a + b) / 2` is wrong
when the chunks have different sizes; the result must also retain counts.

### Fold fusion

**Plain statement:** Post-processing a fold can move into the fold when it
commutes with every fold step.

```text
h(foldr(f, z, xs)) = foldr(g, h(z), xs)
```

provided, for every `x` and `acc`:

```text
h(f(x, acc)) = g(x, h(acc))
```

**Premises:** The commuting condition holds over every reachable accumulator;
the functions meet the semantic baseline.

**Tiny example:** Prove the commuting equation for one constructor, then replace
the post-process-plus-fold pipeline with the fused fold.

**Counterexample:** Matching only the empty case is insufficient; one failing
constructor case invalidates fusion.

### Fold–map fusion

**Plain statement:** A map consumed immediately by a fold can become work inside
the fold step.

```text
foldr(f, z, map(g, xs))
= foldr((x, acc) => f(g(x), acc), z, xs)
```

**Premises:** `f` and `g` meet the semantic baseline and `foldr` has the stated
semantics.

**Tiny example:** Summing squared values needs one fold whose step adds
`x * x`.

**Counterexample:** Fusion can change when an exception occurs or whether a
lazy mapped value is evaluated.

### Banana split

**Plain statement:** Two folds over the same input can share one traversal by
carrying both accumulators.

```text
(foldr(f, a, xs), foldr(g, b, xs))
= foldr((x, (u, v)) => (f(x, u), g(x, v)), (a, b), xs)
```

**Premises:** Both folds meet the semantic baseline, traverse the same carrier,
and the paired evaluation preserves all observations required by the contract.

**Tiny example:** Compute a list's sum and length as the pair `(sum, count)` in
one traversal.

**Counterexample:** Pairing a short-circuiting fold with a full fold can force
work the original program avoided.

## Scan and accumulation

### Prefix accumulation

**Plain statement:** A scan computes every prefix result by carrying the prior
state instead of folding each prefix from scratch.

```text
map(foldl(step, z), inits(xs)) = scanl(step, z, xs)
```

Here `inits(xs)` contains the empty prefix followed by every non-empty prefix.

**Premises:** The standard `foldl`, `inits`, and `scanl` conventions above are
used; `step` meets the semantic baseline; the list is finite when the complete
result is demanded.

**Tiny example:** Prefix sums of `[2, 3, 4]` are `[0, 2, 5, 9]`.

**Counterexample:** Omitting the empty prefix shifts the two sides by one
element; demanding the last result of an infinite scan does not terminate.

## Horner-style distribution

### Polynomial Horner rule

**Plain statement:** Distributivity can turn repeated powers and a final sum
into one nested accumulation.

For coefficients in lowest-power-first order:

```text
sum(map((a, i) => a * x^i, indexed(coefficients)))
= foldr((a, acc) => a + x * acc, 0, coefficients)
```

**Premises:** The numeric operations have the identities, associativity, and
distributivity used by the rearrangement; coefficient order is explicit.

**Tiny example:** `[2, 3, 4]` at `x = 10` becomes
`2 + 10 * (3 + 10 * 4) = 432`.

**Counterexample:** Fixed-width overflow or floating-point rounding can make
the rearranged computation observably different.

Use the same pattern beyond polynomials only after stating the distributive law
that removes the repeated nested work.

## Unfold and deforestation

### Unfold evaluation

**Plain statement:** An unfold builds a sequence by repeatedly testing a seed,
emitting a value, and producing the next seed.

```text
unfold(done, emit, next, seed)
= []                                      when done(seed)
= emit(seed) : unfold(done, emit, next, next(seed)) otherwise
```

**Premises:** `done`, `emit`, and `next` meet the semantic baseline; termination
or stream productivity matches the contract.

**Tiny example:** Repeatedly emit `n` and decrement it until zero to generate a
countdown.

**Counterexample:** A seed that never reaches `done` cannot produce a finite
list, though it may define a productive stream.

### Fold after unfold

**Plain statement:** A consumer can run directly over generated values without
materializing the intermediate sequence.

```text
foldr(step, z, unfold(done, emit, next, seed)) = go(seed)

go(s) = z                              when done(s)
go(s) = step(emit(s), go(next(s)))     otherwise
```

**Premises:** Producer and consumer meet the semantic baseline; termination,
productivity, evaluation order, and strictness remain valid for the contract.

**Tiny example:** Sum a generated countdown while generating it, with no list
between producer and consumer.

**Counterexample:** In a strict language the fused recursion may change stack
use; with effects it may change when generation and consumption occur.

## Sources

The presentation above uses conventional functional notation rather than
historic Squiggol notation. These primary sources provide the calculational
method and the laws' broader setting:

- Lambert Meertens, [*Algorithmics: Towards programming as a mathematical
  activity*](https://ir.cwi.nl/pub/2686/2686D.pdf).
- Richard Bird, [*Lectures on Constructive Functional
  Programming*](https://www.cs.ox.ac.uk/files/3390/PRG69.pdf).
- Jeremy Gibbons, [*Calculating Functional
  Programs*](https://www.cs.ox.ac.uk/people/jeremy.gibbons/publications/acmmpc-calcfp.pdf).
- Jeremy Gibbons, [*Origami
  Programming*](https://www.cs.ox.ac.uk/jeremy.gibbons/publications/origami.pdf).
- Jeremy Gibbons, [*The School of Squiggol: A History of the Bird–Meertens
  Formalism*](https://www.cs.ox.ac.uk/people/jeremy.gibbons/publications/squiggol-history.pdf).
