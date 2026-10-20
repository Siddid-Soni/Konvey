# 3b1b illustration research: why our pictures fall short

Date: 2026-10-20 · Follows `handoff-2026-10-20-render-and-fill.md`.
Sources: github.com/3b1b/videos (`_2019`–`_2026`, 218 scene files), frames from three of his
videos (colliding blocks, Taylor series, convolutions; 16 evenly spaced frames each), compared
with `out/story-render-v7/clacks-v3` (16 frames).

## 1. What his pictures do that ours don't

Seen in frames, then checked in his code (`_2019/clacks/solution1.py`, `AnalyzeCircleGeometry`):

1. **One picture, built up for minutes.** The phase-circle scene is *one* set of axes at
   `width=FRAME_WIDTH, height=FRAME_HEIGHT` (circle radius 3 of a 4-unit half-height) and about 25
   `play` calls, every one of them about *parts of that picture*: the bounce lines are drawn → coloured
   arcs between their endpoints → a count on each arc → three red dots on two lines → θ at
   the middle dot → lines to the centre and 2θ there → the arc moves onto the circle → a shaded wedge
   per hop → one wedge too many, which won't fit. His method names say what is *added to the
   picture* (`show_equal_arc_lengths`, `focus_on_three_points`, `drop_arc_for_each_hop`).
2. **Marks built from the picture's own points.** The most used idiom in his code is putting things
   at a picture's coordinates: `c2p` 943 uses in 94 files, `n2p` 758 in 86, `get_start/get_end` 922,
   `get_corner` 602, `point_from_proportion` 92. What he puts there: `Line` 1,390, `Arrow` 1,403,
   `Dot` 640 (+ `GlowDot` 228), `Brace` 491, `DashedLine` 177, `Arc` 132, `Polygon` 88, `get_graph`
   325, `get_v_line` 35. Frames: chords through the circle, numbered hit points, θ/2θ at a
   vertex, a shaded end-zone wedge, a tangent line at x=0, a dashed drop from a point to the axis, a
   shaded area with a bar at x, a diagonal circling a grid's anti-diagonal.
3. **A parameter drives the picture.** `ValueTracker` 498, `add_updater` 1,825, `always_redraw`
   267: a point slides along a curve and its tangent, drop line and readout follow.
4. **Words live inside the picture's empty space, at a fixed size.** The formulas sit in the
   top-left quadrant of the axes and the slope label sits next to the line, with an arrow to it.
   "1 kg" stays small on a big block. Old formulas are dimmed, not removed.
5. **Two linked views share one frame, both large.** Blocks along the bottom and the phase circle
   above, filling the frame between them. Never five small pictures side by side.
6. **Colour carries identity.** m₁ is red and m₂ is blue in the formula, in the axis labels and in
   the arcs.

## 2. Why our agents can't get there

This is mostly a **vocabulary** gap, not a prompting one. For the clacks phase scene the Director
wrote `<plane circle="true" angle="p:180" vectors="r:-21,0">`, which is everything `plane` can
say: arrows from the origin, the unit circle, one angle on it, lines through the origin. There is
no tag for:

| his mark | ours |
|---|---|
| a path through computed points (the bounce lines), revealed hop by hop | — |
| a dot / label at a point of the picture | `plane points` only (no styling, no reveal) |
| an arc of the circle between two points; an angle at any vertex | `plane angle` (only at the origin, only on the unit circle) |
| a shaded region (wedge, polygon, area under a curve up to x) | `plot shade` between two curves only |
| a segment / dashed drop from a point to an axis | `plot mark` (vertical line only) |
| a tangent line at x | — |
| a point sliding along a curve with its marks following | `plane angle` change only |
| formula in the picture's empty corner | words column beside the picture |

Other causes (from the handoff, still true): too many pictures per beat, labels growing with
the picture, and grid/tick clutter (his phase axes have no grid and only a few ticks).

## 3. Proposal (not started; needs your OK)

**A. Constructions on coordinate pictures (engine, general).** Any picture with coordinates
(`plane`, `plot`, `scatter`, `simview` phase, a number line) takes child marks placed in *its
own coordinates*. Coordinates are data that the Explorer computes with run_python, not
layout, so this fits the "no free geometry" rule: the renderer still places the picture.

```html
<plane id="v" x="-1.2,1.2" y="-1.2,1.2" circle="true" grid="none">
  <point id="h" at="-1,0; -0.94,-0.33; 0.71,-0.71; …" numbered="true"/>
  <path id="bounces" through="h" upto="3"/>           <!-- reveal one hop per beat -->
  <arc on="circle" from="h.2" to="h.4" label="2θ" color="c2"/>
  <angle at="h.3" from="h.2" to="h.4" label="θ"/>
  <region id="end" wedge="0,0; 1.2,0; 1.2,0.4" label="End zone" color="good"/>
</plane>
```

Marks keep their ids across beats, so a beat that adds one plays as a single step (his
`focus_on_three_points`). Text stays a fixed size when the picture grows. A `place="inside"` option
puts a formula or readout in the picture's emptiest quadrant.

