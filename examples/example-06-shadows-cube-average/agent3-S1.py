"""Example 06 S1 — flat projection setup (shadows.py ShadowScene idiom, simplified 2D)."""
from manim_imports_ext import *


class SingleScene(InteractiveScene):
    def construct(self):
        # VO: "Alice and Bob ask: what is the average shadow of a cube?"
        cube = Rectangle(height=2, width=2)
        cube.move_to(ORIGIN + UP * 1.0)
        plane = Line(LEFT * 4, RIGHT * 4)
        plane.next_to(cube, DOWN, buff=2.0)
        self.play(LaggedStartMap(FadeIn, VGroup(cube, plane), shift=UP, lag_ratio=0.15))
        self.wait()
        # VO: "Fix light overhead at infinity: flat projection sends x,y,z to x,y,zero."
        proj_label = Text("(x,y,z)->(x,y,0)")
        proj_label.next_to(cube, RIGHT, buff=0.5)
        proj_arrow = Arrow(cube.get_bottom(), plane.get_center(), buff=0.1)
        self.play(Write(proj_label), ShowCreation(proj_arrow))
        self.wait()
