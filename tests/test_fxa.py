"""Fixes found by scout runs on new topics: planned nulls, separators in system text, nested
array values, array/bars min size, grounding on computed numbers, loose concept names, the
array index base, agent1-output.json written early."""

import copy
import json
from pathlib import Path

import pytest

from konvey.schemas import KnowledgePack, ObjectSpec
from konvey.stage import displays
from konvey.stage.check import MIN_SIZE
from konvey.stage.match import fmt_list, same_values
from konvey.stage.parse import parse_beats
from konvey.validators import (ValidationError, check_plan_grounding, computed_numbers,
                               validate_knowledge_pack, validate_scene_plan)

from tests.test_grounding import KNOWLEDGE, _plan

REPO = Path(__file__).resolve().parent.parent


def leaves(html: str):
    return [n for b in parse_beats(f"<beats><beat>{html}</beat></beats>") for n in b.leaves().values()]


def obj(kind: str, **data):
    return ObjectSpec(id="x", kind=kind, data=data, source="walkthrough")


# 1. a planned null --------------------------------------------------------------------------
def test_planned_null_is_written_and_matched_as_question_mark():
    assert fmt_list([3, None]) == "3,?"
    assert same_values([3, None], "3,?") and same_values([3, None], "3,") and same_values([3, None], "3,none")
    assert not same_values([3, None], "3,4")
    check = displays.for_kind("array").check_drawn
    assert check("w", obj("array", values=[3, None]), leaves('<array id="x" values="3,?"></array>')) == []
    assert 'values="3,?"' in check("w", obj("array", values=[3, None]), leaves('<array id="x" values="3"></array>'))[0]


# 2. separators in system text ---------------------------------------------------------------
def test_system_rejects_bar_and_semicolon_in_planned_text():
    check = displays.for_kind("system").check_object
    data = {"parts": ["cpu", "memory"],
            "items": [{"id": "va", "in": "cpu", "text": "VA 10892", "lines": ["page 2 | offset 2652"]}],
            "holds": {"memory": ["frame 7; dirty"]}}
    problems = check(data)
    assert any("'page 2 · offset 2652'" in p for p in problems)
    assert any("'frame 7 · dirty'" in p for p in problems)
    data["items"][0]["lines"] = ["page 2 · offset 2652"]
    data["holds"] = {"memory": ["frame 7: dirty"]}       # a colon is fine
    assert check(data) == []


@pytest.mark.skipif(not (REPO / "out/fx-mix-paging/agent2-output.json").exists(), reason="scout run not here")
def test_paging_scout_plan_is_now_rejected_up_front():
    plan = json.loads((REPO / "out/fx-mix-paging/agent2-output.json").read_text())
    check = displays.for_kind("system").check_object
    found = [p for s in plan["scenes"] for b in s["beats"] for o in b["objects"]
             if isinstance(o, dict) and o["kind"] == "system" for p in check(o["data"])]
    assert any("page 2 · offset 2652" in p for p in found)


# 3. nested array values ---------------------------------------------------------------------
def test_array_rejects_nested_values():
    check = displays.for_kind("array").check_object
    assert "grid" in check({"values": [[1, 1], [8, 8], [5, 6]]})[0]
    assert check({"values": ["(1, 1)", "(8, 8)"]}) == []


# 4. min size --------------------------------------------------------------------------------
def test_array_and_bars_have_a_min_size():
    assert MIN_SIZE["array"] >= 20 and MIN_SIZE["bars"] >= 20


# 5. grounding on computed numbers -----------------------------------------------------------
def _gamma_plan():
    plan = _plan()
    plan["scenes"][1]["beats"][0]["objects"][0]["data"] = {"labels": ["WEARY", "SLATE"], "values": [4.9, 1.1547]}
    return plan


def test_numbers_printed_by_compute_tools_count_as_known():
    calls = [{"tool": "run_python", "input": "", "output": "0.5 1.1547\n0.8 1.6667\nERROR: line 99"},
             {"tool": "run_python", "input": "", "output": "REJECTED: no imports 42"}]
    nums = computed_numbers(calls)
    assert 1.1547 in nums and 0.8 in nums and 99 not in nums and 42 not in nums
    kp = KnowledgePack.model_validate(KNOWLEDGE)
    with pytest.raises(ValidationError, match=r"nearest to them \(1.1547: .*1"):
        validate_scene_plan(_gamma_plan(), knowledge=kp)
    validate_scene_plan(_gamma_plan(), knowledge=kp, computed=nums)
    check_plan_grounding(validate_scene_plan(_gamma_plan()), kp, nums)


# 6. agent1-output.json is written before planning (pipeline source) ---------------------------
def test_agent1_output_written_before_planning():
    src = (REPO / "konvey/pipeline.py").read_text()
    run = src[src.index("def run_pipeline"):]
    assert run.index('"agent1-output.json"') < run.index("[2/4] Agent 2")


# 7. loose concept names ---------------------------------------------------------------------
def test_worked_example_concept_names_are_matched_loosely():
    kp = copy.deepcopy(KNOWLEDGE)
    kp["worked_examples"][0]["concept"] = "information"
    kp["worked_examples"][1]["concept"] = "Best Wordle opener"        # the topic itself
    out = validate_knowledge_pack(kp, require_grounding=True)
    assert [e.concept for e in out.worked_examples] == ["Information", "Entropy"]
    kp["worked_examples"][1]["concept"] = "Bits"                      # something else: still rejected
    with pytest.raises(ValidationError, match="must equal a key_concepts"):
        validate_knowledge_pack(kp)


# 8. array index base ------------------------------------------------------------------------
def test_planned_array_index_must_be_drawn():
    check = displays.for_kind("array")
    assert check.check_object({"values": [5, 25], "index": 1}) == []
    assert check.check_object({"values": [5, 25], "index": "one"})
    o = obj("array", values=[5, 25], index=1)
    assert 'index="1"' in check.check_drawn("w", o, leaves('<array id="x" values="5,25"></array>'))[0]
    assert check.check_drawn("w", o, leaves('<array id="x" values="5,25" index="1"></array>')) == []


def test_one_value_with_a_comma_is_written_with_a_closing_bar():
    from konvey.stage.match import fmt_list, same_values, split_list

    assert fmt_list(["(0, A)"]) == "(0, A)|"
    assert split_list("(0, A)|") == ["(0, A)"]
    assert split_list("(2, C)|(4, B)") == ["(2, C)", "(4, B)"]
    assert same_values(["(0, A)"], "(0, A)|") and not same_values(["(0, A)"], "(0, A)")


def test_infinity_matches_however_it_is_written():
    from konvey.stage.match import same_values

    assert same_values(["INF", 0, "inf"], "∞,0,∞") and same_values(["∞"], "INF")
    assert same_values(["-inf"], "-∞") and not same_values(["INF"], "-∞") and not same_values(["INF"], "8")
