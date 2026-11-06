---
name: konvey-video
description: Create a 3Blue1Brown-style silent explainer video from a topic with the Konvey MCP engine. Use when the user asks for an explainer video, an animated concept explanation, or a visual essay that should become an MP4.
license: MIT
compatibility: claude-code, opencode, cursor
metadata:
  workflow: konvey-mcp
  output: silent-mp4
---

# Konvey video

Konvey turns one topic into a silent, three-scene explainer video in the 3Blue1Brown
style. **You do the thinking** — research, script, storyboard and beat HTML. Konvey supplies
the beat-DSL reference, the display catalog, exact simulations, deterministic checks, preview
stills and the renderer.

Do not write Python for the video. The scene files are HTML data; the engine lays them out
with Chromium and animates them with manimgl.

Some harnesses surface MCP tools under a namespace: opencode v2 code mode calls them as
`tools.konvey.konvey_new_run`; some clients show `konvey_konvey_new_run`; Claude Code shows
`mcp__konvey__konvey_new_run`. Look for the `konvey` namespace/server and the tool whose name
ends in `konvey_new_run`, `konvey_check`, … If unsure, search the `konvey` namespace.

## When to use this

Use it when the user asks for:

- an explainer video, animated explainer, visual explainer, or 3b1b-style video;
- a concept explained as an animated sequence rather than prose;
- a video version of a topic they are already discussing.

Do not use it for slides, static diagrams, code changes, or narrated video. v1 is **silent**:
the `vo` line drives timing and is reserved for narration later, but it is not spoken.

## Before you start

