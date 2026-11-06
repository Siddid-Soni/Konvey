"""Konvey on mayu without voice: the silent video as its own mayu app.

    story -> direct -> unvoice_run -> render_scene x 3 -> finalize (no mastering)
    (agents)  (agents)  (cpu)          (gpu)              (cpu)

The voiced app (``konvey.mayu_app``) declares Gemma and TTS pools for its voice tasks, and a mayu worker refuses to
start unless it can run every task on the queues it serves. This app has no voice tasks, so its gpu worker needs no
pools. Its tasks run the voiced app's code under their own names (``konvey.silent.*``) and queues (``silent-*``):
the two apps share one Redis, and a worker must never claim the other app's tasks.

Three workers, from the Konvey checkout, in the same 3.13 env as the voiced app (``mayu_app`` docstring):

    mayu worker konvey.mayu_silent:app --queues silent-agents --mode process --processes 2
    # one process owns the card; --autotune gpu picks how many renders run side by side from its utilization
    mayu worker konvey.mayu_silent:app --queues silent-gpu --mode thread --threads 8 --gpus 0 \\
        --resources gpu=auto,vram_gb=auto,cpu=12 --autotune gpu
    mayu worker konvey.mayu_silent:app --queues silent-cpu --mode thread --threads 4

Submitting a video:

    from konvey.mayu_silent import silent_workflow
    wf = silent_workflow("why do rainbows form?", "out/rainbow-silent", max_sec=600).send()
    wf.wait(timeout=4 * 3600)
"""

from __future__ import annotations

import os
from pathlib import Path

import mayu

from konvey import mayu_app as voiced

app = mayu.App(broker=os.environ.get("MAYU_REDIS_URL", "redis://localhost:6379/0"), result_ttl=7 * 86400)


def _unvoice_run(out_dir: str, highlight: str | None = None) -> None:
    """wire_run for a video without voice: each beat's vo keeps only its spoken words (the stage times a beat
    without a clip by its vo, and a DramaBox prompt's directions would lengthen it), the wrappers stay StageScene,
    and the highlight colour is recorded. Like wire, it reads the Director's pages from agent3-S*.tagged.html."""
    import html

    from konvey import render
    from konvey.speech import narrate

    def spoken(m):
        text = html.unescape(m.group(2)).strip()
        return m.group(1) + html.escape(narrate.dialogue(text), quote=True) + m.group(3) if text else m.group(0)

    for page in narrate.pages(Path(out_dir)):
        tagged = narrate.tagged(page)
        if not tagged.exists():
            tagged.write_text(page.read_text(encoding="utf-8"), encoding="utf-8")
        page.write_text(narrate.BEAT_VO.sub(spoken, tagged.read_text(encoding="utf-8")), encoding="utf-8")
        py = page.with_suffix(".py")
        src = py.read_text(encoding="utf-8").replace("from konvey.speech.scene import SpeechScene",
                                                     "from konvey.stage.scene import StageScene")
        py.write_text(src.replace("(SpeechScene)", "(StageScene)"), encoding="utf-8")
    render.style_scenes(out_dir, highlight=highlight)


story = app.task(name="konvey.silent.story", queue="silent-agents")(voiced.story.fn)
direct = app.task(name="konvey.silent.direct", queue="silent-agents")(voiced.direct.fn)
unvoice_run = app.task(name="konvey.silent.unvoice_run", queue="silent-cpu")(_unvoice_run)
# the voiced app's render: same code, same resources (see the note above mayu_app.render_scene)
render_scene = app.task(name="konvey.silent.render_scene", queue="silent-gpu",
                        resources=dict(voiced.render_scene.resources))(voiced.render_scene.fn)
finalize = app.task(name="konvey.silent.finalize", queue="silent-cpu")(voiced.finalize.fn)


def silent_workflow(prompt: str, out_dir: str | Path, max_sec: float = 600, highlight: str | None = None,
                    plan_model: str = "deepseek-v4.1-flash", director_model: str = "claude-haiku-5-5",
                    reuse_script: str | None = None) -> mayu.Workflow:
    """The unsent workflow for a video without voice: story agents, Director, unvoice_run, the renders, the join."""
    out = Path(out_dir).resolve()
    wf = app.workflow(f"silent:{out.name}")
    plan = wf.add(story.s(prompt, str(out), max_sec=max_sec, plan_model=plan_model, reuse_script=reuse_script))
    coded = wf.add(direct.s(str(out), director_model=director_model), after=plan)
    unvoiced = wf.add(unvoice_run.s(str(out), highlight=highlight), after=coded)
    renders = [wf.add(render_scene.s(str(out), sid), after=unvoiced) for sid in voiced.SCENES]
    wf.add(finalize.s(str(out), master=False), after=renders)
    return wf
