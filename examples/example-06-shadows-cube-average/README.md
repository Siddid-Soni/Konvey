# Example 06 — Shadows: average cube shadow = half surface area (geometry)

> Different video: 3D geometry + problem-solving styles, not ML/probability.
> Sources:
> - VO: `3b1b/captions/2021/shadows/english/transcript.txt` — `Alice vs Bob (procrastinate compute vs dig in)... puzzle: average shadow area of cube... light directly above, infinitely far -> flat projection (x,y,z)->(x,y,0)... easy case square s^2... diagonal hexagon sqrt(3)... average over orientations...`
> - Code: `3b1b/videos/_2021/shadows.py:ShadowScene` — `ThreeDScene`, `camera.frame.reorient(-30,75)`, `VCube + NumberPlane + get_shadow(solid, light) + add_updater(update_shadow)`, `get_key_result("Cube")` eq `Area(Shadow)=1/2·c·SurfaceArea`, `flat_project`, `get_convex_hull`
> - Prompts: Agent1 few-shot -> Agent2 few-shot -> Agent3 few-shot

## Files

- `agent1-output.json`, `agent2-output.json`, `agent3-S1.py` (flat projection setup + square case), `agent3-S2.py` (rotate + shadow updater + key equation)
