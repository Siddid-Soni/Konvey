# Spike A — HTML beats → Chromium layout → Manim

Spec: `docs/superpowers/specs/2026-10-15-html-layout-for-manim-design.md` (approach A, milestone 1).
Lesson: `spikes/STORYBOARD.md` (same storyboard as spike C).

```bash
./render.sh preview   # 854x480, ~30 s
./render.sh           # 1920x1080 @30fps, ~45 s  -> out/cube-shadow.mp4 (61 s video)
```

Needs `uv` groups `render` (manimgl) and `layout` (playwright → system `/usr/bin/chromium`).

## What's here

| file | role (spec §) |
|---|---|
| `cube_shadow.html` | **The authored input**: 10 `<beat>` snapshots, what an LLM would write |
| `stage/parse.py` | beat HTML → typed nodes; rejects unknown tags / leaves without id (§6.1) |
| `stage/overlay.py` | leaf tags → mobjects at natural size; `fit()` (§6.2, §6.4) |
| `stage/layout.py` | sizes injected as px boxes, Chromium solves flex, boxes read back; overflow / off-stage errors per beat + id (§6.3, §7) |
| `stage/world.py` | 3D actors declared per beat: `ground`, `cube` (rot / z / `shape="sphere"` / `tint="by-light"`), `shadow` (real convex hull of the projection), `rays`; `camera` |
| `stage/scene.py` | `StageScene`: diff by id → exits, moves, morphs, enters; world + camera interpolation; hold phase (orbit drift, tumble) (§6.6, §6.7) |

## Additions beyond the spec draft

The spec put 3D and moving cameras out of scope for v1. To meet the brief
(3D, fluid camera, morphing, kinetic type, cinematic transitions), the spike adds:

- **`<world>` actors with state.** They are not laid out by flexbox. Each beat
  states where the cube is (`rot="corner"`, `shape="sphere"`, …), and the
  runner interpolates (slerp for rotation, lerp for the cube→sphere morph). The
  shadow and the readouts are *derived* from that state each frame, so they
  are always correct: the square→hexagon morph is the real projection.
- **`<camera theta phi zoom focus="hole">`.** `focus` names an overlay
  element. The camera moves in its own plane so the world target lands on that
  element's box, so the HTML layout decides where the 3D scene sits on screen
  next to the cards. `drift` adds a slow orbit during the hold.
- **`<value bind="shadow.area">`**: live numbers bound to world quantities
  (`shadow.area`, `tumble.n`, `tumble.mean`).
- **Kinetic typography**: text enters and exits word by word; `<em>` words are
  coloured and pop.
- **Morphs**: `<tex morph="match">` uses TransformMatchingTex; same id + same
  content → Transform to the new box (cards resize, the title shrinks to the
  corner).
- **Transitions**: `transition="wipe"` and `letterbox="open|close"` on a beat.

## Findings

- **Layout held up.** Chromium placed every card, caption and title; no
  overlaps in the final render, first try. A deliberately too-wide formula
  (6u inside a 4u card) is reported as
  `beat 0: #card overflows its box by 200px x 0px` and
  `#f is outside the stage: [947, 75, 600x100]`. That is the message to
  send back to Agent 3.
- **The bugs were in the animation diff, not the layout.** The first render
  left old copies of changed elements on screen. The fix was a stricter
  rule: same content → move; tex with `morph="match"` → morph; anything
  else → kinetic exit, then enter. A crossfade between two different
  sentences looked bad.
- **manimgl gotchas**: `--fps` is broken in 1.7.2 (passed as a string).
  `Transform` on a `DecimalNumber` with an updater crashes on point count;
  move its label instead. The shadow skips the depth test and relies on draw
  order to avoid z-fighting with the floor.
- **Cost**: 61 s at 1080p30 renders in ~45 s. The layout pass (one Chromium
  load for all 10 beats) takes about 1 s.
- **Authoring cost for an LLM**: the HTML is small (~130 lines for 61 s) and
  mostly ordinary flexbox. The new vocabulary is the world tags and five
  attributes (`enter/exit/emphasize/morph`, `t/hold/drift`).
  `stage/world.py` is lesson-specific (cube/shadow). A real version needs a
  general actor set (axes/graph/surface/`<manim>` escape hatch) — that is
  milestone 3.
