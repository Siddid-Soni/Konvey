"""Tests for the Konvey Agno pipeline (all offline, no API keys).

Ground truth: tests/fixtures/examples/*/agent{1,2}-output.json (hand-written examples from
the Manim era; their extra plan fields are ignored).
"""

import copy
import json
from pathlib import Path

import pytest

from konvey.prompts import build_agent_instructions, load_agent1_template
from konvey.schemas import KnowledgePack, ScenePlan
from konvey.validators import (
    ValidationError,
    extract_json,
    validate_knowledge_pack,
    validate_scene_plan,
)

EXAMPLES = Path(__file__).resolve().parent / "fixtures" / "examples"


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


# --- JSON extraction -------------------------------------------------------

def test_extract_json_fences_and_tags():
    payload = {"a": 1}
    assert extract_json("```json\n" + json.dumps(payload) + "\n```") == payload
    assert extract_json("<reasoning>hmm</reasoning><output_json>" + json.dumps(payload) + "</output_json>") == payload
    assert extract_json(json.dumps(payload)) == payload


# --- Prompts ---------------------------------------------------------------

def test_prompt_templates_load():
    for mode in ("few-shot", "zero-shot", "cot"):
        assert load_agent1_template(mode)
    for agent in (1, 2, 3):
        assert "{{" not in build_agent_instructions(agent)  # display docs filled in


# --- Model config ----------------------------------------------------------

def test_resolve_model_defaults_to_minimax(monkeypatch):
    from agno.models.minimax import MiniMax

    from konvey.agents import (
        create_coding_agent,
        create_knowledge_agent,
        create_planning_agent,
        resolve_model,
    )

    monkeypatch.delenv("KONVEY_PROVIDER", raising=False)
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    monkeypatch.setattr("konvey.agents.load_dotenv", lambda: None)
    monkeypatch.setenv("MINIMAX_API_KEY", "dummy")
    monkeypatch.setenv("KONVEY_MODEL_ID", "MiniMax-M3")
    model = resolve_model()
    assert isinstance(model, MiniMax)
    assert model.id == "MiniMax-M3"
    # Factories wire the resolved model into all three agents (no network here).
    assert isinstance(create_knowledge_agent().model, MiniMax)
    assert isinstance(create_planning_agent().model, MiniMax)
    assert isinstance(create_coding_agent().model, MiniMax)


def test_resolve_model_opencode(monkeypatch):
    from agno.models.openai.like import OpenAILike

    from konvey.agents import resolve_model

    monkeypatch.setattr("konvey.agents.load_dotenv", lambda: None)
    monkeypatch.delenv("OPENCODE_BASE_URL", raising=False)
    monkeypatch.delenv("OPENCODE_MODEL_ID", raising=False)
    monkeypatch.setenv("KONVEY_MODEL_ID", "MiniMax-M3")  # minimax id must not leak
    monkeypatch.setenv("KONVEY_PROVIDER", "opencode")
    monkeypatch.setenv("OPENCODE_API_KEY", "dummy")
    model = resolve_model()
    assert isinstance(model, OpenAILike)
    assert model.base_url == "https://opencode.ai/inference/v1"
    assert model.id == "glm-5.3"
    assert model.default_headers["x-opencode-session"]
    assert model.supports_native_structured_outputs is False


def test_resolve_model_deepseek_resends_reasoning(monkeypatch):
    from agno.models.message import Message

    from konvey.agents import ReasoningOpenAILike, resolve_model

    monkeypatch.setattr("konvey.agents.load_dotenv", lambda: None)
    monkeypatch.setenv("KONVEY_PROVIDER", "opencode-go")
    monkeypatch.setenv("OPENCODE_API_KEY", "dummy")
    monkeypatch.setenv("OPENCODE_MODEL_ID", "deepseek-v4.1-flash")
    model = resolve_model()
    assert isinstance(model, ReasoningOpenAILike)
    # thinking mode rejects a tool-call turn whose reasoning is not sent back
    turn = model._format_message(Message(role="assistant", content="", reasoning_content="think"))
    assert turn["reasoning_content"] == "think"
    assert "reasoning_content" not in model._format_message(Message(role="user", content="hi"))


