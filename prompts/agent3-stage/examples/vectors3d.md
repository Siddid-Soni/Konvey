---
genre: vectors3d
kinds: axes, line, face, line3d, axes3d, face3d
topic_keywords: vector addition, adding vectors, tip to tail, head to tail, sum of vectors, resultant
---
### Example: vectors in space (topic: adding two vectors tip to tail)

SCENE_SPEC (abridged): beats = [
 {vo_line: "Two arrows from the origin: u is 2, 1, 0 and v is 0, 1, 2.", objects: [{id: axes, kind: axes, data: {}}, {id: u, kind: line, data: {from: [0, 0, 0], to: [2, 1, 0], arrow: true}}, {id: v, kind: line, data: {from: [0, 0, 0], to: [0, 1, 2], arrow: true}}]},
 {vo_line: "Slide v, without turning it, so it starts where u ends.", objects: [{id: v, kind: line, data: {from: [2, 1, 0], to: [2, 2, 2], arrow: true}}]},
 {vo_line: "The sum runs from the origin to where v now ends: 2, 2, 2.", objects: [{id: total, kind: line, data: {from: [0, 0, 0], to: [2, 2, 2], arrow: true}}, {id: rule, kind: tex, data: {tex: "u + v = (2, 2, 2)"}}]} ]

```html
<beats>
<beat vo="Two arrows from the origin: u is 2, 1, 0 and v is 0, 1, 2." t="2" shot="derive">
  <text id="coords" size="30">u = (2, 1, 0)<br/>v = (0, 1, 2)</text>
  <world>
    <axes3d id="axes" x="0,3" y="0,3" z="0,3" grid="true" ticks="true"></axes3d>
    <line3d id="u" from="0,0,0" to="2,1,0" arrow="true" color="c1" label="u"></line3d>
    <line3d id="v" from="0,0,0" to="0,1,2" arrow="true" color="c2" label="v"></line3d>
  </world>
  <camera show="u,v"></camera>
</beat>

<beat vo="Slide v, without turning it, so it starts where u ends." t="2.2" shot="derive">
  <text id="coords" size="30">u = (2, 1, 0)<br/>v = (0, 1, 2)</text>
  <world>
    <axes3d id="axes" x="0,3" y="0,3" z="0,3" grid="true" ticks="true"></axes3d>
    <line3d id="u" from="0,0,0" to="2,1,0" arrow="true" color="c1" label="u"></line3d>
    <line3d id="v" from="2,1,0" to="2,2,2" arrow="true" color="c2" label="v"></line3d>
  </world>
  <camera show="u,v"></camera>
</beat>

<beat vo="The sum runs from the origin to where v now ends: 2, 2, 2." t="2" shot="derive">
  <tex id="rule">u + v = (2, 2, 2)</tex>
  <text id="coords" size="30">u = (2, 1, 0)<br/>v = (0, 1, 2)</text>
  <world>
    <axes3d id="axes" x="0,3" y="0,3" z="0,3" grid="true" ticks="true"></axes3d>
    <line3d id="u" from="0,0,0" to="2,1,0" arrow="true" color="c1" label="u"></line3d>
    <line3d id="v" from="2,1,0" to="2,2,2" arrow="true" color="c2" label="v"></line3d>
    <face3d id="tri" points="0,0,0; 2,1,0; 2,2,2" color="muted" opacity="0.18"></face3d>
    <line3d id="total" from="0,0,0" to="2,2,2" arrow="true" color="accent" width="5" label="u + v"></line3d>
  </world>
  <camera show="u,v,total"></camera>
</beat>
</beats>
```

Why it works: coordinates are only readable against `axes3d` with its `grid` and `ticks`, so
the axes stay for the whole scene. A vector is a `line3d` from the origin with `arrow` and a
`label` at its tip; the arrow head always faces the camera, so it reads from any angle. `v` keeps
its id and only its `from`/`to` change, so it slides into place instead of being redrawn. The new
result is the one accent arrow, and a faint `face3d` shows the triangle the three arrows close.
`<camera show=…>` names what each beat is about, so the camera turns to see those arrows at
their true length and frames them; it holds still while the narration speaks. The coordinates
and the sum are words beside the world (`derive`), never labels floating in it.
