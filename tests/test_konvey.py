"""Tests for the Konvey Agno pipeline (all offline, no API keys).

Ground truth: examples/*/agent{1,2}-output.json + agent3-S*.py.
"""

import copy
import json
from pathlib import Path

import pytest

from konvey.pipeline import build_workflow, run_dry_run
from konvey.prompts import build_agent_instructions, load_agent_template
from konvey.schemas import KnowledgePack, ScenePlan
from konvey.validators import (
    ValidationError,
    extract_json,
    normalize_spatial_relation,
    validate_knowledge_pack,
    validate_manim_code,
    validate_scene_plan,
)

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _load(name: str, fname: str):
    return json.loads((EXAMPLES / name / fname).read_text(encoding="utf-8"))


# --- Agent 1 ---------------------------------------------------------------

STRICT_A1_EXAMPLES = [
    "example-01-mlp-facts",
    "example-02-attention-adjectives",
    "example-04-clt-galton-board",
    "example-05-discrete-convolution-dice",
    "example-06-shadows-cube-average",
]


@pytest.mark.parametrize("name", STRICT_A1_EXAMPLES)
def test_agent1_ground_truth_passes(name):
    kp = validate_knowledge_pack(_load(name, "agent1-output.json"))
    assert isinstance(kp, KnowledgePack)
    assert kp.core_claim and len(kp.mechanism_steps) >= 3


def test_agent1_example03_is_prenormalization_paper_trace():
    """Example-03 carries raw paper relations (contains/stands near); the
    strict gate must reject them — Agent 2 normalizes (see its README)."""
    with pytest.raises(ValidationError, match="relation"):
        validate_knowledge_pack(_load("example-03-elara-paper-adaptation", "agent1-output.json"))


def test_agent1_rejects_open_relation():
    bad = _load("example-01-mlp-facts", "agent1-output.json")
    bad["knowledge_triples"] = [["MLP", "remembers", "facts"]]
    with pytest.raises(ValidationError, match="remembers"):
        validate_knowledge_pack(bad)


def test_agent1_rejects_thin_mechanism():
    bad = _load("example-01-mlp-facts", "agent1-output.json")
    bad["mechanism_steps"] = ["one step"]
    with pytest.raises(ValidationError, match="mechanism_steps"):
        validate_knowledge_pack(bad)


# --- Agent 2 ---------------------------------------------------------------

ALL_A2 = [
    "example-01-mlp-facts",
    "example-02-attention-adjectives",
    "example-03-elara-paper-adaptation",
    "example-04-clt-galton-board",
    "example-05-discrete-convolution-dice",
    "example-06-shadows-cube-average",
]


@pytest.mark.parametrize("name", ALL_A2)
def test_agent2_ground_truth_passes(name):
    plan = validate_scene_plan(_load(name, "agent2-output.json"))
    assert isinstance(plan, ScenePlan)
    assert [s.id for s in plan.scenes] == ["S1", "S2", "S3"]


def test_agent2_rejects_broken_precedes():
    bad = _load("example-01-mlp-facts", "agent2-output.json")
    bad["scenes"][2]["precedes"] = "S1"
    with pytest.raises(ValidationError, match="precedes"):
        validate_scene_plan(bad)


def test_agent2_rejects_duration_mismatch():
    bad = _load("example-01-mlp-facts", "agent2-output.json")
    for s in bad["scenes"]:
        s["duration_sec"] = 5
    with pytest.raises(ValidationError, match="durations sum"):
        validate_scene_plan(bad, target_duration_sec=90.0)


def test_agent2_rejects_unknown_animation():
    bad = _load("example-01-mlp-facts", "agent2-output.json")
    bad["scenes"][0]["beats"][0]["animation"]["type"] = "QuantumSparkle"
    with pytest.raises(ValidationError, match="QuantumSparkle"):
        validate_scene_plan(bad)


def test_agent2_rejects_bad_layout_op():
    bad = _load("example-01-mlp-facts", "agent2-output.json")
    bad["scenes"][0]["beats"][0]["layout"][0]["op"] = "teleport"
    with pytest.raises(ValidationError, match="teleport"):
        validate_scene_plan(bad)


def test_agent2_rejects_predicate_without_layout():
    bad = _load("example-01-mlp-facts", "agent2-output.json")
    bad["scenes"][0]["beats"][0]["layout"] = []
    with pytest.raises(ValidationError, match="layout"):
        validate_scene_plan(bad)


