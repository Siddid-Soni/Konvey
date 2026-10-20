"""Stage mode: Agent 1 works one example fully (walkthrough) and Agent 2 shows every
step in its own beat, in order; Manim-only plan fields are optional."""

from __future__ import annotations

import copy

import pytest

from konvey.schemas import KnowledgePack, ScenePlan
from konvey.validators import ValidationError, validate_knowledge_pack, validate_scene_plan

KNOWLEDGE = {
    "topic": "Greatest common divisor by remainders",
    "core_claim": "Replacing the larger number by the remainder keeps the gcd",
    "key_concepts": [{"name": "Remainder step", "definition_1line": "gcd(a,b) = gcd(b, a mod b)",
                      "why_matters": "Shrinks the pair fast"}],
    "mechanism_steps": ["Divide", "Keep the remainder", "Stop at zero"],
    "narration_beats_3b1b_style": ["Hook", "Intuition", "Formalize"],
    "knowledge_triples": [["Remainder step", "transforms", "pair"]],
    "worked_examples": [{"concept": "Remainder step", "setup": "48 and 18",
                         "values": {"a": 48, "b": 18}, "formula": "\\gcd(a,b)=\\gcd(b, a \\bmod b)"}],
    "walkthrough": {
        "concept": "Remainder step", "question": "gcd of 48 and 18", "start": {"pair": [48, 18]},
        "steps": [{"action": "48 mod 18 = 12", "why": "18 goes into 48 twice, 12 left", "state": {"pair": [18, 12]}},
                  {"action": "18 mod 12 = 6", "why": "12 goes into 18 once, 6 left", "state": {"pair": [12, 6]}},
                  {"action": "12 mod 6 = 0", "why": "6 goes into 12 twice, nothing left", "state": {"pair": [6, 0]}}],
        "result": "gcd is 6"},
    "examples_considered": [{"example": "48 and 18", "makes_visible": "the pair shrinking",
                             "leads_to": "the rule"}],
    "chosen_example": {"example": "48 and 18", "reason": "named", "named_in_request": True},
    "hook": {"shown": "48 and 18 written side by side", "tension": "both hide the same divisor, and no list shows it fast",
             "question": "what is the largest number dividing both?", "withheld": ["remainder", "gcd(b, a mod b)"],
             "type": "vehicle", "why_care": "Two numbers can hide a shared divisor that no list reveals quickly",
             "problem": "What is the largest number dividing both 48 and 18?"},
    "naive_attempt": {"attempt": "list every divisor of both", "falls_short": "48 has 10 divisors to check",
                      "sharper_question": "can the pair be made smaller without losing the divisor?"},
    "promise": "the divisor appears after 3 steps",
    "exploration": [{"case": "gcd of 6 and 4", "what_happens": "6 - 4 = 2 keeps the divisor 2"},
                    {"case": "gcd of 9 and 6", "what_happens": "9 - 6 = 3 keeps the divisor 3"}],
    "insight": {"hunch": "subtracting keeps common divisors", "made_precise": "a mod b keeps them too",
                "idea": "gcd(a, b) = gcd(b, a mod b)", "why_it_holds": "a - qb is a multiple of every common divisor",
                "why_it_settles": "the pair shrinks every step and stops at 0"},
    "viewer_questions": [
        {"question": "Why does the remainder keep the divisor?", "answer": "a - qb keeps every common divisor",
         "shown_by": "derivation"},
        {"question": "Why does it stop?", "answer": "the pair shrinks every step", "shown_by": "picture"},
        {"question": "Why the last nonzero number?", "answer": "it divides the one before", "shown_by": "picture"}],
    "payoff": {"lesson": "shrink a problem while keeping what you want", "generalisation": "gcd(a, b) = gcd(b, a mod b) for any pair",
               "surprise": "it needs few steps", "closes_opening": "the hidden divisor came out in 3 steps"},
}


def _beat(vo, values, step=None):
    return {"vo_line": vo, "teaches": "Remainder step", "walkthrough_step": step,
            "objects": [{"id": "pair", "kind": "array", "data": {"values": values}, "source": "walkthrough"}]}


def _plan(steps=(0, 1, 2)):
    states = [[18, 12], [12, 6], [6, 0]]
    walk = [_beat(f"Step {i}: the pair changes.", states[i], i) for i in steps]
    s1 = [_beat("Take 48 and 18.", [48, 18])]
    s3 = [_beat("The last nonzero number divides both.", [6, 0])]
    scenes = []
    for sid, beats, nxt in (("S1", s1, "S2"), ("S2", walk, "S3"), ("S3", s3, None)):
        scenes.append({"id": sid, "vo_script": [b["vo_line"] for b in beats], "beats": beats,
                       "duration_sec": 30, "precedes": nxt})
    answers = [{"question": q["question"], "where": ["S1 beat 0"]} for q in KNOWLEDGE["viewer_questions"]]
    s2 = f"S2 beat {len(walk) - 1}"
    arc = [{"part": p, "where": [w]} for p, w in (
        ("hook", "S1 beat 0"), ("why_care", "S1 beat 0"), ("problem", "S1 beat 0"), ("naive_attempt", "S1 beat 0"), ("promise", "S1 beat 0"),
        ("exploration", "S2 beat 0"), ("key_insight", "S2 beat 0"), ("why_it_holds", s2), ("lesson", "S3 beat 0"),
        ("generalisation", "S3 beat 0"), ("surprise", "S3 beat 0"), ("closes_opening", "S3 beat 0"))]
    return {"title": "gcd", "scenes": scenes, "answers": answers, "arc": arc}


