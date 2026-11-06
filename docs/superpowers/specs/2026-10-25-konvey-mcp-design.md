# Konvey MCP — an explainer-video engine for coding harnesses

Date: 2026-10-25 · Status: implemented (phases 1–3); phase 4 pending · Scope: v1

Implementation status (2026-10-25): run directories, engine wrappers, per-beat stills, the
job runner, the 10-tool MCP server, the Agent Skill and the install docs are in place. Tests:
the MCP suite (66 tests) passes; the full repo suite is 504 passed, 3 skipped, with the one
pre-existing `test_resolve_model_opencode_gemini` failure. A real 1-scene plot+formula run
passed check, preview and a 480p render, and the server was exercised over stdio with the MCP
client. Phase 4 is done too: a real opencode v2 session loaded the skill, saw the tools under
`tools.konvey.*`, created a 1-scene/3-beat run, and passed check + preview (no render). Its
only failure was a free-model upstream drop, recovered with `--continue`; the skill/docs were
updated for short runs, harness namespaces and session recovery. The MCP render path now
defaults to 24 fps (scene wrappers record `default_camera_config`), and shorter beat
transitions trade expensive transition frames for cheap holds: the 14.6 s HD test went from
23 s (30 fps, `t=1.6`) to 19 s (24 fps) to 16–17 s (24 fps, `t=1`).

## 1. Goal

Make Konvey usable from any MCP-capable coding harness (Claude Code, opencode, Cursor, …) as a
**video engine**, not as a second agent stack.

The harness model does the thinking: it researches the topic with its own tools, writes the
script, plans the scenes, and writes the beat HTML. Konvey supplies what the harness cannot do
locally: the beat DSL reference, the display catalog, the exact simulation numbers, deterministic
checks, Chromium/manimgl layout, preview stills, and the final silent MP4.

The user's decisions for v1:

| Decision | Choice |
|---|---|
| What it explains | any topic, like today's CLI |
| Who does the thinking | the harness model (Explorer + Writer + Planner + Director roles) |
| Packaging | one universal MCP server + one Agent Skill |
| v1 output | silent MP4 (no narration/TTS) |
| Render host | local Konvey checkout + GPU |
| Workflow | storyboard/preview first, render on approval |
| Konvey agents in the MCP | none (engine only) |
| Run artifacts | project-local `.konvey/runs/<slug>/` |
| Preview | per-beat stills + labelled contact sheet |
| DSL knowledge | concise skill + on-demand docs via tools |

## 2. Non-goals for v1

- No Explorer/Writer/Planner/Director agents behind the MCP; no API keys.
- No narration, voice prompts, DramaBox, or TTS.
- No remote render service or mayu queue.
- No codebase/PR-specific mode (the engine is topic-agnostic; the harness can choose a code topic).
- No harness-specific plugin packaging (Claude Code plugin, opencode TS plugin). The MCP + Skill
  is the shared core; plugins can wrap it later.
- No arbitrary number of scenes. v1 supports 1–3 scenes, default 3, matching the engine's
  validated 3-scene path.

## 3. Architecture

```text
Claude Code / opencode / Cursor
  ├─ Agent Skill  skills/konvey-video/SKILL.md
  │    when to use + the review loop + the rules that must not be missed
  └─ MCP client
        │ stdio
        ▼
  konvey-mcp  (Python, konvey/mcp/)
    ├─ server.py    FastMCP tool definitions + JSON-safe responses
    ├─ runs.py      .konvey/runs/<slug>/run.json, scene resolution, engine wrappers
    ├─ docs.py      guide / display catalog / examples / simulations
    ├─ preview.py   per-beat stills + contact sheet (StageScene subclass)
    ├─ jobs.py      detached jobs, status, cancel, log tails
    └─ worker.py    python -m konvey.mcp.worker <kind> <run_dir> ...
        │
        ├─ konvey.stage.check      static checks + runtime layout/audit
        ├─ konvey.stage.scene      StageScene (unchanged; stills via subclass)
        ├─ konvey.render           manimgl per scene + ffmpeg concat
        └─ konvey.story_sim        exact simulation values
```

The engine is imported from the checkout. No engine behaviour changes are required: the MCP writes
its own scene wrappers, calls `check_static` / `check_runtime` / `render_scene` / `concat`, and
captures stills by overriding `StageScene._hold`.

