"""konvey.mayu_app: the task queue integration, without Redis, a GPU or the agents.

Skipped where mayu is not installed (Konvey's own 3.11 env). The module is loaded from its file, so it needs
nothing of Konvey but the file: its imports of torch and the agents are inside the functions.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

pytest.importorskip("mayu")

import mayu  # noqa: E402

APP_FILE = Path(__file__).resolve().parent.parent / "konvey" / "mayu_app.py"


@pytest.fixture(scope="module")
def ma():
    spec = importlib.util.spec_from_file_location("konvey_mayu_app_under_test", APP_FILE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(spec.name, None)


def _run(tmp_path: Path, scenes=("S1", "S2", "S3")) -> Path:
    for sid in scenes:
        (tmp_path / f"agent3-{sid}.py").write_text("# wrapper\n")
        (tmp_path / f"agent3-{sid}.html").write_text("<beat/>")
        (tmp_path / f"agent3-{sid}.tagged.html").write_text("<beat/>")   # not a scene of its own
    (tmp_path / "agent3-S1.layout.html").write_text("not a scene")
    return tmp_path


def _shape(wf):
    """(task name, queue, args, kwargs, names of the parents) per node, in add order."""
    nodes = [n for n, _, _ in wf._nodes]
    return [(sig.task.name, sig.task.queue, sig.args, sig.kwargs, [nodes[i].task.name + f"#{i}" for i in parents])
            for _, sig, parents in wf._nodes]


def test_the_media_workflow_has_the_right_nodes_queues_and_edges(ma, tmp_path):
    out = _run(tmp_path)
    shape = _shape(ma.media_workflow(out, highlight="c2"))
    d = str(out.resolve())
    assert shape == [
        ("konvey.encode_prompts", "gpu", (d,), {}, []),
        ("konvey.voice_lines", "gpu", (d,), {}, ["konvey.encode_prompts#0"]),
        ("konvey.wire_run", "cpu", (d,), {"highlight": "c2"}, ["konvey.voice_lines#1"]),
        ("konvey.render_scene", "gpu", (d, "S1"), {}, ["konvey.wire_run#2"]),
        ("konvey.render_scene", "gpu", (d, "S2"), {}, ["konvey.wire_run#2"]),
        ("konvey.render_scene", "gpu", (d, "S3"), {}, ["konvey.wire_run#2"]),
        ("konvey.finalize", "cpu", (d,), {}, ["konvey.render_scene#3", "konvey.render_scene#4",
                                              "konvey.render_scene#5"]),
    ]


def test_one_render_node_per_scene_file(ma, tmp_path):
    wf = ma.media_workflow(_run(tmp_path, ("S1", "S2", "S3", "S4", "S5")))
    names = [t[0] for t in _shape(wf)]
    assert names.count("konvey.render_scene") == 5
    assert len(wf._nodes) == 3 + 5 + 1
    assert wf.name == f"video:{tmp_path.name}"


def test_no_scenes_is_an_error_not_an_empty_workflow(ma, tmp_path):
    with pytest.raises(ValueError, match="no scenes"):
        ma.media_workflow(tmp_path)


def test_the_workflow_serializes_before_it_is_sent(ma, tmp_path):
    """send() writes the payloads first: everything in them must be plain data."""
    wf = ma.media_workflow(_run(tmp_path), highlight=None)
    for _, sig, _ in wf._nodes:
        ma.app.serializer.dumps([list(sig.args), sig.kwargs])


def test_scene_ids_are_the_wrappers_in_join_order(ma, tmp_path):
    assert ma.scene_ids(_run(tmp_path, ("S2", "S1", "S3"))) == ["S1", "S2", "S3"]


def test_scene_ids_agree_with_konvey_render(ma, tmp_path):
    render = pytest.importorskip("konvey.render")
    out = _run(tmp_path)
    assert ma.scene_ids(out) == render.scene_ids(out)


def test_task_names_queues_and_resources(ma):
    tasks = ma.app.registry
    assert {n: (t.queue, t.resources) for n, t in tasks.items()} == {
        "konvey.story": ("agents", {}),
        "konvey.direct": ("agents", {}),
        "konvey.encode_prompts": ("gpu", {"gpu": 0.1}),
        "konvey.voice_lines": ("gpu", {"gpu": 0.1}),
        "konvey.wire_run": ("cpu", {}),
        "konvey.render_scene": ("gpu", {"gpu": 0.1, "vram_gb": 0.6, "cpu": 2.0}),
        "konvey.finalize": ("cpu", {}),
    }
    assert all(t.implemented for t in tasks.values())


def test_the_model_tasks_take_their_pool(ma):
    tasks = ma.app.registry
    assert tasks["konvey.encode_prompts"].pools == {"gemma": "gemma"}
    assert tasks["konvey.voice_lines"].pools == {"tts": "tts"}
    assert all(not t.pools for n, t in tasks.items() if n not in ("konvey.encode_prompts", "konvey.voice_lines"))


def test_pools_declare_their_ledger_sizes_and_every_hook(ma):
    gemma, tts = ma.app.pools["gemma"], ma.app.pools["tts"]
    assert gemma.resources == {"vram_gb": 7.4} and tts.resources == {"vram_gb": 7.2}
    assert gemma.parked == {"ram_gb": 7.8} and tts.parked == {"ram_gb": 6.9}
    for pool in (gemma, tts):
        assert callable(pool.factory)
        assert pool.parker is ma._park and pool.unparker is ma._unpark and pool.closer is ma._close
        assert callable(pool.stager)
    assert gemma.stager is ma._stage_gemma and tts.stager is ma._stage_tts


def test_the_documented_gpu_worker_passes_mayus_startup_checks(ma):
    from mayu.worker import WorkerRunner

    flags = dict(threads=4, resources={"gpu": 1, "vram_gb": 7.5, "ram_gb": 16, "cpu": 12}, pool_mode="lazy",
                 lookahead=True, schedule="throughput", prefetch_multiplier=1, gpu_monitor="off")
    WorkerRunner(ma.app, queues=["gpu"], pools={"gemma": 1, "tts": 1}, **flags)
    # the parked claims are what the 16 GB budget is for: both parked fit, and a smaller budget is refused
    assert ma.GEMMA_PARKED_GB + ma.TTS_PARKED_GB <= 16
    with pytest.raises(ValueError, match="ram_gb"):
        WorkerRunner(ma.app, queues=["gpu"], pools={"gemma": 1, "tts": 1}, **{**flags, "resources": {
            "gpu": 1, "vram_gb": 7.5, "ram_gb": 6.5, "cpu": 12}})


def test_its_gpu_worker_must_declare_the_pools(ma):
    """Why the silent video is its own app (konvey.mayu_silent): a worker on this app's gpu queue can't skip them."""
    from mayu.worker import WorkerRunner

    with pytest.raises(ValueError, match="pool"):
        WorkerRunner(ma.app, queues=["gpu"], threads=8, resources={"gpu": 1, "vram_gb": 7.5, "cpu": 12},
                     gpu_monitor="off")


def test_the_agents_and_cpu_workers_need_no_pools_or_resources(ma):
    from mayu.worker import WorkerRunner

    WorkerRunner(ma.app, queues=["agents"], threads=1)
    WorkerRunner(ma.app, queues=["cpu"], threads=4)


def test_a_render_fits_beside_a_parked_model_but_not_beside_a_loaded_one(ma):
    """vram_gb 7.5 holds a loaded model (7.4 / 7.2) or several renders (0.6 each), so a render makes the worker park
    the model first. Every gpu task takes the same small gpu share, so --autotune gpu can settle on 1 render up to
    the cpu limit (12 / 2 = 6), and the vram ledger, not gpu, keeps model tasks apart from renders."""
    tasks = ma.app.registry
    render = tasks["konvey.render_scene"].resources
    assert {tasks[n].resources["gpu"] for n in ("konvey.encode_prompts", "konvey.voice_lines")} == {render["gpu"]}
    assert 12 / render["cpu"] * render["gpu"] <= 1
    assert 6 * render["vram_gb"] <= 7.5
    assert ma.GEMMA_VRAM_GB + render["vram_gb"] > 7.5 and ma.TTS_VRAM_GB + render["vram_gb"] > 7.5


def test_app_takes_the_redis_url_from_the_environment(ma, monkeypatch):
    # the module-level app was built at import; a fresh load sees the variable
    monkeypatch.delenv("MAYU_BROKER", raising=False)
    monkeypatch.setenv("MAYU_REDIS_URL", "redis://example.invalid:6390/3")
    spec = importlib.util.spec_from_file_location("konvey_mayu_app_env", APP_FILE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        assert module.app.broker_url == "redis://example.invalid:6390/3"
    finally:
        sys.modules.pop(spec.name, None)


def test_follow_is_a_workflow_handle_on_the_app(ma):
    handle = ma.follow("01JXYZ")
    assert isinstance(handle, mayu.WorkflowHandle) and handle.id == "01JXYZ" and handle.app is ma.app


def _fake_scripts(ma, monkeypatch, plan=True):
    """Stands in for the story scripts: records each call and writes what the real one would."""
    calls = []

    def script(name, *args, **env):
        calls.append((name, args, env))
        if name == "story_eval_v7.py":
            story = Path(args[0])
            (story / "video.json").write_text('{"error": "writer failed"}')
            if plan:
                (story / "video.stage-plan.json").write_text("{}")
        else:
            _run(Path(args[1]))

    monkeypatch.setattr(ma, "_script", script)
    return calls


def test_story_runs_the_story_agents_on_the_prompt(ma, monkeypatch, tmp_path):
    calls = _fake_scripts(ma, monkeypatch)
    story = tmp_path / "story"
    assert ma.story("why do rainbows form?", str(tmp_path), max_sec=180) == str(story / "video.stage-plan.json")
    ((name, args, env),) = calls
    assert (name, args) == ("story_eval_v7.py", (str(story), "video"))
    assert env == {"TOPICS_FILE": str(story / "topics.json"), "PLAN_MODEL": "deepseek-v4.1-flash",
                   "DURATION_SEC": "180", "REUSE_SCRIPT": ""}
    assert (story / "topics.json").read_text() == '{"video": "why do rainbows form?"}'


def test_story_reuses_a_saved_script_only_when_its_video_asks(ma, monkeypatch, tmp_path):
    calls = _fake_scripts(ma, monkeypatch)
    ma.story("why do rainbows form?", str(tmp_path / "a"), reuse_script=str(tmp_path / "saved"))
    ma.story("why is the sky blue?", str(tmp_path / "b"))
    assert [env["REUSE_SCRIPT"] for _, _, env in calls] == [str(tmp_path / "saved"), ""]


def test_story_reuses_a_stage_plan_it_already_has(ma, monkeypatch, tmp_path):
    calls = _fake_scripts(ma, monkeypatch)
    (tmp_path / "story").mkdir()
    (tmp_path / "story" / "video.stage-plan.json").write_text("{}")
    ma.story("why do rainbows form?", str(tmp_path))
    assert calls == []


def test_story_without_a_stage_plan_fails_with_the_story_error(ma, monkeypatch, tmp_path):
    _fake_scripts(ma, monkeypatch, plan=False)
    with pytest.raises(RuntimeError, match="writer failed"):
        ma.story("why do rainbows form?", str(tmp_path))


def test_direct_runs_the_director_on_the_stage_plan(ma, monkeypatch, tmp_path):
    calls = _fake_scripts(ma, monkeypatch)
    ma.direct(str(tmp_path), director_model="m")
    ((name, args, env),) = calls
    assert name == "story_render_v7.py" and env == {"DIRECTOR_MODEL": "m"}
    assert args == (str(tmp_path / "story" / "video.stage-plan.json"), str(tmp_path), "--no-render")


def test_the_video_workflow_is_the_agents_then_the_media(ma, tmp_path):
    wf = ma.video_workflow("why do rainbows form?", tmp_path, max_sec=180, highlight="c2", plan_model="p")
    d = str(tmp_path.resolve())
    shape = _shape(wf)
    assert shape[:3] == [
        ("konvey.story", "agents", ("why do rainbows form?", d), {"max_sec": 180, "plan_model": "p", "reuse_script": None}, []),
        ("konvey.direct", "agents", (d,), {"director_model": "claude-haiku-5-5"}, ["konvey.story#0"]),
        ("konvey.encode_prompts", "gpu", (d,), {}, ["konvey.direct#1"]),
    ]
    assert [n[0] for n in shape[3:]] == ["konvey.voice_lines", "konvey.wire_run"] + ["konvey.render_scene"] * 3 + [
        "konvey.finalize"]
    assert [n[2][1] for n in shape if n[0] == "konvey.render_scene"] == ["S1", "S2", "S3"]
    assert wf.name == f"video:{tmp_path.name}"
    for _, sig, _ in wf._nodes:
        ma.app.serializer.dumps([list(sig.args), sig.kwargs])


# -- the hooks and tasks, with fake models ---------------------------------------------------------------------------


class FakeModel:
    """Stands in for _SplitGemma / Voicer: records the calls the hooks make."""

    def __init__(self):
        self.mirror = None
        self.calls = []

    def gpu_modules(self):
        return ["gpu-side"]

    def before_gpu(self):
        self.calls.append(("before_gpu", list(self.mirror.calls) if self.mirror else None))

    def on_gpu(self):
        self.calls.append("on_gpu")

    def close(self):
        self.calls.append("close")


class FakeMirror:
    made = []

    def __init__(self, device, *modules):
        self.device, self.modules, self.calls = device, modules, []
        FakeMirror.made.append(self)

    def park(self):
        self.calls.append("park")

    def unpark(self):
        self.calls.append("unpark")


@pytest.fixture
def fake_mirror(monkeypatch):
    """konvey.speech.mirror is torch-only, but torch may be missing here: give the hooks a stand-in module."""
    FakeMirror.made = []
    module = types.ModuleType("konvey.speech.mirror")
    module.Mirror = FakeMirror
    for name in ("konvey", "konvey.speech"):
        monkeypatch.setitem(sys.modules, name, sys.modules.get(name) or types.ModuleType(name))
    monkeypatch.setitem(sys.modules, "konvey.speech.mirror", module)
    return FakeMirror


def test_the_first_park_makes_the_mirror_and_later_ones_reuse_it(ma, fake_mirror):
    model = FakeModel()
    ma._park(model)
    ma._unpark(model)
    ma._park(model)
    (mirror,) = fake_mirror.made
    assert mirror.device == "cuda" and mirror.modules == ("gpu-side",)
    assert mirror.calls == ["park", "unpark", "park"]
    assert model.calls == [("before_gpu", ["park"]), "on_gpu"], "set up before the weights come back"


def test_a_staged_instance_is_mirrored_from_the_cpu_and_parked(ma, fake_mirror):
    model = ma._staged(FakeModel())
    (mirror,) = fake_mirror.made
    assert mirror.device == "cpu" and mirror.calls == ["park"] and model.mirror is mirror


def test_close_goes_to_the_instance(ma):
    model = FakeModel()
    ma._close(model)
    assert model.calls == ["close"]


@pytest.fixture
def speech(monkeypatch, fake_mirror):
    """Stand-ins for konvey.speech.dramabox / narrate that record the calls the tasks make, in order."""
    events = []
    dramabox = types.ModuleType("konvey.speech.dramabox")
    dramabox.pending = lambda prompts: [p for p in prompts if p != "cached"]
    dramabox.embed_inputs = lambda texts: [*texts, "negative"]

    def encode_hidden(gemma, todo, progress=None):
        for i in range(len(todo)):
            progress(i + 1, len(todo))
        events.append(("encode", list(todo)))
        return ["raw"] * len(todo)

    def embed_hidden(todo, raw):
        events.append(("embed", len(raw), list(fake_mirror.made[-1].calls)))   # Gemma is parked by now
        if dramabox.fail_embed:
            raise RuntimeError("processor failed")

    dramabox.encode_hidden, dramabox.embed_hidden, dramabox.fail_embed = encode_hidden, embed_hidden, False
    narrate = types.ModuleType("konvey.speech.narrate")
    narrate.lines = lambda out: [{"say": "one"}, {"say": "two"}]
    narrate.voice = lambda out, voicer=None, progress=None: events.append(("voice", voicer, progress))
    for name, module in (("dramabox", dramabox), ("narrate", narrate)):
        monkeypatch.setitem(sys.modules, f"konvey.speech.{name}", module)
        monkeypatch.setattr(sys.modules["konvey.speech"], name, module, raising=False)
    reports = []
    monkeypatch.setattr(mayu, "progress", lambda done, total=None: reports.append((done, total)) or True)
    return types.SimpleNamespace(events=events, dramabox=dramabox, reports=reports)


def test_encode_prompts_parks_gemma_around_the_embeddings_processor(ma, speech, tmp_path):
    gemma = FakeModel()
    assert ma.encode_prompts(str(tmp_path), gemma=gemma) == 3   # two lines and the negative prompt
    assert speech.events == [("encode", ["one", "two", "negative"]), ("embed", 3, ["park"])]
    (mirror,) = FakeMirror.made
    assert mirror.device == "cuda" and mirror.calls == ["park", "unpark"], "parked for the processor, back after"
    assert gemma.calls == [("before_gpu", ["park"]), "on_gpu"]
    assert speech.reports == [(1, 3), (2, 3), (3, 3)], "per prompt"


def test_encode_prompts_hands_each_chunk_to_the_processor_before_encoding_the_next(ma, speech, tmp_path,
                                                                                   monkeypatch):
    monkeypatch.setattr(ma, "ENCODE_CHUNK", 2)
    gemma = FakeModel()
    assert ma.encode_prompts(str(tmp_path), gemma=gemma) == 3
    assert speech.events == [("encode", ["one", "two"]), ("embed", 2, ["park"]),
                             ("encode", ["negative"]), ("embed", 1, ["park", "unpark", "park"])]
    assert FakeMirror.made[0].calls == ["park", "unpark", "park", "unpark"]
    assert gemma.calls == [("before_gpu", ["park"]), "on_gpu", ("before_gpu", ["park", "unpark", "park"]), "on_gpu"]
    assert speech.reports == [(1, 3), (2, 3), (3, 3)], "counted across chunks"


def test_encode_prompts_with_everything_cached_does_nothing(ma, speech, tmp_path, monkeypatch):
    monkeypatch.setattr(sys.modules["konvey.speech.narrate"], "lines", lambda out: [])
    speech.dramabox.pending = lambda prompts: []
    gemma = FakeModel()
    assert ma.encode_prompts(str(tmp_path), gemma=gemma) == 0
    assert speech.events == [] and FakeMirror.made == [] and speech.reports == []


def test_encode_prompts_brings_gemma_back_when_the_processor_fails(ma, speech, tmp_path):
    speech.dramabox.fail_embed = True
    with pytest.raises(RuntimeError, match="processor failed"):
        ma.encode_prompts(str(tmp_path), gemma=FakeModel())
    assert FakeMirror.made[-1].calls == ["park", "unpark"]


def test_encode_prompts_discards_gemma_when_it_cannot_be_brought_back(ma, speech, tmp_path, monkeypatch):
    def broken_unpark(self):
        raise RuntimeError("cuda out of memory")

    monkeypatch.setattr(FakeMirror, "unpark", broken_unpark)
    with pytest.raises(mayu.DiscardInstance):
        ma.encode_prompts(str(tmp_path), gemma=FakeModel())


def test_voice_lines_voices_with_the_pooled_model_and_reports_progress(ma, speech, tmp_path):
    tts = FakeModel()
    assert ma.voice_lines(str(tmp_path), tts=tts) == str(tmp_path / "speech.json")
    ((kind, voicer, progress),) = speech.events
    assert kind == "voice" and voicer is tts and progress is mayu.progress
