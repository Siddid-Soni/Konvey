"""``<attention>`` (kind ``attention``): words attending to words, laid out by the renderer."""

import importlib.util

import numpy as np
import pytest

from konvey.stage.displays import get
from konvey.stage.parse import BeatError, parse_beats, prepare_beats

HAS_MANIM = importlib.util.find_spec("manimlib") is not None
manim = pytest.mark.skipif(not HAS_MANIM, reason="needs manimgl (uv --group render)")

TOKS = ["fluffy", "blue", "creature", "roamed"]
RAW = "2,0.5,-1,0.1;1.5,2,0.3,-0.4;6,5.5,1,0.2;0.1,0.3,4,1"
SOFT = "1,0,0,0;0.6,0.4,0,0;0.57,0.42,0.01,0;0.02,0.05,0.9,0.03"


def leaf(html: str, i: str = "x"):
    return parse_beats(f"<beats><beat>{html}</beat></beats>")[0].leaves()[i]


def scene(*attrs: str):
    """One <attention id=x> per beat, prepared as the scene would be (shared room)."""
    body = "".join(f'<beat><attention id="x" tokens="{",".join(TOKS)}" {a}></attention></beat>' for a in attrs)
    beats = parse_beats(f"<beats>{body}</beats>")
    prepare_beats(beats)
    return [b.leaves()["x"] for b in beats]


# --- the plan -----------------------------------------------------------------------------------
def check(**d):
    return get("attention").check_object({"tokens": TOKS, **d})


def test_plan_weights_are_one_group_per_query_and_softmax_sums_to_one():
    assert check(weights=[[1, 0, 0, 0], [0.6, 0.4, 0, 0], [0.57, 0.42, 0.01, 0], [0.02, 0.05, 0.9, 0.03]],
                 softmax=True, mask="causal") == []
    assert "4 groups of 4" in check(weights=[[1, 0, 0, 0]])[0]
    assert "sum to 0.9" in check(weights=[[0.5, 0.4, 0, 0], [], [], []], softmax=True)[0]
    assert "must have weight 0" in check(weights=[[0.5, 0.5, 0, 0], [], [], []], softmax=True, mask="causal")[0]
    assert check(weights=[[], [], [6, 5.5, 1, 0.2], []]) == []          # only one query computed yet
    assert "not one of the tokens" in check(focus="dog")[0]
    assert "view" in check(view="table")[0]
    assert "at most 6" in check(vectors=[[1] * 7, [], [], []])[0]


def test_plan_needs_the_drawn_tokens_weights_and_mask():
    class Obj:
        kind = "attention"
        data = {"tokens": TOKS, "weights": [[1, 0, 0, 0], [0.6, 0.4, 0, 0], [0.57, 0.42, 0.01, 0],
                                            [0.02, 0.05, 0.9, 0.03]], "softmax": True, "mask": "causal",
                "focus": "creature"}
    ok = leaf(f'<attention id="x" tokens="fluffy,blue,creature,roamed" weights="{SOFT}" softmax="true" '
              f'mask="causal" focus="creature"></attention>')
    assert get("attention").check_drawn("b0", Obj, [ok]) == []
    bare = leaf(f'<attention id="x" tokens="fluffy,blue,creature,roamed" weights="{SOFT}"></attention>')
    got = " ".join(get("attention").check_drawn("b0", Obj, [bare]))
    assert 'softmax="true"' in got and 'mask="causal"' in got and 'focus="creature"' in got
    wrong = leaf('<attention id="x" tokens="fluffy,creature" weights="1,0;0,1"></attention>')
    assert "planned words" in get("attention").check_drawn("b0", Obj, [wrong])[0]


def test_one_room_and_one_score_scale_for_the_scene():
    a, b, c = scene('view="words" vectors="1,2;3,4;5,6;7,8"', f'weights="{RAW}"',
                    f'view="both" weights="{SOFT}" softmax="true" focus="creature"')
    assert a.attrs["_room"] == b.attrs["_room"] == c.attrs["_room"] == "grid=1;arcs=1;qk=0;vec=2;rows=4"
    assert a.attrs["_scale"] == "6"            # the largest raw score anywhere in the scene


# --- the picture --------------------------------------------------------------------------------
@manim
def test_words_stay_put_across_views():
    from konvey.stage.displays.attention.mobject import AttentionBlock

    blocks = [AttentionBlock(n) for n in scene('view="words" vectors="1,2;3,4;5,6;7,8"', f'weights="{RAW}" qk="true"',
                                                f'view="words" weights="{SOFT}" softmax="true" focus="creature"')]
    ref = [w.get_center() for w in blocks[0].words]
    for blk in blocks[1:]:
        assert np.allclose([w.get_center() for w in blk.words], ref, atol=1e-6)
        assert np.allclose(blk.canvas.get_center(), blocks[0].canvas.get_center())
        assert abs(blk.get_width() - blocks[0].get_width()) < 1e-6


