# Example 02 — Attention adjectives (fluffy blue creature ... verdant forest)

> Sources:
> - VO: `3b1b/captions/2024/attention/english/transcript.txt` (`a fluffy blue creature roamed the verdant forest`, `mole` polysemy, query/key/dot-product grid)
> - Code: `3b1b/videos/_2024/transformers/attention.py:AttentionPatterns` (word rects `SurroundingRectangle`, `adj_arrows path_arc`, `ContextAnimation`, `NumericEmbedding`, `Brace + CountInFrom(dim 12288)`, `bake_mobject_into_vector_entries`, full `LaggedStart(FadeTransform...)` connections)
> - Prompts: Agent1 CoT -> Agent2 CoT -> Agent3 CoT

## Agent 1 output (abbrev)

```json
{
  "topic": "Single attention head: adjectives update nouns",
  "core_claim": "Queries ask, keys answer, dot-product grid routes adjective meaning into nouns",
  "mechanism_steps": [
    "Embed tokens + positions as vectors E",
    "Compute queries Q=Wq·E and keys K=Wk·E",
    "Dot-product Q·K grid measures match",
    "Softmax + value mix updates noun embeddings E'"
  ],
  "knowledge_triples": [
    ["Query", "transforms", "noun-need"],
    ["Key", "transforms", "adjective-offer"],
    ["Dot-product", "causes", "routing"]
  ]
}
```

## Agent 2 output (abbrev, 3 scenes)

- **S1 hook:** `mole` polysemy (3 phrases) — layout `arrange(DOWN)` — animation `LaggedStartMap(FadeIn, shift=UP)`.
- **S2 build:** `fluffy/blue -> creature` arrows — layout `SurroundingRectangle(word)`, `Arrow(adj_top, noun_top, path_arc=-150°)` — animation `DrawBorderThenFill + ShowCreation(arrows) + ContextAnimation(noun, adj, strengths=[1,1])`.
- **S3 payoff:** embeddings `E` + `Brace + CountInFrom(12288)` + collapse to `E'` — animation `LaggedStart(FadeTransform(entry,sym) + MoveToTarget) + ShowCreation(full_connections, lag_ratio=0.01) + TransformFromCopy(sym, sym_prime)`.

See `agent2-output.json` for full beats with `code_hint`.

## Agent 3

`agent3-S2.py` implements S2 verbatim (rects + curved arrows + ContextAnimation). Run `manimgl agent3-S2.py SingleScene`.
