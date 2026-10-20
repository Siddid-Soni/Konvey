# Spike C: render the explainer straight from React (Remotion + three.js)

Approach C from `docs/superpowers/specs/2026-10-15-html-layout-for-manim-design.md` §4: no Manim.
The lesson in `../STORYBOARD.md` ("The average shadow of a cube") is rendered as React and
captured frame by frame by headless Chromium. The output is `out/cube-shadow.mp4` (1920×1080, 30 fps,
56 s, 1680 frames, h264).

## Render

```bash
bun install                        # or npm install
bun run test                       # math checks (hull area = |ux|+|uy|+|uz| = ½Σ|cos θ|, tumble mean, Cauchy)
bun run render                     # -> out/cube-shadow.mp4
./stills.sh 400 860 1500           # bundle once, then single frames -> out/stills/f<frame>.png
bun run studio                     # live preview with a scrubber
```

The render command is
`remotion render src/index.ts CubeShadow out/cube-shadow.mp4 --browser-executable=/usr/bin/chromium --gl=angle`.
The system Chromium (152) worked as is: Remotion did not download chrome-headless-shell, and
`--gl=angle` gave working WebGL on the first try, so swangle, swiftshader and egl were never needed.

**Render time** (20-core machine, Remotion's default concurrency of 8 tabs): **2 min 57 s** for 1680 frames,
about 9.5 frames per second, plus about 10 s to bundle. Once the bundle exists, one still takes about 2 s.
The output is 54 MB at the default CRF 18; add `--crf=23` for a smaller file.

## Layout

| File | Role |
|---|---|
| `src/storyboard.ts` | **The only per-video file.** Plain data: beats with times, captions, cards (heading, TeX, live readouts, chart), centre formulas, and `world` keyframes for the 3D state. |
| `src/math/geometry.ts` | Pure math with no three.js: quaternions, the convex hull, cube faces, seeded uniform random rotations (Shoemake), the cube→sphere morph, surface area, and the mean shadow over a Fibonacci sphere of directions. |
| `src/timeline.ts` | Turns the storyboard into `worldAt(frame)`, a pure function from time to state. It eases the keyframe tracks, slerps poses, integrates orbit and spin, and runs the tumble sampler. It also computes every readout from the same geometry that gets drawn. |
| `src/components/World3D.tsx` | Draws the scene with react-three-fiber: the cube or morphing solid, the shadow polygon, light rays that stop where they hit the solid, and the face projections that drop onto the floor. |
| `src/components/Overlays.tsx`, `Tex.tsx` | Kinetic title, captions, cards with live readouts, the running-mean chart, the centre formula morph and the letterbox. KaTeX formulas are fitted to a width that is measured in the browser. |
| `src/Video.tsx` | Derives the scenes from the beats and joins them with `TransitionSeries`: a `wipe` into the payoff and an `iris` into the sphere scene. |

### How every effect is tied to the math
- **Shadow** is the convex hull of the projected vertices, recomputed every frame. That makes the square→hexagon change a true morph, and the morphing solid uses all 1,734 vertices of its mesh.
- **"shadow area" readout** is |u_x|+|u_y|+|u_z| with u = Rᵀẑ for the pose being drawn. The "why" card also shows Σ over up faces, Σ over down faces, ½Σ, and the shoelace area of the drawn polygon. All four stay equal while the cube drifts to a generic pose.
- **"Tilted copies"**: each face's quad slides from the cube down to its actual floor projection. A dolly zoom to a near-orthographic top view (fov 34°→14°, distance 6→15) then shows the three up faces sitting exactly on their rhombi.
- **Tumble** uses 5,000 seeded uniform random rotations. The mean is 1.478 after 10 samples and 1.498 after 5,000, and the chart plots the real running mean on a log-n axis.
- **Cube→sphere** interpolates each vertex: p·(1−t + t·R/|p|), with R chosen so the sphere's surface area is 6. Both live readouts are computed from the mesh: S/4, and the mean shadow over 256 directions. They agree all through the morph (1.50 → 1.42 → 1.50), which is Cauchy's formula checked numerically, not merely asserted.
- **Light rays** use a slab test or a ray–sphere test, so they end on the solid. The shadow is visibly where the rays are blocked.

## Frame check (frames pulled from the mp4 with ffmpeg, one or more per beat)
- The first full render had a real bug: half of each cube's faces were back-face culled because their triangle winding faced inward. Light-blue edges, black interiors. Fixed in `cubeSurfaceGrid`.
- The "Why?" card formula ran past the card border. Fixed by `Tex maxWidth`, which measures in the browser and scales to fit.
- `interpolate()` throws on `Infinity` in its input range, and that crashed two stills. Fixed.
- The "why" beat at a 68° camera made the three floor rhombi look like a second cube (the classic isometric illusion). Fixed with the near-orthographic top-down dolly.
- After the fixes, no text overlaps in any beat. The title stays top-left, the card is right, the caption sits above the letterbox, and the 3D is framed left of the card using `camera.setViewOffset`. The shadow matches the cube in every pose checked (square 1.00, hexagon 1.73, generic polygons, the rounded morph, the disk). The KaTeX output is crisp, and the letterbox, wipe and iris all render.
- Known cosmetic issues: the closing letterbox clips the small title in the last 0.5 s, which is by design. The mid-morph solid shows a crease at the old cube edges; that crease is real geometry of the lerped surface. The light rays read a bit like rain.

## What worked
- **WebGL headless with no fuss.** System Chromium plus `--gl=angle` worked first time, with 3D, antialiasing and thick lines (`LineSegments2`).
- **Deterministic per-frame state.** `worldAt(frame)` is a pure function, so parallel tabs and random frame access just work, and the same function feeds both the drawing and the readouts. The math has unit tests (`bun test`, 408 assertions).
- **Layout is the browser's.** Flexbox, text wrapping, fit-to-width math and tabular numbers behaved as expected the first time. The only layout bug (the formula overflow) was easy to see and fixed with one measured scale.
- **KaTeX** renders fast and looks clean at 1080p. It is real TeX layout with KaTeX fonts, but it is not a LaTeX engine.
- **Transitions** from `@remotion/transitions` (wipe, iris) took one line each.
- Iteration is quick: a 2 s still per frame after a 10 s bundle, and the studio has a scrubber.

## What was painful
- **No equation morphing.** There is no `TransformMatchingTex`: the payoff "morph" is a crossfade with slide and blur between full equations. A real glyph morph would need per-glyph DOM measurement and FLIP animation, and that is a project of its own.
- **three.js boilerplate.** Thick lines (`LineSegments2`, resolution, depthTest), per-face material groups, triangle winding, a y-up vs z-up wrapper group, fog that scales with camera distance, and manual camera rigging with `setViewOffset`. None of it is hard, but an LLM would get the winding, normals and line resolution wrong often, and those failures are silent.
- **Silent visual failures.** Missing faces and the illusory "second cube" raised no errors, and only reading frames caught them. A vision-check loop is mandatory for this approach.
- **Shader-based transitions** (cross-zoom, zoom-blur, film-burn) depend on an experimental HTML-in-canvas path. I used the DOM-based ones only.
- Remotion's `interpolate` is strict about its inputs: no `Infinity`, and ranges must be monotonic. The errors are clear, but they abort the render.

## Notes for the A-vs-C comparison
| | Spike C (Remotion) |
|---|---|
| **LaTeX quality** | KaTeX is good and crisp, close to TeX Computer Modern, but it covers only a subset of LaTeX and has no TikZ, no `align`-heavy derivations and no glyph-level morphing between equations. Manim's MathTex with TransformMatchingTex is clearly better for derivation beats. |
| **3D quality** | Better than Manim CE's Cairo 3D, on par with or above ManimGL: real PBR lighting, MSAA, transparency, fog, smooth 1.7k-vertex morphs, dolly zoom. The cost is that the author writes three.js. |
| **Layout reliability** | The strongest point. It is real CSS, so text, cards and captions never overlapped once laid out, and a fit-to-width primitive covers formula overflow. This is the problem spike A tries to solve by borrowing Chromium. C gets it natively, but only for the 2D overlay. 3D framing (where the cube lands on screen) is still camera math. |
| **How an LLM would author it** | Split it in two. **Easy:** `storyboard.ts` is plain typed data (beats, captions, TeX strings, card readouts, keyframes such as `{at: 0.4, dur: 3.6, pose: "cornerOn"}`), and an LLM can write that reliably. TypeScript catches typos in readout or pose names, and the keyframe "ease from the current value" model is forgiving. **Hard:** anything new, such as a new 3D primitive, a new live quantity or a new chart, means writing React and three.js code with silent failure modes. The realistic setup is a fixed component library with the LLM writing only the storyboard. Each new lesson type then needs a human or agent to extend the library, and that is roughly the same trade-off as spike A's HTML-to-Manim mapping. |
| **Render speed** | 2:57 for 56 s of 1080p30 (about 3.2× real time) with WebGL and 8 tabs. Most of the time is Chromium screenshots and encoding. Expect this to be comparable to or faster than Manim CE with OpenGL, and much faster than Cairo 3D. |
| **Licensing** | Remotion is **not** OSI open source. Its Remotion License is free for individuals, non-profits and for-profit organisations with up to 3 employees. Larger companies need a paid Company License (per-seat or per-render pricing), and automated, server-side rendering at scale falls under that too. Check `remotion.dev/license` before Konvey depends on it commercially. three.js, react-three-fiber and KaTeX are MIT. Manim (MIT) has no such constraint. |
| **Look** | Cinematic motion graphics (kinetic type, transitions, letterbox) come out naturally. It does not look like 3b1b. |

**Bottom line:** C is the strongest option for layout, 3D and cinematic polish, and it is pleasant to iterate on.
It loses on derivation-style math (no TeX morphs) and on licensing. An LLM can author it only through
a fixed component library plus a data storyboard. Spike A keeps Manim's TeX animation and gets
CSS layout for the 2D part, which targets exactly the gap C leaves open.
