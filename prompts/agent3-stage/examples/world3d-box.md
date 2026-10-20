---
genre: world3d
kinds: solid, sphere, line, angle, line3d, angle3d, label3d, light, shadow
topic_keywords: space diagonal, cuboid, diagonal of a box, box diagonal
---
### Example: a 3D scene (topic: the long diagonal of a box)

SCENE_SPEC (abridged): beats = [
 {vo_line: "A box three long, two deep and two high.", objects: [{id: crate, kind: solid, data: {shape: box, size: [3, 2, 2]}}]},
 {vo_line: "Seen from above, the floor diagonal closes a right triangle on three and two.", objects: [{id: floor_eq, kind: tex, data: {tex: "d_{floor}^2 = 3^2 + 2^2 = 13"}}]},
 {vo_line: "Stand that diagonal up against the height, and the right-triangle rule runs once more.", objects: [{id: floor_eq, kind: tex, data: {tex: "d^2 = 13 + 2^2 = 17"}}]} ]

```html
<beats>
<beat vo="A box three long, two deep and two high." t="2" shot="full">
  <world>
    <ground></ground>
    <solid id="crate" shape="box" size="3,2,2" color="c4"></solid>
    <label3d id="len" at="0,-1.3,0" text="3"></label3d>
    <label3d id="dep" at="1.8,0,0" text="2"></label3d>
    <label3d id="hgt" at="1.8,-1.3,1" text="2"></label3d>
  </world>
  <camera show="crate"></camera>
</beat>

<beat vo="Seen from above, the floor diagonal closes a right triangle on three and two." t="2.4" shot="derive">
  <tex id="floor_eq">d_{floor}^2 = 3^2 + 2^2 = 13</tex>
  <world>
    <ground></ground>
    <light id="top" dir="0,0,-1"></light>
    <solid id="crate" shape="box" size="3,2,2" color="c4" opacity="0.4"></solid>
    <shadow id="footprint" of="crate"></shadow>
    <label3d id="len" at="0,-1.3,0" text="3"></label3d>
    <label3d id="dep" at="1.8,0,0" text="2"></label3d>
    <line3d id="floor_diag" from="-1.5,-1,0" to="1.5,1,0" color="accent"></line3d>
    <angle3d id="floor_right" at="1.5,-1,0" from="-1.5,-1,0" to="1.5,1,0"></angle3d>
  </world>
  <camera theta="-90" phi="8"></camera>
</beat>

<beat vo="Stand that diagonal up against the height, and the right-triangle rule runs once more." t="2.6" shot="derive">
  <tex id="floor_eq" morph="match">d^2 = 13 + 2^2 = 17</tex>
  <world>
    <ground></ground>
    <solid id="crate" shape="box" size="3,2,2" color="c4" opacity="0.4" vertices="true"></solid>
    <line3d id="floor_diag" from="-1.5,-1,0" to="1.5,1,0" color="muted"></line3d>
    <line3d id="rise" from="1.5,1,0" to="1.5,1,2" color="muted"></line3d>
    <line3d id="space_diag" from="-1.5,-1,0" to="1.5,1,2" color="accent" width="5"></line3d>
    <angle3d id="up_right" at="1.5,1,0" from="-1.5,-1,0" to="1.5,1,2"></angle3d>
    <label3d id="d" at="0,0,1.2" text="d = √17" color="accent"></label3d>
  </world>
  <camera show="space_diag,rise,floor_diag"></camera>
</beat>
</beats>
```

Why it works: the same box carries all three beats, so the camera does the explaining — a
top-down view turns the 3D box into the flat right triangle of the first step, and the tilt
back up shows the second. The triangles the narration names are drawn: `line3d` sides (the
floor diagonal keeps its id and dims to `muted` once it becomes a leg), `angle3d` marks each right
angle, and the new diagonal is the one accent line. The corners are the box's own
(`vertices="true"`), not extra spheres; the see-through box shows all its edges, so the diagonal
can be followed through it. The formula appears beside the box once there is one to read (`derive`) and morphs as it grows.
