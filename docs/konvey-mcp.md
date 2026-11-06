# Konvey MCP — use Konvey from a coding harness

Konvey can run as an MCP server plus one Agent Skill. The harness model researches the topic,
writes the script and storyboard, and writes the beat HTML. Konvey supplies the DSL reference,
the display catalog, exact simulation values, deterministic checks, per-beat preview stills,
and the manimgl render.

v1 is a **silent** HD video: `vo` lines drive timing and are reserved for narration later.

- Server: `konvey/mcp/`
- Skill: `skills/konvey-video/SKILL.md`
- Design: `docs/superpowers/specs/2026-10-25-konvey-mcp-design.md`

## Requirements

- Python 3.11+ and [`uv`](https://docs.astral.sh/uv/)
- This Konvey checkout
- For checks/preview/render: manimgl, Chromium (Playwright), LaTeX, ffmpeg
- A GPU is strongly recommended; CPU rendering works but is slow

```bash
uv sync --group mcp --group render --group layout
uv run --group mcp --group render --group layout konvey-mcp --help
```

If your environment already has extra groups installed, `uv sync` may remove them; use
`uv sync --inexact --group mcp --group render --group layout` to keep them.

## Connect a harness

The server speaks MCP over stdio. It reads runs from `KONVEY_WORKSPACE` (the project you are
working in) and falls back to its own cwd. Use an absolute path for `--project` and for the
workspace.

### Claude Code

Project `.mcp.json` (or user scope):

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
      "env": {"KONVEY_WORKSPACE": "/path/to/your/project"}
    }
  }
}
```

### opencode

`opencode.json` (or `opencode.jsonc`):

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
      "environment": {"KONVEY_WORKSPACE": "/path/to/your/project"},
      "enabled": true,
      "timeout": 600000
    }
  }
}
```

The `timeout` is in milliseconds. The default local-MCP timeout (30 s) is shorter than a
preview or a render; the job model still recovers, but a longer timeout avoids most polling.
A runtime check also starts a job, so it is safe either way.

### Cursor

`.cursor/mcp.json`:

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
      "env": {"KONVEY_WORKSPACE": "/path/to/your/project"}
    }
  }
}
```

### Install the skill

The skill is a normal Agent Skills folder. Symlink it where your harness looks:

```bash
# Claude Code, project or global
ln -s /path/to/Konvey/skills/konvey-video /path/to/project/.claude/skills/konvey-video
ln -s /path/to/Konvey/skills/konvey-video ~/.claude/skills/konvey-video

# opencode
ln -s /path/to/Konvey/skills/konvey-video /path/to/project/.opencode/skills/konvey-video
ln -s /path/to/Konvey/skills/konvey-video ~/.config/opencode/skills/konvey-video

# portable / agent-compatible location
ln -s /path/to/Konvey/skills/konvey-video /path/to/project/.agents/skills/konvey-video
```

opencode also reads the Claude-compatible `.claude/skills/` path, so the first symlink is
enough there. Create the parent directory first if it does not exist.

## Ask for a video

With the skill loaded and the MCP server connected:

```text
Make a 90-second explainer about why a rainbow forms, in the 3Blue1Brown style.
```

The agent should call `konvey_new_run`, research and write `plan.md`, fetch the reference and
an example, write `S1.html` … `S3.html`, run `konvey_check`, review `preview/sheet.png`, fix,
then `konvey_render`.

`konvey_new_run` accepts `scenes=1..3`; a 1-scene, 15-second short is a fine test. On short
runs, `konvey_check` and `konvey_preview` usually finish inside the call (a few seconds) and
return `status: "done"`; the job model covers longer ones. Run ids are dated and can be long,
so keep a run id rather than retyping the path.

## Tools

Harnesses surface MCP tools differently: opencode v2 code mode calls them as
`tools.konvey.konvey_new_run`; some clients show `konvey_konvey_new_run`; Claude Code shows
`mcp__konvey__konvey_new_run`. The table below uses the tool's own name — look for the
`konvey` namespace/server and the suffix.

| Tool | What it does |
|---|---|
| `konvey_new_run` | Create `.konvey/runs/<id>/` with `run.json` and `S1.html` … `S3.html`; reports the render stack |
| `konvey_guide` | The Director reference and the MCP workflow/review/checks sections |
| `konvey_displays` | The overlay catalog, one display's docs, or every display of a plan kind |
| `konvey_example` | One worked scene to copy the structure from |
| `konvey_simulate` | The exact numbers a `<sim>` will play (blocks, drop, spread, pendulum, circles, line, heat, walk) |
| `konvey_check` | Static rules immediately; the headless play as a job |
| `konvey_preview` | One still per beat and `preview/sheet.png` |
| `konvey_render` | manimgl render + ffmpeg join (`video.mp4`; `preview=True` gives a 480p preview; `fps=24` by default) |
| `konvey_status` | Poll the latest job: state, log tail, elapsed time, artifacts |
| `konvey_cancel` | Stop the active job |

Long operations return `status="running"` after their `wait_seconds` budget; poll
`konvey_status(run_id)`. State is on disk, so an MCP restart does not lose a render.

## Run layout

```text
<project>/.konvey/
  .gitignore                 # runs/ (self-ignoring)
  runs/<run-id>/
    run.json
    plan.md                  # optional storyboard
    S1.html S2.html S3.html  # the harness owns these
    .engine/                 # generated wrappers, scene videos, joined video
    preview/
      sheet.png
      S1-beat-00.png …
      index.json
    jobs/<job-id>.json
    jobs/<job-id>.log
    video.mp4                # final deliverable
    video-preview.mp4        # optional 480p render
