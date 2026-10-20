---
genre: shots
kinds: plot
fits: read off, slope, derive, compare, zoom, closer look, from the picture
topic_keywords: runner, running, jog, race
---
### Example: composing beats with shots, the 2D camera and a formula read off the picture (topic: a runner's average speed from a distance-time graph)

SCENE_SPEC (abridged): beats = [
 {vo_line: "Where is the runner after two minutes?", objects: [{id: run, kind: plot, data: {fns: {d: "0.2*x^2"}, x: [0, 4]}}]},
 {vo_line: "Look closely at two minutes on the curve.", objects: [{id: run, kind: plot}]},
 {vo_line: "Distance over time read off the curve gives the average speed.", objects: [{id: speed, kind: tex, data: {tex: "v = \\frac{d}{t}", built_from: ["S1 beat 1"]}}]},
 {vo_line: "Average speed.", objects: [{id: speed, kind: tex}]} ]

```html
<beats>
<beat vo="Where is the runner after two minutes?" shot="question">
  <text id="q">Where is the runner after two minutes?</text>
  <plot id="run" fn="d: 0.2*x^2" x="0,4" y="0,3.5" points="P: 2,d" xlabel="minutes" ylabel="km"></plot>
</beat>

<beat vo="Look closely at two minutes on the curve." shot="full" view="run>x=2" zoom="2.2">
  <plot id="run" fn="d: 0.2*x^2" x="0,4" y="0,3.5" points="P: 2,d" xlabel="minutes" ylabel="km"></plot>
</beat>

<beat vo="Distance over time read off the curve gives the average speed." shot="derive" focus="run>P, speed">
  <plot id="run" fn="d: 0.2*x^2" x="0,4" y="0,3.5" points="P: 2,d" xlabel="minutes" ylabel="km"></plot>
  <tex id="speed" from="d: run>P">v = \frac{d}{t}</tex>
</beat>

<beat vo="Average speed." shot="title">
  <tex id="speed">v = \frac{d}{t}</tex>
</beat>
</beats>
```

Why it works: no beat writes a container or a headline: each picks a `shot` and lists its
elements, and the renderer composes it. The first beat asks a concrete question over the picture
(`question`); the camera then pushes in on the one point the line names (`view` on a part,
`id>part`) and glides back out; in `derive` the formula's `d` flies out of that very point
(`from="d: run>P"`, the named point), while `focus` dims everything else; the payoff line stands alone (`title`). The same
ids carry the plot and the formula through every shot, so each change is a move, not a cut.
