# Design: a general stage renderer — swappable themes, Editorial look, genre examples, multi-topic dev loop

Date: 2026-10-15 · Branch: `design/html-layout` · Status: draft for review
Builds on: `docs/superpowers/specs/2026-10-15-html-layout-for-manim-design.md` (approach A, beat
HTML → Chromium layout → Manim) and `docs/superpowers/handoff-2026-10-15-stage-renderer.md`.

## 1. Why

The stage renderer works end to end (`--renderer stage`, latest run `out/stage-gradient/`, 75 tests
pass), but:

- **It is overfitted.** Agent 3's only worked example (`prompts/agent3-stage/few-shot.md`) is the
  cube-shadow lesson (18 mentions of cube/shadow), and the world kit (`konvey/stage/world.py`) is
  mostly cube-specific. Videos come out "cube- or gradient-shaped".
- **The user dislikes the look and layout.** The current frames use a fixed template: 3D on the
  left, a dark card on the right, a caption pill at the bottom, letterbox bars, a flat grey/navy
  background with a yellow accent. Problems seen in `out/stage-gradient/video.mp4`: card-in-card
  clutter, a lone box in empty space for the outro, an equation drawn on the letterbox bar, and a
  kinetic caption fading into the bar.
- **Theme constants are scattered** across `overlay.py` (`ACCENT`, `INK`, `MUTED`, `CARD_*`,
  `FONT`), `scene.py` (`BG`, `BAR_OPEN`) and `world.py` (`CUBE_COLOR`, tints, `GROUND_COLOR`).

Goal: a renderer and Agent 3 prompt that produce good videos for **any** topic, in a look the user
chose, with the look swappable, developed against several unrelated topics rather than one.

## 2. Decisions made in the brainstorm (2026-10-15)

### 2.1 Look: "Editorial" dark theme, default; themes swappable

Chosen after five rounds of real Manim mockups (throwaway scripts in the job tmp dir; the
Editorial reference is class `Editorial` in `dark.py`):

| Token | Value | Use |
|---|---|---|
| `bg` | `#0B0B0C` | near-black background |
| `ink` | `#F2EDE4` | primary text, equations, ivory solids |
| `muted` | `#8C877E` | labels, secondary text, guide lines |
| `accent` | `#D4A853` | warm gold: the one thing to look at |
| heading font | `C059` (URW Century Schoolbook, serif, regular weight) | `h1`–`h3` |
| body font | `Adwaita Sans` | text, captions, labels |
| solids | matte: ivory/gold, `shading=(0.3, 0.35, 0.3)` | 3D actors |
| decoration | one faint gold ring on the floor (`stroke 1, opacity 0.25`) | optional |

A supporting palette `c1…c5` is still needed for multi-series charts and multi-object scenes; it
must stay muted and warm (gold, ivory, plus desaturated companions — e.g. sage, clay, slate blue,
dusty rose). Exact hexes are chosen during implementation by rendering the swatch sheet (§6.1) and
showing it to the user.

**Rejected** (do not reintroduce): the current navy/yellow card template; light themes (paper,
risograph, paper cutout); colour-block; infinite-canvas travel layout; a "fun" neon bouncy style;
and the dark variants Cosmic, Terminal, Synthwave, Soft dark, Blueprint. The user wants a dark
background. Those variants may exist later as extra themes but are not built now.

### 2.2 Layout: no cards, no letterbox

- Headline top-left (serif), equation directly under it, left-aligned.
- The visual (3D world, chart, grid…) owns the centre of the frame.
- Captions are plain subtitles at the bottom: body font, ink colour, no pill/box.
- No letterbox bars. `card` becomes an opt-in `panel` class for the rare case that needs a
  backdrop; it is not used by default and the examples do not use it.

### 2.3 Generalisation: genre example library (option 1)

Agent 3 sees 1–2 short worked examples chosen by the **kind of visual** the scene needs, from a
library of 4–5 genres. Rejected alternatives: no examples at all (quality drop) and a raw-Manim
escape hatch (needs a sandbox; deferred).

### 2.4 Hard rule: the example and the request are never the same topic

