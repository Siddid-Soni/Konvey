---
genre: constructions
kinds: plane, dots, path, arc, angle_mark, brace, note
fits: triangle, circle, angle, side, corner, point, points, path, hop, bounce, chord, arc, radius, midpoint, geometry, construction, wedge, region, slope, tangent
topic_keywords: ladder, wall, slides, sliding
---
### Example: building one figure up, a mark per line (topic: a ladder sliding down a wall)

SCENE_SPEC (abridged): beats = [
 {vo_line: "A five metre ladder leans on a wall, its foot three metres out.", objects: [{id: room, kind: plane, data: {}}, {id: ends, kind: dots, data: {on: room, at: [[0, 4], [3, 0]], labels: ["top", "foot"]}}, {id: ladder, kind: path, data: {on: room, through: "ends"}}, {id: len, kind: brace, data: {on: room, from: [0, 4], to: [3, 0], label: "5"}}]},
 {vo_line: "Mark its middle.", objects: [{id: mid, kind: dots, data: {on: room, at: [[1.5, 2]], labels: ["M"]}}]},
 {vo_line: "Slide the foot out to four metres, then to almost five.", objects: [{id: ends, kind: dots, data: {on: room, at: [[0, 3], [4, 0]], labels: ["top", "foot"]}}, {id: mid, kind: dots, data: {on: room, at: [[2, 1.5]], labels: ["M"]}}, {id: trail, kind: path, data: {on: room, through: [[1.5, 2], [2, 1.5], [2.4, 0.7]], dashed: true}}]},
 {vo_line: "The middle is always two and a half metres from the corner: it runs along a circle.", objects: [{id: r, kind: path, data: {on: room, through: [[0, 0], [2, 1.5]], label: "2.5"}}, {id: circ, kind: arc, data: {on: room, center: [0, 0], from: [0, 2.5], to: [2.5, 0], label: "radius 2.5"}}, {id: why, kind: note, data: {text: "half the ladder, from the right angle", on: room, at: [[0, 0]]}}]} ]

```html
<beats>
<beat vo="A five metre ladder leans on a wall, its foot three metres out." t="2" shot="full">
  <plane id="room" x="-0.6,5.6" y="-0.4,5" grid="none" ticks="none" xlabel="\text{floor}" ylabel="\text{wall}"></plane>
  <dots id="ends" on="room" at="0,4; 3,0" labels="top,foot"></dots>
  <path id="ladder" on="room" through="ends" width="4"></path>
  <angle id="corner" on="room" at="0,0" from="3,0" to="0,4"></angle>
  <brace id="len" on="room" from="0,4" to="3,0" label="5"></brace>
</beat>

<beat vo="Mark its middle." t="1.6" shot="full">
  <plane id="room" x="-0.6,5.6" y="-0.4,5" grid="none" ticks="none" xlabel="\text{floor}" ylabel="\text{wall}"></plane>
  <dots id="ends" on="room" at="0,4; 3,0" labels="top,foot"></dots>
  <path id="ladder" on="room" through="ends" width="4"></path>
  <angle id="corner" on="room" at="0,0" from="3,0" to="0,4"></angle>
  <brace id="len" on="room" from="0,4" to="3,0" label="5" dim="true"></brace>
  <dots id="mid" on="room" at="1.5,2" labels="M" color="c2"></dots>
</beat>

<beat vo="Slide the foot out to four metres, then to almost five." t="2.4" shot="full">
  <plane id="room" x="-0.6,5.6" y="-0.4,5" grid="none" ticks="none" xlabel="\text{floor}" ylabel="\text{wall}"></plane>
  <dots id="ends" on="room" at="0,3; 4,0" labels="top,foot"></dots>
  <path id="ladder" on="room" through="ends" width="4"></path>
  <angle id="corner" on="room" at="0,0" from="4,0" to="0,3"></angle>
  <dots id="mid" on="room" at="2,1.5" labels="M" color="c2"></dots>
  <path id="trail" on="room" through="1.5,2; 2,1.5; 2.4,0.7" dashed="true" color="c2"></path>
</beat>

<beat vo="The middle is always two and a half metres from the corner: it runs along a circle." t="2" shot="full">
  <plane id="room" x="-0.6,5.6" y="-0.4,5" grid="none" ticks="none" xlabel="\text{floor}" ylabel="\text{wall}"></plane>
  <dots id="ends" on="room" at="0,3; 4,0" labels="top,foot"></dots>
  <path id="ladder" on="room" through="ends" width="4" dim="true"></path>
  <dots id="mid" on="room" at="2,1.5" labels="M" color="c2"></dots>
  <path id="r" on="room" through="0,0; 2,1.5" label="2.5" color="c2"></path>
  <arc id="circ" on="room" center="0,0" from="0,2.5" to="2.5,0" dir="cw" label="radius 2.5" color="c2"></arc>
  <note id="why" on="room" at="0,0" text="half the ladder, from the right angle"></note>
</beat>
</beats>
```

Why it works: one plane, kept bare (`grid="none" ticks="none"`), is the whole picture; every
line adds one mark to it at its own coordinates, and the marks that are no longer the point dim
instead of vanishing. Points are named once in a `<dots>` (`through="ends"`), so the ladder
follows its ends when they slide. Words sit where they belong: the length on a brace along the
ladder, the radius on its segment, the reason in a note pointing at the corner it is about.
