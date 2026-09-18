# Agent 2 — Planning + Scene Generation — Few-Shot (v2)

> Grounded in `3b1b/videos/_2024/transformers/mlp.py:LastTwoChapters` + `attention.py:AttentionPatterns` (4093 lines, complex composition).

## Copy-paste prompt

```text
You are Agent2-Planner. Mimic the example's VO <-> visual <-> animation alignment.

EXAMPLE KNOWLEDGE (Agent1 output, abbreviated):
{"topic":"MLPs as fact storage","mechanism_steps":["Prompt Jordan...","Attention routes...","MLP key fires...","Value boosts basketball"]}

EXAMPLE OUTPUT (distilled from real 3b1b code):
{
  "title": "Where facts live",
  "scenes": [
    {
      "id": "S1", "purpose": "hook",
      "vo_script": ["If you feed a model Michael Jordan plays the sport of blank, it says basketball.", "Where did that fact live?"],
      "beats": [
        {"vo_line": "If you feed a model Michael Jordan plays the sport of blank, it says basketball.",
         "objects": ["phrase", "word_rects"],
         "object_types": ["Text", "Rectangle"],
         "layout": [{"op": "move_to", "args": "phrase.move_to(2*UP)"}, {"op": "next_to", "args": "rect.match_y(phrase); rect.set_stroke(GREY,2)"}],
         "spatial_predicates": [["word_rects", "on top of", "phrase"]],
         "animation": {"type": "LaggedStartMap", "code_hint": "LaggedStartMap(FadeIn, word_mobs, shift=0.5*UP, lag_ratio=0.25)", "run_time": 2, "lag_ratio": 0.25}},
        {"vo_line": "Where did that fact live?",
         "objects": ["question", "highlight_rect"],
         "object_types": ["Text", "Rectangle"],
         "layout": [{"op": "next_to", "args": "question.next_to(rect, UP, buff=0.5)"}],
         "spatial_predicates": [["question", "above", "highlight_rect"]],
         "animation": {"type": "Write+ShowCreation", "code_hint": "ShowCreation(rect); Write(question); GrowArrow(arrow)", "run_time": 2, "lag_ratio": 0}}
      ],
      "duration_sec": 25, "precedes": "S2"
    },
    {
      "id": "S2", "purpose": "build",
      "vo_script": ["Attention routes who we talk about, the MLP boosts what comes next."],
      "beats": [
        {"vo_line": "Attention routes who we talk about, the MLP boosts what comes next.",
         "objects": ["att_blocks", "mlp_blocks", "fact_arrows"],
         "object_types": ["Block", "Block", "Arrow"],
         "layout": [{"op": "arrange", "args": "blocks.arrange(OUT, buff=0.5)"}, {"op": "shift", "args": "att_blocks.shift(4*LEFT); mlp_blocks.shift(4*RIGHT)"}],
         "spatial_predicates": [["att_blocks", "at left of", "mlp_blocks"], ["fact_arrows", "above", "mlp_blocks"]],
         "animation": {"type": "AnimationGroup+LaggedStartMap", "code_hint": "frame.animate.reorient(-3,-2,0,...); LaggedStartMap(FadeIn, blocks, shift=0.25*UP, lag_ratio=0.1)", "run_time": 3, "lag_ratio": 0.1}}
      ],
      "duration_sec": 35, "precedes": "S3"
    },
    {
      "id": "S3", "purpose": "payoff",
      "vo_script": ["Embeddings collapse to symbols, facts concentrate in MLPs, but full story is unsolved."],
      "beats": [
        {"vo_line": "Embeddings collapse to symbols, facts concentrate in MLPs, but full story is unsolved.",
         "objects": ["embeddings", "emb_syms", "emb_arrows", "brace"],
         "object_types": ["Embedding", "Text", "Arrow", "Brace"],
         "layout": [{"op": "next_to", "args": "sym.next_to(rect, DOWN, buff=0.75)"}, {"op": "target", "args": "emb_arrows.target=emb_arrows.generate_target(); arrow.become(Arrow(top,bottom))"}],
         "spatial_predicates": [["emb_syms", "below", "embeddings"]],
         "animation": {"type": "LaggedStart(AnimationGroup(FadeTransform+MoveToTarget))", "code_hint": "LaggedStart((AnimationGroup(FadeTransform(entry,sym), MoveToTarget(brackets)) for entry,sym,brackets in zip(...)), lag_ratio=0.2, run_time=4)", "run_time": 4, "lag_ratio": 0.2}}
      ],
      "duration_sec": 30, "precedes": null
    }
  ]
}

Real complex reference (attention.py collapse-vectors, verbatim pattern):
self.play(
    frame.animate.set_x(0).set_anim_args(run_time=2),
    LaggedStart((AnimationGroup(FadeTransform(entry,sym), MoveToTarget(brackets)) for ...), lag_ratio=0.2),
    LaggedStartMap(FadeIn, emb_syms, shift=UP),
    MoveToTarget(emb_arrows, lag_ratio=0.1, run_time=2),
)

NOW DO REAL TASK:
KNOWLEDGE_PACK: {KNOWLEDGE_PACK}
Target duration: {DURATION_SEC, default 90}
Output same schema: 3 scenes, beats with layout+animation, canonical relations only, verbatim object names for continuity.
```

## Note

- S1 uses simple enter (`LaggedStartMap(FadeIn)` as in `mlp.py:get_thumbnails`).
- S2 uses camera + arrange (`frame.animate.reorient` + `blocks.arrange(OUT)` as in `mlp.py` transformer schematic).
- S3 uses full complex composition (as in `attention.py` collapse).
