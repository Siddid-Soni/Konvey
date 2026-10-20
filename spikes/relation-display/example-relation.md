---
genre: relation
kinds: relation
topic_keywords: pronoun, refers to, coreference, the cat sat
fits: attention, attends, query, key, softmax, token, words, transformer, alignment, context, similarity, confusion matrix, correlation, matching, pairs
---
### Example: one word looking back at the others (topic: what a pronoun refers to)

SCENE_SPEC (abridged): beats = [
 {vo_line: "To read it, the model scores every earlier word against it.", objects: [{id: att, kind: relation, data: {cols: [the, cat, sat, because, it, was, tired], weights: [[], [], [], [], [0.2, 4.1, 1.0, 0.3, 1.6, 0.5, -0.4], [], []], focus: it, numbers: true}}]},
 {vo_line: "Later words are hidden, and softmax turns the scores into weights.", objects: [{id: att, kind: relation, data: {cols: [the, cat, sat, because, it, was, tired], weights: [[], [], [], [], [0.02, 0.85, 0.04, 0.02, 0.07, 0, 0], [], []], normalize: columns, op: softmax, mask: later, focus: it, numbers: true}}]},
 {vo_line: "Almost all of it's attention goes to cat.", objects: [{id: att, kind: relation, data: {cols: [the, cat, sat, because, it, was, tired], weights: [[], [], [], [], [0.02, 0.85, 0.04, 0.02, 0.07, 0, 0], [], []], normalize: columns, op: softmax, mask: later, focus: it, view: links}}]} ]

```html
<beats>
<beat vo="To read it, the model scores every earlier word against it." t="2.4" style="padding: 0.5u 0.6u; gap: 0.2u">
  <h2 id="title">Score every word</h2>
  <div class="grow center">
    <relation id="att" cols="the,cat,sat,because,it,was,tired" weights=";;;;0.2,4.1,1.0,0.3,1.6,0.5,-0.4;;" focus="it" numbers="true"></relation>
  </div>
</beat>

<beat vo="Later words are hidden, and softmax turns the scores into weights." t="3.4" style="padding: 0.5u 0.6u; gap: 0.2u">
  <h2 id="title">Mask, then softmax</h2>
  <div class="grow center">
    <relation id="att" cols="the,cat,sat,because,it,was,tired" weights=";;;;0.02,0.85,0.04,0.02,0.07,0,0;;" normalize="columns" op="softmax" mask="later" focus="it" numbers="true"></relation>
  </div>
</beat>

<beat vo="Almost all of it's attention goes to cat." t="2.4" style="padding: 0.5u 0.6u; gap: 0.2u">
  <h2 id="title">It means the cat</h2>
  <div class="grow center">
    <relation id="att" cols="the,cat,sat,because,it,was,tired" weights=";;;;0.02,0.85,0.04,0.02,0.07,0,0;;" normalize="columns" op="softmax" mask="later" focus="it" view="links"></relation>
  </div>
</beat>
</beats>
```

Why it works: one id and the same `cols` all scene, so the words never move and only the
picture under them changes. One list relates to itself, so `rows` is left out. Only the focus
word's group of `weights` is filled (the other groups are `""`: not computed in this story), so
one column tells it. Beat 2 adds `mask="later"` and `normalize="columns"` together: the later
words' cells are struck first, then the column's scores turn into weights that sum to 1 (the
masked ones 0) under a frame labelled by `op`. Beat 3 switches to `view="links"`: the grid gives
way to the sentence and arrows grow from the related words into "it", thick for "cat". With two
lists (a sentence and its translation, actual and predicted classes) add `rows="…"`: the grid's
rows are the second list, and `view="links"` puts it in a line under the first with a line
joining each pair. A word's numbers (its embedding) would be a `<vector>` beside the picture.