def test_normalize_spatial_relation_paper_sec32():
    assert normalize_spatial_relation("contains") == "on top of"
    assert normalize_spatial_relation("stands near") == "at left of"
    assert normalize_spatial_relation("sits atop") == "on top of"
    assert normalize_spatial_relation("above") == "above"


# --- Agent 3 ---------------------------------------------------------------

def _all_code_files():
    return sorted(EXAMPLES.glob("*/agent3-*.py"))


def test_agent3_ground_truth_passes():
    files = _all_code_files()
    assert len(files) >= 10
    for f in files:
        assert validate_manim_code(f.read_text(encoding="utf-8"))


def test_agent3_allows_self_check_comment():
    """CoT prompt mandates '# ... no forbidden APIs (ImageMobject...)' comments."""
    code = (
        "from manim_imports_ext import *\n"
        "class SingleScene(InteractiveScene):\n"
        "    def construct(self):\n"
        "        # 4. Self-check: no forbidden APIs (ImageMobject/external/torch)?\n"
        "        # VO: hello\n"
        "        self.play(Write(Text('hi')))\n"
        "        self.wait()\n"
    )
    assert validate_manim_code(code)


def test_agent3_rejects_real_imagemobject():
    code = (
        "from manim_imports_ext import *\n"
        "class SingleScene(InteractiveScene):\n"
        "    def construct(self):\n"
        "        # VO: hello\n"
        "        self.add(ImageMobject('pic.png'))\n"
        "        self.wait()\n"
    )
    with pytest.raises(ValidationError, match="ImageMobject"):
        validate_manim_code(code)


def test_agent3_rejects_torch_and_missing_vo():
    code = (
        "from manim_imports_ext import *\n"
        "import torch\n"
        "class SingleScene(InteractiveScene):\n"
        "    def construct(self):\n"
        "        # VO: hello\n"
        "        self.wait()\n"
    )
    with pytest.raises(ValidationError, match="torch"):
        validate_manim_code(code)

    no_vo = (
        "from manim_imports_ext import *\n"
        "class SingleScene(InteractiveScene):\n"
        "    def construct(self):\n"
        "        self.wait()\n"
    )
    with pytest.raises(ValidationError, match="# VO:"):
        validate_manim_code(no_vo)


def test_agent3_rejects_movetotarget_without_target():
    code = (
        "from manim_imports_ext import *\n"
        "class SingleScene(InteractiveScene):\n"
        "    def construct(self):\n"
        "        # VO: hello\n"
        "        self.play(MoveToTarget(m))\n"
        "        self.wait()\n"
    )
    with pytest.raises(ValidationError, match="generate_target"):
        validate_manim_code(code)


# --- JSON extraction -------------------------------------------------------

def test_extract_json_fences_and_tags():
    payload = {"a": 1}
    assert extract_json("```json\n" + json.dumps(payload) + "\n```") == payload
    assert extract_json("<reasoning>hmm</reasoning><output_json>" + json.dumps(payload) + "</output_json>") == payload
    assert extract_json(json.dumps(payload)) == payload


# --- Prompts ---------------------------------------------------------------

def test_prompt_templates_load():
    for agent in (1, 2, 3):
        for mode in ("few-shot", "zero-shot", "cot"):
            assert load_agent_template(agent, "generic", mode)
    for s in ("set-01-mlp-facts", "set-02-clt-galton-board", "set-03-shadows-cube"):
        for agent in (1, 2, 3):
            assert load_agent_template(agent, s, "few-shot")  # type: ignore[arg-type]
    instructions = build_agent_instructions(2, "set-01-mlp-facts", "few-shot")
    assert "LaggedStartMap" in instructions  # authority refs appended


# --- Model config ----------------------------------------------------------

def test_resolve_model_defaults_to_minimax(monkeypatch):
    from agno.models.minimax import MiniMax

    from konvey.agents import (
        create_coding_agent,
        create_knowledge_agent,
        create_planning_agent,
        resolve_model,
    )

    monkeypatch.setenv("MINIMAX_API_KEY", "dummy")
    monkeypatch.setenv("KONVEY_MODEL_ID", "MiniMax-M3")
    model = resolve_model()
    assert isinstance(model, MiniMax)
    assert model.id == "MiniMax-M3"
    # Factories wire the resolved model into all three agents (no network here).
    assert isinstance(create_knowledge_agent().model, MiniMax)
    assert isinstance(create_planning_agent().model, MiniMax)
    assert isinstance(create_coding_agent().model, MiniMax)


def test_resolve_model_explicit_passthrough():
    from konvey.agents import resolve_model

    assert resolve_model("openai:gpt-4o-mini") == "openai:gpt-4o-mini"