The user's explicit requirement. Enforced three ways:

1. **Library content:** no example may be about any topic in the test set (§2.5), any shipped
   prompt set (MLP, CLT/Galton, shadows/cube), or any earlier eval topic (Wordle, Bayes medical
   test, gradient descent, dice convolution). The cube lesson is removed from Agent 3's prompt.
2. **Selection guard:** each example declares `topic_keywords` in its front matter. The selector
   drops any example whose keywords overlap the user prompt or Agent 1/2 output (case-insensitive
   word match after stemming plurals). If that leaves a genre empty, the selector falls back to the
   next-closest genre, never to the overlapping example.
3. **Test:** a unit test runs the selector on each test-set prompt and asserts that no chosen
   example shares a keyword with it, and a lint test asserts that no example file mentions a
   test-set topic.

### 2.5 Test set: five unrelated topics

Picked from `github.com/3b1b/videos`, unrelated to each other and to existing examples; each
stresses a different kind of visual.

| # | Topic | Source | Stresses |
|---|---|---|---|
| T1 | Binary search | user's pick | algorithm: array tiles, moving pointers, step state, no formulas |
| T2 | Hamming codes | `_2020/hamming.py` | grid of bits, parity groups lighting up rows/columns |
| T3 | SIR epidemic model | `_2020/sir.py` | **chart**: S/I/R curves over time, peak, flattening |
| T4 | Hairy ball theorem | `_2026/hairy_ball` | **3D**: vector field on a sphere, the unavoidable bald spot |
| T5 | Cosmic distance ladder | `_2025/cosmic_distance` | **3D** at scale: Earth/Moon/Sun, angles, shadows |

We take only the topic from 3b1b, not code or scripts.

### 2.6 Out of scope

Mascot (deferred, not dropped), the `<manim>` escape hatch / sandbox, converting the 6 shipped
examples, and the raw-Manim vs. stage LLM eval.

## 3. Architecture

```
prompt ─► Agent 1 ─► Agent 2 (plan: scenes, objects with kinds) ─► example selector ─► Agent 3
                                                                       │ (genre examples,
                                                                       │  minus same-topic)
Agent 3 beat HTML ─► check_static ─► check_runtime (with prelude) ─► render with Theme ─► video.mp4
        ▲                    │                 │
        └──── repair loop ◄──┴─────────────────┘
```

Units and their single job:

| Unit | File | Job |
|---|---|---|
| Theme | `konvey/stage/theme.py` (new) | Dataclass of tokens; registry `THEMES = {"editorial", "classic"}`; `get_theme(name)`; colour resolution |
| Overlay/scene/world | existing `konvey/stage/*.py` | Read every colour, font and material from the active `Theme`; no module-level colour constants |
| New building blocks | `konvey/stage/overlay.py`, `konvey/stage/field.py` | General tags listed in §4.3 |
| Example library | `prompts/agent3-stage/examples/*.md` (new) | 4–5 genre examples with front matter |
| Selector | `konvey/stage/examples.py` (new) | Pick 1–2 examples per scene; apply the same-topic guard |
| Prompt | `prompts/agent3-stage/few-shot.md` → split into `reference.md` (tags, rules, stage) + injected examples | Tag reference stays one file; examples are injected per scene |
| Checker | `konvey/stage/check.py` | Runtime check runs the scene with its prelude (§4.5) |
| Dev loop | `scripts/topics.py` (new) + `topics.toml` | Generate the five videos, build a contact sheet, open it |

## 4. Components

### 4.1 Theme layer

```python
@dataclass(frozen=True)
class Theme:
    name: str
    bg: str; ink: str; muted: str; accent: str
    palette: tuple[str, ...]          # c1..c5
    heading_font: str; body_font: str; mono_font: str
    heading_weight: str               # "NORMAL" for editorial serif
    solid_shading: tuple[float, float, float]
    floor: str                        # "ring" | "none" | "plane"
    caption: str                      # "subtitle" | "pill"
    letterbox: bool
    panel_fill: str; panel_stroke: str
```

- `editorial` (default) with §2.1 values; `classic` reproduces today's look exactly so existing
  renders and tests stay comparable.