- The `konvey` MCP server must be configured (see the project's `docs/konvey-mcp.md`).
- Runs live in `<project>/.konvey/runs/<run-id>/`; tell the user this is self-ignoring.
- Default is **3 scenes, 90 seconds**. Ask about length or theme only when it matters.
- If the user asks for a short, honor it: **1–2 scenes and 3–6 beats** are fine. The 3-scene /
  8–12-beat guidance is the default, not a hard limit for a deliberate short.
- `konvey_new_run` reports the render stack. If `render_stack.missing` is non-empty, tell
  the user before doing a lot of work; preview and render will fail.

## Workflow

### 1. Create the run

```text
konvey_new_run(topic="Where do facts live in an LLM?", duration=90)
```

Keep the returned `run_id` and scene paths for every later call.

### 2. Research and compute

Use your own tools (web, files, Python, bash). Every number the viewer will see or hear must
be computed, not guessed. For a simulation, call:

```text
konvey_simulate(rule="blocks", settings='{"mass": 10000}', times="end")
```

Use those exact values; the engine will play the same run.

### 3. Write the storyboard

Write `plan.md` in the run directory (recommended for 3 scenes; optional for a 1–2 scene short):

- three acts, 8–12 beats each, one idea per beat;
- one spoken line (`vo`) per beat, 20 words or fewer;
- one picture that evolves; not a new card every line;
- Act 1 opens on a concrete case, Act 2 takes the idea into the topic, Act 3 pays it off.

### 4. Fetch only what the scene needs

```text
konvey_guide("beats")        # the beat model
konvey_guide("shots")        # full / question / derive / compare / title
konvey_displays(kind="plot") # the display(s) that draw what you need
konvey_example(kind="plot")  # one worked scene to copy the structure from
```

Copy an example's **structure and display choices**, never its topic, numbers or wording.

### 5. Write the beat HTML

Write `S1.html`, `S2.html`, `S3.html`. Each is a `<beats>` document. A beat is a full
snapshot of the screen at the end of one line; the engine diffs consecutive beats by `id`.

```html
<beats>
<beat vo="Start with one concrete case." shot="question">
  <h2 id="q">What does a dose actually do?</h2>
  <plot id="p" fn="one dose: 100*0.5^(x/2)" x="0,12" y="0,160"
        color="c1" xlabel="hours" ylabel="mg/L"></plot>
</beat>

<beat vo="Two hours later, half of it is gone." shot="full">
  <plot id="p" fn="one dose: 100*0.5^(x/2)" x="0,12" y="0,160"
        color="c1" points="half: 2,one dose" mark="x=2: 2 h"
        xlabel="hours" ylabel="mg/L"></plot>
</beat>
</beats>
```

Rules that matter:

- One `<beat>` per plan line, in order, with `vo="…"` exactly that line.
- Keep an element's `id` to change it in place; a new `id` enters, a missing `id` exits.
- Use `shot="…"` so the engine composes the screen; most beats are `full`.
- One dominant picture. Show less instead of shrinking text or adding cards.
- Colours are theme roles: `ink`, `muted`, `accent`, `c1`…`c5`. Never hex.
- Silent v1: no subtitles; do not add `<caption>` for the vo.
- Marks (`dots`, `path`, `arc`, `angle`, `brace`, `note`, `ring`, `arrow`) sit on the thing
  they mark and take no room. See `konvey_guide("marks")`.

### 6. Check

```text
konvey_check(run_id)
```

- `static`, `errors`, `warnings` come back immediately.
- The runtime layer (overflow, LaTeX, frame audit) runs as a job. If the response says
  `status="running"`, poll `konvey_status(run_id)`.
- Fix every error and every named beat. Warnings are advisory; a short scene may be fine.
- If static fails, runtime is not started. Fix the static problems first.

### 7. Preview and review

```text
konvey_preview(run_id)
```

This writes `preview/sheet.png` (one tile per beat) and `preview/index.json` (VO, seconds,
still path). **Open the sheet first.** It should read as a storyboard: each tile answers the
line under it, and the picture changes between beats.

Then open individual `S1-beat-03.png` files for weak tiles. Check:

- the thing the line names is the largest, brightest thing;
- one focal point, no overlap, nothing clipped or too small to read;
- the picture evolves instead of cutting to a new unrelated screen;
- at least one beat carries a visible mark or annotation that states the claim (an asymptote,
  a gap, a labelled point), not just an axis range that implies it.

Fix the named beat, re-run `konvey_check` and `konvey_preview`. Do not render for every small
fix.

### 8. Render

```text
konvey_render(run_id)
```

The static check gates the render. It runs as a detached job; poll `konvey_status(run_id)`
until `state` is `done` or `failed`. `preview=True` gives a 480p `video-preview.mp4` for a
quick motion check; the final render is `<run>/video.mp4`.

MCP renders at **24 fps** by default (`fps=30` is smoother, `fps=20` is a faster draft).
Most render time is transition frames, not holds: for a short/simple video, use
`t="1"`–`t="1.2"` on the beats instead of the 1.6 s default.

### 9. Deliver

Give the user:

- `<run>/video.mp4` (silent, HD);
- `preview/sheet.png` if they want to see the storyboard;
- the run directory, so they can ask for a fix later.

## Hard rules

- Default 3 scenes, 8–12 beats per scene; a requested short can be 1–2 scenes and 3–6 beats.
  One idea per beat.
- `vo` on every beat, 20 words or fewer.
- Compute or simulate every number. Never invent one.
- One dominant picture per beat; text supports the picture, it is not the picture.
- Theme colour roles only.
- No Python, no shell, no script files.
- Do not render before the preview sheet tells the story on its own.

## Recovering

| What you see | What to do |
|---|---|
| `{ok: false, error: …}` | Fix the named input; do not retry blindly. |
| `status: "running"` / `"busy"` | A job is running. Poll `konvey_status(run_id)`. |
| `status: "blocked"` from render | Static check failed. Fix it, or use `force=True` only if the user accepts the problems. |
| `state: "failed"` | Read `log_tail`; fix the named scene/beat. A render can be retried. |
| Session/agent died mid-run (provider error, timeout) | Do not call `konvey_new_run` again. List `.konvey/runs/`, reuse the existing run id, and continue with `konvey_status(run_id)` and the scene files already written. |
| `render_stack.missing` | Tell the user which piece is missing; do not keep generating. |

## More reference

`konvey_guide()` lists every section. Fetch `workflow`, `review`, `checks`, `shots`,
`camera`, `overlay`, `world`, `rules`, `themes`, `sims` or `marks` only when needed.
