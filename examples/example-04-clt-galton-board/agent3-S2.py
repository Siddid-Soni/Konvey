"""Example 04 S2 — many balls -> histogram hints bell (drop_n_balls idiom, simplified)."""
from manim_imports_ext import *


class SingleScene(InteractiveScene):
    def construct(self):
        buckets = VGroup(*[Rectangle(height=1.0, width=0.5) for _ in range(6)])
        buckets.arrange(RIGHT, buff=0.1)
        # VO: "Many ghost balls fill buckets; counts hint at probabilities."
        balls = VGroup(*[Dot(color=YELLOW, radius=0.08) for _ in range(25)])
        balls.arrange_in_grid(5, 5, buff=0.15)
        balls.next_to(buckets, UP, buff=0.5)
        self.add(buckets)
        self.play(LaggedStartMap(FadeIn, balls, shift=DOWN * 0.5, lag_ratio=0.05))
        self.wait()
        self.play(balls.animate.shift(DOWN * 1.0), run_time=2)
        self.wait()
        sums = VGroup(*[Integer(s, include_sign=True, font_size=24) for s in range(-5, 6, 2)])
        for bucket, label in zip(buckets, sums):
            label.next_to(bucket, DOWN, SMALL_BUFF)
        self.play(Write(sums))
        self.wait()
