"""konvey.lean: 2-agent (Researcher -> 3 directors) and 1-agent (Solo) stage pipelines, stub agents."""

from __future__ import annotations

import json
import re

import pytest

import konvey.lean as lean
import konvey.pipeline as pipe
from konvey.pipeline import PipelineConfig
from tests.test_walkthrough import KNOWLEDGE, _plan


class Resp:
    def __init__(self, content):
        self.content = content


class Stub:
    model = None

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def run(self, prompt, *a, **k):
        self.prompts.append(prompt)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return Resp(reply(prompt) if callable(reply) else reply)


def beats_for(scene: dict) -> str:
    body = "".join(f'<beat vo="{b["vo_line"]}"><array id="pair" values="{",".join(map(str, b["objects"][0]["data"]["values"]))}"/></beat>'
                   for b in scene["beats"])
    return f"<beats>{body}</beats>"


def research_json(plan=None) -> str:
    return json.dumps({"knowledge": KNOWLEDGE, "plan": plan or _plan()})


def config(tmp_path, **kw) -> PipelineConfig:
    return PipelineConfig(user_prompt="How does repeated remainder find a common divisor?",
                          out_dir=str(tmp_path / "o"), probe=False, verbose=False,
                          duration_sec=90, grounded=False, **kw)


def test_prompts_wrap_the_shared_agent_instructions():
    c = PipelineConfig(user_prompt="x")
    r = lean.researcher_instructions(c)
    s = lean.solo_instructions(c)
    assert "{agent1}" not in r and "{agent2}" not in r and "{agent3}" not in s
    assert "Agent2-Planner" in r and "walkthrough" in r and '"knowledge"' in r
    assert "Agent3-StageDirector" in s and "<research>" in s


def test_two_agent_runs_research_once_then_three_directors(tmp_path, monkeypatch):
    researcher = Stub([research_json()])

    def director(prompt):
        spec = json.loads(re.search(r"Input SCENE_SPEC: (\{.*\})\n", prompt).group(1))
        return beats_for(spec)

    directors = Stub([director])
    monkeypatch.setitem(lean._AGENT_MAKERS, "researcher", lambda c, **k: researcher)
    monkeypatch.setattr(pipe, "_make_agent", lambda name, c, mode=None: directors)
    result = lean.run_lean(config(tmp_path), agents=2)
    assert [s.scene_id for s in result.scenes] == ["S1", "S2", "S3"] and not result.rejected
    assert len(researcher.prompts) == 1 and len(directors.prompts) == 3
    out = tmp_path / "o"
    assert (out / "agent3-S2.html").exists() and (out / "agent1-output.json").exists()
    timings = json.loads((out / "timings.json").read_text())
    assert timings["agents"] == 2 and timings["model_calls"] == 4


def test_researcher_repair_names_the_failing_part(tmp_path, monkeypatch):
    bad = _plan()
    bad["scenes"] = bad["scenes"][:2]
    researcher = Stub([json.dumps({"knowledge": KNOWLEDGE, "plan": bad}), research_json()])
    monkeypatch.setitem(lean._AGENT_MAKERS, "researcher", lambda c, **k: researcher)
    c = config(tmp_path)
    kp, plan = lean.run_research(c, lean._Clock())
    assert len(plan.scenes) == 3 and len(researcher.prompts) == 2
    assert "in `plan`" in researcher.prompts[1] and "REJECTED" in researcher.prompts[1]


def solo_reply(plan=None, skip=()) -> str:
    plan = plan or _plan()
    scenes = "".join(f'<scene id="{s["id"]}">\n{beats_for(s)}\n</scene>\n'
                     for s in plan["scenes"] if s["id"] not in skip)
    return f"<research>\n{research_json(plan)}\n</research>\n{scenes}"


def test_parse_solo_splits_blocks_and_tolerates_missing_ones():
    research, html = lean.parse_solo("chatter\n" + solo_reply(skip=("S3",)))
    assert json.loads(research)["plan"]["title"] == "gcd"
    assert sorted(html) == ["S1", "S2"] and html["S1"].startswith("<beats>")
    assert lean.parse_solo('<scene id="S2">only</scene>') == (None, {"S2": ""})


def test_one_agent_repairs_only_the_missing_scene(tmp_path, monkeypatch):
    plan = _plan()
    s3 = plan["scenes"][2]
    solo = Stub([solo_reply(skip=("S3",)), f'<scene id="S3">{beats_for(s3)}</scene>'])
    monkeypatch.setitem(lean._AGENT_MAKERS, "solo", lambda c, **k: solo)
    result = lean.run_lean(config(tmp_path), agents=1)
    assert not result.rejected and len(solo.prompts) == 2
    assert "[S3]" in solo.prompts[1] and "[S1]" not in solo.prompts[1]
    assert {s.scene_id: bool(s.code) for s in result.scenes} == {"S1": True, "S2": True, "S3": True}
    assert json.loads((tmp_path / "o" / "timings.json").read_text())["model_calls"] == 2


def test_one_agent_raises_when_research_never_validates(tmp_path, monkeypatch):
    solo = Stub(['<scene id="S1"><beats></beats></scene>'])
    monkeypatch.setitem(lean._AGENT_MAKERS, "solo", lambda c, **k: solo)
    with pytest.raises(lean.ValidationError, match="research"):
        lean.run_lean(config(tmp_path, repair_rounds=1), agents=1)


def test_narration_mode_reaches_the_lean_prompts():
    from konvey.speech.narrate import narration_mode

    c = PipelineConfig(user_prompt="x")
    with narration_mode():
        solo, research = lean.solo_instructions(c), lean.researcher_instructions(c)
    assert "narration mode" in research and "Narration mode: no subtitles" in solo
    assert "narration mode" not in lean.researcher_instructions(c)   # restored afterwards


def test_directors_cache_is_warmed_only_for_caching_models(tmp_path, monkeypatch):
    class Model:
        def __init__(self, id):
            self.id = id

    for model_id, warmed in (("deepseek-v4.1-flash", True), ("claude-haiku-5-5", True), ("glm-5.3", False)):
        stub = Stub(["OK"])
        stub.model = Model(model_id)
        monkeypatch.setattr(pipe, "_make_agent", lambda name, c, mode=None: stub)
        clock = lean._Clock()
        pipe.warm_cache(config(tmp_path), lambda agent: lean._counting(agent, clock))
        assert (stub.prompts == [pipe.WARM_UP]) == warmed and clock.calls == int(warmed)