```

The MCP only writes under `.konvey/`; it never edits the scene HTML or the project.

## Check, preview and render from the shell

The same building blocks are runnable without an MCP client, which is useful for debugging:

```bash
uv run --group mcp --group render --group layout python -m konvey.mcp.check  out/run-dir
uv run --group mcp --group render --group layout python -m konvey.mcp.preview out/run-dir
uv run --group mcp --group render --group layout python -m konvey.mcp.render  out/run-dir --preview
```

## Tests

```bash
uv run --group dev --group render --group layout python -m pytest tests -q
```

The server tests are skipped when the `mcp` package is not installed; the `dev` group now
includes it.

## Troubleshooting

**The call timed out.** The operation is a detached job. Call `konvey_status(run_id)`; do not
restart the work. Increase the harness's MCP timeout if this happens often.

**`render_stack.missing` is not empty.** Install the missing piece. The server needs manimgl,
Playwright + Chromium, LaTeX (for `tex` displays), and ffmpeg. Re-run `konvey_new_run` or
inspect the current run; do not keep writing scenes that cannot render.

**Preview is blank or fails.** Open `jobs/<id>.log` and the `konvey_status` `log_tail`. A
scene with a parse error names the beat; fix that beat first.

**Render is slow.** The MCP renders at **24 fps** by default; pass `fps=30` for smoother camera
moves or `fps=20` for a quick draft. Most of the time is transition frames, not holds: shorten
a beat's transition with `t="1"`–`t="1.2"` when the move is simple, and use fewer beats or
transitions. On the RTX 3070 Ti reference machine, a 14.6 s 1080p single-scene test took
**23 s** as a full MCP job at 30 fps with `t="1.6"`, **19 s** at 24 fps, and **16–17 s** at
24 fps with `t="1"`. The manimgl step alone was 14.4 s at 24 fps/`t="1"` and 12.3 s at
20 fps/`t="1"`; the rest is process startup and the join. The video length stays the same
because the hold absorbs the shortened transition. Preview stills are cheap; use
`preview=True` for a 480p motion check before the HD render. Scenes render in parallel
(`KONVEY_RENDER_JOBS`, default 3) and manimgl uses PRIME offload + NVENC on an NVIDIA laptop.
`KONVEY_RENDER_GPU=default` keeps the system GPU and libx264. Renders are CPU-bound; more
parallel jobs help until the GPU/CPU saturates.

**A harness session dies mid-run.** A provider endpoint can drop between tool calls; the run
on disk is still valid. Resume the session (`opencode run --continue`) or load the existing
run id rather than starting a new run. For repeatable tests, pin a stable model
(`opencode run -m provider/model`); free default models can be unavailable.

**Runs land in the wrong project.** Set `KONVEY_WORKSPACE` in the MCP server's environment,
or pass `workspace=` to `konvey_new_run` and the run tools.

**The harness cannot open the sheet.** `konvey_preview` returns the sheet path and the beat
metadata; the harness can read the PNG if it has image input, or use `preview/index.json`
(VO, seconds, still path) to review structurally.

## Limits

- 1–3 scenes, 90 s default, 15 beats per scene.
- Silent only; `vo` is timing metadata for now.
- No Konvey agents run behind the MCP: the harness model is the Explorer, Writer, Planner and
  Director. This keeps the server free of API keys and model spending.
- Local checkout only; there is no remote render service yet.
