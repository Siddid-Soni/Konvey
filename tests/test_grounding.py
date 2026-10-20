"""Grounding fixes: worked examples (A1), typed data-carrying objects (A2),
template-copy check, konvey_kit builders."""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

import pytest

from konvey.schemas import KnowledgePack
from konvey.validators import (
    ValidationError,
    example_vo_lines_from_template,
    validate_knowledge_pack,
    validate_scene_plan,
)

REPO = Path(__file__).resolve().parent.parent
HAS_MANIM = importlib.util.find_spec("manimlib") is not None

KNOWLEDGE = {
    "topic": "Best Wordle opener by entropy",
    "core_claim": "The best opener maximizes expected information in bits",
    "key_concepts": [
        {"name": "Information", "definition_1line": "Bits = log2(1/p)", "why_matters": "Measures one pattern"},
        {"name": "Entropy", "definition_1line": "Expected information over patterns", "why_matters": "Scores a guess"},
    ],
    "mechanism_steps": ["Guess", "See pattern", "Average bits over patterns"],
    "narration_beats_3b1b_style": ["Hook", "Intuition", "Formalize"],
    "knowledge_triples": [["Entropy", "is-a", "expected information"]],
    "worked_examples": [
        {"concept": "Information", "setup": "halving 2,315 answers", "values": {"bits_for_half": 1, "bits_for_quarter": 2},
         "formula": "I = \\log_2(1/p)"},
        {"concept": "Entropy", "setup": "WEARY vs SLATE", "values": {"WEARY_bits": 4.9, "SLATE_bits": 5.8}},
    ],
}


def _beat(vo, teaches, objects):
    return {"vo_line": vo, "teaches": teaches, "objects": objects}


def _plan():
    s1 = _beat("Cutting the answers in half is one bit of information.", "Information", [
        {"id": "formula", "kind": "tex", "data": {"tex": "I = \\log_2(1/p)", "built_from": ["S1 beat 0"]},
         "source": "worked_examples[0].formula"},
        {"id": "half", "kind": "text", "data": {"text": "half the answers = 1 bit"}, "source": "worked_examples[0].values"},
    ])
    s2 = _beat("SLATE averages more bits than WEARY.", "Entropy", [
        {"id": "opener_bits", "kind": "bars", "data": {"labels": ["WEARY", "SLATE"], "values": [4.9, 5.8]},
         "source": "worked_examples[1].values"},
    ])
    s3 = _beat("So the opener with the most expected bits wins.", "Entropy", [
        {"id": "best", "kind": "tiles", "data": {"word": "SLATE"}, "source": "worked_examples[1].values"},
    ])
    return {"title": "Wordle entropy", "scenes": [
        {"id": "S1", "purpose": "hook", "vo_script": [s1["vo_line"]], "beats": [s1], "duration_sec": 30, "precedes": "S2"},
        {"id": "S2", "purpose": "build", "vo_script": [s2["vo_line"]], "beats": [s2], "duration_sec": 30, "precedes": "S3"},
        {"id": "S3", "purpose": "payoff", "vo_script": [s3["vo_line"]], "beats": [s3], "duration_sec": 30, "precedes": None},
    ]}


def _kp():
    return KnowledgePack.model_validate(KNOWLEDGE)


# --- Agent 1 ----------------------------------------------------------------

def test_knowledge_grounded_passes():
    validate_knowledge_pack(KNOWLEDGE, require_grounding=True)


def test_knowledge_requires_worked_example_per_concept():
    kp = copy.deepcopy(KNOWLEDGE)
    kp["worked_examples"] = kp["worked_examples"][:1]
    with pytest.raises(ValidationError, match="missing \\['Entropy'\\]"):
        validate_knowledge_pack(kp, require_grounding=True)
    validate_knowledge_pack(kp)  # legacy mode tolerates it


def test_knowledge_worked_example_concept_must_exist():
    kp = copy.deepcopy(KNOWLEDGE)
    kp["worked_examples"][0]["concept"] = "Bits"
    with pytest.raises(ValidationError, match="must equal a key_concepts"):
        validate_knowledge_pack(kp)


# --- Agent 2 ----------------------------------------------------------------

def test_plan_grounded_passes():
    validate_scene_plan(_plan(), knowledge=_kp())


def test_plan_rejects_bare_object_names():
    plan = _plan()
    plan["scenes"][2]["beats"][0]["objects"] = ["partition_groups"]
    with pytest.raises(ValidationError, match="bare name"):
        validate_scene_plan(plan, knowledge=_kp())


def test_plan_rejects_invented_numbers():
    plan = _plan()
    plan["scenes"][1]["beats"][0]["objects"][0]["data"]["values"] = [4.9, 7.3]
    with pytest.raises(ValidationError, match=r"\[7.3\]"):
        validate_scene_plan(plan, knowledge=_kp())


def test_plan_visual_source_is_exempt():
    plan = _plan()
    plan["scenes"][2]["beats"][0]["objects"].append(
        {"id": "deco", "kind": "text", "data": {"text": "step 99"}, "source": "visual"})
    validate_scene_plan(plan, knowledge=_kp())


def test_plan_rejects_untaught_concept():
    plan = _plan()
    plan["scenes"][0]["beats"][0]["teaches"] = "Entropy"
    with pytest.raises(ValidationError, match="never taught.*Information"):
        validate_scene_plan(plan, knowledge=_kp())


def test_plan_rejects_missing_kind_data():
    plan = _plan()
    del plan["scenes"][1]["beats"][0]["objects"][0]["data"]["values"]
    with pytest.raises(ValidationError, match="needs data\\['values'\\]"):
        validate_scene_plan(plan, knowledge=_kp())


