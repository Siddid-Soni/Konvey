---
genre: simulation
kinds: simulation
fits: over time, spreads, evens out, random, collisions, swing, settles, runs, simulation, pile
topic_keywords: dye, tube, ink, food colouring
---
### Example: a simulation that plays while the line is spoken (topic: a drop of dye spreading along a still tube)

SCENE_SPEC (abridged): beats = [
 {vo_line: "Put a drop of dye in the middle of a tube of still water.", objects: [{id: tube, kind: simulation, data: {rule: line, start: spike, until: 0}}]},
 {vo_line: "Watch the arrows: the dye moves fastest where its edge bends most.", objects: [{id: tube, kind: simulation, data: {rule: line, start: spike, until: 6}}]},
 {vo_line: "On the right, the gap between the darkest and palest point. It falls quickly, then slower and slower.", objects: [{id: tube, kind: simulation, data: {rule: line, start: spike, until: 30, views: ["graph: spread"]}}]} ]

```html
<beats>
<beat vo="Put a drop of dye in the middle of a tube of still water." shot="full" hold="2">
  <sim id="tube" rule="line" equation="heat" start="spike" rate="0.0006" label="dye" t="0"></sim>
</beat>

<beat vo="Watch the arrows: the dye moves fastest where its edge bends most." shot="full">
  <sim id="tube" rule="line" equation="heat" start="spike" rate="0.0006" label="dye" t="6"></sim>
</beat>

<beat vo="On the right, the gap between the darkest and palest point. It falls quickly, then slower and slower." shot="compare">
  <sim id="tube" rule="line" equation="heat" start="spike" rate="0.0006" label="dye" t="30"></sim>
  <simview id="gap" sim="tube" show="graph" y="spread" time="seconds"></simview>
</beat>
</beats>
```

Why it works: one `<sim>` id runs through the scene and only `t` grows, so each line watches the
next stretch of the same run instead of a new picture; the first beat holds the start still
(`t="0"`) so the viewer sees the setup before anything moves. The graph is a `<simview>` of the same
run, so the curve grows exactly as the tube evens out; the narration says what to watch ("the
arrows", "on the right") and never states a number the engine has not shown.
