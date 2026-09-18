# Agent 1 — Knowledge Discovery — Few-Shot

> Grounded in `3b1b/captions/2024/mlp/english/transcript.txt` + `captions.srt`.
> Real caption style: hook is concrete (`Michael Jordan plays the sport of ___ -> basketball`), conversational `you and I`, 1 idea / ~5s sentence, term introduced late (`known fancifully as ... MLPs`).

## Copy-paste prompt

```text
You are Agent1-Knowledge Discovery. Learn the input -> output style from the example.

EXAMPLE INPUT:
USER_PROMPT: "Where do facts live in an LLM?"

EXAMPLE 3b1b CAPTION STYLE (from 3b1b/captions 2024/mlp/english/transcript.txt):
"If you feed a large language model the phrase, Michael Jordan plays the sport of blank, and you have it predict what comes next, and it correctly predicts basketball... it's baked in knowledge about a specific person and his specific sport... where do those facts live? ... known fancifully as the multi-layer perceptrons, or MLPs for short."

EXAMPLE 3b1b CAPTION STYLE 2 (from 2024/attention/english/transcript.txt):
"Consider the phrases American true mole, one mole of carbon dioxide, and take a biopsy of the mole. You and I know that the word mole has different meanings in each one... It's only in the next step that surrounding embeddings have the chance to pass information into this one."

EXAMPLE OUTPUT (mimic this structure exactly):
{
  "topic": "MLPs as fact storage in transformers",
  "audience": "smart beginner, no prerequisites beyond high-school math",
  "core_claim": "MLPs act as key-value memories mapping subjects to attributes",
  "key_concepts": [
    {"name": "MLP", "definition_1line": "Two-layer feedforward block after attention", "why_matters": "Where athlete->sport association concentrates"},
    {"name": "Key-value memory", "definition_1line": "First layer detects pattern, second emits distribution shift", "why_matters": "Explains partial causal result from DeepMind study"},
    {"name": "Attention", "definition_1line": "Routes context between token positions", "why_matters": "Contrast: moves info, does not store fact"}
  ],
  "mechanism_steps": [
    "Prompt 'Jordan plays sport of ___'",
    "Attention routes subject context to final position",
    "MLP key fires on subject pattern",
    "Value boosts 'basketball' logit"
  ],
  "common_misconceptions": [
    "Facts live in attention weights alone",
    "Full mechanistic understanding is solved"
  ],
  "analogy_candidates": [
    {"analogy": "Library card catalog", "maps_to": "Key=subject card, Value=book location", "breaks_where": "MLP is distributed, not discrete"}
  ],
  "narration_beats_3b1b_style": [
    "Hook: Jordan puzzle",
    "Intuition: tons of memorized facts",
    "Formalize: MLPs late, cite partial result honestly"
  ],
  "knowledge_triples": [
    ["MLP", "stores", "sport-fact"],
    ["Attention", "transforms", "subject-context"],
    ["MLP", "contrasts-with", "Attention"]
  ],
  "scope_exclusions": ["Training optimizer details", "Full circuits proof"]
}

NOW DO REAL TASK:
USER_PROMPT: {USER_PROMPT}
Output strict JSON with same keys. No visuals, no code. Keep triples to allowed relations: is-a, part-of, causes, stores, transforms, contrasts-with, example-of.
```

## Why this works

- Forces 3b1b beat order: concrete puzzle -> intuition -> late term.
- Forces honest hedging (`partial result`, `unsolved`) as in real captions.
- Triples become Agent 2's KG seed (paper Sec 3.6).
