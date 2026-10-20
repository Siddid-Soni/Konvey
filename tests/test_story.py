"""The story fields (example, hook, viewer questions, payoff) and the plan checks built on them:
every question answered on screen, every formula built before it is shown, the stock opening
flagged."""

from __future__ import annotations

import copy

import pytest

from konvey.schemas import KnowledgePack
from konvey.speech.checks import opening_warnings
from konvey.validators import (ValidationError, check_plan_answers, check_plan_arc, check_plan_formulas,
                               validate_knowledge_pack, validate_scene_plan)
from tests.test_walkthrough import KNOWLEDGE, _plan


def test_story_fields_required_with_the_walkthrough():
    validate_knowledge_pack(copy.deepcopy(KNOWLEDGE), require_walkthrough=True)
    kp = copy.deepcopy(KNOWLEDGE)
    for key in ("hook", "payoff", "viewer_questions", "chosen_example", "examples_considered", "naive_attempt",
                "promise", "exploration", "insight"):
        del kp[key]
    with pytest.raises(ValidationError) as e:
        validate_knowledge_pack(kp, require_walkthrough=True)
    for word in ("examples_considered", "chosen_example", "hook", "viewer_questions", "payoff", "naive_attempt",
                 "promise", "exploration", "insight"):
        assert word in str(e.value)
    validate_knowledge_pack(kp)   # without the walkthrough requirement the story is optional


def test_an_example_the_request_did_not_name_needs_rivals():
    kp = copy.deepcopy(KNOWLEDGE)
    kp["chosen_example"]["named_in_request"] = False
    with pytest.raises(ValidationError, match="give 3 or more different"):
        validate_knowledge_pack(kp, require_walkthrough=True)
    kp["examples_considered"] *= 3
    validate_knowledge_pack(kp, require_walkthrough=True)


def test_hook_type_and_question_answers_come_from_the_menus():
    kp = copy.deepcopy(KNOWLEDGE)
    kp["hook"]["type"] = " Surprise "
    kp["viewer_questions"][0]["shown_by"] = "Trials"
    out = validate_knowledge_pack(kp, require_walkthrough=True)
    assert out.hook.type == "surprise" and out.viewer_questions[0].shown_by == "trials"
    kp["hook"]["type"] = "puzzle"
    kp["viewer_questions"][0]["shown_by"] = "voice"
    with pytest.raises(ValidationError) as e:
        validate_knowledge_pack(kp, require_walkthrough=True)
    assert "hook.type 'puzzle'" in str(e.value) and "shown_by 'voice'" in str(e.value)


def _answered(plan):
    plan["answers"] = [{"question": q["question"], "where": ["S2 beat 0"]} for q in KNOWLEDGE["viewer_questions"]]
    return plan


def test_every_viewer_question_is_answered_in_a_real_beat():
    kp = KnowledgePack.model_validate(KNOWLEDGE)
    plan = validate_scene_plan(_answered(_plan()), knowledge=kp)
    check_plan_answers(plan, kp)
    assert plan.answers[0].where == ["S2 beat 0"]
    plan.answers.pop()
    plan.answers[0].where = ["S2 beat 9"]
    with pytest.raises(ValidationError) as e:
        check_plan_answers(plan, kp)
    assert "'S2 beat 9' is not a beat" in str(e.value) and "Why the last nonzero number?" in str(e.value)


def test_a_formula_names_the_earlier_beats_it_is_built_from():
    plan = _plan()
    rule = {"id": "rule", "kind": "tex", "data": {"tex": "\\gcd(a,b)=\\gcd(b,\\ a \\bmod b)"}, "source": "x"}
    plan["scenes"][2]["beats"][0]["objects"].append(rule)
    with pytest.raises(ValidationError, match="appears without being built"):
        check_plan_formulas(validate_scene_plan(copy.deepcopy(plan)))
    rule["data"]["built_from"] = ["S2 beat 0", "S3 beat 1"]
    with pytest.raises(ValidationError) as e:
        check_plan_formulas(validate_scene_plan(copy.deepcopy(plan)))
    assert "'S3 beat 1' is not a beat" in str(e.value)
    rule["data"]["built_from"] = ["S2 beat 0", "S2 beat 2", "S3 beat 0"]
    check_plan_formulas(validate_scene_plan(copy.deepcopy(plan)))
    # only its first appearance names its sources
    plan["scenes"][2]["beats"].append(copy.deepcopy(plan["scenes"][2]["beats"][0]))
    plan["scenes"][2]["beats"][1]["objects"][-1]["data"].pop("built_from")
    plan["scenes"][2]["vo_script"].append(plan["scenes"][2]["beats"][1]["vo_line"])
    check_plan_formulas(validate_scene_plan(plan))


def test_stock_phrases_are_a_warning():
    plan = validate_scene_plan(_plan())
    plan.scenes[1].vo_script[0] = "A playful young woman asks, “Which is fastest? Take a guess before we count.”"
    assert any("take a guess" in w and "before we count" in w for w in opening_warnings(plan))
    plan.scenes[1].vo_script[0] = "A playful young woman asks, “Which way is fastest?”"
    assert opening_warnings(plan) == []


def test_the_arc_opens_with_why_and_keeps_its_order():
    kp = KnowledgePack.model_validate(KNOWLEDGE)
    plan = _plan()
    check_plan_arc(validate_scene_plan(copy.deepcopy(plan)), kp)
    bad = copy.deepcopy(plan)
    bad["arc"][0]["where"] = ["S1 beat 1"]          # not a beat, and not the opening
    bad["arc"][6]["where"] = ["S3 beat 0"]          # the key insight after why_it_holds
    bad["arc"] = [a for a in bad["arc"] if a["part"] != "promise"]
    with pytest.raises(ValidationError) as e:
        check_plan_arc(validate_scene_plan(bad), kp)
    msg = str(e.value)
    assert "'S1 beat 1' is not a beat" in msg and "'promise'" in msg and "why_it_holds" in msg
    counts = copy.deepcopy(plan)
    counts["scenes"][0]["vo_script"][0] = "A calm young woman says, “Five towns, seven roads, and a time on each.”"
    counts["scenes"][0]["beats"][0]["vo_line"] = counts["scenes"][0]["vo_script"][0]
    with pytest.raises(ValidationError, match="list of counts"):
        check_plan_arc(validate_scene_plan(counts), kp)


def test_the_answer_is_held_back_until_the_insight():
    kp = KnowledgePack.model_validate(KNOWLEDGE)
    plan = _plan()
    plan["scenes"][0]["vo_script"][0] = "A calm young woman says, “Keep swapping in the Remainder, and it works.”"
    plan["scenes"][0]["beats"][0]["vo_line"] = plan["scenes"][0]["vo_script"][0]
    with pytest.raises(ValidationError, match=r"given away.*\['remainder'\]"):
        check_plan_arc(validate_scene_plan(copy.deepcopy(plan)), kp)
    # once the insight has been shown, the word is free to use
    for a in plan["arc"]:
        if a["part"] in ("hook", "why_care", "problem", "naive_attempt", "promise", "exploration", "key_insight"):
            a["where"] = ["S1 beat 0"]
    check_plan_arc(validate_scene_plan(plan), kp)