## 4. Run directory

Everything the MCP creates lives under the workspace:

```text
<workspace>/.konvey/
  .gitignore                 # "runs/" — self-ignoring, never edits the project's .gitignore
  runs/<slug>/
    run.json                 # topic, theme, duration, scenes, status, latest job, artifacts
    plan.md                  # optional: the harness's 3-act storyboard
    S1.html                  # harness-owned beat HTML (S2, S3 likewise)
    S2.html
    S3.html
    .engine/                 # regenerated on every check/preview/render
      agent3-S1.html         # copy of S1.html
      agent3-S1.py           # StageScene wrapper with theme + previous-scene prelude
      agent3-S2.html/.py
      agent3-S3.html/.py
      video/S1.mp4 ...
      video.mp4              # joined
    preview/
      sheet.png              # labelled contact sheet, one tile per beat
      S1-beat-03.png ...
      index.json             # scene, beat, vo, t/hold, estimate, still path
    jobs/
      <job-id>.json          # state, pid, timestamps, result, artifacts, error
      <job-id>.log
    video.mp4                # final deliverable (silent, HD)
    video-preview.mp4        # optional 480p preview render
```

`run.json`:

```json
{
  "id": "2026-10-25-where-facts-live",
  "topic": "Where do facts live in an LLM?",
  "created_at": "2026-10-25T12:00:00Z",
  "updated_at": "2026-10-25T12:00:00Z",
  "scene_count": 3,
  "duration_sec": 90,
  "theme": "editorial",
  "highlight": null,
  "status": "draft",
  "scenes": [
    {"id": "S1", "file": "S1.html"},
    {"id": "S2", "file": "S2.html"},
    {"id": "S3", "file": "S3.html"}
  ],
  "active_job": null,
  "artifacts": {}
}
```

The harness edits `S1.html` … directly with its normal file tools. The MCP never overwrites them.

## 5. Tool surface

Ten tools, all returning JSON-safe dicts. Heavy work runs as a detached job; a tool waits up to
`wait_seconds` and then returns `{status: "running", job_id}`. The skill polls `konvey_status`.
This matters because opencode's local-MCP timeout defaults to 30 s.

### 5.1 `konvey_new_run`

```python
konvey_new_run(
    topic: str,
    workspace: str | None = None,     # default: KONVEY_WORKSPACE, else server cwd
    scenes: int = 3,                  # v1: 1..3
    duration: float = 90.0,
    theme: str = "editorial",
    highlight: str | None = None,
    slug: str | None = None,
) -> dict
```

Creates `.konvey/.gitignore`, the run directory, `run.json`, and empty `S1.html` … scenes with
`<beats>\n</beats>`. Validates the theme with `konvey.stage.theme.get_theme` and the highlight
with `use()` before any model work. Returns the run id, directory, scene file paths, and the
suggested next step (`konvey_guide("workflow")`).

### 5.2 `konvey_guide`

```python
konvey_guide(section: str | None = None) -> str
```

No argument: a compact list of section names. With a section: that section of the Director
reference, read from `prompts/agent3-stage/reference.md` and split by headings. MCP-specific
sections (`workflow`, `review`, `checks`) are authored in `konvey/mcp/docs.py`. Sections:
`workflow`, `beats`, `stage`, `shots`, `world`, `camera`, `marks`, `themes`, `sims`, `checks`,
`review`, `all`.

This is progressive disclosure: the skill carries only the workflow and the hard rules; the full
director reference is fetched when the harness writes beats.

### 5.3 `konvey_displays`

```python
konvey_displays(tag: str | None = None, kind: str | None = None) -> dict
```

- No filter: a compact catalog `[{tag, kind, summary, min_size, aliases}]` for every display,
  built from `all_displays()` plus each `agent3.md`'s first line.
- `tag`: the full `agent3.md` for that display (attributes, rules, examples).
- `kind`: every display that draws that plan kind.

Each entry also names one or two examples that use it, so the harness knows what to copy.

### 5.4 `konvey_example`

```python
konvey_example(name: str | None = None, kind: str | None = None,
               genre: str | None = None) -> dict
```

No argument: the example index (`name`, `genre`, `kinds`, `fits`). Otherwise one worked scene from
`prompts/agent3-stage/examples/`. The response repeats the rule: copy the structure, never the
topic or its numbers.