def test_vo_copy_of_plan_example_is_rejected():
    from konvey.prompts import load_plan_template

    lines = example_vo_lines_from_template(load_plan_template())
    assert "Halve 13 again and again. Each leftover becomes a digit." in lines
    plan = _plan()
    copied = "Halve 29 again and again. Each leftover becomes a digit."
    plan["scenes"][0]["vo_script"].append(copied)
    with pytest.raises(ValidationError, match="copies example line"):
        validate_scene_plan(plan, example_vo_lines=lines)
    validate_scene_plan(_plan(), example_vo_lines=lines)


# --- Prompts ----------------------------------------------------------------

def test_prompts_include_grounding_rules():
    from konvey.prompts import build_agent_instructions

    text = build_agent_instructions(1, "few-shot")
    assert "GROUNDING RULES" in text and "worked_examples" in text
    assert "GROUNDING RULES" not in build_agent_instructions(1, "few-shot", grounded=False)


# --- konvey_kit -----------------------------------------------------------

@pytest.mark.skipif(not HAS_MANIM, reason="needs manimgl (uv --group render)")
def test_kit_galton_board_counts_follow_paths(monkeypatch):
    monkeypatch.setattr(sys, "argv", sys.argv[:1])
    monkeypatch.syspath_prepend(str(REPO / "render"))
    from konvey_kit import BarChart, GaltonBoard, WordTiles

    board = GaltonBoard(rows=5)
    assert len(board.pegs) == 15 and len(board.buckets) == 6
    assert [lab.text for lab in board.bucket_labels] == ["-5", "-3", "-1", "+1", "+3", "+5"]
    paths = board.simulate(64, seed=1)
    assert paths == board.simulate(64, seed=1)
    assert sum(board.counts(paths)) == 64
    assert board.expected_counts(32) == [1, 5, 10, 10, 5, 1]
    board.drop_balls(paths)
    assert len(board.balls) == 64
    chart = BarChart(["WEARY", "SLATE"], [4.9, 5.8])
    assert chart.bars[1].get_height() > chart.bars[0].get_height()
    with pytest.raises(ValueError):
        WordTiles("CRANE", "gy")


# --- Numbers ----------------------------------------------------------------

def test_comma_lists_are_separate_numbers_not_thousands():
    from konvey.validators import _numbers_in

    assert _numbers_in("a,4,6,4,2;b,8,12,6,2") == [4, 6, 4, 2, 8, 12, 6, 2]
    assert _numbers_in("12,000 and 1,234,567.5") == [12000, 1234567.5]


def test_grid_values_may_be_a_list_of_rows():
    from konvey.schemas import ObjectSpec
    from konvey.validators import _object_problems

    rows = [["A", "B", 7], ["A", "C", 9]]
    ok = ObjectSpec(id="g", kind="grid", data={"rows": 2, "cols": 3, "values": rows}, source="x")
    bad = ObjectSpec(id="g", kind="grid", data={"rows": 3, "cols": 3, "values": rows}, source="x")
    assert not _object_problems(ok)
    assert "grid has 6 values for 3x3 cells" in _object_problems(bad)


def test_tiny_numbers_stay_traceable():
    from konvey.validators import _numbers_in, _traceable

    assert _numbers_in("error 2.1239e-06 now") == [2.1239e-06]
    known = {float(f"{2.1239e-06:.6g}")}
    assert _traceable(2.124e-06, known) and not _traceable(3e-06, known)


def test_stage_plan_schema_has_no_manim_fields_and_keeps_its_limits():
    import json as _json

    from agno.utils.prompts import get_json_output_prompt
    from pydantic import ValidationError as PydErr

    from konvey.schemas import ScenePlan, StagePlan

    shown = get_json_output_prompt(StagePlan)          # what agno puts in the planner's prompt
    assert not [k for k in ("animation", "code_hint", "layout", "predicates", "manim") if k in shown]
    obj = {"id": "pair", "kind": "array", "data": {"values": [1, 2]}}
    beat = {"vo_line": "One.", "objects": [obj], "animation": {"type": "Write", "run_time": 1}}
    scenes = [{"id": f"S{k}", "purpose": p, "vo_script": ["One."], "duration_sec": 30,
               "precedes": n, "beats": [beat]}
              for k, p, n in ((1, "hook", "S2"), (2, "build", "S3"), (3, "payoff", None))]
    plan = StagePlan.model_validate({"title": "T", "scenes": scenes})   # stray animation: ignored
    assert isinstance(plan.to_scene_plan(), ScenePlan)
    scenes[0]["beats"] = [{**beat, "objects": [obj] * 6}]
    with pytest.raises(PydErr):
        StagePlan.model_validate(_json.loads(_json.dumps({"title": "T", "scenes": scenes})))


def test_schema_errors_in_agent_text_go_to_repair_and_brackets_are_rebalanced():
    from konvey.schemas import StagePlan
    from konvey.validators import ValidationError, coerce_content, extract_json

    # agno's text fallback: a schema mistake must be a repairable ValidationError, not a crash
    with pytest.raises(ValidationError, match="schema violation"):
        coerce_content('{"title": "T", "scenes": []}', StagePlan)
    # a long reply closed in the wrong order at the end still parses
    assert extract_json('{"a": [{"b": [1, 2]}, {"c": "x]}"}]}}') == {"a": [{"b": [1, 2]}, {"c": "x]}"}]}
    assert extract_json('{"a": [1, 2,], "b": {"c": [3}') == {"a": [1, 2], "b": {"c": [3]}}
