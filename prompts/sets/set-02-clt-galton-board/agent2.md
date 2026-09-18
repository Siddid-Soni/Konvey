# Set 02 — Agent 2 (CLT Galton video)

## Copy-paste prompt

```text
You are Agent2-Planner for the CLT-Galton video family. Mimic THIS video's plan shape.

EXAMPLE KNOWLEDGE: {"topic":"Galton board CLT preview","mechanism_steps":["±1 per peg","5 rows -> sum","many balls -> counts","more rows -> bell"]}

EXAMPLE OUTPUT (from _2023/clt/galton_board.py:GaltonBoard):
{"title":"Galton board previews the CLT","scenes":[
{"id":"S1","purpose":"hook","vo_script":["This is a Galton board: chaotic one ball, precise many balls.","Each bounce is plus-one or minus-one, fifty-fifty; final bucket is the sum."],"beats":[
{"vo_line":"This is a Galton board: chaotic one ball, precise many balls.","objects":["pegs","buckets"],"object_types":["Dot","Rectangle"],"layout":[{"op":"arrange","args":"pegs.arrange_in_grid(rows, cols, buff=spacing)"},{"op":"arrange","args":"buckets.arrange(RIGHT, buff=0.2).next_to(pegs, DOWN, buff=1.0)"}],"spatial_predicates":[["buckets","below","pegs"]],"animation":{"type":"LaggedStartMap","code_hint":"LaggedStartMap(Write, buckets); LaggedStartMap(Write, pegs)","run_time":2,"lag_ratio":0.1}},
{"vo_line":"Each bounce is plus-one or minus-one, fifty-fifty; final bucket is the sum.","objects":["ball","pm_arrows","trajectory_piece"],"object_types":["Sphere","Arrow"],"layout":[{"op":"move_to","args":"ball.move_to(piece.get_start())"},{"op":"next_to","args":"pm_arrows.next_to(ball, UP, buff=0.2)"}],"spatial_predicates":[["pm_arrows","above","ball"]],"animation":{"type":"Succession+FadeIn","code_hint":"falling_anim(ball, piece); FadeIn(pm_arrows, lag_ratio=0.1); pm_arrows[1-bit].animate.set_opacity(0.25)","run_time":2,"lag_ratio":0.1}}],"duration_sec":30,"precedes":"S2"},
{"id":"S2","purpose":"build","vo_script":["Many ghost balls fill buckets; counts hint at probabilities, like Pascal's triangle."],"beats":[
{"vo_line":"Many ghost balls fill buckets; counts hint at probabilities, like Pascal's triangle.","objects":["many_balls","sum_labels"],"object_types":["Sphere","Integer"],"layout":[{"op":"next_to","args":"sum_labels.next_to(buckets, DOWN, SMALL_BUFF)"}],"spatial_predicates":[["sum_labels","below","many_balls"]],"animation":{"type":"LaggedStart","code_hint":"drop_n_balls(25); FadeOut(balls, lag_ratio=0.05)","run_time":3,"lag_ratio":0.05}}],"duration_sec":30,"precedes":"S3"},
{"id":"S3","purpose":"payoff","vo_script":["Add rows and the sum histogram looks more and more like a bell curve."],"beats":[
{"vo_line":"Add rows and the sum histogram looks more and more like a bell curve.","objects":["histogram_5_rows","histogram_many_rows","bell_overlay"],"object_types":["Rectangle","Function"],"layout":[{"op":"move_to","args":"bell_curve.move_to(histogram.get_top())"}],"spatial_predicates":[["bell_overlay","on top of","histogram_many_rows"]],"animation":{"type":"LaggedStartMap","code_hint":"LaggedStartMap(FadeIn, taller_histogram, shift=UP, lag_ratio=0.05)","run_time":3,"lag_ratio":0.05}}],"duration_sec":25,"precedes":null}]}

NOW DO REAL TASK:
KNOWLEDGE_PACK: {KNOWLEDGE_PACK}
Target duration: {DURATION_SEC, default 90}
Output same schema: 3 scenes S1->S2->S3, beats with layout+animation. layout.op ONLY: next_to/to_edge/to_corner/move_to/arrange/arrange_in_grid/align_to/match_x/match_y/shift/scale/frame_reorient/target. Relations ONLY: above/below/at left of/at right of/on top of. animation.type ONLY from manim-reference/animations.md. Worked outputs: examples/example-04-clt-galton-board/.
```