def test_resolve_model_opencode_gemini(monkeypatch):
    from agno.models.google import Gemini

    from konvey.agents import resolve_model

    monkeypatch.setattr("konvey.agents.load_dotenv", lambda: None)
    monkeypatch.delenv("OPENCODE_BASE_URL", raising=False)
    monkeypatch.setenv("KONVEY_PROVIDER", "opencode-go")
    monkeypatch.setenv("OPENCODE_API_KEY", "dummy")
    monkeypatch.setenv("OPENCODE_MODEL_ID", "gemini-4-argon-contributor")
    model = resolve_model()
    assert isinstance(model, Gemini)
    assert model.id == "gemini-4-argon-contributor"
    http = model.client_params["http_options"]
    assert http["base_url"] == "https://opencode.ai/inference/go/"
    assert http["api_version"] == "v1"
    assert http["headers"]["x-opencode-session"]
    assert http["headers"]["User-Agent"] == "opencode/latest/2.0.32/cli"


def test_resolve_model_opencode_go_default_is_muse_responses(monkeypatch):
    from agno.models.openai.open_responses import OpenResponses

    from konvey.agents import resolve_model

    monkeypatch.setattr("konvey.agents.load_dotenv", lambda: None)
    monkeypatch.delenv("OPENCODE_BASE_URL", raising=False)
    monkeypatch.delenv("OPENCODE_MODEL_ID", raising=False)
    monkeypatch.setenv("KONVEY_PROVIDER", "opencode-go")
    monkeypatch.setenv("OPENCODE_API_KEY", "dummy")
    model = resolve_model()
    assert isinstance(model, OpenResponses)
    assert model.id == "muse-spark-1.3-contributor"
    assert model.base_url == "https://opencode.ai/inference/go/v1"
    assert model.store is False
    assert model.default_headers["x-opencode-session"]


def test_resolve_model_opencode_auto_selected(monkeypatch):
    from konvey.agents import resolve_model

    monkeypatch.setattr("konvey.agents.load_dotenv", lambda: None)
    monkeypatch.delenv("KONVEY_PROVIDER", raising=False)
    monkeypatch.setenv("OPENCODE_API_KEY", "dummy")
    monkeypatch.setenv("OPENCODE_MODEL_ID", "kimi-k3")
    model = resolve_model()
    assert model.provider == "OpenCode" and model.id == "kimi-k3"


def test_resolve_model_inception(monkeypatch):
    from agno.models.openai.like import OpenAILike

    from konvey.agents import resolve_model

    monkeypatch.setattr("konvey.agents.load_dotenv", lambda: None)
    monkeypatch.delenv("INCEPTION_MODEL_ID", raising=False)
    monkeypatch.delenv("INCEPTION_BASE_URL", raising=False)
    monkeypatch.delenv("KONVEY_EFFORT", raising=False)
    monkeypatch.setenv("KONVEY_PROVIDER", "inception")
    monkeypatch.setenv("INCEPTION_API_KEY", "dummy")
    model = resolve_model()
    assert isinstance(model, OpenAILike)
    assert model.base_url == "https://api.inceptionlabs.ai/v1"
    assert model.id == "mercury-3"
    assert model.reasoning_effort == "medium"
    assert model.max_completion_tokens == 131072
    assert model.supports_native_structured_outputs is False


def test_inception_retries_rate_limits():
    from agno.exceptions import ModelProviderError

    from konvey.agents import InceptionChat

    model = InceptionChat(id="mercury-3", api_key="dummy")
    limit = ModelProviderError("Rate limit reached: output token limit exceeded", status_code=429)
    assert not super(InceptionChat, model)._is_retryable_error(limit)   # agno alone gives up
    assert model._is_retryable_error(ModelProviderError.classify(limit))
    assert not model._is_retryable_error(ModelProviderError("bad request", status_code=400))


def test_resolve_model_explicit_passthrough():
    from konvey.agents import resolve_model

    assert resolve_model("openai:gpt-4o-mini") == "openai:gpt-4o-mini"


# --- Prompts filled with real data ---------------------------------------

def _fill(template: str, mapping: dict) -> str:
    for key, value in mapping.items():
        template = template.replace(key, value)
    return template


def test_agent1_prompt_fills_with_user_prompt():
    """The Agent 1 template takes the user prompt with no leftover placeholder."""
    user_prompt = "Where do facts live in an LLM?"
    for mode in ("few-shot", "zero-shot", "cot"):
        filled = _fill(load_agent1_template(mode), {"{USER_PROMPT}": user_prompt})  # type: ignore[arg-type]
        assert "{USER_PROMPT}" not in filled and user_prompt in filled
