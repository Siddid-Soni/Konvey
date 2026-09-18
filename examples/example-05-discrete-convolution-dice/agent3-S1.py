"""Example 05 S1 — 36-pair grid, diagonals = sums (discrete.py idiom)."""
from manim_imports_ext import *


class SingleScene(InteractiveScene):
    def construct(self):
        # Grid of 36 pairs; SurroundingRectangle per diagonal group
        dice = VGroup(*[Rectangle(height=0.4, width=0.4) for _ in range(36)])
        dice.arrange_in_grid(6, 6, buff=0.12)
        # VO: "Thirty-six pairs in a grid; each diagonal is one sum."
        self.play(LaggedStartMap(FadeIn, dice, shift=UP, lag_ratio=0.03))
        self.wait()
        diag = VGroup(*dice[7:12])
        rect = SurroundingRectangle(diag, buff=0.08)
        rect.set_stroke(YELLOW, 2)
        self.play(ShowCreation(rect, lag_ratio=0.1))
        self.wait()
