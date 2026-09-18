# Set 03 — Agent 3 (shadows cube video)

## Copy-paste prompt

```text
You are Agent3-ManimCoder for the shadows-geometry video family. Mimic THESE patterns from shadows.py. Output code only.

PATTERN 1 — setup (ShadowScene.setup idiom, simplified 2D):
from manim_imports_ext import *
class SingleScene(InteractiveScene):
    def construct(self):
        cube = Rectangle(height=2, width=2)
        cube.move_to(ORIGIN + UP*1.0)
        plane = Line(LEFT*4, RIGHT*4)
        plane.next_to(cube, DOWN, buff=2.0)
        # VO: "Alice and Bob ask: what is the average shadow of a cube?"
        self.play(LaggedStartMap(FadeIn, VGroup(cube, plane), shift=UP, lag_ratio=0.15))
        self.wait()
        proj_label = Text("(x,y,z)->(x,y,0)")
        proj_label.next_to(cube, RIGHT, buff=0.5)
        proj_arrow = Arrow(cube.get_bottom(), plane.get_center(), buff=0.1)
        # VO: "Fix light overhead: flat projection."
        self.play(Write(proj_label), ShowCreation(proj_arrow))
        self.wait()

PATTERN 2 — cases (square -> hexagon, real updater idea):
        shadow = Rectangle(height=2, width=2, fill_opacity=0.4)
        shadow.move_to(cube.get_center())
        square_label = Text("s^2")
        square_label.next_to(shadow, DOWN, buff=0.3)
        # VO: "Face-on shadow is a square."
        self.play(FadeIn(shadow), Write(square_label))
        self.play(Indicate(shadow))
        self.wait()
        hexagon = RegularPolygon(n=6, fill_opacity=0.4)
        hexagon.move_to(cube.get_center())
        # VO: "Diagonal shadow is a hexagon."
        self.play(ReplacementTransform(shadow, hexagon))
        self.wait()

PATTERN 3 — key equation (get_key_result idiom):
        # VO: "Average: Area(Shadow) = 1/2 x surface area."
        key_eq = Tex(r"\text{Area}(\text{Shadow}) = \frac{1}{2}\cdot(\text{Surface area})")
        key_eq.to_edge(DOWN, buff=0.5)
        self.play(Write(key_eq))
        self.wait()

Real 3D updater when available: shadow = get_shadow(solid, light_source); shadow.add_updater(lambda s: update_shadow(s, mobject, light_source)).

NOW DO REAL TASK.
Input SCENE_SPEC: {SCENE_SPEC}
Rules: implement beats[].layout + animation.code_hint verbatim with idioms above; # VO comments per beat; no ImageMobject/external; code only.
```
