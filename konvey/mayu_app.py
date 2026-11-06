"""Konvey on mayu (https://github.com/Siddid-Soni/mayu): narrated videos as a workflow of tasks on three queues.

    story -> direct -> encode_prompts -> voice_lines -> wire_run -> render_scene x 3 -> finalize
    (agents)  (agents)  (gpu, gemma)      (gpu, tts)     (cpu)        (gpu)              (cpu)

One video is one mayu workflow (``video_workflow``): story pipeline v7's agents (Explorer, chapter judge, Writer,
Visual Planner), the Director, then voice, render and join. A video without voice is its own app,
``konvey.mayu_silent`` (no model pools, so its gpu worker needs none).

Nodes pass nothing to each other: every task works on the run directory ``out_dir``, which all workers must share
(a local path, or a shared mount). Tasks can run more than once after a crash (at-least-once); each one rewrites
what it makes, so that is safe, and ``story`` keeps a stage plan it already made, so a redelivery doesn't pay for
the agents twice.

Three workers (Redis at ``MAYU_REDIS_URL``, default redis://localhost:6379/0; ``MAYU_BROKER`` overrides it, as in
any mayu app), started from the Konvey checkout:

    # agents: the story scripts, each in a subprocess (they chdir and patch module globals), plus the
    # Director's headless manimgl check. One task per process: scale with --processes.
    mayu worker konvey.mayu_app:app --queues agents --mode process --processes 2

    # gpu: one process owns the card (two processes on one GPU would each think they own it). The models don't
    # fit together (Gemma 7.4 GB + DiT 7.2 GB of 7.5), so the pools are lazy; --lookahead loads/stages the next
    # model while the current task runs, and --schedule throughput groups tasks by loaded model. gpu and vram_gb
    # are read from the card (NVML, the mayu[gpu] extra), and --autotune gpu picks how many renders run side by
    # side from its utilization. Thread mode (the GPU env is a 3.13 GIL build: torch and the manimgl subprocesses
    # release it); ram_gb is the host RAM parked models may take.
    mayu worker konvey.mayu_app:app --queues gpu --mode thread --threads 8 --gpus 0 \\
        --pools gemma=1,tts=1 --pool-mode lazy --lookahead --schedule throughput --prefetch-multiplier 1 \\
        --resources gpu=auto,vram_gb=auto,ram_gb=16,cpu=12 --autotune gpu

    # cpu: wiring the scenes, joining the video and mastering its audio (ffmpeg)
    # (--mode thread: on a GIL build mayu defaults to process mode)
    mayu worker konvey.mayu_app:app --queues cpu --mode thread --threads 4

Environment. mayu needs Python >= 3.13, so it can't go in Konvey's 3.11 ``.venv``. One 3.13 venv runs all three
workers (the agents worker is in process mode, so the GIL doesn't matter there). pydub needs audioop-lts on 3.13.

    cd ~/Projects/Konvey
    UV_PROJECT_ENVIRONMENT=.venv-gpu uv sync --python 3.13 --group speech --group render --group layout --no-dev
    VIRTUAL_ENV=$PWD/.venv-gpu uv pip install "mayu[gpu]" audioop-lts
    # later syncs of that venv must keep them: UV_PROJECT_ENVIRONMENT=.venv-gpu uv sync --inexact ...

Submitting a video (from any environment that has mayu and Konvey's base dependencies):

    from konvey.mayu_app import video_workflow, follow
    wf = video_workflow("why do rainbows form?", "out/mayu-rainbow", max_sec=600, highlight="c2").send()
    wf.wait(timeout=4 * 3600)                # "done" / "failed" / "cancelled"; or watch it with:
    #   mayu inspect konvey.mayu_app:app     (running tasks with their progress, and the workflow)
    # later, from its id: follow(wf.id).status()
    # a run whose scenes the Director already wrote: media_workflow("out/mayu-rainbow").send()
    # without voice: konvey.mayu_silent.silent_workflow(...), on that app's own workers

Importing this module needs only mayu: torch, transformers and the agents are imported inside the functions, so
every worker (and a producer) can import it. (``import konvey`` itself still imports the agents package.)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import mayu

# What the GPU ledger holds for a loaded model (vram_gb): the measured peaks while it works (2026-10-21). They are
# the 8 GB card's reason for lazy pools: the two don't fit together in the worker's 7.5.
GEMMA_VRAM_GB = 7.4
TTS_VRAM_GB = 7.2
# What one *parked* model holds in host RAM (ram_gb). Gemma: the Mirror of its GPU-side tensors (5.78 GB measured)
# plus the 2.0 GB embedding table that _SplitGemma always keeps in host RAM, so 7.8, not just the 6.0 the mirror
# alone would suggest. The TTS: the DiT's mirror (6.57 GB) plus the decoder and vocoder (~0.3 GB, mirrored with it).
GEMMA_PARKED_GB = 7.8
TTS_PARKED_GB = 6.9
# The gpu share every gpu task takes. --autotune gpu moves the worker's gpu capacity in steps of the smallest request
# down to the largest, so one small value for all of them lets it settle anywhere from 1 task to the cpu limit.
# The model tasks get the card to themselves through vram_gb (a loaded model takes 7.4 of 7.5), not through gpu.
GPU_STEP = 0.1
# Prompts encode_prompts encodes before handing them to the embeddings processor: 8 x 0.37 GB of hidden states.
ENCODE_CHUNK = 8

app = mayu.App(broker=os.environ.get("MAYU_REDIS_URL", "redis://localhost:6379/0"), result_ttl=7 * 86400)


# -- pools: the two models ------------------------------------------------------------------------------------------
# Both pool objects (konvey.speech.dramabox._SplitGemma and Voicer) have gpu_modules(), on_gpu(), close() and a
# `mirror` attribute, so one set of park / unpark / close hooks serves both.


@app.pool("gemma", vram_gb=GEMMA_VRAM_GB, parked={"ram_gb": GEMMA_PARKED_GB})
def gemma_pool(ctx):
    from konvey.speech import dramabox

    return dramabox.load_gemma()


@app.pool("tts", vram_gb=TTS_VRAM_GB, parked={"ram_gb": TTS_PARKED_GB})
def tts_pool(ctx):
    from konvey.speech import dramabox
    from konvey.speech.narrate import REF

    return dramabox.Voicer(REF)


def _park(model) -> None:
    """GPU -> host RAM. The first park of an instance built on the GPU pays for the host copy."""
    from konvey.speech.mirror import Mirror

    if model.mirror is None:
        model.mirror = Mirror("cuda", *model.gpu_modules())
    model.mirror.park()


def _unpark(model) -> None:
    """Host RAM -> GPU, in place. before_gpu() first: the Voicer's allocator settings must be in place before its
    weights come back, or the decoder has no room left on the GPU."""
    model.before_gpu()
    model.mirror.unpark()
    model.on_gpu()


def _staged(model):
    """An instance built on the CPU, with its GPU-side weights in one host copy, ready to be unparked."""
    from konvey.speech.mirror import Mirror

    model.mirror = Mirror("cpu", *model.gpu_modules())
    model.mirror.park()   # the CPU-built weights are dropped; one host copy remains
    return model


def _close(model) -> None:
    model.close()


@gemma_pool.stage
def _stage_gemma(ctx):
    from konvey.speech import dramabox

    return _staged(dramabox.load_gemma(cpu=True))


@tts_pool.stage
def _stage_tts(ctx):
    from konvey.speech import dramabox
    from konvey.speech.narrate import REF

    return _staged(dramabox.Voicer(REF, cpu=True))


for _pool in (gemma_pool, tts_pool):
    _pool.park(_park)
    _pool.unpark(_unpark)
    _pool.close(_close)
del _pool


# -- tasks ----------------------------------------------------------------------------------------------------------


REPO = Path(__file__).resolve().parents[1]


def _script(name: str, *args: str, **env: str) -> None:
    """Run one of Konvey's scripts as its own process: the story scripts chdir, patch each other's module globals
    and read their models from the environment at import, which must not leak into this worker."""
    subprocess.run([sys.executable, str(REPO / "scripts" / name), *args], cwd=REPO, env={**os.environ, **env},
                   check=True)


@app.task(name="konvey.story", queue="agents")
def story(prompt: str, out_dir: str, max_sec: float = 600, plan_model: str = "deepseek-v4.1-flash",
          reuse_script: str | None = None) -> str:
    """Story pipeline v7 for ``prompt``: Explorer, chapter judge, Writer and Visual Planner (scripts/story_eval_v7.py,
    on ``plan_model``) write the stage plan under ``out_dir/story``; returns its path.

    A stage plan already there (an earlier delivery, or a retry after a later node failed) is used as it is: the
    story agents cost the most. ``reuse_script``: a story run dir whose ``video.json`` holds an exploration and
    script to take as they are (only the Visual Planner runs); it belongs to this video, never to the worker."""
    story_dir = Path(out_dir).resolve() / "story"
    plan = story_dir / "video.stage-plan.json"
    if not plan.exists():
        story_dir.mkdir(parents=True, exist_ok=True)
        topics = story_dir / "topics.json"
        topics.write_text(json.dumps({"video": prompt}, ensure_ascii=False))
        _script("story_eval_v7.py", str(story_dir), "video", TOPICS_FILE=str(topics), PLAN_MODEL=plan_model,
                DURATION_SEC=f"{max_sec:g}", REUSE_SCRIPT=str(Path(reuse_script).resolve()) if reuse_script else "")
    if not plan.exists():
        error = json.loads((story_dir / "video.json").read_text()).get("error", "no stage plan")
        raise RuntimeError(f"story agents made no stage plan for {prompt!r}: {error}")
    return str(plan)


@app.task(name="konvey.direct", queue="agents")
def direct(out_dir: str, director_model: str = "claude-haiku-5-5") -> None:
    """The Director (scripts/story_render_v7.py --no-render, on ``director_model``) codes the stage plan's scenes into
    ``out_dir``. Scenes it rejected are still voiced and rendered as written (problems in agent3-S*.problems.txt)."""
    out = Path(out_dir).resolve()
    _script("story_render_v7.py", str(out / "story" / "video.stage-plan.json"), str(out), "--no-render",
            DIRECTOR_MODEL=director_model)


@app.task(name="konvey.encode_prompts", queue="gpu", resources={"gpu": GPU_STEP})
def encode_prompts(out_dir: str, gemma=app.use("gemma")) -> int:
    """Stage 1 of the voice: Gemma's hidden states for every line's prompt, then the embeddings processor.

    The processor lives here, not in the tts pool: it consumes the hidden states (0.37 GB per prompt, in this
    process's host RAM) and writes small embeddings to the on-disk cache that the tts pool reads, so no big data
    crosses a task boundary. It needs a GB or two of VRAM that Gemma's 7.4 GB claim doesn't leave beside the
    loaded model, so the task parks Gemma's GPU weights in host RAM (0.3 s, back in 0.5 s) while it runs, the order
    the CLI follows by freeing Gemma first. It works in chunks of ENCODE_CHUNK prompts, so at most one chunk's hidden
    states are in host RAM (all 101 of a 10-minute video were 37 GB). Returns how many prompts it encoded (0 when
    all were cached)."""
    from konvey.speech import dramabox, narrate

    todo = dramabox.pending(dramabox.embed_inputs([x["say"] for x in narrate.lines(Path(out_dir))]))
    for start in range(0, len(todo), ENCODE_CHUNK):
        chunk = todo[start:start + ENCODE_CHUNK]
        raw = dramabox.encode_hidden(gemma, chunk, progress=lambda done, _: mayu.progress(start + done, len(todo)))
        _park(gemma)
        try:
            dramabox.embed_hidden(chunk, raw)
        finally:
            del raw
            try:
                _unpark(gemma)
            except Exception as e:   # the instance's state is unknown: have the worker close it and load a fresh one
                raise mayu.DiscardInstance(pool="gemma") from e
    return len(todo)


@app.task(name="konvey.voice_lines", queue="gpu", resources={"gpu": GPU_STEP})
def voice_lines(out_dir: str, tts=app.use("tts")) -> str:
    """Stage 2: voice every line with the pooled DramaBox -> audio/<id>.wav and speech.json (progress per line)."""
    from konvey.speech import narrate

    out = Path(out_dir)
    narrate.voice(out, voicer=tts, progress=mayu.progress)
    return str(out / "speech.json")


@app.task(name="konvey.wire_run", queue="cpu")
def wire_run(out_dir: str, highlight: str | None = None) -> None:
    """Point each voiced beat at its clip and each scene wrapper at SpeechScene, and record the highlight colour."""
    from konvey import render
    from konvey.speech import narrate

    narrate.wire(Path(out_dir))
    render.style_scenes(out_dir, highlight=highlight)


# A render is manimgl in a subprocess drawing on the RTX (PRIME offload, NVENC): ~0.5 GB VRAM and about two cores
# each (measured). How many run side by side is the gpu worker's --autotune gpu: it adds a GPU_STEP while the card
# is under 70% busy and takes one away at 90%, up to cpu=12 / 2 = 6 renders. They declare vram_gb, so a loaded
# model that has no room beside them is parked first, and no render runs beside a model task (7.4 + 0.6 > 7.5).
# Host RAM (~1.6 GB each) is not declared: it would only hold renders back behind parked models.
@app.task(name="konvey.render_scene", queue="gpu", resources={"gpu": GPU_STEP, "vram_gb": 0.6, "cpu": 2})
def render_scene(out_dir: str, sid: str) -> str:
    """Render one scene to video/<sid>.mp4."""
    from konvey import render

    return str(render.render_scene(out_dir, sid))


@app.task(name="konvey.finalize", queue="cpu")
def finalize(out_dir: str, master: bool = True) -> str:
    """Join the rendered scenes into video.mp4 and master its audio (``master``: a video without voice has none);
    returns the video's path."""
    from konvey import render
    from konvey.speech import narrate

    out = Path(out_dir)
    parts = [out / "video" / f"{sid}.mp4" for sid in scene_ids(out)]
    missing = [p.name for p in parts if not p.exists()]
    if missing:
        raise FileNotFoundError(f"cannot join {out}: not rendered yet: {', '.join(missing)}")
    video = render.concat(out, parts)
    if master:
        narrate.master(video)
    return str(video)


# -- the workflow ---------------------------------------------------------------------------------------------------


def scene_ids(out_dir: str | Path) -> list[str]:
    """The run's scenes (``S1``, ``S2`` ...) in the order they are joined; the same as konvey.render.scene_ids."""
    return [py.stem.split("-")[-1] for py in sorted(Path(out_dir).glob("agent3-S*.py"))]


# Story v7's stage plan always has these three scenes (Act 1, the chapters, the ending), so the whole video is one
# workflow built before any agent runs.
SCENES = ("S1", "S2", "S3")


def video_workflow(prompt: str, out_dir: str | Path, max_sec: float = 600, highlight: str | None = None,
                   plan_model: str = "deepseek-v4.1-flash", director_model: str = "claude-haiku-5-5",
                   reuse_script: str | None = None) -> mayu.Workflow:
    """The unsent workflow for a whole video: story agents, Director, then the media (see media_workflow)."""
    out = Path(out_dir).resolve()
    wf = app.workflow(f"video:{out.name}")
    _add_media(wf, out, SCENES, highlight, after=_add_agents(wf, prompt, out, max_sec, plan_model, director_model,
                                                                   reuse_script))
    return wf


def _add_agents(wf: mayu.Workflow, prompt: str, out: Path, max_sec: float, plan_model: str, director_model: str,
                reuse_script: str | None = None):
    """The story agents, then the Director; returns the Director's node."""
    plan = wf.add(story.s(prompt, str(out), max_sec=max_sec, plan_model=plan_model, reuse_script=reuse_script))
    return wf.add(direct.s(str(out), director_model=director_model), after=plan)


def media_workflow(out_dir: str | Path, highlight: str | None = None) -> mayu.Workflow:
    """The unsent workflow that voices, wires, renders and joins the Director's scenes already in ``out_dir``."""
    out = Path(out_dir).resolve()
    scenes = scene_ids(out)
    if not scenes:
        raise ValueError(f"no scenes in {out}: expected agent3-S*.py written by the Director")
    wf = app.workflow(f"video:{out.name}")
    _add_media(wf, out, scenes, highlight)
    return wf


def _add_media(wf: mayu.Workflow, out: Path, scenes, highlight: str | None, after=()) -> None:
    """Voice before wire (wire rewrites the pages that voicing reads), and every render after both (a scene is timed
    by its clips). Renders run side by side; the join waits for all of them."""
    encode = wf.add(encode_prompts.s(str(out)), after=after)
    voice = wf.add(voice_lines.s(str(out)), after=encode)
    wire = wf.add(wire_run.s(str(out), highlight=highlight), after=voice)
    renders = [wf.add(render_scene.s(str(out), sid), after=wire) for sid in scenes]
    wf.add(finalize.s(str(out)), after=renders)


def follow(workflow_id: str) -> mayu.WorkflowHandle:
    """A handle on a submitted video's workflow by id: ``status()``, ``wait()`` and ``cancel()``."""
    return mayu.WorkflowHandle(app, workflow_id, [])