### 5.5 `konvey_simulate`

```python
konvey_simulate(rule: str | None = None, settings: str = "{}",
                times: str = "end") -> str
```

No rule: the rule list and the setting reference from `konvey.story_sim.simulate`'s docstring.
With a rule: the exact numbers the `<sim>` / `<simview>` displays will play, via
`konvey.story_sim.simulate`. The harness must use this for every number that appears inside a
simulation.

### 5.6 `konvey_check`

```python
konvey_check(run_id: str, scenes: list[str] | None = None,
             runtime: bool = True, wait_seconds: float = 20) -> dict
```

Static layer (synchronous, always run):

- `check_static(html, scene)` from `konvey.stage.check`: parse, minimum sizes, theme colours,
  letterbox placement, point/curve rules, display-specific scene checks.
- MCP rules: every beat has a non-empty `vo`; 3–15 beats per scene; estimated duration within
  0.6–1.5× the target; no `TODO`/placeholder text; all expected scene files exist; the scene count
  matches `run.json`.
- A lightweight plan check when `plan.md` exists: every planned line appears as a `<beat vo="…">`.
  This is optional and never blocks a run.

Runtime layer (job): `check_runtime(html, workdir, sid, prelude_html=previous_scene_html)` with
the theme set, which plays the scene headless and returns layout/overflow/LaTeX/frame-audit
problems, already renumbered for the scene's own beats.

Returns `{ok, status, job_id?, scenes: [{id, ok, static: [...], mcp: [...], runtime: [...]}]}`.
`wait_seconds=0` returns immediately with a job id.

### 5.7 `konvey_preview`

```python
konvey_preview(run_id: str, scenes: list[str] | None = None,
               wait_seconds: float = 25) -> dict
```

Renders one PNG at the end of every beat (native 1422×800 stage resolution) and a labelled contact
sheet. Implementation: `konvey/mcp/preview.py` runs a `StageScene` subclass in a subprocess; the
subclass overrides `_hold` to call `update_frame(force_draw=True)` and save `get_image()` after
each beat. This uses the engine's own layout/animations exactly as the video does, but without
encoding frames.

Writes `preview/S1-beat-03.png` … and `preview/sheet.png` (PIL: one tile per beat, labelled
`S1 b03 · 4.2s`, with the VO line wrapped underneath). `preview/index.json` maps every still to
its beat attributes and estimated duration.

Returns `{status, job_id?, ok, sheet, scenes: [{id, stills: [...], problems: [...]}]}`. A scene
that fails still returns the stills produced before the failure plus the engine's problems.

### 5.8 `konvey_render`

```python
konvey_render(run_id: str, scenes: list[str] | None = None,
              preview: bool = False, wait_seconds: float = 0) -> dict
```

Regenerates `.engine/` wrappers, renders the requested scenes in parallel
(`KONVEY_RENDER_JOBS`, default 3) with `konvey.render.render_scene`, joins them with
`konvey.render.concat`, and copies the result to `<run>/video.mp4` (or `video-preview.mp4` for a
480p render). Scene continuity uses each wrapper's `prelude_file`, so a subset still opens on the
previous scene's last frame.

Always a detached job by default (`wait_seconds=0`). The worker updates `run.json` on start and
finish, writes `jobs/<id>.log`, and records artifacts and elapsed time. A second render of a run
with a live job is rejected.

### 5.9 `konvey_status`

```python
konvey_status(run_id: str, job_id: str | None = None) -> dict
```

The source of truth for polling and recovery. Reads `run.json` and `jobs/`, checks whether the
worker pid is alive, reconciles a dead worker to `failed`, and returns:

```json
{
  "run_id": "...",
  "status": "draft|checked|previewed|rendering|done|failed",
  "job": {"id": "...", "kind": "render", "state": "running", "elapsed_sec": 42},
  "artifacts": {"video": "...", "sheet": "...", "stills": 31},
  "log_tail": ["...last 40 lines..."],
  "scenes": [{"id": "S1", "ok": true, "problems": 0}]
}
```

State is on disk, so an MCP restart does not lose a running render.

### 5.10 `konvey_cancel`

```python
konvey_cancel(run_id: str, job_id: str | None = None) -> dict
```

