---
genre: world3d-cut
kinds: hull, solid
topic_keywords: frustum, truncated pyramid, slice the top off
---
### Example: cutting a piece off a solid (topic: slicing the top off a pyramid)

SCENE_SPEC (abridged): beats = [
 {vo_line: "A square pyramid: base two by two, height two.", objects: [{id: body, kind: solid, data: {shape: hull, points: [[-1,-1,0],[1,-1,0],[1,1,0],[-1,1,0],[0,0,2]]}}]},
 {vo_line: "Cut it level, halfway up.", objects: [{id: vol, kind: tex, data: {tex: "V = \\tfrac{1}{3} \\cdot 4 \\cdot 2 = \\tfrac{8}{3}"}}, {id: tip, kind: solid, data: {shape: hull}}]},
 {vo_line: "The small pyramid on top comes away: one third of one by one by one.", objects: [{id: vol, kind: tex, data: {tex: "V = \\tfrac{8}{3} - \\tfrac{1}{3} = \\tfrac{7}{3}"}}]} ]

```html
<beats>
<beat vo="A square pyramid: base two by two, height two." t="2.2" shot="full">
  <world>
    <ground></ground>
    <solid id="body" shape="hull" points="-1,-1,0; 1,-1,0; 1,1,0; -1,1,0; 0,0,2*4" color="c1"></solid>
  </world>
  <camera theta="-35" phi="65"></camera>
</beat>

<beat vo="Cut it level, halfway up." t="2.6" shot="derive">
  <tex id="vol">V = \tfrac{1}{3} \cdot 4 \cdot 2 = \tfrac{8}{3}</tex>
  <world>
    <ground></ground>
    <solid id="body" shape="hull" points="-1,-1,0; 1,-1,0; 1,1,0; -1,1,0; -0.5,-0.5,1; 0.5,-0.5,1; 0.5,0.5,1; -0.5,0.5,1" color="c1"></solid>
    <solid id="tip" shape="hull" points="-0.5,-0.5,1; 0.5,-0.5,1; 0.5,0.5,1; -0.5,0.5,1; 0,0,2" color="accent"></solid>
  </world>
  <camera theta="-35" phi="65"></camera>
</beat>

<beat vo="The small pyramid on top comes away: one third of one by one by one." t="2.4" shot="derive">
  <tex id="vol">V = \tfrac{8}{3} - \tfrac{1}{3} = \tfrac{7}{3}</tex>
  <world>
    <ground></ground>
    <solid id="body" shape="hull" color="c1"></solid>
    <solid id="tip" shape="hull" at="0,0,1.3" color="accent" vertices="true"></solid>
  </world>
  <camera theta="-35" phi="65"></camera>
</beat>
</beats>
```

Why it works: the solid itself loses the piece, instead of a highlighted piece sitting inside an
unchanged solid. A hull keeps its corner count, so the tip is written four times (`0,0,2*4`) in
the first beat: one copy for each corner the cut will make. The cutting beat moves those four
copies to the corners of the cut square, so the top slices off in one motion while the base
stays put, and the removed piece appears as its own hull exactly where it was. The next beat
lifts it away with `at` (its corners are still written where it was cut from) and the formula
subtracts it. To cut several pieces one by one, cut one per beat the same way. The first beat is the
picture alone (`full`); once there is a volume to write, it goes beside the solid (`derive`).