# --- Prompts filled with real data ---------------------------------------

def _fill(template: str, mapping: dict) -> str:
    for key, value in mapping.items():
        template = template.replace(key, value)
    return template


def test_prompts_fill_with_example01_data():
    """Every prompt template must accept real pipeline data with no
    leftover placeholders (USER_PROMPT -> KNOWLEDGE_PACK -> SCENE_SPEC)."""
    knowledge = (EXAMPLES / "example-01-mlp-facts" / "agent1-output.json").read_text(encoding="utf-8")
    plan = json.loads((EXAMPLES / "example-01-mlp-facts" / "agent2-output.json").read_text(encoding="utf-8"))
    scene_spec = json.dumps(plan["scenes"][0])
    user_prompt = "Where do facts live in an LLM?"
    sets = ["generic", "set-01-mlp-facts", "set-02-clt-galton-board", "set-03-shadows-cube"]

    for s in sets:
        filled1 = _fill(load_agent_template(1, s, "few-shot"), {"{USER_PROMPT}": user_prompt})  # type: ignore[arg-type]
        assert "{USER_PROMPT}" not in filled1 and user_prompt in filled1

        filled2 = _fill(
            load_agent_template(2, s, "few-shot"),  # type: ignore[arg-type]
            {"{KNOWLEDGE_PACK}": knowledge, "{DURATION_SEC, default 90}": "90"},
        )
        assert "{KNOWLEDGE_PACK}" not in filled2 and "MLPs act as key-value memories" in filled2

        filled3 = _fill(load_agent_template(3, s, "few-shot"), {"{SCENE_SPEC}": scene_spec})  # type: ignore[arg-type]
        assert "{SCENE_SPEC}" not in filled3 and "LaggedStartMap" in filled3


# --- Progress output (stub agents, no network) ------------------------------

def test_run_pipeline_progress_output(tmp_path, capsys, monkeypatch):
    import konvey.pipeline as pipe
    from konvey.pipeline import PipelineConfig, run_pipeline

    a1 = (EXAMPLES / "example-01-mlp-facts" / "agent1-output.json").read_text(encoding="utf-8")
    a2 = (EXAMPLES / "example-01-mlp-facts" / "agent2-output.json").read_text(encoding="utf-8")
    code = (EXAMPLES / "example-01-mlp-facts" / "agent3-S1.py").read_text(encoding="utf-8")

    class _Resp:
        def __init__(self, content):
            self.content = content

    class _StubAgent:
        def __init__(self, content):
            self.content = content
            self.model = None

        def run(self, *args, **kwargs):
            return _Resp(self.content)

    stubs = {"knowledge": _StubAgent(a1), "planning": _StubAgent(a2), "coding": _StubAgent(code)}
    monkeypatch.setattr(pipe, "_with_cot_retry", lambda name, config: stubs[name])

    result = run_pipeline(PipelineConfig(user_prompt="Where do facts live?", out_dir=str(tmp_path / "live")))
    assert [s.scene_id for s in result.scenes] == ["S1", "S2", "S3"]
    out = capsys.readouterr().out
    for marker in ("[1/4] Agent 1", "[2/4] Agent 2", "[3/4] Agent 3",
                   "S1 done", "S2 done", "S3 done", "[4/4] Done."):
        assert marker in out, f"missing progress marker {marker!r} in:\n{out}"


# --- Dry run + workflow construction ---------------------------------------

def test_dry_run_example01(tmp_path):
    result = run_dry_run(EXAMPLES / "example-01-mlp-facts", tmp_path / "dry")
    assert [s.scene_id for s in result.scenes] == ["S1", "S2", "S3"]
    assert (tmp_path / "dry" / "agent1-output.json").exists()
    assert (tmp_path / "dry" / "agent3-S1.py").exists()


def test_build_workflow_structure():
    from konvey.pipeline import PipelineConfig

    wf = build_workflow(PipelineConfig(user_prompt="Where do facts live in an LLM?"))
    names: list[str] = []

    def collect(steps):
        for st in steps:
            name = getattr(st, "name", type(st).__name__)
            names.append(name)
            for attr in ("steps", "_steps", "sub_steps"):
                sub = getattr(st, attr, None)
                if sub:
                    collect(sub if isinstance(sub, list) else list(sub))

    collect(wf.steps)
    flat = " ".join(names)
    for expected in ("Knowledge", "Validate knowledge", "Planning", "Validate plan",
                     "Code S1", "Code S2", "Code S3", "Assemble"):
        assert expected in flat, f"{expected} missing from workflow: {names}"
