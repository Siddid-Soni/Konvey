---
genre: equation
kinds: tex, number, grid
topic_keywords: odd number, odd numbers, perfect square, square numbers
---
### Example: an equation scene (topic: the odd numbers add up to squares)

SCENE_SPEC (abridged): beats = [
 {vo_line: "One plus three is four: a two by two square.", objects: [{id: sum, kind: tex, data: {tex: "1 + 3 = 4 = 2^2"}}, {id: sq2, kind: grid, data: {rows: 2, cols: 2, values: [1, 3, 3, 3]}}]},
 {vo_line: "Add the next odd number, five, and the square grows by one row and column.", objects: [{id: sum, kind: tex, data: {tex: "1 + 3 + 5 = 9 = 3^2"}}, {id: sq3, kind: grid, data: {rows: 3, cols: 3, values: [1, 3, 5, 3, 3, 5, 5, 5, 5]}}]},
 {vo_line: "So the first n odd numbers always make n squared.", objects: [{id: sum, kind: tex, data: {tex: "1 + 3 + \\cdots + (2n - 1) = n^2"}}]} ]

```html
<beats>
<beat vo="One plus three is four: a two by two square." t="2" shot="derive">
  <grid id="sq2" rows="2" cols="2" values="1,3;3,3" highlight-rows="1" highlight-cols="1"></grid>
  <tex id="sum" size="52">1 + 3 = 4 = 2^2</tex>
</beat>

<beat vo="Add the next odd number, five, and the square grows by one row and column." t="2.4" shot="derive">
  <grid id="sq3" rows="3" cols="3" values="1,3,5;3,3,5;5,5,5" highlight-rows="2" highlight-cols="2"></grid>
  <tex id="sum" size="52" morph="match">1 + 3 + 5 = 9 = 3^2</tex>
</beat>

<beat vo="So the first n odd numbers always make n squared." t="2.2" shot="title">
  <tex id="sum" size="64" morph="match" emphasize="circle">1 + 3 + \cdots + (2n - 1) = n^2</tex>
</beat>
</beats>
```

Why it works: the equation keeps one id and morphs symbol by symbol as it grows, so the viewer
sees the new term arrive; the grid highlights exactly the cells the new odd number adds (one
row plus one column); the sum is written beside the square it counts (`derive`); on the payoff beat the formula
stands alone (`title`), grows and is circled.
