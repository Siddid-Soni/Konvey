---
genre: world3d-hull
kinds: hull, solid
topic_keywords: wedge, triangular prism, half a box, cavalieri
---
### Example: solids given by their corners (topic: a box cut into two wedges)

SCENE_SPEC (abridged): beats = [
 {vo_line: "A box three by two by two, cut corner to corner.", objects: [{id: back, kind: solid, data: {shape: hull, points: [[0,0,0],[3,0,0],[0,2,0],[3,2,0],[0,2,2],[3,2,2]]}}, {id: front, kind: solid, data: {shape: hull, points: [[0,0,0],[3,0,0],[0,0,2],[3,0,2],[0,2,2],[3,2,2]]}}]},
 {vo_line: "The two wedges are the same shape, so each is half the box.", objects: [{id: vol, kind: tex, data: {tex: "V = \\tfrac{1}{2} \\cdot 3 \\cdot 2 \\cdot 2 = 6"}}]},
 {vo_line: "Slide the top edge back and the wedge leans, but its volume stays 6.", objects: [{id: back, kind: solid, data: {shape: hull, points: [[0,0,0],[3,0,0],[0,2,0],[3,2,0],[0,3,2],[3,3,2]]}}]} ]

```html
<beats>
<beat vo="A box three by two by two, cut corner to corner." t="2" shot="full">
  <world>
    <ground></ground>
    <solid id="back" shape="hull" points="0,0,0; 3,0,0; 0,2,0; 3,2,0; 0,2,2; 3,2,2" color="c1"></solid>
    <solid id="front" shape="hull" points="0,0,0; 3,0,0; 0,0,2; 3,0,2; 0,2,2; 3,2,2" color="c2"></solid>
  </world>
  <camera show="back,front"></camera>
</beat>

<beat vo="The two wedges are the same shape, so each is half the box." t="2.4" shot="derive">
  <tex id="vol">V = \tfrac{1}{2} \cdot 3 \cdot 2 \cdot 2 = 6</tex>
  <world>
    <ground></ground>
    <solid id="back" shape="hull" color="c1"></solid>
    <solid id="front" shape="hull" at="0,-1.6,0" color="c2"></solid>
  </world>
  <camera theta="-60" phi="65"></camera>
</beat>

<beat vo="Slide the top edge back and the wedge leans, but its volume stays 6." t="2.4" shot="derive">
  <tex id="vol">V = \tfrac{1}{2} \cdot 3 \cdot 2 \cdot 2 = 6</tex>
  <world>
    <ground></ground>
    <solid id="back" shape="hull" points="0,0,0; 3,0,0; 0,2,0; 3,2,0; 0,3,2; 3,3,2" color="c1" vertices="true"></solid>
    <solid id="front" shape="hull" at="0,-1.4,0" color="c2" opacity="0.35"></solid>
  </world>
  <camera show="back"></camera>
</beat>
</beats>
```

Why it works: neither wedge is a preset shape, so each is a `hull` written by its corners, and
because the two share the corners on the cut they fill the box exactly in the first beat. `at`
pulls one away without retyping its corners, and the camera turns to the end where both
triangles show, so the gap between the pieces is the cut. In the last beat the same id gets new `points` (same count): the top edge slides back and
the wedge leans while the base stays put, which is the narration's point. `vertices="true"`
marks the corners that moved. The volume is written beside the pieces (`derive`).
