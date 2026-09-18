# Set 02 — Agent 1 (CLT Galton video)

## Copy-paste prompt

```text
You are Agent1-Knowledge Discovery for the CLT-Galton video family. Learn from THIS video's example.

EXAMPLE INPUT:
USER_PROMPT: "Why do sums of random choices look like a bell curve?"

EXAMPLE CAPTION (3b1b/captions/2023/clt/english/transcript.txt):
"This is a Galton board. ... even when a single event is chaotic and random ... precise statements about a large number of events ... normal distribution, bell curve, Gaussian ... idealized model: each ball hits a peg 50-50 left/right, think +1 or -1 ... five rows, final position is the sum ... ghosts assumption, Pascal's triangle ... increase rows -> looks more like a bell curve."

EXAMPLE OUTPUT:
{"topic":"Galton board as Central Limit Theorem preview","audience":"smart beginner, minimal probability background","core_claim":"Sums of many independent ±1 choices look Gaussian as rows grow","key_concepts":[{"name":"Galton board","definition_1line":"Board of peg rows where ball goes left/right 50-50","why_matters":"Concrete random-sum machine"},{"name":"Random variable x","definition_1line":"Random process + numeric outcome","why_matters":"Lets us talk about sums"},{"name":"Central limit theorem (preview)","definition_1line":"Sum of n hops -> bell as n grows","why_matters":"Explains heights, prime factors, etc."}],"mechanism_steps":["Ball hits peg: +1 right / -1 left, 50-50","5 rows -> final position = sum of 5 hops","Many ghost balls -> bucket counts ~= probabilities","More rows -> histogram looks more like bell curve"],"common_misconceptions":["Goal is accurate physics","Bell appears with 5 balls","CLT predicts single ball"],"analogy_candidates":[{"analogy":"Ghost balls that never collide","maps_to":"Independence of hops","breaks_where":"Real balls collide"}],"narration_beats_3b1b_style":["Hook: chaotic one ball, precise many balls","Intuition: idealized ±1 walk, 5 rows, buckets labeled by sum","Formalize: random variable x late, promise proof + pi later"],"knowledge_triples":[["Galton board","example-of","random sum"],["Single bounce","causes","plus-one-or-minus-one"],["Many sums","transforms","bell distribution"]],"scope_exclusions":["Gaussian formula + pi derivation","Continuous convolution proof"]}

NOW DO REAL TASK:
USER_PROMPT: {USER_PROMPT}
Output strict JSON, same keys. Relations ONLY: is-a, part-of, causes, stores, transforms, contrasts-with, example-of. Name the idealizations explicitly (50-50, ghosts, dead-center landing). No visuals, no code.
```
