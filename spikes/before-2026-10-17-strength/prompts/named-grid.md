---
genre: named-grid
kinds: grid, graph
topic_keywords: pronoun, refers to, coreference, the cat sat
fits: attention, attends, query, key, softmax, token, words, alignment, confusion matrix, similarity, correlation, table, weights, mask
---
### Example: one word looking back at the others (topic: what a pronoun refers to)

SCENE_SPEC (abridged): beats = [
 {vo_line: "To read it, the model scores it against every earlier word.", objects: [{id: sc, kind: grid, data: {rows: 5, cols: 1, row_labels: [the, cat, sat, because, it], col_labels: [it], values: [[0.2], [4.1], [1.0], [0.3], [1.6]]}}]},
 {vo_line: "Softmax turns the scores into weights that sum to one.", objects: [{id: sc, kind: grid, data: {rows: 5, cols: 1, row_labels: […], col_labels: [it], values: [[0.02], [0.85], [0.04], [0.02], [0.07]], sweep: columns}}]},
 {vo_line: "Almost all of its attention goes to cat.", objects: [{id: s, kind: graph, data: {nodes: [the, cat, sat, because, it], edges: [[the, it, 0.02], [cat, it, 0.85], [sat, it, 0.04], [because, it, 0.02]], weighted: true, layout: line}}]} ]

```html
<beats>
<beat vo="To read it, the model scores it against every earlier word." t="2.4" style="padding: 0.5u 0.6u; gap: 0.2u">
  <h2 id="title">Score every word</h2>
  <div class="grow center">
    <grid id="sc" rows="5" cols="1" row-labels="the,cat,sat,because,it" col-labels="it" values="0.2;4.1;1.0;0.3;1.6"></grid>
  </div>
</beat>

<beat vo="Softmax turns the scores into weights that sum to one." t="3.0" style="padding: 0.5u 0.6u; gap: 0.2u">
  <h2 id="title">Softmax</h2>
  <div class="grow center">
    <grid id="sc" rows="5" cols="1" row-labels="the,cat,sat,because,it" col-labels="it" values="0.02;0.85;0.04;0.02;0.07" sweep="columns" op="softmax"></grid>
  </div>
</beat>

<beat vo="Almost all of its attention goes to cat." t="2.6" style="padding: 0.5u 0.6u; gap: 0.2u">
  <h2 id="title">It means the cat</h2>
  <div class="grow center">
    <graph id="s" nodes="the,cat,sat,because,it" layout="line" edges="the>it:0.02;cat>it:0.85;sat>it:0.04;because>it:0.02" weighted="true"></graph>
  </div>
</beat>
</beats>
```

Why it works: the grid names its rows and its one column, so the numbers read as "how much it
looks at each word"; the same id across beats keeps it still while the scores become weights,
and `sweep` with `op="softmax"` shows that step. The last beat says the same thing as links: a
`graph` with `layout="line"` puts the sentence in a row and arcs each word into "it", thick for
cat. For every word against every word use `rows` = `cols` = the words with both label lists
(`strike="below"` hides the later words, `cells="dots"` shows the pattern); for a sentence and
its translation use `layout="two-lines"` with `nodes="the,cat|le,chat"`. A word's own numbers
are a `vector` beside the picture.
