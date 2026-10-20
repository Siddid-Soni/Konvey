---
genre: world3d
kinds: solid, sphere, field, surface, point, gradient, contours, axes3d, label3d, light, shadow
topic_keywords: cone, cylinder, volume of a cone, cone volume
---
### Example: a 3D scene (topic: why a cone holds one third of its cylinder)

SCENE_SPEC (abridged): beats = [
 {vo_line: "A cylinder holds its base area times its height.", objects: [{id: tube, kind: solid, data: {shape: cylinder}}, {id: v_cyl, kind: tex, data: {tex: "V = \\pi r^2 h"}}]},
 {vo_line: "Shrink the top to a point and the same base holds only a third.", objects: [{id: tip, kind: solid, data: {shape: cone}}, {id: v_cone, kind: tex, data: {tex: "V = \\tfrac{1}{3}\\pi r^2 h"}}]},
 {vo_line: "From above, both cast exactly the same disc.", objects: [{id: v_cone, kind: tex, data: {tex: "V = \\tfrac{1}{3}\\pi r^2 h"}}]} ]

```html
<beats>
<beat vo="A cylinder holds its base area times its height." t="2" shot="derive">
  <tex id="eq">V = \pi r^2 h</tex>
  <world>
    <ground></ground>
    <solid id="tube" shape="cylinder" r="1.2" h="2.6" at="-1.6,0,1.3" color="c4"></solid>
    <label3d id="tube_tag" of="tube" text="cylinder"></label3d>
  </world>
  <camera theta="-30" phi="65"></camera>
</beat>

<beat vo="Shrink the top to a point and the same base holds only a third." t="2.4" shot="derive">
  <tex id="eq" morph="match">V = \tfrac{1}{3}\pi r^2 h</tex>
  <world>
    <ground></ground>
    <solid id="tube" shape="cylinder" r="1.2" h="2.6" at="-1.6,0,1.3" color="c4" opacity="0.35"></solid>
    <solid id="tip" shape="cone" r="1.2" h="2.6" at="1.6,0,1.3" color="accent"></solid>
    <label3d id="tube_tag" of="tube" text="cylinder"></label3d>
    <label3d id="tip_tag" of="tip" text="cone: one third"></label3d>
  </world>
  <camera theta="-40" phi="62"></camera>
</beat>

<beat vo="From above, both cast exactly the same disc." t="2.6" shot="derive">
  <tex id="eq">V = \tfrac{1}{3}\pi r^2 h</tex>
  <world>
    <ground></ground>
    <light id="sun" dir="0,0,-1"></light>
    <solid id="tube" shape="cylinder" r="1.2" h="2.6" at="-1.6,0,1.3" color="c4" opacity="0.35"></solid>
    <solid id="tip" shape="cone" r="1.2" h="2.6" at="1.6,0,1.3" color="accent"></solid>
    <shadow id="tube_disc" of="tube"></shadow>
    <shadow id="tip_disc" of="tip"></shadow>
  </world>
  <camera theta="-90" phi="12"></camera>
</beat>
</beats>
```

Why it works: the cylinder keeps its id, so it stays while the cone joins it, then fades to
see-through so the eye goes to the accent cone; the formula morphs because the same idea
changes form; the last beat *shows* "the same base" by tilting the camera top-down onto two
real shadows instead of saying it in text. The formula is a word beside the world (`derive`),
so the solids keep the left of the screen and the camera frames them there.
