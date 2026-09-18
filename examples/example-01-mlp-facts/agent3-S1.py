"""Example 01 S1 — hook. Implements Agent2 S1 beats verbatim."""
from manim_imports_ext import *


class SingleScene(InteractiveScene):
    def construct(self):
        # 1. Objects -> Text + Rectangle
        # 2. Layout -> move_to + next_to/match_y
        # 3. Animation -> LaggedStartMap(FadeIn) then Write+ShowCreation
        # 4. Check: no ImageMobject, every object animated
        phrase_mob = Text("Jordan plays sport of ___")
        phrase_mob.move_to(2 * UP)
        words = VGroup(*phrase_mob.submobjects)
        rect = SurroundingRectangle(phrase_mob)
        rect.set_stroke(GREY, 2).set_fill(GREY, 0.2)

        # VO: "If you feed a model Michael Jordan plays the sport of blank, it says basketball."
        self.play(LaggedStartMap(FadeIn, phrase_mob, shift=0.5 * UP, lag_ratio=0.25))
        self.play(DrawBorderThenFill(rect))
        self.wait()

        question = Text("Where did that fact live?")
        question.next_to(rect, UP, buff=0.5)
        arrow = Arrow(question.get_bottom(), rect.get_top(), buff=0.1)
        # VO: "Where did that fact live?"
        self.play(ShowCreation(rect), Write(question), GrowArrow(arrow))
        self.wait()
