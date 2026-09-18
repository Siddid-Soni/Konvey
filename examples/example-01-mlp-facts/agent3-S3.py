"""Example 01 S3 — payoff. Complex collapse (attention.py idiom)."""
from manim_imports_ext import *


class SingleScene(InteractiveScene):
    def construct(self):
        frame = self.frame
        embeddings = VGroup(*[Dot().get_grid(4, 1) for _ in range(4)])
        embeddings.arrange(RIGHT, buff=1.0)
        emb_syms = VGroup(*[Text(f"E_{i}") for i in range(1, 5)])
        for sym, rect in zip(emb_syms, embeddings):
            sym.next_to(rect, DOWN, buff=0.75)
        emb_arrows = VGroup(*[Arrow(e.get_bottom(), s.get_top(), buff=0.1) for e, s in zip(embeddings, emb_syms)])
        brackets = VGroup(*[SurroundingRectangle(e) for e in embeddings])

        # VO: "Facts concentrate in MLPs, but full story is unsolved."
        ghost_syms = emb_syms.copy()
        ghost_syms.set_opacity(0)
        emb_arrows.target = emb_arrows.generate_target()
        brackets_target = [b.generate_target() for b in brackets]
        self.play(
            LaggedStart(
                (AnimationGroup(
                    FadeTransform(entry, sym),
                    MoveToTarget(arr),
                ) for entry, sym, arr in zip(embeddings, ghost_syms, emb_arrows.target)),
                lag_ratio=0.2, run_time=4),
            LaggedStartMap(FadeIn, emb_syms, shift=UP),
            MoveToTarget(emb_arrows, lag_ratio=0.1, run_time=2),
        )
        emb_arrows.refresh_bounding_box(recurse_down=True)
        self.wait()
