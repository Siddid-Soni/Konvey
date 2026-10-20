---
genre: vector
kinds: vector, tex
topic_keywords: king minus man, king - man, word analogy
fits: vector, embedding, state, gradient, velocity, coordinates, components, distribution, entries, numbers, list of numbers
---
### Example: arithmetic on word vectors (topic: king − man + woman ≈ queen)

SCENE_SPEC (abridged): beats = [
 {vo_line: "Each word is stored as a list of numbers.", objects: [{id: vk, kind: vector, data: {values: [0.8, 0.6, 0.1], label: king}}, {id: vm, kind: vector, data: {values: [0.7, 0.1, 0.1], label: man}}, {id: vw, kind: vector, data: {values: [0.7, 0.1, 0.9], label: woman}}]},
 {vo_line: "Take king, subtract man, add woman, one entry at a time.", objects: [{id: f, kind: tex, data: {tex: "\\text{king} - \\text{man} + \\text{woman}"}}, {id: vr, kind: vector, data: {values: ["?", "?", "?"], label: "r"}}, …]},
 {vo_line: "The last entry jumps to 0.9: the woman direction.", objects: [{id: vr, kind: vector, data: {values: [0.8, 0.6, 0.9], label: "r", highlight: [2]}}, …]} ]

```html
<beats>
<beat vo="Each word is stored as a list of numbers." t="2.2" shot="full">
  <vector id="vk" values="0.8,0.6,0.1" label="king"></vector>
  <vector id="vm" values="0.7,0.1,0.1" label="man"></vector>
  <vector id="vw" values="0.7,0.1,0.9" label="woman"></vector>
</beat>

<beat vo="Take king, subtract man, add woman, one entry at a time." t="2.6" shot="full">
  <vector id="vk" values="0.8,0.6,0.1" label="king"></vector>
  <tex id="minus" inline>-</tex>
  <vector id="vm" values="0.7,0.1,0.1" label="man"></vector>
  <tex id="plus" inline>+</tex>
  <vector id="vw" values="0.7,0.1,0.9" label="woman"></vector>
  <tex id="eq" inline>=</tex>
  <vector id="vr" values="?,?,?"></vector>
</beat>

<beat vo="The last entry jumps to 0.9: the woman direction." t="2.4" shot="full">
  <vector id="vk" values="0.8,0.6,0.1" label="king"></vector>
  <tex id="minus" inline>-</tex>
  <vector id="vm" values="0.7,0.1,0.1" label="man"></vector>
  <tex id="plus" inline>+</tex>
  <vector id="vw" values="0.7,0.1,0.9" label="woman" highlight="2"></vector>
  <tex id="eq" inline>=</tex>
  <vector id="vr" values="0.8,0.6,0.9" highlight="2"></vector>
</beat>
</beats>
```

Why it works: the sum is written as one row of pictures, the operators between them marked
`inline` so they stay in the row: the vectors themselves are the formula (in such a row each
vector's `label` is written under it, not as "king ="). Each vector keeps its
id, so it stays put and only its entries change. The result
starts as `?` entries and fills in a later beat; the entry the narration names is `highlight`ed
in both vectors, and because woman's 0.9 is lit, the result's new 0.9 flies in from it. A vector
sits beside the other pictures (a row of them, a formula, a plot, a plane, a grid): it is
never drawn inside another tag.
