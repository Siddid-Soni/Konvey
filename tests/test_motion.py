"""Same id, new content -> in-place motion (cells slide/hop, words stay) instead of exit +
re-enter; plans keep one evolving picture per scene."""

import importlib.util
import sys

import pytest

from konvey.schemas import ScenePlan
from konvey.validators import ValidationError, check_plan_motion, plan_cuts

HAS_MANIM = importlib.util.find_spec("manimlib") is not None
manim = pytest.mark.skipif(not HAS_MANIM, reason="needs manimgl")


@pytest.fixture(autouse=True)
def _plain_argv(monkeypatch):
    # manimlib parses sys.argv when first imported; pytest's own flags would make it exit.
    monkeypatch.setattr(sys, "argv", sys.argv[:1])


@manim
def test_cells_match_by_value_and_only_crossing_items_hop():
    from konvey.stage.displays.array.mobject import _hoppers, _match_by_value

    pairs = _match_by_value(list("25814"), list("12584"))
    assert pairs == {0: 3, 1: 0, 2: 1, 3: 2, 4: 4}      # 1 jumps to the front, the rest shift
    assert _hoppers(pairs) == {0}
    assert _hoppers(_match_by_value(list("52"), list("25"))) == {0}   # a swap: the left mover hops
    assert _hoppers(_match_by_value(list("123"), list("123"))) == set()
    assert _match_by_value(list("aab"), list("baa")) == {0: 2, 1: 0, 2: 1}  # duplicates pair in order


@manim
def test_array_morph_moves_cells_and_pointers_by_name():
    from manimlib import AnimationGroup, Transform

    from konvey.stage.displays.array.mobject import ArrayBlock
    from konvey.stage.motion import morph
    from konvey.stage.parse import parse_beats

    def arr(values, pointers):
        node = parse_beats(f'<beats><beat><array id="a" values="{values}" pointers="{pointers}">'
                           '</array></beat></beats>')[0].leaves()["a"]
        return ArrayBlock(node)

    anim = morph(arr("5,2,8", "i:1"), arr("2,5,8", "i:2"))
    assert isinstance(anim, AnimationGroup)
    kinds = [type(a).__name__ for a in anim.animations]
    assert kinds.count("Transform") == 5   # 3 cells + index row + pointer i, nothing re-enters
    assert not any(k in ("FadeIn", "FadeOut") for k in kinds)


@manim
def test_text_changes_like_3b1b_never_shuffles():
    from konvey.stage.motion import morph
    from konvey.stage.overlay import KineticText
    from konvey.stage.parse import parse_beats

    def text(s, tag="text"):
        node = parse_beats(f'<beats><beat><{tag} id="t">{s}</{tag}></beat></beats>')[0].leaves()["t"]
        return KineticText(node)

    def kinds(anim):
        return [type(a).__name__ for a in anim.animations]

    # a counter: the words stay still and the number counts in place (no separate fade)
    k = kinds(morph(text("moves so far: 1"), text("moves so far: 12")))
    assert k == ["Transform", "Transform", "Transform", "UpdateFromAlphaFunc"]
    # a number the picture points at flies from that cell: the old number fades, a copy flies
    cell = text("71")
    k = kinds(morph(text("mid value 44"), text("mid value 71"), sources={71.0: cell}))
    assert k == ["Transform", "Transform", "FadeOut", "UpdateFromAlphaFunc"]
    # a new sentence is never matched word by word, and never overlaps the old one
    assert kinds(morph(text("Probe two: too small"), text("Probe three: too big"))) == ["FadeOut", "FadeIn"]
    assert "Write" in kinds(morph(text("Too small", "h2"), text("Still too small", "h2")))
    assert kinds(morph(text("one line", "caption"), text("another line", "caption"))) == ["FadeOut", "FadeIn"]


def _plan(scene_objects):
    scenes = []
    for sid, nxt, beats in zip(("S1", "S2", "S3"), ("S2", "S3", None), scene_objects):
        bs = [{"vo_line": f"{sid} line {k}", "objects": [{"id": i, "kind": "array", "data": {"values": [1]}}
                                                        for i in ids]} for k, ids in enumerate(beats)]
        scenes.append({"id": sid, "vo_script": [b["vo_line"] for b in bs], "beats": bs,
                       "duration_sec": 30, "precedes": nxt})
    return ScenePlan.model_validate({"title": "t", "scenes": scenes})


def test_plan_cuts_counts_beats_that_replace_the_picture():
    plan = _plan([[["a"], ["a"], ["b"]], [["c"], ["d"], ["e"]], [["f"], ["f", "g"]]])
    assert plan_cuts(plan) == [("S1", 2), ("S2", 1), ("S2", 2)]
    with pytest.raises(ValidationError, match=r"Scene S2: beats \[1, 2\]"):
        check_plan_motion(plan)
    check_plan_motion(_plan([[["a"], ["b"]], [["c"], ["c"]], [["f"]]]))   # one cut per scene is fine
