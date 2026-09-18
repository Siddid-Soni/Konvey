"""Example 01 S2 — build. Transformer split (mlp.py idiom)."""
from manim_imports_ext import *


class SingleScene(InteractiveScene):
    def construct(self):
        frame = self.frame
        # Blocks schematic: arrange OUT then split LEFT/RIGHT
        blocks = VGroup(*[Rectangle(height=2, width=1) for _ in range(6)])
        blocks.arrange(OUT, buff=0.5)
        att_blocks = blocks[0::2]
        mlp_blocks = blocks[1::2]

        trans_title = Text("Transformer")
        trans_title.next_to(blocks, UP, buff=0.5)

        # VO: "Attention routes who we talk about, the MLP boosts what comes next."
        self.play(
            LaggedStartMap(FadeIn, blocks, shift=0.25 * UP, lag_ratio=0.1),
            FadeIn(trans_title, UP),
        )
        self.wait()
        self.play(
            att_blocks.animate.shift(4 * LEFT),
            mlp_blocks.animate.shift(4 * RIGHT),
        )
        att_title = Text("Attention")
        mlp_title = Text("MLP")
        att_title.next_to(att_blocks, UP, buff=0.5)
        mlp_title.next_to(mlp_blocks, UP, buff=0.5)
        fact_arrow = Arrow(att_blocks.get_right(), mlp_blocks.get_left(), buff=0.2)
        self.play(FadeIn(att_title, UP), Write(mlp_title), GrowArrow(fact_arrow))
        self.wait()
