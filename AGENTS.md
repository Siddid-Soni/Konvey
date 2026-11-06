# AGENTS.md — working in Konvey

Konvey turns a topic into a 3Blue1Brown-style explainer video. LLM agents (Agno) research,
script and plan it; the **Director** (Agent 3) writes each scene as *beat HTML*; `konvey.stage`
lays the beats out with headless Chromium and draws/animates them with **manimgl**; optional
narration is voiced by **DramaBox** on the GPU. Human-facing overview: `README.md`.

## Setup

```bash
uv sync --group dev --group render --group layout          # Python 3.11 in .venv
uv run --group layout playwright install chromium           # layout pass needs Chromium
uv sync --group speech                                      # narration only (torch, ~8 GB GPU)
cp .env.example .env                                        # then fill in keys
```

Also needs `ffmpeg` and a LaTeX install for `<tex>`. Credentials live in `.env` (gitignored):
`OPENCODE_API_KEY` + `KONVEY_PROVIDER` / `OPENCODE_MODEL_ID`, or `MINIMAX_API_KEY`.
Narration needs a reference voice clip: `KONVEY_VOICE_REF=/path/clip.wav` or
`assets/voices/narrator.mp3` (clips are never committed — see `assets/voices/README.md`).

## Run

```bash
# tests (~3 min, no API keys or GPU needed; manimgl reads sys.argv, so avoid exotic pytest flags like -p)
uv run --group dev pytest -q
uv run --group dev pytest -q tests/test_parts.py -k some_name

# 3-agent pipeline: topic -> knowledge pack -> 3-scene plan -> beat HTML -> video
uv run --group render --group layout run_konvey.py --prompt "Explain <topic>" --render --out-dir out/<name>
uv run --group render python -m konvey.render out/<name>            # re-render saved beats
run_konvey_narrated.py   # same + narration;   run_konvey_lean.py --agents {1,2}   # fewer-agent variants

# story pipeline v7 (current direction): Explorer -> chapter judge -> Writer -> Visual Planner -> stage plan
uv run python scripts/story_eval_v7.py OUT_DIR "<topic>"
uv run --group render --group layout --group speech python scripts/story_render_v7.py OUT_DIR/<t>.stage-plan.json out/<run>

# MCP server: a coding harness writes the beats, Konvey checks/previews/renders (docs/konvey-mcp.md)
uv run --group mcp --group render --group layout konvey-mcp --help
```

Production runs go through **mayu** (a task-queue engine, Python 3.13, separate `.venv-gpu`):
`konvey/mayu_app.py` (voiced) and `konvey/mayu_silent.py` (silent). Their module docstrings
have the worker commands and env setup.

Every run writes `out/<run>/` (gitignored): `agent1-output.json`, `agent2-output.json`,
`agent3-S*.html` (beats) and `.py`, `repair-log.txt`, `cost.json` (tokens + $ per request),
`video.mp4`; narrated runs add `speech.json` and `audio/`.

## What is where

| Path | What |
|---|---|
| `konvey/pipeline.py` | 3-agent orchestration: validate, repair rounds, scenes in parallel |
| `konvey/agents.py` | agent factories + `resolve_model` (providers, headers, token limits) |
| `konvey/schemas.py`, `validators.py` | Pydantic contracts and plan checks between agents |
| `konvey/story*.py` | story-first agents (v7): Explorer findings, simulations, voice-prompt checks |
| `konvey/compute.py`, `cost.py`, `probe.py` | calc tools for agents, price log, runtime-check probe |
| `konvey/render.py` | render `agent3-S*.py` scenes with manimgl (NVENC, parallel) and join |
| `konvey/stage/` | the renderer. `parse.py` beat HTML → tree; `layout.py` Chromium pass; `scene.py` StageScene; `check.py` static + runtime checks; `shots.py` compositions; `marks.py` marks on pictures; `motion.py` between-beat morphs; `world.py`/`solids.py`/`field.py`/`actors3d.py`/`diagram3d.py`/`layers3d.py` 3D; `sims.py`/`models.py` simulations; `theme.py` colours and fonts |
| `konvey/stage/displays/<tag>/` | one folder per beat tag, auto-registered: `__init__.py` (pure-Python spec), `mobject.py` (manimgl build), `agent3.md` (Director docs), `plan.md` (planner row). See its `README.md` |
| `konvey/speech/` | narration: `dramabox.py` (TTS, staged for 8 GB), `narrate.py` (voice/wire/master), `spoken.py`, `checks.py`, `mirror.py` (park models in host RAM); `vendor/` is vendored DramaBox |
| `konvey/mcp/` | MCP server, runs, jobs/worker, check, preview, render, docs |
| `konvey/mayu_app.py`, `mayu_silent.py` | the pipeline as mayu workflows |
| `prompts/` | all agent prompts (`README.md` maps them); `{{...}}` slots are filled from the displays |
| `skills/konvey-video/` | Agent Skill for harnesses using the MCP server |
| `scripts/` | eval and batch scripts; `story_eval_v7` imports v6→v5→…→v2, so keep the chain |
| `render/konvey_kit.py` | legacy Manim builders, still used by the `<tiles>` display |
| `tests/` | pytest; `fixtures/` holds sample plans and beats |
| `docs/konvey-mcp.md`, `docs/superpowers/specs/` | MCP docs and dated design specs |
| `spikes/` | archived prototypes, not imported by anything (has a README) |
| `topics.toml` | the topic list `scripts/topics.py` runs |
| `assets/` | Tabler icons (MIT); voice clips are local only |

## Conventions

- **Add, don't fork.** A new display is a new folder in `konvey/stage/displays/`, and the
  parser, checker and both prompts pick it up. Name displays after the picture they draw
  (`<plot>`, `<graph>`), never after one topic.
- **The renderer lays things out.** Prefer tags whose geometry the renderer computes over
  free-form `<draw>` coordinates, because weaker models place free geometry badly.
- **No subtitles.** The stage default is `caption="none"`.
- **Numbers are computed, not recalled.** Agents get calc/simulation tools; checks reject
  invented values.
- **Agent-facing docs and prompts use neutral examples**, never the topics used in tests or evals.
- **Report cost.** Include the `cost.json` total with any generation result.
- **Before deleting**, run `git ls-files` to see whether a file is tracked, and archive old
  experiments to `spikes/`.
- **The repo is public.** Never commit `.env`, voice clips, `out/`, or absolute home paths;
  scripts use repo-relative paths (`Path(__file__).resolve().parents[1]`).
