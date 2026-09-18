"""Example 06 S2 — square then hexagon shadow (updater idiom, simplified)."""
from manim_imports_ext import *


class SingleScene(InteractiveScene):
    def construct(self):
        cube = Rectangle(height=2, width=2)
        shadow = Rectangle(height=2, width=2, fill_opacity=0.4)
        shadow.move_to(cube.get_center())
        square_label = Text("s^2")
        square_label.next_to(shadow, DOWN, buff=0.3)
        # VO: "Face-on shadow is a square of area s-squared."
        self.add(cube)
        self.play(FadeIn(shadow), Write(square_label))
        self.play(Indicate(shadow))
        self.wait()
        # VO: "Diagonal shadow is a hexagon of root-three faces."
        hexagon = RegularPolygon(n=6, fill_opacity=0.4)
        hexagon.move_to(cube.get_center())
        hex_label = Text("sqrt(3) faces")
        hex_label.next_to(hexagon, DOWN, buff=0.3)
        self.play(ReplacementTransform(shadow, hexagon), FadeOut(square_label, UP))
        self.play(Write(hex_label))
        self.wait()
