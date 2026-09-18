"""Example 04 S1 — Galton board setup + single ±1 walk (galton_board.py idiom, simplified 2D)."""
from manim_imports_ext import *


class SingleScene(InteractiveScene):
    def construct(self):
        # 1. Objects -> pegs (Dots grid) + buckets (Rects) + ball + ±1 arrows
        # 2. Layout -> buckets below pegs; arrows above ball
        # 3. Animation -> LaggedStartMap(Write) then falling + FadeIn(arrows)
        pegs = Dot().get_grid(5, 5, buff=0.6)
        buckets = VGroup(*[Rectangle(height=1.0, width=0.5) for _ in range(6)])
        buckets.arrange(RIGHT, buff=0.1)
        buckets.next_to(pegs, DOWN, buff=1.0)

        # VO: "This is a Galton board: chaotic one ball, precise many balls."
        self.play(
            LaggedStartMap(Write, buckets),
            LaggedStartMap(Write, pegs),
        )
        self.wait()

        ball = Dot(color=YELLOW)
        ball.move_to(pegs[0].get_center() + UP * 0.5)
        pm_arrows = VGroup(
            Arrow(ball.get_center(), ball.get_center() + LEFT * 0.6, buff=0.05),
            Arrow(ball.get_center(), ball.get_center() + RIGHT * 0.6, buff=0.05),
        )
        # VO: "Each bounce is plus-one or minus-one, fifty-fifty; final bucket is the sum."
        self.play(FadeIn(ball))
        self.play(FadeIn(pm_arrows, lag_ratio=0.1))
        self.wait()
        # Chosen path: dim the rejected arrow (real idiom: pm_arrows[1-bit].animate.set_opacity(0.25))
        self.play(pm_arrows[0].animate.set_opacity(0.25))
        self.play(ball.animate.shift(RIGHT * 0.6 + DOWN * 0.6))
        self.wait()
