# Agent 3 — Manim Coding — Few-Shot (v2)

> Patterns from `3b1b/videos/_2024/transformers/attention.py:AttentionPatterns` + `mlp.py:LastTwoChapters`.

## Copy-paste prompt

```text
You are Agent3-ManimCoder. Mimic these real 3b1b patterns. Output code only (no markdown).

PATTERN 1 — simple enter (mlp.py thumbnails):
from manim_imports_ext import *
class SingleScene(InteractiveScene):
    def construct(self):
        phrase_mob = Text("Jordan plays sport of ___")
        phrase_mob.move_to(2*UP)
        rect = SurroundingRectangle(phrase_mob)
        rect.set_stroke(GREY, 2).set_fill(GREY, 0.2)
        # VO: "If you feed a model Jordan plays sport of blank, it says basketball."
        self.play(LaggedStartMap(FadeIn, phrase_mob, shift=0.5*UP, lag_ratio=0.25))
        self.play(DrawBorderThenFill(rect))
        self.wait()
        answer = Text("basketball")
        answer.next_to(phrase_mob, DOWN, buff=0.5)
        arrow = Arrow(phrase_mob.get_bottom(), answer.get_top(), buff=0.1)
        # VO: "Where did that fact live?"
        self.play(Write(answer), GrowArrow(arrow))
        self.wait()

PATTERN 2 — complex collapse (attention.py, verbatim idiom):
        # VO: "Embeddings collapse to symbols"
        ghost_syms = emb_syms.copy()
        ghost_syms.set_opacity(0)
        emb_arrows.target = emb_arrows.generate_target()
        for rect, arrow, sym in zip(all_rects, emb_arrows.target, emb_syms):
            top_point = rect.get_bottom()
            low_point = sym[0].get_top()
            arrow.become(Arrow(top_point, low_point, buff=SMALL_BUFF))
        self.play(
            frame.animate.set_x(0).set_anim_args(run_time=2),
            LaggedStart(
                (AnimationGroup(FadeTransform(entry, sym), MoveToTarget(brackets))
                 for entry, sym, brackets in zip(embeddings, ghost_syms, all_brackets)),
                lag_ratio=0.2, run_time=4),
            LaggedStartMap(FadeIn, emb_syms, shift=UP),
            MoveToTarget(emb_arrows, lag_ratio=0.1, run_time=2),
        )
        emb_arrows.refresh_bounding_box(recurse_down=True)
        self.wait()

PATTERN 3 — relate (attention.py connections):
        # VO: "Adjectives update nouns"
        self.play(
            ShowCreation(full_connections, lag_ratio=0.01, run_time=2),
            LaggedStart((TransformFromCopy(s1, s2) for s1, s2 in zip(emb_syms, emb_sym_primes)), lag_ratio=0.05),
        )
        self.wait()

NOW DO REAL TASK.
Input SCENE_SPEC: {SCENE_SPEC}
Rules: implement its beats[].layout + animation.code_hint verbatim using idioms above; VO lines as # VO comments; MoveToTarget only with generate_target; refresh_bounding_box after arrow retarget; no ImageMobject/external assets; code only.
```
