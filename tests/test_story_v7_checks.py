"""Story v7 planner and writer checks on worked traces: which lines walk a step, and what a step's beat shows."""

import sys
from pathlib import Path
from types import SimpleNamespace as N

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
v7 = pytest.importorskip("story_eval_v7")


def trace(*actions):
    return N(id="T1", of="a run", findings=["F1"], steps=[N(action=a) for a in actions])


def script(*moves):
    return N(moves=[N(lines=[N(line=x, uses=["F1"]) for x in m]) for m in moves])


def test_the_item_of_a_step_is_what_goes_in_not_the_verb():
    t = trace("insert kim: slots 2 and 9", "insert lee: slots 4 and 7", "query max: slots 2, 4 — all set")
    assert [v7.item_words(t, j)[0] for j in range(3)] == ["kim", "lee", "max"]
    named = trace("Kim leaves: clear slots 2 and 9", "Query Lee: slots 4 and 7", "Query Kim: slot 9")
    assert v7.item_words(named, 0)[0] == "kim" and v7.item_words(named, 2) == ["kim"]


def test_a_line_walks_a_step_by_its_item_or_its_numbers_never_by_a_lone_one():
    t = trace("insert kim: slots 12 and 19", "clear slot 1")
    assert v7._names_step("Kim's two arrows land on the board.", t, 0)
    assert v7._names_step("Slots 12 and 19 light up.", t, 0)
    assert not v7._names_step("One more idea.", t, 1)


def test_a_story_that_sums_up_its_trace_in_one_line_is_sent_back():
    t = trace("insert kim: slots 12 and 19", "insert lee: slots 4 and 7", "insert max: slots 3 and 8")
    exp = N(traces=[t])
    summed = script(["Kim, Lee and Max go in, and six slots end up set."])
    walked = script(["Kim lands on two slots.", "Lee lands on two others.", "Max fills the rest."])
    assert v7.trace_walk_problems(summed, exp) and not v7.trace_walk_problems(walked, exp)


def test_a_step_shows_its_cause_on_the_line_that_says_it():
    t = trace("insert kim: slots 12 and 19", "insert lee: slots 4 and 7")
    exp, sc = N(traces=[t]), script(["Kim lands on two slots.", "Something else entirely."])
    beat = lambda line, step, objs: N(move=0, line=line, trace_step=step, objects=objs)  # noqa: E731
    note = {"kind": "note", "data": {"text": "kim", "at": [[12], [19]]}}
    assert v7.cause_problems([beat(0, "T1.0", [note])], exp, sc) == []
    assert "new state only" in v7.cause_problems([beat(0, "T1.0", [])], exp, sc)[0]
    assert "something else" in v7.cause_problems([beat(1, "T1.1", [])], exp, sc)[0]
