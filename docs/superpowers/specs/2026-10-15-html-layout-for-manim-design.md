# HTML layout layer for Manim (Konvey) — design draft

Status: **draft for review** · 2026-10-15
Open decision: §9 (authoring format). The rest of this document assumes HTML.

## 1. Problem

Konvey's Agent 3 writes raw manimgl code and has to position every object
itself (`next_to`, `shift`, `move_to`). It cannot see the result, and it
does not know how big a `Text` or `Tex` will be until the code runs. The
consequences:

- Labels overlap other labels, or sit on curves and axes.
- Long `next_to` chains drift off the frame.
- Objects from earlier beats are never faded out and pile up.
- A `VGroup` that never calls `arrange()` stacks all its elements on one point.

These are measured, not guessed. The executed layout check on the
`layout-check` branch found them in the shipped examples:

- example-05 S2: all six `low_row` digits stacked on one point.
- example-01 S3: crashes at runtime but passes the AST validator.
- example-04 S2: the balls overlap the buckets.

Better prompting reduces these failures but cannot remove them, because the
information the model needs (real sizes, real positions) does not exist
until the code runs.

## 2. Key insight

LLMs are reliably good at HTML/CSS layout. They write flexbox and grid
layouts that do not collide, because:

- they have seen a huge amount of it, and
- the browser does the geometry; the model only states intent ("a row,
  gap 8, this takes the remaining space").

**Goal: carry that skill over to Manim.** The model writes layout in the
format it is good at; a real layout engine computes positions; Manim still
draws everything.

## 3. Goals and non-goals

Goals
- Overlaps and off-frame objects are prevented by construction for anything
  placed through the layout, not caught after the fact.
- The authoring format is one the model already knows (HTML + CSS).
- Manim keeps rendering: LaTeX, function graphs, 3D, the 3b1b look.
- Animation between beats is mostly automatic, so the model cannot forget
  to clean up.
- There is an escape hatch for custom Manim code.

Non-goals
- A fork of manimgl. Nothing in the renderer needs to change; this is a
  layer on top.
- Full CSS support. We support the subset needed for explainer layouts (§5).
- Replacing Agents 1 and 2. Agent 3's output format changes; their contracts
  stay as they are, apart from the small prompt updates in §8.

## 4. Approaches considered

| | Approach | Verdict |
|---|---|---|
| **A** | **HTML keyframes laid out by headless Chromium, rendered by Manim** | **Chosen.** Real CSS semantics: what the model learned is exactly what runs. |
| B | Same HTML, layout solved in Python by `stretchable` (Taffy flexbox/grid) | Fallback. Lighter (no browser), but partial CSS; some of the model's knowledge won't transfer. The HTML format is the same, so it can replace the browser later. |
| C | Drop Manim; render HTML directly (Remotion / Motion Canvas) | Rejected. Full knowledge transfer, but loses native LaTeX, 3D and the 3b1b look. |
| D | Keep raw Manim and add helper functions (`place()` regions) | Already shipped on `layout-check` as prevention. It helps, but the model still computes positions. |

## 5. Authoring format

Each beat is one HTML fragment: a full snapshot of what should be on screen
at the end of that beat. Standard layout elements and CSS, plus a few
custom tags for Manim content.

```html
<beat vo="Start with the bell curve, then its formula.">
  <h1 id="title">Central Limit Theorem</h1>
  <div class="row" style="gap: 0.6u; flex: 1">
    <axes id="plot" x="-3,3" y="0,1" style="flex: 1">
      <graph id="bell" fn="exp(-x^2)" color="YELLOW"></graph>
      <label for="bell" at="peak" side="up">bell curve</label>
    </axes>
    <tex id="eq" style="width: 40%">\frac{1}{\sqrt{2\pi}} e^{-x^2/2}</tex>
  </div>
  <text id="cap" enter="write">Sums of many small effects look like this.</text>
</beat>
```

Rules:
- **Units.** The stage is 14.22 × 8 Manim units, mapped to a 1422 × 800 px
  viewport (1u = 100px). The model may write px, %, or `u`.
- **Layout.** `display: flex` / `grid`, `gap`, `padding`, `flex`,
  `justify-content`, `align-items`, `width/height` (incl. %), `max-width`,
  and `position: absolute` for intentional overlays. Utility classes
  `row`, `col`, `center`, `grow` are provided in a base stylesheet.
- **Leaf tags** (become Manim mobjects):
  - `text`, `h1`–`h3`: `Text`
  - `tex`: `Tex`
  - `axes`, `graph`, `numberline`: coordinate systems and plots
  - `shape` (circle/rect/arrow/…)
  - `group`: `VGroup` of same-type children
  - `manim`: escape hatch, see §6.4
- **Anchored children.** `label for=… at=… side=…` and `arrow from=… to=…`
  are positioned relative to a point inside another element (a curve's
  peak, a bar's top), not by flexbox. They are placed after the layout pass
  and checked for collisions (§6.5).
- **Identity.** `id` is what links an object across beats. Same id means
  same object.

## 6. Architecture

```
beat HTML ──► 1. Parse ──► 2. Build mobjects ──► 3. Measure intrinsic sizes
                                                        │
          6. Animate (diff vs previous beat) ◄── 5. Fit mobjects into boxes ◄── 4. Browser layout
                    │
                    ▼
            manimgl InteractiveScene  ──►  video
```

Package: `konvey/stage/`, one unit per file:

### 6.1 Parse (`parse.py`)
Parses HTML into a typed tree (`Node(tag, id, attrs, style, children)`).
Rejects unknown tags and leaf tags without an `id`, with error messages
written for the LLM.

### 6.2 Build (`build.py`)
For each leaf node, constructs the manimgl mobject at its natural size.
This is the only place Manim objects are created.

### 6.3 Layout (`layout.py`)
Two passes so the browser knows real content sizes:

1. **Measure.** Each built mobject's natural width and height (in units)
   are written into the HTML as fixed `width`/`height` (or `aspect-ratio` +
   `max-*` for stretchable items such as `axes`).
2. **Solve.** Load the page in headless Chromium (Playwright). Read
   `getBoundingClientRect()` for every `id`. Also read overflow
   (`scrollWidth > clientWidth`) and out-of-stage boxes.

Output: `{id: Box(x, y, w, h)}` in Manim coordinates. One browser instance
is reused for a whole video; every beat in a scene is laid out on one page
load.

### 6.4 Fit (`fit.py`)
Scales each mobject uniformly to fit its box (never stretches text) and
moves it to the box center.

`<manim id=… code="…">` runs a small Python function returning a mobject.
That mobject is fitted into its box like any other, so custom visuals
cannot escape their region.

### 6.5 Anchored placement (`anchors.py`)
Places `label` / `arrow` / `brace` relative to points on already-placed
mobjects:
- tries the requested side first, then the other sides;
- picks the first position that does not overlap any box or drawn points;
- adds a background rectangle as a last resort.

It reuses the collision math from `layout_probe`.

### 6.6 Animate (`animate.py`)
Diffs beat N−1 against beat N by id:

| case | default animation | override attribute |
|---|---|---|
| id new | `FadeIn` (text: `Write`, curves/shapes: `ShowCreation`) | `enter="write|fade|grow|draw"` |
| id gone | `FadeOut` | `exit="fade|shrink|none"` |
| id moved or resized | `Transform` into the new box (FLIP-style) | `move="transform|fade"` |
| content changed, same id | `TransformMatchingTex` / `ReplacementTransform` | — |
| `emphasize` attribute | `Indicate` / `FlashAround` | `emphasize="indicate|flash|circle"` |

Exits run first, then moves, then enters, overlapping by a short lag. The
beat ends with `self.wait()` sized from the VO line, which keeps the
`layout_probe` beat contract intact. Pile-ups are impossible: anything not
in the new beat is removed.

### 6.7 Scene runner (`scene.py`)
`StageScene(InteractiveScene)` takes a list of beats and plays them. Agent
3's output becomes beat HTML; the generated `.py` file becomes a thin
wrapper:

```python
from konvey.stage import StageScene
class SingleScene(StageScene):
    beats = "agent3-S1.html"
```

so `manimgl agent3-S1.py SingleScene` keeps working.

## 7. Error handling

All errors are reported per beat and per id, in the same style as
`layout_probe`, so they can go back to Agent 3:

- **Parse errors:** unknown tag, missing id, invalid CSS value.
- **Layout errors:**
  - content overflows its container or the stage, including how much
  - box too small to fit a mobject at a readable size (text below the
    minimum height)
- **Anchor errors:** no collision-free position found for a label.
- **Build errors:** bad `fn` expression, `manim` escape-hatch exception
  (with traceback line).
- The existing repair loop (`run_coding`) is reused unchanged. Only the
  validator and probe it calls differ.

`layout_probe` stays as a final safety net. It mostly catches problems in
`manim` escape-hatch content.

## 8. Changes to Konvey

- **Agent 3 prompt:** rewritten to emit `<beat>` HTML, with the tag
  reference (§5) and 2–3 few-shot examples converted from the existing
  examples.
- **Agent 2:**
  - `layout[]` and `spatial_predicates` become optional hints;
  - its animation choices map to `enter` / `exit` / `emphasize`;
  - `code_hint` stays for escape-hatch content.
- **Validators:** `validate_manim_code` gains a sibling `validate_beats`.
- **Dependencies:** `playwright` (Chromium) in the `layout` extra.
- **Raw-Manim mode:** stays available via a flag, so old prompt sets and
  examples keep working.

## 9. Open decision: authoring format

| Option | Pros | Cons |
|---|---|---|
| **HTML** (assumed above) | Maximum transfer of what the model knows; easy to inspect in a normal browser | Escape hatch is code in an attribute; one more format in the repo |
| Python builder (`Row(Axes(...), Col(Tex(...)))`) | Mixes naturally with custom Manim code; no parser | Less of the model's web knowledge applies; it must learn our API |

Recommendation: HTML.

## 10. Testing

- **Unit:**
  - parser (valid/invalid fragments)
  - fit (aspect-preserving, never upscales text past its font size)
  - diff → animation plan (new/gone/moved/changed)
- **Layout golden tests:** fixed beat HTML produces expected boxes within
  tolerance; overflow is reported.
- **End-to-end:**
  - convert the 6 shipped examples to beat HTML;
  - run them through `StageScene` headlessly with `layout_probe`;
  - require zero errors on all of them. (Today: 2 runtime errors and 1
    stacking error.)
- **LLM eval:**
  - same prompts, raw-Manim Agent 3 vs beat-HTML Agent 3;
  - compare layout errors per scene before repair and the number of repair
    rounds needed.

## 11. Milestones

1. **Spike (throwaway):**
   - one hand-written beat sequence;
   - Chromium layout → Manim fit → diff animation;
   - render one scene and look at it.
2. Core package: parse, build, layout, fit, animate, scene runner, unit and
   golden tests.
3. Anchored labels/arrows and the escape hatch.
4. Agent 3 prompt + validator + pipeline flag; convert examples.
5. LLM eval vs raw-Manim mode; decide the default.

## 12. Risks

- **Browser dependency.**
  - Chromium adds weight and startup time; one browser is reused per run.
  - Option B (stretchable) is the fallback behind the same interface.
- **Model writing HTML that's valid but ugly.** Mitigated by the base
  stylesheet and few-shot examples. The probe still flags tiny text and
  clutter.
- **3D scenes.**
  - Flexbox lays out a 2D stage.
  - 3D content goes into a box via `<manim>`, with a fixed-in-frame overlay
    for labels.
  - Moving 3D cameras are out of scope for v1.
- **Transform quality between very different shapes.** Falls back to a
  crossfade (`move="fade"`).
