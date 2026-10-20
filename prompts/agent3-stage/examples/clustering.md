---
genre: clustering
kinds: scatter
fits: cluster, clusters, centroid, centre, center, data points, scatter, classify, regression, line of best fit, least squares, outlier
topic_keywords: k-means, kmeans, k means, lloyd
---
### Example: points, centres that move, points that switch (topic: k-means with k = 3)

SCENE_SPEC (abridged): beats = [
 {vo_line: "Twelve points, and three starting centres placed badly on purpose.", objects: [{id: pts, kind: scatter, data: {points: [[1, 2], [2, 1], [2, 3], [3, 2], [6, 2], [7, 3], [8, 2], [7, 1], [4, 7], [5, 8], [6, 7], [5, 9]], centroids: [[1, 1], [5, 3], [8, 1]]}}]},
 {vo_line: "Each point joins its nearest centre.", objects: [{id: pts, kind: scatter, data: {centroids: [[1, 1], [5, 3], [8, 1]], groups: [0, 0, 0, 0, 1, 1, 2, 2, 1, 1, 1, 1], links: true}}]},
 {vo_line: "Each centre moves to the mean of its points.", objects: [{id: pts, kind: scatter, data: {centroids: [[2, 2], [5.5, 6], [7.5, 1.5]], groups: [0, 0, 0, 0, 1, 1, 2, 2, 1, 1, 1, 1], links: true}}, {id: mean, kind: tex, data: {tex: "\\mu_j = \\frac{1}{|S_j|}\\sum_{x \\in S_j} x"}}]},
 {vo_line: "Assign again: two points switch to the third centre.", objects: [{id: pts, kind: scatter, data: {centroids: [[2, 2], [5.5, 6], [7.5, 1.5]], groups: [0, 0, 0, 0, 2, 2, 2, 2, 1, 1, 1, 1], links: true, highlight: [4, 5]}}]} ]

```html
<beats>
<beat vo="Twelve points, and three starting centres placed badly on purpose." t="2" shot="full">
  <scatter id="pts" points="1,2; 2,1; 2,3; 3,2; 6,2; 7,3; 8,2; 7,1; 4,7; 5,8; 6,7; 5,9" centroids="1,1; 5,3; 8,1" xlabel="x" ylabel="y"></scatter>
</beat>

<beat vo="Each point joins its nearest centre." t="1.6" shot="full">
  <scatter id="pts" points="1,2; 2,1; 2,3; 3,2; 6,2; 7,3; 8,2; 7,1; 4,7; 5,8; 6,7; 5,9" centroids="1,1; 5,3; 8,1" groups="0,0,0,0,1,1,2,2,1,1,1,1" links="on" xlabel="x" ylabel="y"></scatter>
</beat>

<beat vo="Each centre moves to the mean of its points." t="1.6" shot="derive">
  <scatter id="pts" points="1,2; 2,1; 2,3; 3,2; 6,2; 7,3; 8,2; 7,1; 4,7; 5,8; 6,7; 5,9" centroids="2,2; 5.5,6; 7.5,1.5" groups="0,0,0,0,1,1,2,2,1,1,1,1" links="on" xlabel="x" ylabel="y"></scatter>
  <tex id="mean">\mu_j = \frac{1}{|S_j|}\sum_{x \in S_j} x</tex>
</beat>

<beat vo="Assign again: two points switch to the third centre." t="1.6" shot="derive">
  <scatter id="pts" points="1,2; 2,1; 2,3; 3,2; 6,2; 7,3; 8,2; 7,1; 4,7; 5,8; 6,7; 5,9" centroids="2,2; 5.5,6; 7.5,1.5" groups="0,0,0,0,2,2,2,2,1,1,1,1" links="on" highlight="4,5" xlabel="x" ylabel="y"></scatter>
  <tex id="mean">\mu_j = \frac{1}{|S_j|}\sum_{x \in S_j} x</tex>
</beat>
</beats>
```

Why it works: one `scatter` id with the same `points` in every beat, so nothing is redrawn:
the renderer draws the axes, colours each point by its `groups` entry, draws the centres as
labelled diamonds and places every label clear of the dots. Each step changes only `groups`,
`centroids`, `links` or `highlight`, so the centres glide to their means and the two points that
switch pulse into their new colour while their links re-attach. The formula sits beside the
plot (`derive`), not on it. Every number is copied from the plan; a fitted line would be `lines="a,b"`.
