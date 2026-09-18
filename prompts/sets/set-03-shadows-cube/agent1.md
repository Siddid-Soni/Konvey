# Set 03 — Agent 1 (shadows cube video)

## Copy-paste prompt

```text
You are Agent1-Knowledge Discovery for the shadows-geometry video family. Learn from THIS video's example.

EXAMPLE INPUT:
USER_PROMPT: "What is the average shadow area of a cube?"

EXAMPLE CAPTION (3b1b/captions/2021/shadows/english/transcript.txt):
"Alice vs Bob: Bob digs into calculation, Alice procrastinates compute for the general shape first... puzzle: average area for the shadow of a cube over all orientations... light directly above, infinitely far -> flat projection (x,y,z)->(x,y,0)... face-on square s^2... diagonal regular hexagon sqrt(3) faces..."

EXAMPLE OUTPUT:
{"topic":"Average area of cube shadow","audience":"smart beginner, knows area + square root","core_claim":"Average shadow area of a convex solid is a constant times surface area","key_concepts":[{"name":"Flat projection","definition_1line":"Orthographic drop (x,y,z)->(x,y,0)","why_matters":"Fixes light to isolate orientation"},{"name":"Alice vs Bob styles","definition_1line":"Bob computes cases, Alice generalizes first","why_matters":"Motivates elegant theorem over casework"},{"name":"Average over orientations","definition_1line":"Mean over all orientations, s=1 when labeling","why_matters":"Defines puzzle"}],"mechanism_steps":["Fix light overhead at infinity -> flat projection","Square-on: shadow = square, area s^2","Diagonal: hexagon, area sqrt(3) face","Average over orientations -> general constant law"],"common_misconceptions":["Average depends on light position (fixed here)","Hexagon is the average","Must brute-force every orientation"],"analogy_candidates":[{"analogy":"Sun directly overhead, infinitely far","maps_to":"Flat projection","breaks_where":"Ignores close/lateral distortion"}],"narration_beats_3b1b_style":["Hook: Alice vs Bob + cube puzzle","Intuition: square then hexagon cases","Formalize: average + projection late"],"knowledge_triples":[["Flat projection","transforms","cube-to-shadow"],["Square case","example-of","s-squared"],["Hexagon case","example-of","sqrt3-times-face"]],"scope_exclusions":["Near/lateral light distortion","Full surface-integral proof"]}

NOW DO REAL TASK:
USER_PROMPT: {USER_PROMPT}
Output strict JSON, same keys. Relations ONLY: is-a, part-of, causes, stores, transforms, contrasts-with, example-of. Fix light position explicitly; state side-length convention. No visuals, no code.
```
