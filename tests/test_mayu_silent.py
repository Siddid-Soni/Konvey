"""konvey.mayu_silent: the video without voice as its own mayu app, without Redis, a GPU or the agents.

Skipped where mayu is not installed (Konvey's own 3.11 env)."""

from __future__ import annotations

import pytest

pytest.importorskip("mayu")


@pytest.fixture(scope="module")
def ms():
    from konvey import mayu_silent
    return mayu_silent


def _shape(wf):
    """(task name, queue, args, kwargs, names of the parents) per node, in add order."""
    nodes = [n for n, _, _ in wf._nodes]
    return [(sig.task.name, sig.task.queue, sig.args, sig.kwargs, [nodes[i].task.name + f"#{i}" for i in parents])
            for _, sig, parents in wf._nodes]


def test_the_silent_workflow_is_the_agents_then_the_renders_without_voice(ms, tmp_path):
    wf = ms.silent_workflow("why do rainbows form?", tmp_path, highlight="c2")
    d = str(tmp_path.resolve())
    assert _shape(wf) == [
        ("konvey.silent.story", "silent-agents", ("why do rainbows form?", d),
         {"max_sec": 600, "plan_model": "deepseek-v4.1-flash", "reuse_script": None}, []),
        ("konvey.silent.direct", "silent-agents", (d,), {"director_model": "claude-haiku-5-5"},
         ["konvey.silent.story#0"]),
        ("konvey.silent.unvoice_run", "silent-cpu", (d,), {"highlight": "c2"}, ["konvey.silent.direct#1"]),
        ("konvey.silent.render_scene", "silent-gpu", (d, "S1"), {}, ["konvey.silent.unvoice_run#2"]),
        ("konvey.silent.render_scene", "silent-gpu", (d, "S2"), {}, ["konvey.silent.unvoice_run#2"]),
        ("konvey.silent.render_scene", "silent-gpu", (d, "S3"), {}, ["konvey.silent.unvoice_run#2"]),
        ("konvey.silent.finalize", "silent-cpu", (d,), {"master": False},
         ["konvey.silent.render_scene#3", "konvey.silent.render_scene#4", "konvey.silent.render_scene#5"]),
    ]
    assert wf.name == f"silent:{tmp_path.name}"


def test_its_tasks_are_the_voiced_apps_code_on_queues_of_their_own(ms):
    from konvey import mayu_app

    tasks = ms.app.registry
    assert set(tasks) == {f"konvey.silent.{n}" for n in ("story", "direct", "unvoice_run", "render_scene", "finalize")}
    assert {t.queue for t in tasks.values()}.isdisjoint({t.queue for t in mayu_app.app.registry.values()})
    assert ms.render_scene.fn is mayu_app.render_scene.fn and ms.story.fn is mayu_app.story.fn
    assert ms.render_scene.resources == mayu_app.render_scene.resources
    assert not ms.app.pools


def test_the_documented_workers_pass_mayus_startup_checks_without_pools(ms):
    from mayu.worker import WorkerRunner

    WorkerRunner(ms.app, queues=["silent-gpu"], threads=8, resources={"gpu": 1, "vram_gb": 7.5, "cpu": 12},
                 gpu_monitor="off")
    WorkerRunner(ms.app, queues=["silent-agents"], threads=1)
    WorkerRunner(ms.app, queues=["silent-cpu"], threads=4)


def test_unvoice_run_keeps_the_spoken_words_and_the_stage_wrapper(ms, tmp_path):
    pytest.importorskip("konvey.speech.narrate")
    page = tmp_path / "agent3-S1.html"
    page.write_text('<beats><beat vo="A calm young woman speaks evenly, &#8220;So the rule is not 42.&#8221; '
                    'She pauses, &#8220;Not quite.&#8221;" shot="full" caption="none"><text/></beat>'
                    '<beat vo="" shot="title"></beat></beats>')
    wired = "from konvey.speech.scene import SpeechScene\n\n\nclass SingleScene(SpeechScene):\n    pass\n"
    (tmp_path / "agent3-S1.py").write_text(wired)   # voiced before: back to the stage wrapper
    director = page.read_text()
    for _ in range(2):   # reads the Director's page each time, so running it again changes nothing
        ms.unvoice_run(str(tmp_path))
        assert page.read_text() == ('<beats><beat vo="So the rule is not 42. Not quite." shot="full" caption="none">'
                                    '<text/></beat><beat vo="" shot="title"></beat></beats>')
    assert (tmp_path / "agent3-S1.tagged.html").read_text() == director
    assert (tmp_path / "agent3-S1.py").read_text() == wired.replace("SpeechScene", "StageScene").replace(
        "konvey.speech.scene", "konvey.stage.scene")
