---
genre: world3d-flow
kinds: flow, surface3d, sphere
fits: field, flow, current, circulation, vector field, stream, surface, swirl
topic_keywords: wind, air, trade winds, weather, jet stream
---
### Example: a field flowing over a surface (topic: bands of wind circling a spinning planet)

SCENE_SPEC (abridged): beats = [
 {vo_line: "Air near a spinning planet's equator streams one way round.", objects: [{id: ball, kind: solid, data: {shape: sphere}}, {id: air, kind: flow, data: {fn: "-y; x; 0", on: ball}}]},
 {vo_line: "Further north the bands turn and run the other way.", objects: [{id: ball, kind: solid, data: {shape: sphere}}, {id: bands, kind: flow, data: {fn: "-y*(1 - 3*z^2); x*(1 - 3*z^2); 0", on: ball}}]},
 {vo_line: "Between two bands, a line where the air barely moves.", objects: [{id: ball, kind: solid, data: {shape: sphere}}, {id: bands, kind: flow, data: {fn: "-y*(1 - 3*z^2); x*(1 - 3*z^2); 0", on: ball}}]} ]

```html
<beats>
<beat vo="Air near a spinning planet's equator streams one way round." shot="full">
  <world>
    <sphere id="ball" r="2" at="0,0,0"></sphere>
    <flow id="air" on="ball" fn="-y; x; 0" count="700" t="4"></flow>
  </world>
  <camera theta="-60" phi="70"></camera>
</beat>

<beat vo="Further north the bands turn and run the other way." shot="full">
  <world>
    <sphere id="ball" r="2" at="0,0,0"></sphere>
    <flow id="bands" on="ball" fn="-y*(1 - 3*z^2); x*(1 - 3*z^2); 0" count="900" t="5"></flow>
  </world>
  <camera theta="-60" phi="60"></camera>
</beat>

<beat vo="Between two bands, a line where the air barely moves." shot="full">
  <world>
    <sphere id="ball" r="2" at="0,0,0"></sphere>
    <flow id="bands" on="ball" fn="-y*(1 - 3*z^2); x*(1 - 3*z^2); 0" count="900" t="10"></flow>
  </world>
  <camera theta="-60" phi="35"></camera>
</beat>
</beats>
```

Why it works: the field is written, never drawn by hand: the engine traces each line along it and
slides a glow along the lines, coloured by speed, so the still line between two bands shows dark
by itself. A new pattern is a new `<flow>` id (the old lines fade, the new ones come in on the same
ball); the same pattern keeps its id and only `t` grows, so it keeps flowing. Give each beat
about as much flow time as its line takes to say: more makes the glow race. The camera tilts down
for the last line, where the dark band the narration names faces the viewer.
