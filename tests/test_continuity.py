"""Scene continuity in the checker (spec §4.5): S(n) is checked opening on S(n-1)'s last frame."""

import importlib.util
from pathlib import Path

import pytest

from konvey.stage.check import _renumber, check_runtime, continuity_note

HAS_MANIM = importlib.util.find_spec("manimlib") is not None
HAS_CHROMIUM = importlib.util.find_spec("playwright") is not None and Path("/usr/bin/chromium").exists()

S1 = """<beats>
<beat vo="A bowl." style="padding: 0.5u 0.6u; gap: 0.2u">
  <h2 id="t">Shapes</h2><div id="view" class="grow"></div>
  <world><surface id="s" fn="x^2 + y^2"></surface></world><camera focus="view"></camera>
</beat>
</beats>"""

# Fine on its own; but S1's surface is also id "s", so continuing from S1 the id changes tag.
S2 = """<beats>
<beat vo="A ball." style="padding: 0.5u 0.6u; gap: 0.2u">
  <h2 id="t">Shapes</h2><div id="view" class="grow"></div>
  <world><sphere id="s" r="1"></sphere></world><camera focus="view"></camera>
</beat>
</beats>"""


@pytest.mark.skipif(not (HAS_MANIM and HAS_CHROMIUM), reason="needs manimgl + Chromium")
def test_scene_that_only_fails_after_the_previous_one_is_caught(tmp_path):
    assert check_runtime(S2, tmp_path, "S2") == []
    problems = check_runtime(S2, tmp_path, "S2", prelude_html=S1)
    assert any('id="s" is a <sphere> here but a <surface> in an earlier beat' in p for p in problems)
    assert any(p.startswith("beat 0:") for p in problems)          # this scene's own numbering
    assert problems[-1].startswith("note: this scene was played the way it renders")
    assert '<surface id="s"' in problems[-1]                       # Agent 3 sees what it continues from


@pytest.mark.skipif(not (HAS_MANIM and HAS_CHROMIUM), reason="needs manimgl + Chromium")
def test_compatible_scenes_pass_with_prelude(tmp_path):
    ok = S2.replace('id="s" r="1"', 'id="ball" r="1"')
    assert check_runtime(ok, tmp_path, "S2", prelude_html=S1) == []


def test_beat_numbers_skip_the_carried_over_frame():
    assert _renumber("beat 3: #x sticks out") == "beat 2: #x sticks out"
    assert _renumber("beat 0 <tex id=f>: bad") == "the opening frame (previous scene's last beat) <tex id=f>: bad"
    assert "<beat vo=\"A bowl.\"" in continuity_note(S1)


def test_run_staging_checks_with_the_previous_scenes_beats(monkeypatch, tmp_path):
    import konvey.stage.check as check
    from konvey.pipeline import run_staging
    from konvey.schemas import Scene

    seen = {}
    monkeypatch.setattr(check, "check_runtime",
                        lambda html, d, sid, prelude_html=None: seen.update(prelude=prelude_html) or [])
    scene = Scene.model_validate({
        "id": "S2", "purpose": "build", "duration_sec": 5, "vo_script": ["A ball."],
        "beats": [{"vo_line": "A ball.", "objects": [], "animation": {"type": "FadeIn", "code_hint": "", "run_time": 1}}]})

    class Agent:
        def run(self, prompt):
            return type("R", (), {"content": S2})()

    run_staging(scene, Agent(), check_dir=tmp_path, prelude=lambda: S1)
    assert seen["prelude"] == S1


def test_pipeline_checks_scenes_in_order_each_after_the_previous(monkeypatch, tmp_path):
    """Writing is parallel (S1 is made the slowest), runtime checks still go S1 -> S2 -> S3."""
    import json
    import re
    import time

    import konvey.pipeline as pipe
    import konvey.stage.check as check
    from konvey.pipeline import PipelineConfig, run_pipeline

    examples = Path(__file__).resolve().parent / "fixtures" / "examples" / "example-01-mlp-facts"
    a1 = (examples / "agent1-output.json").read_text()
    # a Manim-era plan: bare-string objects become stage objects (StagePlan has no bare strings)
    plan = json.loads((examples / "agent2-output.json").read_text())
    for scene in plan["scenes"]:
        for beat in scene["beats"]:
            beat["objects"] = [{"id": o, "kind": "text", "source": "visual"} if isinstance(o, str) else o
                               for o in beat["objects"]]
    a2 = json.dumps(plan)

    class Resp:
        def __init__(self, content):
            self.content = content

    class Stub:
        model = None

        def __init__(self, content=None):
            self.content = content

        def run(self, prompt, *a, **k):
            if self.content is not None:
                return Resp(self.content)
            spec = json.loads(re.search(r"Input SCENE_SPEC: (\{.*\})\n", prompt).group(1))
            if spec["id"] == "S1":
                time.sleep(0.5)
            beats = "".join(f'<beat vo="{b["vo_line"]}"><h2 id="t">{spec["id"]}</h2></beat>' for b in spec["beats"])
            return Resp(f"<beats>{beats}</beats>")

    stubs = {"knowledge": Stub(a1), "planning": Stub(a2), "coding": Stub()}
    calls = []
    monkeypatch.setattr(pipe, "_make_agent", lambda name, config, mode=None: stubs[name])
    monkeypatch.setattr(pipe, "probe_available", lambda: True)
    monkeypatch.setattr(pipe, "_stage_check_available", lambda: True)
    monkeypatch.setattr(check, "check_static", lambda html, scene: [])
    monkeypatch.setattr(check, "check_runtime",
                        lambda html, d, sid, prelude_html=None: calls.append((sid, html, prelude_html)) or [])
    warmed = []   # the directors' prompt is cached once, before any scene is written
    monkeypatch.setattr(pipe, "warm_cache", lambda c, *a: warmed.append(len(calls)))
    result = run_pipeline(PipelineConfig(user_prompt="Where do facts live?", out_dir=str(tmp_path / "o"),
                                         grounded=False, verbose=False))
    assert warmed == [0]
    html = {s.scene_id: s.code for s in result.scenes}
    assert [c[0] for c in calls] == ["S1", "S2", "S3"]
    assert calls[0][2] is None and calls[1][2] == html["S1"] and calls[2][2] == html["S2"]
