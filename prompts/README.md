# Konvey — Prompt Library

Agent pipeline to generate explainer videos from a prompt (manimgl / 3b1b style).

- **Agent 1 — Knowledge Discovery:** `USER_PROMPT -> KNOWLEDGE_PACK (JSON)`
- **Agent 2 — Planning + Scene Generation:** `KNOWLEDGE_PACK -> 3-scene plan (beats with layout + animation)` — **decides animation**
- **Agent 3 — Coding:** `SCENE_SPEC (1 scene) -> manimgl code` — **implements only**

Each agent has `zero-shot.md`, `few-shot.md`, `cot.md`. Start with few-shot, use CoT on failure, zero-shot as baseline.

## Layout

```text
prompts/agent1-knowledge-discovery/{zero-shot,few-shot,cot}.md
prompts/agent2-planning-scene-generation/{zero-shot,few-shot,cot}.md
prompts/agent3-manim-coding/{zero-shot,few-shot,cot}.md
manim-reference/animations.md      # from manimlib/animation/*.py (docs site is thin)
manim-reference/spatial-layout.md  # paper predicates -> next_to/to_edge/arrange/target
examples/example-01-mlp-facts/                    # Jordan puzzle + mlp.py LastTwoChapters
examples/example-02-attention-adjectives/         # fluffy blue creature + attention.py AttentionPatterns
examples/example-03-elara-paper-adaptation/       # arXiv:2509.04481 Table 2 story -> explainer
```

## Sources

- Captions: `https://github.com/3b1b/captions` (`2024/mlp/english/transcript.txt`, `2024/attention/english/transcript.txt`)
- Code: `https://github.com/3b1b/videos` (`_2024/transformers/mlp.py`, `attention.py`)
- Pipeline: `https://arxiv.org/abs/2509.04481` (Prompt_1/Prompt_2, triples, Alg 1/2/3, precedes KG)
- Manim API: `https://3b1b.github.io/manim/` + `https://github.com/3b1b/manim` (`manimlib/animation`, `manimlib/mobject/mobject.py`)

## Run order

```text
Agent1 (few-shot/CoT) -> validate JSON -> Agent2 (few-shot/CoT) -> split S1,S2,S3 -> Agent3 x3 in parallel -> manimgl file.py SingleScene
```
