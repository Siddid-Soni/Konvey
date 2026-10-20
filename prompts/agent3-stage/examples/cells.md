---
genre: cells
kinds: array, grid, tiles
topic_keywords: largest number, maximum of a list, running maximum, find the max
---
### Example: a cells scene (topic: finding the largest number in one pass)

SCENE_SPEC (abridged): beats = [
 {vo_line: "Walk the list once, remembering the best number so far.", objects: [{id: nums, kind: array, data: {values: [4, 9, 2, 7, 11, 3]}}]},
 {vo_line: "Each new number either loses, or becomes the new best.", objects: [{id: nums, kind: array, data: {values: [4, 9, 2, 7, 11, 3]}}]},
 {vo_line: "One look per number: six numbers, six steps.", objects: [{id: steps, kind: tex, data: {tex: "n \\text{ numbers} \\Rightarrow n \\text{ steps}"}}]} ]

```html
<beats>
<beat vo="Walk the list once, remembering the best number so far." t="1.8" shot="full">
  <array id="nums" values="4,9,2,7,11,3" pointers="i:0,best:0" highlight="0" size="36"></array>
</beat>

<beat vo="Each new number either loses, or becomes the new best." t="1.4" hold="1.4" shot="full">
  <array id="nums" values="4,9,2,7,11,3" pointers="i:3,best:1" highlight="1" dim="0,2" size="36"></array>
</beat>

<beat t="1.4" hold="1.6" shot="full">
  <array id="nums" values="4,9,2,7,11,3" pointers="i:5,best:4" highlight="4" dim="0-3,5" size="36"></array>
</beat>

<beat vo="One look per number: six numbers, six steps." shot="derive">
  <tex id="steps">n \text{ numbers} \Rightarrow n \text{ steps}</tex>
  <array id="nums" values="4,9,2,7,11,3" pointers="best:4" highlight="4" size="36"></array>
</beat>
</beats>
```

Why it works: the array keeps its id and its values, so between beats only the pointers slide
and the highlight moves; dimming what is settled keeps the eye on the frontier. The extra beat
(no `vo`, short `hold`) lets a step that needs two screens finish without new narration. The
count is written beside the finished array (`derive`) only once the walk is over.