- `--theme NAME` on `run_konvey.py` and `python -m konvey.render`; the wrapper `.py` written per
  scene records the theme so re-renders are stable.
- **Colour resolution** (`theme.color(value)`): accepts semantic names (`ink`, `muted`, `accent`,
  `c1`…`c5`), CSS colour names (`red`, `blue`, …: mapped to the nearest palette entry by hue,
  fixing open issue 5), and hex (passed through, but the checker warns and suggests a semantic
  name). Agent 3's reference documents only semantic names.
- **Fonts:** C059 and Adwaita Sans are system fonts here. To make renders portable, the render
  step sets `FONTCONFIG_FILE` to a repo config that adds `render/fonts/` (fonts committed there
  only if their licence allows; C059 is URW base-35, AGPL/GPL with font exception — check before
  committing, else rely on the system package).

### 4.2 Layout defaults

- `scene.py`: letterbox only when `theme.letterbox`; `SAFE_PX` check in `layout.py` applies only
  then. Caption rendered per `theme.caption`.
- Agent 3 reference: beats use `style="padding: 0.5u 0.6u"`; the header pattern is
  `<h2>` + `<tex>` stacked top-left; the visual goes in a `grow` region; no `card` in examples.
- `check_static` rule "letterbox only S1/S3" is dropped for themes without letterbox.

### 4.3 General building blocks (each topic-free, each with a unit test)

| Tag | Purpose | Notes |
|---|---|---|
| `<array values="…" highlight="i,j" pointers="lo:0,hi:9,mid:4">` | row of cells with index labels and named pointer arrows | pointers animate between beats by id diff; cells can be dimmed (`dim="0-3"`) — T1 |
| `<grid rows cols values="…" highlight-rows highlight-cols mark="r,c">` | 2D cell grid | groups light up, one cell flagged — T2 |
| `<chart series="S:…;I:…;R:…" x="0,160" fill="stack|none">` | line/area chart from data series | colours from palette, legend inline at line ends, zero baseline — T3 |
| `<bars>` fix | negative values drawn downward from a zero baseline; value labels below negative bars | open issue 1 |
| `<sphere>`, `<solid shape="cone|cylinder|box">` | general lit 3D solids with position/size | theme material — T5 |
| `<field on="sphere" fn="…" density>` | tangent vector field on a sphere (or plane) | uses the whitelisted `parse_expr`; arrows sized by magnitude, zero shown as a marked point — T4 |
| `<label3d at="x,y,z">` | text pinned to a 3D point, kept facing the camera | T4/T5 |
| `<light dir="…">` + `<shadow of="id">` generalised | shadow of any solid onto the floor | currently cube-only — T5 |

All data-bearing tags keep the existing rule: values come verbatim from Agent 2's plan, the checker
verifies them, Agent 3 never computes data.

`schemas.OBJECT_KINDS` gains `array`, `grid`, `chart`, `solid`, `field` so Agent 2 can plan them;
Agent 2's prompt lists them with one-line meanings.

### 4.4 Example library and selector

Genres, one example each, each ~40–60 lines of beat HTML for **one scene**, each on a topic
outside §2.4's exclusion list:

| Genre | Triggered by plan kinds | Example topic (placeholder, final pick must pass the guard) |
|---|---|---|
| `world3d` | `solid`, `field`, `surface`, `point` | A helix is a circle stretched along a line: a cylinder, a curve wound on it, label3d, a camera move from top view to side view |
| `chart` | `chart`, `bars`, `graph`, `axes` | Coffee cooling (Newton's law of cooling) — one decaying curve, a marked temperature |
| `cells` | `array`, `grid`, `tiles` | Bubble sort on 6 numbers — swaps, a moving pointer |
| `diagram` | `shape`, `arrow`, `text` | How a lock-and-key cipher (Caesar shift) maps letters |
| `equation` | `tex`, `number` | Sum of the first n odd numbers is n² — tex morphs + a value |

Selector (`konvey/stage/examples.py`):

1. Collect the object kinds Agent 2 planned for the scene; score each genre by overlap.
2. Take the top genre, plus the second if it scores > 0; at most 2 examples (prompt budget).
3. Apply the same-topic guard (§2.4.2) against the user prompt + Agent 1/2 text.
4. Inject the chosen examples under `## Examples (different topics — do not copy content)` after
   the tag reference.

The reference also gains the rule for open issue 2: *when the narration describes motion or
change in the world (something moves, falls, grows, leaps), show it in the world; use a chart only
for quantities over time or comparisons.*

### 4.5 Checker covers scene continuity

`check_runtime` currently runs each scene alone and in parallel, so a crash in the carry-over from
the previous scene (`prelude_file`, `_settle_points`, `_adopt_ids`) only shows at render. Change:

- Check scenes in order; S(n) is checked with the already-accepted S(n-1) as its prelude.
- A prelude failure is fed to Agent 3 for S(n) with the prelude context in the message.
- Static checks stay parallel; only the runtime step becomes sequential.

### 4.6 Multi-topic dev loop

- `topics.toml` lists T1–T5 with a prompt each and an output dir `out/topics/<slug>/`.
- `uv run --group render --group layout python scripts/topics.py [--only T3] [--theme editorial]`
  runs the pipeline per topic (in parallel up to N=2, the model is the bottleneck), renders, then
  builds `out/topics/sheet.png`: 4 frames per video in a labelled grid, and opens it with `imv`.
  `--rerender` re-renders existing beats without calling the model.
- **Anti-overfit rule for every fix found in this loop:** a fix is either a general building block,
  a theme change, or a prompt rule. No code or prompt text may name a test topic; a lint test
  greps `konvey/` and `prompts/agent3-stage/` for the test-topic keywords and fails on a match.
- Iterate until all five render without repair-loop exhaustion and the user signs off on the
  contact sheet.

## 5. Error handling

- Unknown theme name → CLI error listing available themes.
- Unknown colour → resolved by nearest hue; if unparseable, checker error with the allowed names.
- Selector finds no example after the guard → proceed with the reference only and log it (never
  fall back to a same-topic example).
- Prelude crash in the checker → repair loop as in §4.5; after max repairs, the run fails with the
  scene id and log path (same as today's render failure).

## 6. Testing

1. **Theme swatch + golden frame:** a test renders one fixed beat per theme to PNG (low res) and
   checks it renders; the swatch sheet is for the user's eyes, not asserted pixel-exact.
2. **Unit tests per building block** (§4.3): construction, highlight/pointer diffs between beats,
   negative bars point down (`bar.get_bottom()[1] < baseline`), chart series count/colours, field
   zero marker present.
3. **Colour resolution:** `red` → palette entry, `c3` → palette[2], hex passthrough + warning.
4. **Selector:** kind→genre scoring; the same-topic guard drops overlapping examples; the lint test
   that no example mentions a test topic, and that no code/prompt names one (§4.6).
5. **Checker prelude:** a two-scene fixture where S2 only fails with S1's prelude is caught by
   `check_runtime`.
6. **Existing 75 tests** keep passing with `theme=classic` where they depend on old visuals.
7. **End-to-end:** the five topic videos (§4.6), reviewed by the user from the contact sheet.

## 7. Open issues carried in, and where they land

| Handoff issue | Resolution |
|---|---|
| 1. Negative bars drawn up | §4.3 `bars` fix |
| 2. Agent 3 drops 3D when it would teach better | §4.4 prompt rule + `world3d` example |
| 3. Checker doesn't test the prelude | §4.5 |
| 4. `<manim>` escape hatch | out of scope |
| 5. Colour names like `red` rejected | §4.1 colour resolution |
| 6. Convert 6 examples, raw-vs-stage eval | out of scope |

## 8. Implementation order

1. Theme layer + `classic` parity (tests green), then `editorial` + layout defaults; render the
   swatch and one frame, show the user.
2. Building blocks (§4.3) with unit tests; bars fix.
3. Example library + selector + guard tests; split the Agent 3 prompt.
4. Checker prelude.
5. Dev loop script; run T1–T5; iterate under the anti-overfit rule; user review.