def _kp():
    return KnowledgePack.model_validate(KNOWLEDGE)


def test_walkthrough_required_in_stage_mode():
    kp = copy.deepcopy(KNOWLEDGE)
    del kp["walkthrough"]
    validate_knowledge_pack(kp, require_grounding=True)  # manim mode: optional
    with pytest.raises(ValidationError, match="walkthrough"):
        validate_knowledge_pack(kp, require_grounding=True, require_walkthrough=True)


def test_walkthrough_steps_need_state_and_count():
    kp = copy.deepcopy(KNOWLEDGE)
    kp["walkthrough"]["steps"][1]["state"] = {}
    with pytest.raises(ValidationError, match="no state"):
        validate_knowledge_pack(kp, require_walkthrough=True)
    kp = copy.deepcopy(KNOWLEDGE)
    kp["walkthrough"]["steps"] = kp["walkthrough"]["steps"][:2]
    with pytest.raises(ValidationError, match="3-10"):
        validate_knowledge_pack(kp, require_walkthrough=True)


def test_plan_with_walkthrough_passes():
    plan = validate_scene_plan(_plan(), 90, knowledge=_kp())
    assert [b.walkthrough_step for s in plan.scenes for b in s.beats if b.walkthrough_step is not None]


def test_plan_must_show_every_step_once_in_order():
    with pytest.raises(ValidationError, match=r"never shown: 1"):
        validate_scene_plan(_plan((0, 2)), 90, knowledge=_kp())
    with pytest.raises(ValidationError, match="more than one beat"):
        validate_scene_plan(_plan((0, 1, 1, 2)), 90, knowledge=_kp())
    with pytest.raises(ValidationError, match="out of order"):
        validate_scene_plan(_plan((0, 2, 1)), 90, knowledge=_kp())




# --- a second method worked through (more_walkthroughs) and what the request asked for ---------

SUBTRACT = {"concept": "Remainder step", "question": "gcd of 48 and 18 by subtracting",
            "start": {"pair": [48, 18]},
            "steps": [{"action": "48 - 18 = 30", "why": "48 is the larger", "state": {"pair": [30, 18]}},
                      {"action": "30 - 18 = 12", "why": "30 is the larger", "state": {"pair": [12, 18]}},
                      {"action": "18 - 12 = 6", "why": "18 is the larger", "state": {"pair": [12, 6]}}],
            "result": "gcd is 6"}


def _two_methods(second_steps=(0, 1, 2)):
    plan = _plan()
    states = [[30, 18], [12, 18], [12, 6]]
    for i in second_steps:
        beat = _beat(f"Subtract {i}: the pair shrinks.", states[i], i)
        beat["walkthrough"] = 1
        plan["scenes"][2]["beats"].append(beat)
        plan["scenes"][2]["vo_script"].append(beat["vo_line"])
    return plan


def test_a_second_method_is_checked_like_the_first():
    kp = copy.deepcopy(KNOWLEDGE)
    kp["more_walkthroughs"] = [copy.deepcopy(SUBTRACT)]
    kp["more_walkthroughs"][0]["steps"][2]["state"] = {}
    with pytest.raises(ValidationError, match=r"more_walkthroughs\[0\]: steps\[2\].*no state"):
        validate_knowledge_pack(kp, require_walkthrough=True)


def test_every_step_of_every_worked_example_gets_its_own_beat():
    kp = KnowledgePack.model_validate({**KNOWLEDGE, "more_walkthroughs": [SUBTRACT]})
    validate_scene_plan(_two_methods(), 120, knowledge=kp)
    with pytest.raises(ValidationError, match=r"more_walkthroughs\[0\] \(walkthrough 1\) steps never shown: 1"):
        validate_scene_plan(_two_methods((0, 2)), 120, knowledge=kp)
    with pytest.raises(ValidationError, match=r"\(walkthrough 1\) steps never shown: 0 .*; 1 .*; 2 "):
        validate_scene_plan(_plan(), 120, knowledge=kp)   # the second method left out


def test_everything_the_request_asked_for_is_placed_on_real_beats():
    kp = KnowledgePack.model_validate({**KNOWLEDGE, "requested": ["the pair after each step"]})
    with pytest.raises(ValidationError, match="'the pair after each step' is not placed"):
        validate_scene_plan(_plan(), 90, knowledge=kp)
    plan = _plan()
    plan["requested_shown"] = [{"item": "The pair after each step", "where": ["S2 beat 0", "S2 beat 7"]}]
    with pytest.raises(ValidationError, match="'S2 beat 7' is not a beat of this plan"):
        validate_scene_plan(plan, 90, knowledge=kp)
    plan["requested_shown"][0]["where"] = ["S2 beat 0", "S2 beat 2"]
    assert validate_scene_plan(plan, 90, knowledge=kp).requested_shown[0].where == ["S2 beat 0", "S2 beat 2"]


def test_every_step_says_why_it_happens():
    validate_knowledge_pack(copy.deepcopy(KNOWLEDGE), require_walkthrough=True)
    kp = copy.deepcopy(KNOWLEDGE)
    kp["walkthrough"]["steps"][1]["why"] = " "
    with pytest.raises(ValidationError, match=r"steps\[1\] .* has no why"):
        validate_knowledge_pack(kp, require_walkthrough=True)