Sends `SIGTERM` to the job's process group, then `SIGKILL` after 5 s, marks the job `cancelled`,
and leaves any partial artifacts in place.

## 6. Workflow the skill teaches

```text
user: "make an explainer about X"
 1. konvey_new_run(topic=X, duration=90)              → .konvey/runs/<slug>/
 2. research X with the harness's own tools           → notes + computed numbers
 3. write plan.md: 3 acts, 8–12 beats each, one VO line per beat, one evolving picture
 4. konvey_guide("workflow"|"beats"|"shots")
    konvey_displays() / konvey_displays(tag)
    konvey_example(kind=...)                          → copy structure, not content
    konvey_simulate(rule, settings, times)            → exact simulation numbers
 5. write S1.html … S3.html (beat HTML only, no Python)
 6. konvey_check(run_id)                              → fix static + runtime problems
 7. konvey_preview(run_id)                            → look at sheet.png + per-beat stills
    fix weak beats, re-check, re-preview              → repeat until approved
 8. konvey_render(run_id)                             → poll konvey_status
 9. deliver <run>/video.mp4
```

Gate: no render until the preview stills look right. The skill must inspect the sheet, not just
trust the checks.

## 7. Skill

`skills/konvey-video/SKILL.md` (Agent Skills format: `name`, `description`, optional `license`,
`compatibility`, `metadata`). Name `konvey-video`, matching its folder. It contains:

- **When to use / not use** — an explainer video or animated visual explanation is requested;
  not for slides, static diagrams, or code changes.
- **The workflow above**, including the preview gate.
- **Hard rules** — one idea and one VO line per beat; 8–12 beats per scene; ≤ ~20 words per VO;
  one dominant picture that evolves; numbers computed or simulated, never invented; theme colour
  roles, never hex; no subtitles in silent v1; do not write Python.
- **Minimal beat template** and a pointer to `konvey_example` for full scenes.
- **Recovery** — if a tool returns `status: "running"`, poll `konvey_status`; if a job fails, read
  `log_tail` and fix the named beat, not the whole scene.
- **Deliverable** — path to `video.mp4`, plus the preview sheet if the user wants to review.

Installation is documented for Claude Code (`~/.claude/skills/konvey-video/` or
`.claude/skills/`), opencode (`.opencode/skills/` or `~/.config/opencode/skills/`, and the
Claude-compatible paths opencode also reads), and generic Agent Skills (`.agents/skills/`).
A symlink from the checkout is enough; no copy step is required.

## 8. Engine reuse and new code

New files, no edits to the existing pipeline:

| File | Purpose |
|---|---|
| `konvey/mcp/__init__.py` | package marker |
| `konvey/mcp/server.py` | FastMCP server, tool wrappers, `main()` |
| `konvey/mcp/runs.py` | run/topic slugs, `run.json`, scene resolution, `.engine/` wrappers |
| `konvey/mcp/docs.py` | guide sections, display catalog, example index, simulation passthrough |
| `konvey/mcp/preview.py` | still-capturing `StageScene` subclass, contact sheet, index |
| `konvey/mcp/jobs.py` | detached process jobs, status reconciliation, cancel |
| `konvey/mcp/worker.py` | `python -m konvey.mcp.worker check|preview|render <run>` |
| `skills/konvey-video/SKILL.md` | the universal skill |
| `docs/konvey-mcp.md` | install + config for Claude Code, opencode, Cursor |
| `tests/test_mcp_runs.py` | slugs, run.json, wrappers, path safety |
| `tests/test_mcp_docs.py` | guide sections, catalog, examples, simulations |
| `tests/test_mcp_jobs.py` | job state machine, dead-worker reconciliation, cancel |
| `tests/test_mcp_preview.py` | still hook + sheet (skips without manimgl) |
| `tests/test_mcp_server.py` | tool handlers called directly (no stdio) |

`pyproject.toml` additions:

```toml
[project.scripts]
konvey-mcp = "konvey.mcp.server:main"

[dependency-groups]
mcp = ["mcp>=1.2"]
```

Run from the checkout:

```bash
uv run --group mcp --group render --group layout konvey-mcp
```

The server uses `KONVEY_WORKSPACE` if set, else the process cwd, as the workspace for `.konvey/`.
It always imports the engine from its own checkout; run artifacts can live in any project.

## 9. Job model

