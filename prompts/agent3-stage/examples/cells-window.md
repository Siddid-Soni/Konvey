---
genre: cells
kinds: grid
topic_keywords: edge detector, edge detection, vertical edge, dark to bright
fits: filter, kernel, pixel, sliding window, feature map, stride, neighbourhood
---
### Example: a filter sliding over a grid (topic: finding a vertical edge in a picture)

SCENE_SPEC (abridged): beats = [
 {vo_line: "A 3 by 3 detector sits on the corner of the picture: right column minus left column.", objects: [{id: pic, kind: grid, data: {rows: 5, cols: 5, values: [[2,2,9,9,9],[1,2,8,9,9],[2,1,9,8,9],[1,2,9,9,8],[2,1,8,9,9]], window: [0,0,3,3], kernel: [[-1,0,1],[-1,0,1],[-1,0,1]]}}, {id: out, kind: grid, data: {rows: 3, cols: 3, values: [[21,"",""],["","",""],["","",""]], heat: true}}]},
 {vo_line: "It steps right, one pixel at a time, writing one number per step.", objects: [{id: pic, kind: grid, data: {window: [0,2,3,3]}}, {id: out, kind: grid, data: {values: [[21,21,1],["","",""],["","",""]]}}]},
 {vo_line: "Row by row it covers the picture; the big numbers line up where dark meets bright.", objects: [{id: pic, kind: grid, data: {window: [2,2,3,3]}}, {id: out, kind: grid, data: {values: [[21,21,1],[22,21,0],[21,22,0]]}}]} ]

```html
<beats>
<beat vo="A 3 by 3 detector sits on the corner of the picture: right column minus left column." t="1.8" shot="compare">
  <grid id="pic" rows="5" cols="5" values="2,2,9,9,9;1,2,8,9,9;2,1,9,8,9;1,2,9,9,8;2,1,8,9,9" heat="true" window="0,0,3,3" kernel="-1,0,1;-1,0,1;-1,0,1" size="36"></grid>
  <grid id="out" rows="3" cols="3" values="21,,;,,;,," heat="true" size="36"></grid>
</beat>

<beat vo="It steps right, one pixel at a time, writing one number per step." t="2.6" shot="compare">
  <grid id="pic" rows="5" cols="5" values="2,2,9,9,9;1,2,8,9,9;2,1,9,8,9;1,2,9,9,8;2,1,8,9,9" heat="true" window="0,2,3,3" kernel="-1,0,1;-1,0,1;-1,0,1" size="36"></grid>
  <grid id="out" rows="3" cols="3" values="21,21,1;,,;,," heat="true" size="36"></grid>
</beat>

<beat vo="Row by row it covers the picture; the big numbers line up where dark meets bright." t="4" shot="compare">
  <grid id="pic" rows="5" cols="5" values="2,2,9,9,9;1,2,8,9,9;2,1,9,8,9;1,2,9,9,8;2,1,8,9,9" heat="true" window="2,2,3,3" kernel="-1,0,1;-1,0,1;-1,0,1" size="36"></grid>
  <grid id="out" rows="3" cols="3" values="21,21,1;22,21,0;21,22,0" heat="true" size="36"></grid>
</beat>
</beats>
```

Why it works: the picture keeps its id, values and `kernel`; only `window` changes, so the
frame steps cell by cell to its new place (two steps in beat 2, six in beat 3, each beat given
enough `t`). The output grid starts with empty cells and gets exactly one new value per step,
so its cells fill in one after another in time with the frame. `heat` on both lets the eye
see the pattern (dark left, bright right; big outputs at the boundary) without a legend.
