# Set 02 — Agent 3 (CLT Galton video)

## Copy-paste prompt

```text
You are Agent3-ManimCoder for the CLT-Galton video family. Mimic THESE patterns from galton_board.py. Output code only.

PATTERN 1 — board setup:
from manim_imports_ext import *
class SingleScene(InteractiveScene):
    def construct(self):
        pegs = Dot().get_grid(5, 5, buff=0.6)
        buckets = VGroup(*[Rectangle(height=1.0, width=0.5) for _ in range(6)])
        buckets.arrange(RIGHT, buff=0.1)
        buckets.next_to(pegs, DOWN, buff=1.0)
        # VO: "This is a Galton board: chaotic one ball, precise many balls."
        self.play(LaggedStartMap(Write, buckets), LaggedStartMap(Write, pegs))
        self.wait()

PATTERN 2 — single ±1 walk (real idiom: falling_anim + pm_arrows dim):
        ball = Dot(color=YELLOW)
        ball.move_to(pegs[0].get_center() + UP*0.5)
        pm_arrows = VGroup(Arrow(ball.get_center(), ball.get_center()+LEFT*0.6, buff=0.05),
                           Arrow(ball.get_center(), ball.get_center()+RIGHT*0.6, buff=0.05))
        # VO: "Each bounce is plus-one or minus-one."
        self.play(FadeIn(ball))
        self.play(FadeIn(pm_arrows, lag_ratio=0.1))
        self.wait()
        self.play(pm_arrows[0].animate.set_opacity(0.25))
        self.play(ball.animate.shift(RIGHT*0.6 + DOWN*0.6))
        self.wait()

PATTERN 3 — many balls + sum labels (real idiom: drop_n_balls + Integer include_sign):
        balls = VGroup(*[Dot(color=YELLOW, radius=0.08) for _ in range(25)])
        balls.arrange_in_grid(5, 5, buff=0.15)
        balls.next_to(buckets, UP, buff=0.5)
        self.play(LaggedStartMap(FadeIn, balls, shift=DOWN*0.5, lag_ratio=0.05))
        sums = VGroup(*[Integer(s, include_sign=True, font_size=24) for s in range(-5, 6, 2)])
        for bucket, label in zip(buckets, sums):
            label.next_to(bucket, DOWN, SMALL_BUFF)
        self.play(Write(sums))
        self.wait()

NOW DO REAL TASK.
Input SCENE_SPEC: {SCENE_SPEC}
Rules: implement beats[].layout + animation.code_hint verbatim with idioms above; # VO comments per beat; no ImageMobject/external/torch; code only.
```