- One active job per run. `run.json.active_job` is the lock; `konvey_render` refuses a second
  render while the pid is alive.
- Jobs are detached (`start_new_session=True`) and survive the MCP server process. State lives in
  `jobs/<id>.json`; the worker is the only writer of its own job file.
- Atomic writes: JSON to a temp file, then `os.replace`.
- `konvey_status` reconciles: if the state is `running` and the pid is gone, mark `failed` with
  the log tail.
- `wait_seconds` polling: 0.5 s interval. A timed-out wait is not a failure; it returns
  `status: "running"`.
- Logs capture stdout/stderr; the last 40 lines are returned by `konvey_status`.

## 10. Errors, safety, limits

- Expected errors return `{ok: false, error: "..."}`; unexpected errors return a clear message and
  a short traceback tail, and are logged. No stack traces in stdout (stdio protocol).
- Run ids and scene ids are validated (`^[a-z0-9][a-z0-9-]{0,63}$`, `^S[1-9][0-9]*$`). Scene paths
  must resolve inside the run directory.
- The MCP writes only under `<workspace>/.konvey/`. It never edits `S*.html` or the project.
- No user-controlled shell strings; subprocess args are lists.
- v1 cap: 3 scenes, 90 s default, 15 beats per scene. Larger runs are a follow-up.
- Rendering needs manimgl + Chromium + LaTeX + ffmpeg; preview stills need manimgl + Chromium.
  The skill and docs say so, and `konvey_new_run` reports a missing-render-stack hint rather than
  failing late.

## 11. Install and config

Claude Code `.mcp.json` (project or user scope):

```json
{
  "mcpServers": {
    "konvey": {
      "command": "uv",
      "args": [
        "run", "--project", "/path/to/Konvey",
        "--group", "mcp", "--group", "render", "--group", "layout",
        "konvey-mcp"
      ],
      "env": {"KONVEY_WORKSPACE": "/path/to/the/project"}
    }
  }
}
```

opencode `opencode.json` (note the long tool timeout, because preview/render are jobs and
`konvey_check` can run the runtime check):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "konvey": {
      "type": "local",
      "command": [
        "uv", "run", "--project", "/path/to/Konvey",
        "--group", "mcp", "--group", "render", "--group", "layout",
        "konvey-mcp"
      ],
      "environment": {"KONVEY_WORKSPACE": "/path/to/the/project"},
      "enabled": true,
      "timeout": 600000
    }
  }
}
```

Skill install: symlink `skills/konvey-video` into the harness's skills directory. The docs list
the paths for each harness.

## 12. Testing

- Unit: `runs.py` (slug collision, path safety, run.json round-trip, wrapper prelude chain),
  `docs.py` (every reference heading has a section; every display has a summary; examples load),
  `jobs.py` (queued → running → done, dead worker → failed, cancel), `server.py` (tool handlers).
- Engine: a 2-beat fixture scene checks static and runtime; preview produces two stills and a
  sheet; skip when manimgl/Chromium is unavailable, as the repo already does.
- Contract: the skill's tool names and response fields match the server.
- Manual: one full run from Claude Code and one from opencode on the same topic; compare the
  sheet, the video, and the number of review iterations.

## 13. Phases

1. **Run + stills plumbing** — `runs.py`, `preview.py`, wrapper generation, tests. No MCP yet.
2. **MCP server** — tools, job runner, `pyproject` entry, stdio smoke test.
3. **Skill + docs** — `SKILL.md`, install/config docs, a minimal beat template.
4. **End-to-end** — real harness run; tune the skill, check messages, and still sheet labels.
5. **Later** — narration/TTS (`voice_lines` already exists), `make_video` fallback, Claude Code
   plugin and opencode plugin wrappers, remote/mayu rendering, codebase/PR mode.

## 14. Open items

- Voice: v1 writes `vo` on every beat for timing and future narration, but renders silent.
- Distribution: v1 runs from this checkout. A pip-installable `konvey[mcp]` package needs
  `prompts/`, `skills/` and the display docs included in the wheel.
- The MCP server should be tested against the harness's actual tool timeout; the config shows a
  10-minute opencode timeout, and the job model makes a shorter timeout recoverable.
- The existing uncommitted engine work (`render.py`, `scene.py`, `plot/`, …) must not be touched
  by this feature; the MCP only calls public helpers.
