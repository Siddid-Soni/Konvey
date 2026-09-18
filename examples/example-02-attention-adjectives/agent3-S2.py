"""Example 02 S2 — adjectives update nouns (attention.py idiom, simplified, no external assets)."""
from manim_imports_ext import *


class SingleScene(InteractiveScene):
    def construct(self):
        # 1. Objects -> Text phrase + rects + arrows
        # 2. Layout -> rect.match_y(phrase); Arrow(adj_top, noun_top, path_arc)
        # 3. Animation -> DrawBorderThenFill + ShowCreation + ContextAnimation
        # 4. Check: every object animated, no ImageMobject
        phrase_mob = Text("a fluffy blue creature roamed the verdant forest")
        phrase_mob.move_to(2 * UP)
        words = ["a", "fluffy", "blue", "creature", "roamed", "the", "verdant", "forest"]
        # NOTE: real code indexes phrase_mob[" word"]; here split roughly for portability
        word_mobs = VGroup(*[Text(w) for w in words])
        word_mobs.arrange(RIGHT, buff=0.2)
        word_mobs.move_to(2 * UP)

        word2rect = {w: SurroundingRectangle(m) for w, m in zip(words, word_mobs)}
        for r in word2rect.values():
            r.set_stroke(GREY, 2).set_fill(GREY, 0.2)

        adj_mobs = VGroup(*[word_mobs[i] for i in [1, 2, 6]])
        noun_mobs = VGroup(*[word_mobs[i] for i in [3, 7]])
        adj_rects = VGroup(*[word2rect[w] for w in ["fluffy", "blue", "verdant"]])
        noun_rects = VGroup(*[word2rect[w] for w in ["creature", "forest"]])

        # VO: "Adjectives fluffy and blue update the noun creature."
        self.play(LaggedStartMap(FadeIn, word_mobs, shift=0.5 * UP, lag_ratio=0.25))
        self.wait()
        self.play(LaggedStartMap(DrawBorderThenFill, adj_rects))
        self.wait()
        adj_arrows = VGroup(*[
            Arrow(adj.get_top(), noun.get_top(), path_arc=-150 * DEGREES, buff=0.1)
            for adj, noun in [(adj_mobs[0], noun_mobs[0]), (adj_mobs[1], noun_mobs[0]), (adj_mobs[2], noun_mobs[1])]
        ])
        self.play(
            LaggedStartMap(DrawBorderThenFill, noun_rects),
            LaggedStartMap(ShowCreation, adj_arrows, lag_ratio=0.2, run_time=1.5),
        )
        self.wait()
        # VO: "Embeddings carry meaning plus position."
        self.play(
            ContextAnimation(noun_mobs[0], adj_mobs[:2], strengths=[1, 1], time_width=2, max_stroke_width=10, lag_ratio=0.2, path_arc=150 * DEGREES),
            ContextAnimation(noun_mobs[1], adj_mobs[2:], strengths=[1], time_width=2, max_stroke_width=10, lag_ratio=0.2, path_arc=150 * DEGREES),
        )
        self.wait()
