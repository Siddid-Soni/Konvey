"""Streamed agent turns (`konvey.pipeline._streamed`) and what they cost (`konvey.cost.track`).

A streamed call's deltas carry no token metrics; only the run output ending the stream does.
These tests pin that cost, the fallback for an agent that cannot stream, and the progress
events `run_pipeline` reports through `PipelineConfig.on_event`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from agno.run.agent import RunOutput
from pydantic import BaseModel

from konvey.cost import CostLog, track
from konvey.pipeline import PipelineConfig, _emit, _streamed, run_pipeline

MODEL = "glm-5.3-flash"


def usage(inp=1000, out=200):
    return SimpleNamespace(input_tokens=inp, output_tokens=out, cache_read_tokens=0,
                           cache_write_tokens=0, reasoning_tokens=0)


def delta(text):
    """A streamed chunk the way agno sends it: content only, no metrics."""
    return type("Ev", (), {"content": text})()


def run_output(content=None):
    """The RunOutput that ends a stream: the whole run, with its messages and tokens."""
    return RunOutput(content=content, messages=[SimpleNamespace(role="assistant", metrics=usage())],
                     metrics=usage())


@pytest.fixture(autouse=True)
def streaming_on(monkeypatch):
    monkeypatch.delenv("KONVEY_STREAM", raising=False)


class Tiny(BaseModel):
    answer: str
    count: int


class StreamingAgent:
    """Streams only: a non-streaming call is a bug (it would report no tokens at all)."""

    model = SimpleNamespace(id=MODEL)

    def __init__(self, final="Alpha beta"):
        self.final = final

    def run(self, prompt, stream=False, yield_run_output=False):
        if not (stream and yield_run_output):
            raise AssertionError("a streamed agent must be called with stream=True")
        return iter([delta("Alpha "), delta("beta"), run_output(self.final)])


def test_a_streamed_call_is_priced_once(monkeypatch, tmp_path):
    log = CostLog()
    log.out_dir = tmp_path
    agent = track(StreamingAgent(), log, "A2")

    assert _streamed(agent, "go").content == "Alpha beta"
    assert len(log.requests) == 1                     # the terminal RunOutput, priced once
    assert log.requests[0]["agent"] == "A2"
    assert log.requests[0]["usd"] is not None and log.requests[0]["usd"] > 0
    assert json.loads((tmp_path / "cost.json").read_text())["total"]["usd"] > 0


def test_plain_and_stream_disabled_calls_are_priced(monkeypatch, tmp_path):
    class Plain:
        model = SimpleNamespace(id=MODEL)

        def __init__(self):
            self.prompts = []

        def run(self, prompt, *a, **k):
            assert not k.get("stream")
            self.prompts.append(prompt)
            return SimpleNamespace(messages=[SimpleNamespace(role="assistant", metrics=usage())])

    log = CostLog()
    log.out_dir = tmp_path
    agent = track(Plain(), log, "Agent 1")
    monkeypatch.setenv("KONVEY_STREAM", "0")
    _streamed(agent, "go")                            # disabled: one plain call, still priced
    agent.run("again")                                # a repair is a second request
    assert agent.prompts == ["go", "again"]
    assert [r["agent"] for r in log.requests] == ["Agent 1", "Agent 1"]
    assert all(r["usd"] is not None for r in log.requests)


def test_text_deltas_are_concatenated_and_not_duplicated():
    class TextAgent:
        def __init__(self, final):
            self.final = final

        def run(self, prompt, **kw):
            return iter([delta("Alpha "), delta("beta"), run_output(self.final)])

    seen = []
    assert _streamed(TextAgent("Alpha beta"), "go", seen.append).content == "Alpha beta"
    assert "".join(seen) == "Alpha beta"              # the live view saw the text
    # a stream that ends without content still has its deltas
    assert _streamed(TextAgent(None), "go").content == "Alpha beta"


def test_schema_agents_return_json_text():
    class SchemaAgent:
        def __init__(self, value):
            self.value = value

        def run(self, prompt, **kw):
            return iter([delta("ignored"), run_output(self.value)])

    parsed = _streamed(SchemaAgent(Tiny(answer="x", count=2)), "go")
    assert json.loads(parsed.content) == {"answer": "x", "count": 2}
    mapping = _streamed(SchemaAgent({"answer": "y", "count": 3}), "go")
    assert json.loads(mapping.content) == {"answer": "y", "count": 3}


def test_an_agent_without_a_stream_kwarg_gets_the_plain_path():
    class NoStream:
        def __init__(self):
            self.calls = []

        def run(self, prompt):
            self.calls.append(prompt)
            return SimpleNamespace(content="ok")

    agent = NoStream()
    assert _streamed(agent, "go").content == "ok"
    assert agent.calls == ["go"]                      # the rejected signature, then one plain call


def test_a_type_error_from_inside_a_streamed_call_is_not_retried():
    class Exploding:
        def __init__(self):
            self.plain = 0

        def run(self, prompt, **kw):
            if kw:
                self._inner()                         # dies mid-call, after the prompt was sent
            self.plain += 1
            return SimpleNamespace(content="ok")

        def _inner(self):
            raise TypeError("the reply could not be parsed")

    agent = Exploding()
    with pytest.raises(TypeError):
        _streamed(agent, "go")
    assert agent.plain == 0                           # never paid for the prompt twice


def test_emit_swallows_a_sink_that_raises():
    seen = []

    def sink(kind, **data):
        seen.append((kind, data))
        raise RuntimeError("the event store is unavailable")

    _emit(PipelineConfig(user_prompt="x", on_event=sink), "run.start", prompt="x", model=MODEL)
    assert seen[0][0] == "run.start" and seen[0][1]["model"] == MODEL
    _emit(PipelineConfig(user_prompt="x"), "run.start")   # no sink at all is fine too


def test_run_pipeline_emits_the_documented_events(monkeypatch, tmp_path):
    import konvey.pipeline as pipe
    import konvey.stage.check as check

    examples = Path(__file__).resolve().parent / "fixtures" / "examples" / "example-01-mlp-facts"
    knowledge = (examples / "agent1-output.json").read_text()
    plan = json.loads((examples / "agent2-output.json").read_text())
    for scene in plan["scenes"]:                       # the plan fixture predates typed objects
        for beat in scene["beats"]:
            beat["objects"] = [{"id": o, "kind": "text", "source": "visual"} if isinstance(o, str) else o
                               for o in beat["objects"]]

    class Reply:
        def __init__(self, content):
            self.content = content

    class FakeAgent:
        model = SimpleNamespace(id="a-neutral-model")

        def __init__(self, content=None):
            self.content = content

        def run(self, prompt, *a, **k):
            if self.content is not None:
                return Reply(self.content)
            spec = json.loads(re.search(r"Input SCENE_SPEC: (\{.*\})\n", prompt).group(1))
            beats = "".join(f'<beat vo="{b["vo_line"]}"></beat>' for b in spec["beats"])
            return Reply(f"<beats>{beats}</beats>")

    agents = {"knowledge": FakeAgent(knowledge), "planning": FakeAgent(json.dumps(plan)),
              "coding": FakeAgent()}
    monkeypatch.setattr(pipe, "_make_agent", lambda name, config, mode=None: agents[name])
    monkeypatch.setattr(pipe, "probe_available", lambda: True)
    monkeypatch.setattr(pipe, "_stage_check_available", lambda: True)
    monkeypatch.setattr(check, "check_static", lambda html, scene: [])
    monkeypatch.setattr(check, "check_runtime", lambda html, d, sid, prelude_html=None: [])

    events = []
    run_pipeline(PipelineConfig(user_prompt="How does a queue drain?", out_dir=str(tmp_path / "run"),
                                grounded=False, verbose=False,
                                on_event=lambda kind, **data: events.append({"type": kind, **data})))

    kinds = [e["type"] for e in events]
    assert kinds[0] == "run.start" and events[0]["model"] == "a-neutral-model"
    assert kinds[-1] == "run.scenes_done"
    assert all(isinstance(k, str) for k in kinds)
    requested = [e["agent"] for e in events if e["type"] == "agent.request"]
    assert requested[:2] == ["Agent 1", "Agent 2"]
    assert all(sid in requested for sid in ("S1", "S2", "S3"))
    first_scene = min(i for i, k in enumerate(kinds) if k.startswith("scene."))
    assert kinds.index("plan.ready") < first_scene
    for sid in ("S1", "S2", "S3"):
        states = [e["state"] for e in events if e["type"] == "scene.state" and e["scene"] == sid]
        assert states == ["writing", "done"]
