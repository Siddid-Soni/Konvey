# Set 03 — Agent 2 (shadows cube video)

## Copy-paste prompt

```text
You are Agent2-Planner for the shadows-geometry video family. Mimic THIS video's plan shape.

EXAMPLE KNOWLEDGE: {"topic":"Average cube shadow","mechanism_steps":["Fix overhead light -> flat projection","Square s^2","Hexagon sqrt(3)","Average -> constant law"]}

EXAMPLE OUTPUT (from _2021/shadows.py:ShadowScene):
{"title":"Average shadow of a cube","scenes":[
{"id":"S1","purpose":"hook","vo_script":["Alice and Bob ask: what is the average shadow of a cube?","Fix light overhead at infinity: flat projection sends x,y,z to x,y,zero."],"beats":[
{"vo_line":"Alice and Bob ask: what is the average shadow of a cube?","objects":["cube","ground_plane"],"object_types":["Cube","Plane"],"layout":[{"op":"frame_reorient","args":"camera.frame.reorient(-30, 75); camera.frame.move_to([0,0,2])"},{"op":"move_to","args":"cube.move_to([0,0,3]); plane.next_to(cube, DOWN, buff=2.0)"}],"spatial_predicates":[["ground_plane","below","cube"]],"animation":{"type":"LaggedStartMap","code_hint":"LaggedStartMap(FadeIn, [cube, plane], shift=UP, lag_ratio=0.15)","run_time":2,"lag_ratio":0.15}},
{"vo_line":"Fix light overhead at infinity: flat projection sends x,y,z to x,y,zero.","objects":["proj_label_xyz_to_xy0","proj_arrow"],"object_types":["Text","Arrow"],"layout":[{"op":"next_to","args":"proj_label.next_to(cube, RIGHT, buff=0.5)"}],"spatial_predicates":[["proj_label_xyz_to_xy0","at right of","cube"]],"animation":{"type":"Write+ShowCreation","code_hint":"Write(proj_label); ShowCreation(proj_arrow)","run_time":2,"lag_ratio":0}}],"duration_sec":30,"precedes":"S2"},
{"id":"S2","purpose":"build","vo_script":["Face-on shadow is a square of area s-squared.","Diagonal shadow is a hexagon of root-three faces; most orientations lie between."],"beats":[
{"vo_line":"Face-on shadow is a square of area s-squared.","objects":["square_shadow","square_label_s2"],"object_types":["Rectangle","Text"],"layout":[{"op":"move_to","args":"square_shadow.move_to(cube.get_center())"},{"op":"next_to","args":"square_label.next_to(square_shadow, DOWN, buff=0.3)"}],"spatial_predicates":[["square_label_s2","below","square_shadow"]],"animation":{"type":"Write+Indicate","code_hint":"Write(square_label); Indicate(square_shadow)","run_time":2,"lag_ratio":0}},
{"vo_line":"Diagonal shadow is a hexagon of root-three faces; most orientations lie between.","objects":["hex_shadow","hex_label_sqrt3"],"object_types":["Polygon","Text"],"layout":[{"op":"move_to","args":"hex_shadow.move_to(cube.get_center())"}],"spatial_predicates":[["hex_label_sqrt3","below","hex_shadow"]],"animation":{"type":"UpdateFromFunc","code_hint":"Rotate(cube, angle); UpdateFromFunc(shadow, update_shadow); Write(hex_label)","run_time":3,"lag_ratio":0}}],"duration_sec":35,"precedes":"S3"},
{"id":"S3","purpose":"payoff","vo_script":["Average over orientations: area of shadow is half surface area times a constant."],"beats":[
{"vo_line":"Average over orientations: area of shadow is half surface area times a constant.","objects":["key_eq_area_shadow","avg_value"],"object_types":["Tex","DecimalNumber"],"layout":[{"op":"to_edge","args":"key_eq.to_edge(DOWN, buff=0.5)"},{"op":"next_to","args":"avg_value.next_to(key_eq, RIGHT, buff=0.5)"}],"spatial_predicates":[["avg_value","at right of","key_eq_area_shadow"]],"animation":{"type":"Write+Indicate+CountInFrom","code_hint":"Write(key_eq); Indicate(shadow); CountInFrom(avg_value, 0)","run_time":3,"lag_ratio":0}}],"duration_sec":25,"precedes":null}]}

Real updater idiom: shadow = get_shadow(solid, light_source); shadow.add_updater(lambda s: update_shadow(s, mobject, light_source)).

NOW DO REAL TASK:
KNOWLEDGE_PACK: {KNOWLEDGE_PACK}
Target duration: {DURATION_SEC, default 90}
Output same schema: 3 scenes S1->S2->S3, beats with layout+animation. layout.op ONLY: next_to/to_edge/to_corner/move_to/arrange/arrange_in_grid/align_to/match_x/match_y/shift/scale/frame_reorient/target. Relations ONLY: above/below/at left of/at right of/on top of. animation.type ONLY from manim-reference/animations.md. Worked outputs: examples/example-06-shadows-cube-average/.
```
