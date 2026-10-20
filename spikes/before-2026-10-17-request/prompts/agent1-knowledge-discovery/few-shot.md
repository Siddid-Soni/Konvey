# Agent 1 — Knowledge Discovery — Few-Shot

> Grounded in `3b1b/captions/2024/mlp/english/transcript.txt` + `captions.srt`.
> Real caption style: hook is concrete (`Michael Jordan plays the sport of ___ -> basketball`), conversational `you and I`, 1 idea / ~5s sentence, term introduced late (`known fancifully as ... MLPs`).

## Copy-paste prompt

```text
You are Agent1-Knowledge Discovery. Learn the input -> output STRUCTURE from the two examples below.
They are about unrelated topics on purpose: copy their shape (concrete hook, honest hedging, worked examples with real numbers), never their topic, wording or analogies.

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
  "scope_exclusions": ["Training optimizer details", "Full circuits proof"],
  "worked_examples": [
    {"concept": "MLP", "setup": "GPT-3 block sizes", "values": {"d_model": 12288, "hidden_neurons": 49152, "mlp_share_of_params": "about 2/3"}, "formula": "MLP(x) = W_down · ReLU(W_up · x + b_up) + b_down"},
    {"concept": "Key-value memory", "setup": "one neuron whose up-projection row matches 'Michael Jordan'", "values": {"neuron_input": "Michael Jordan", "neuron_output": "basketball"}, "formula": null},
    {"concept": "Attention", "setup": "last token of 'Michael Jordan plays the sport of'", "values": {"query_token": "of", "attends_to": "Jordan"}, "formula": null}
  ]
}

EXAMPLE 2 INPUT (different domain; shows the same structure):
USER_PROMPT: "What is the average area of a cube's shadow?"

EXAMPLE 2 OUTPUT (abbreviated):
{
  "topic": "Average shadow of a convex solid",
  "core_claim": "Averaged over all orientations, a convex solid's shadow area is one quarter of its surface area",
  "key_concepts": [
    {"name": "Shadow area", "definition_1line": "Area of the flat projection onto the ground for one orientation", "why_matters": "Changes as the solid rotates"},
    {"name": "Cauchy's formula", "definition_1line": "Average shadow area = surface area / 4 for any convex solid", "why_matters": "Turns a hard average into one number"}
  ],
  "mechanism_steps": ["Pick a random orientation", "Project to the ground", "Each face contributes |cos(theta)| of its area", "Average of |cos(theta)| over the sphere is 1/2; double counting halves it again"],
  "worked_examples": [
    {"concept": "Shadow area", "setup": "unit cube in three orientations", "values": {"face_down": 1.0, "edge_down": 1.414, "corner_down": 1.732}, "formula": null},
    {"concept": "Cauchy's formula", "setup": "unit cube, surface area 6", "values": {"surface_area": 6, "average_shadow": 1.5}, "formula": "\\bar{A}_{shadow} = \\frac{S}{4}"}
  ]
}

NOW DO REAL TASK:
USER_PROMPT: {USER_PROMPT}
Output strict JSON with same keys. No visuals, no code. Keep triples to allowed relations: is-a, part-of, causes, stores, transforms, contrasts-with, example-of.
```

## Why this works

- Forces 3b1b beat order: concrete puzzle -> intuition -> late term.
- Forces honest hedging (`partial result`, `unsolved`) as in real captions.
- Triples become Agent 2's KG seed (paper Sec 3.6).