**B. Demo before any model run**. Hand-written beats copying three of his
frames from different topics: the phase circle step by step, the Taylor tangent and parabola on
`cos x`, and one non-geometry frame (the anti-diagonal circled on a product grid). Rendered and
shown next to his frames.

**C. Agents.** The planner lists, per beat, the one thing *added to the main picture* (a
construction step), with points from the Explorer's numbers. The Director copies it and checks
that every mark's points exist in the picture. Hard checks: at most two pictures per beat, and
every construction refers to existing points.

**D. Measure.** The layout bench plus a frame-by-frame sheet against his video on two or three of
his topics, and a held-out topic so we don't tune to his.

## 4. Placement and spacing (round 2, 15 videos)

Sampled 12 frames each from 12 more videos (eigenvectors, Fourier series, Bayes, neural networks,
gradient descent, Hamming codes, factorial/gamma, Basel, attention, epidemics, normal distribution,
Hilbert curves). What repeats across topics, and what the engine now does about it:

| his habit | evidence | engine |
|---|---|---|
| axes run edge to edge; the picture *is* the frame | clacks, Taylor, eigen, Fourier, gamma | a lone `plane` takes spare room and its range grows to the box (`_fill`, `layout.REDRAW`/`STRETCH`) |
| text keeps its size as pictures grow | all | planes are rebuilt at their box size; marks are drawn after layout |
| a short note in open space, thin arrow to the exact point ("Slope =", "Prior", "Remember this", "0.3", "Bias") | nearly every video; `Arrow` 1,403, `buff=0.1` most common | `<note on at text>` / `<note to text>` |
| braces on a picture's own stretch (triangle sides, "784 {", "P(E∣H) {") | Basel, NN, Bayes, Fourier | `<brace on from to label>` |
| region names at the region's far end, in its colour | clacks End zone | `path closed` label placed in the farthest corner that fits |
| words over grids with a dark backstroke, not pushed away by them | eigen, Fourier (`set_backstroke` 329, `BackgroundRectangle` 191) | faint lines no longer count as obstacles; labels have a halo |
| gaps: 0.1 small, 0.25 beside a thing, corners via `to_corner` | `buff=SMALL_BUFF` 739, `MED_SMALL_BUFF` 374 | `of=` gap 0.25; inside corners 0.2 |
| text sizes: 36 body, 60–72 big, 24–30 labels | `font_size=` counts | mark labels 28–32, notes 32 |

Not done yet: number-line sliders with a marker (Fourier t, epidemic factor, Basel 0.744), a
coloured "main object" (his circle is yellow), the grid display growing into spare room.

## 5. Round 3 (27 videos)

Added Wordle, calculus, determinants, dot product, zeta, Hanoi, sphere area, Newton's fractal,
Gaussian-integer primes, chain rule, backprop, medical-test Bayes. New recurring idioms:

| his habit | engine |
|---|---|
| number lines with a triangle marker and its name, sliding; stacked lines with an arrow per step (chain rule, Hilbert, primes, epidemic sliders, Fourier t) | `<numberline x markers>`: spans its column at a fixed height, rebuilt at its width; has coordinates (marks go on it) and parts (`nl>x`, `nl>x=1.5`) |
| one label, several arrows ("Already Gaussian primes", "2πr dr") | `<note at="a; b; c">` / `to="p; q"`; arrows stop at a target's own name |
| braces / boxes on formula terms ("Inner/Outer", "Complex conjugate") | already there: `brace of="eq>\cos(x^2)"`, `ring of="eq>…"` |
| labels never on a line | arrow labels avoid their own arrow (dark outline), mark labels stay inside the frame with a second, farther ring of spots; picture braces step out past the picture's numbers |

Seen but not built: split screen with a divider and two headings (Probability | Odds); Riemann
strips / area pieces (calculus, product rule square); picture-in-picture insets.

## 6. Agent runs (planner + Director, 2026-10-20)

Marks are plan kinds now (`dots`, `path`, `arc`, `angle_mark`, `note`, `brace`, `numberline`; data =
the tag's attributes, checked verbatim), with Director docs, two neutral examples (`constructions`,
`number-lines`) and one planner rule ("build the main picture up, one mark per line").
Planner re-run (deepseek, saved scripts) + Director (haiku) on three topics, silent 480p previews:

| run | marks the planner/Director used | result |
|---|---|---|
| `out/story-render-v7/taylor-marks2` | 24 notes, 11 dots, 6 braces, 1 path | clearly better: notes point at the exact term/point, braces on plots |
| `out/story-render-v7/overhang-marks2` | 11 number lines, 6 dots, 5 notes, 1 brace | number line at the end has crowded dot labels |
| `out/story-render-v7/clacks-marks` | 6 arcs, 1 note | little change: the phase picture is still a sim view; planner did not build it up |

Bugs found by the runs and fixed: scene-wide check compared only the first tag; `>>` in part refs;
comma labels; a `<draw>`'s own `<arc>` collected as a page leaf; `draw` has coordinates now; dots
have parts; renders drop an unresolvable mark/camera ref instead of failing. Two Director errors
hand-fixed (`HAND-EDITS.txt`). Cost $0.85 (planner $0.29, Directors $0.56).