@manim
def test_grid_has_queries_across_and_keys_down_with_dots_sized_by_weight():
    from konvey.stage.displays.attention.mobject import AttentionBlock

    a = AttentionBlock(leaf(f'<attention id="x" tokens="fluffy,blue,creature,roamed" weights="{SOFT}" '
                            f'softmax="true" mask="causal"></attention>'))
    n = 4
    cell = lambda key, query: a.cells[key * n + query]   # noqa: E731
    for q in range(n):     # a query's column sits under its word, a key's row beside its label
        assert abs(cell(0, q)[1].get_x() - a.words[q].get_x()) < 1e-6
    for k in range(n):
        assert abs(cell(k, 0)[1].get_y() - a.keys[k].get_y()) < 1e-6
        assert a.keys[k].get_right()[0] < a.lines.get_left()[0]
    assert cell(0, 2)[1].get_width() > cell(1, 2)[1].get_width() > cell(2, 2)[1].get_width()   # .57 > .42 > .01
    assert cell(3, 1)[1].get_fill_opacity() == 0 and cell(3, 1)[0].get_stroke_opacity() > 0    # masked: later key
    assert cell(0, 3)[0].get_stroke_opacity() == 0                                             # earlier key: open


@manim
def test_arrows_come_from_attended_words_into_the_focus_and_labels_stay_clear():
    from konvey.stage.displays.attention.mobject import AttentionBlock

    a = AttentionBlock(leaf(f'<attention id="x" tokens="fluffy,blue,creature,roamed" weights="{SOFT}" '
                            f'softmax="true" mask="causal" focus="creature" view="words"></attention>'))
    drawn = [j for j, g in enumerate(a.arrows) if g.family_members_with_points()]
    assert drawn == [0, 1]                    # not itself (0.01 is too small anyway), not the masked word
    for j in drawn:
        arrow, lab, _ = a.arrows[j]
        assert arrow.get_bottom()[1] >= a.words.get_top()[1] - 1e-6      # arcs over the words
        assert abs(arrow.get_end()[0] - a.words[2].get_x()) < a.words[2].get_width() / 2
        assert lab.get_bottom()[1] > a.words.get_top()[1]
    l0, l1 = a.arrows[0][1], a.arrows[1][1]
    assert l0.get_right()[0] < l1.get_left()[0]
    assert len(a.frame) == 1 and a.frame[0].get_top()[1] > a.words[2].get_top()[1]


@manim
def test_bad_weights_name_the_problem():
    from konvey.stage.displays.attention.mobject import AttentionBlock

    with pytest.raises(BeatError, match="3 groups for 4 tokens"):
        AttentionBlock(leaf('<attention id="x" tokens="a,b,c,d" weights="1,0,0,0;1,0,0,0;1,0,0,0"></attention>'))
    with pytest.raises(BeatError, match="sum to"):
        AttentionBlock(leaf('<attention id="x" tokens="a,b" weights="0.5,0.2;0,1" softmax="true"></attention>'))
    with pytest.raises(BeatError, match="not one of the tokens"):
        AttentionBlock(leaf('<attention id="x" tokens="a,b" focus="c"></attention>'))


@manim
def test_morph_plays_the_mechanism():
    from manimlib import UpdateFromAlphaFunc

    from konvey.stage.displays.attention.mobject import AttentionBlock, morph

    words, raw, soft, arrows, moved = [AttentionBlock(n) for n in scene(
        'view="words" vectors="1,2;3,4;5,6;7,8"', f'weights="{RAW}"',
        f'weights="{SOFT}" softmax="true" mask="causal" focus="creature"',
        f'view="words" weights="{SOFT}" softmax="true" mask="causal" focus="creature" vectors="1,2;3,4;5,6;7,8"',
        f'view="words" weights="{SOFT}" softmax="true" mask="causal" focus="creature" vectors="1,2;3,4;9,9;7,8"')]

    def carriers(anim):
        out = []
        for a in getattr(anim, "animations", [anim]):
            out += carriers(a) if hasattr(a, "animations") else [a]
        return [a for a in out if isinstance(a, UpdateFromAlphaFunc)]
    assert morph(words, raw) is not None
    assert len(carriers(morph(raw, soft))) == 1                 # the softmax sweep
    assert len(carriers(morph(arrows, moved))) == 3             # two values along two arrows + a flash
    assert not carriers(morph(soft, soft))
