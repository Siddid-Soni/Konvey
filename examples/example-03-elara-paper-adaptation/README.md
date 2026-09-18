# Example 03 — Elara story (paper adaptation: narrative-to-explainer)

> Sources:
> - Story + triples: `arXiv:2509.04481 Sec 3.1 Table 2` (Elara / hollow oak / map / rocky path / Crystal Cavern / Guardian dragon).
> - Pipeline mapping: paper `Prompt_1` (100-word story) = Agent1, `Prompt_2` (3 frames + `[Object][Relation][Object]`) = Agent2 beats, `Alg 1/2/3` (terrain continuity + offsets + layered render) = Agent2 layout + Agent3 render order.
> - This adapts game-scene pipeline to explainer-video pipeline: terrain -> canvas layout, tiles -> manim objects, offsets -> next_to/arrange.

## Agent 1 output (abbrev)

```json
{
  "topic": "How stories split into 3 visual frames",
  "core_claim": "One story -> 3 time frames, each with 3 spatial triples, rendered with continuity",
  "mechanism_steps": ["Generate 100-word story", "Extract 3 frames", "Triples per frame", "Retrieve assets", "Place with offsets", "Link with precedes"],
  "knowledge_triples": [
    ["Hollow oak", "contains", "ancient map"],
    ["Elara", "stands near", "hollow oak"],
    ["Guardian dragon", "sits atop", "crystal throne"]
  ]
}
```

## Agent 2 output (see `agent2-output.json`)

- Normalizes open relations per paper Sec 3.2: `contains -> on top of`, `stands near -> at left/right of`, `sits atop -> on top of`.
- Continuity grouping per Alg 1: S1+S2 share forest base, S3 cavern base (patch propagation).
- Each triple -> one `layout` op + one `animation` (enter `FadeIn`, relate `TransformFromCopy`, emphasize `Indicate`).
- `precedes` chain S1->S2->S3 (paper Sec 3.6.2).

## Agent 3

`agent3-S1.py` renders Frame 1 (oak + map + Elara) with `arrange + next_to + LaggedStartMap(FadeIn) + GrowArrow`. Same pattern extends to S2/S3 by swapping objects.
