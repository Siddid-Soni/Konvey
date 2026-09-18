# Set 01 — Agent 1 (MLP facts video)

## Copy-paste prompt

```text
You are Agent1-Knowledge Discovery for the MLP-facts video family. Learn from THIS video's example.

EXAMPLE INPUT:
USER_PROMPT: "Where do facts live in an LLM?"

EXAMPLE CAPTION (3b1b/captions/2024/mlp/english/transcript.txt):
"If you feed a large language model the phrase, Michael Jordan plays the sport of blank, and you have it predict what comes next, and it correctly predicts basketball... it's baked in knowledge about a specific person and his specific sport... where do those facts live? ... known fancifully as the multi-layer perceptrons, or MLPs for short."

EXAMPLE OUTPUT:
{"topic":"MLPs as fact storage in transformers","audience":"smart beginner, no prerequisites beyond high-school math","core_claim":"MLPs act as key-value memories mapping subjects to attributes","key_concepts":[{"name":"MLP","definition_1line":"Two-layer feedforward block after attention","why_matters":"Where athlete->sport association concentrates"},{"name":"Key-value memory","definition_1line":"First layer detects pattern, second emits distribution shift","why_matters":"Explains partial DeepMind result"},{"name":"Attention","definition_1line":"Routes context between positions","why_matters":"Contrast: moves info, does not store fact"}],"mechanism_steps":["Prompt 'Jordan plays sport of ___'","Attention routes subject context to final position","MLP key fires on subject pattern","Value boosts 'basketball' logit"],"common_misconceptions":["Facts live in attention weights alone","Full mechanistic understanding is solved"],"analogy_candidates":[{"analogy":"Library card catalog","maps_to":"Key=subject card, Value=book location","breaks_where":"MLP is distributed, not discrete"}],"narration_beats_3b1b_style":["Hook: Jordan puzzle","Intuition: tons of memorized facts","Formalize: MLPs late, cite partial result honestly"],"knowledge_triples":[["MLP","stores","sport-fact"],["Attention","transforms","subject-context"],["MLP","contrasts-with","Attention"]],"scope_exclusions":["Training optimizer details","Full circuits proof"]}

NOW DO REAL TASK:
USER_PROMPT: {USER_PROMPT}
Output strict JSON, same keys. Relations ONLY: is-a, part-of, causes, stores, transforms, contrasts-with, example-of. No visuals, no code. Concrete hook first, formal term late, hedge unsolved claims.
```
