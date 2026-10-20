"""``<relation>`` (kind ``relation``): how strongly the items of one or two lists relate, laid out
by the renderer (attention, word alignment, confusion matrices, similarity)."""

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
EN, FR = ["the", "blue", "cat"], ["le", "chat", "bleu"]
ALIGN = "0.9,0.05,0.05;0.05,0.1,0.85;0.05,0.85,0.1"      # per English word: its weight on each French word


def leaf(html: str, i: str = "x"):
    return parse_beats(f"<beats><beat>{html}</beat></beats>")[0].leaves()[i]


def scene(*attrs: str, lists: str = f'cols="{",".join(TOKS)}"'):
    """One <relation id=x> per beat, prepared as the scene would be (shared room)."""
    body = "".join(f'<beat><relation id="x" {lists} {a}></relation></beat>' for a in attrs)
    beats = parse_beats(f"<beats>{body}</beats>")
    prepare_beats(beats)
    return [b.leaves()["x"] for b in beats]


TWO = f'cols="{",".join(EN)}" rows="{",".join(FR)}"'


# --- the plan -----------------------------------------------------------------------------------
def check(**d):
    return get("relation").check_object({"cols": TOKS, **d})


def test_plan_weights_are_one_group_per_column_and_normalised_columns_sum_to_one():
    assert check(weights=[[1, 0, 0, 0], [0.6, 0.4, 0, 0], [0.57, 0.42, 0.01, 0], [0.02, 0.05, 0.9, 0.03]],
                 normalize="columns", mask="later") == []
    assert check(weights=[[1, 0, 0, 0], [0.6, 0.4, 0, 0], [0.57, 0.42, 0.01, 0], [0.02, 0.05, 0.9, 0.03]],
                 normalize="columns", mask="causal") == []           # the attention word still works
    assert "4 groups of 4" in check(weights=[[1, 0, 0, 0]])[0]
    assert "sum to 0.9" in check(weights=[[0.5, 0.4, 0, 0], [], [], []], normalize="columns")[0]
    assert "must have weight 0" in check(weights=[[0.5, 0.5, 0, 0], [], [], []], normalize="columns", mask="later")[0]
    assert check(weights=[[], [], [6, 5.5, 1, 0.2], []]) == []          # only one column computed yet
    assert "not one of the cols" in check(focus="dog")[0]
    assert "view" in check(view="table")[0]


def test_plan_two_lists_rows_normalise_and_one_list_only_options():
    two = lambda **d: get("relation").check_object({"cols": EN, "rows": FR, **d})   # noqa: E731
    w = [[0.9, 0.05, 0.05], [0.05, 0.1, 0.85], [0.05, 0.85, 0.1]]
    assert two(weights=w, view="links") == []
    assert "3 groups of 3" in two(weights=w[:2])[0]
    assert "needs one list" in two(mask="later")[0]
    assert "needs one list" in two(view="both")[0]
    assert "not one of the rows" in two(focus_row="cat")[0]
    # a confusion matrix: rows = actual, normalised by row (each actual class sums to 1)
    conf = lambda w: get("relation").check_object(   # noqa: E731
        {"cols": ["said cat", "said dog"], "rows": ["cat", "dog"], "weights": w, "normalize": "rows"})
    assert conf([[0.8, 0.3], [0.2, 0.7]]) == []
    assert "row" in conf([[0.8, 0.3], [0.3, 0.7]])[0]


def test_plan_needs_the_drawn_lists_weights_and_mask():
    class Obj:
        kind = "relation"
        data = {"cols": TOKS, "weights": [[1, 0, 0, 0], [0.6, 0.4, 0, 0], [0.57, 0.42, 0.01, 0],
                                          [0.02, 0.05, 0.9, 0.03]], "normalize": "columns", "mask": "later",
                "focus": "creature"}
    ok = leaf(f'<relation id="x" cols="fluffy,blue,creature,roamed" weights="{SOFT}" normalize="columns" '
              f'mask="later" focus="creature"></relation>')
    assert get("relation").check_drawn("b0", Obj, [ok]) == []
    bare = leaf(f'<relation id="x" cols="fluffy,blue,creature,roamed" weights="{SOFT}"></relation>')
    got = " ".join(get("relation").check_drawn("b0", Obj, [bare]))
    assert 'normalize="columns"' in got and 'mask="later"' in got and 'focus="creature"' in got
    wrong = leaf('<relation id="x" cols="fluffy,creature" weights="1,0;0,1"></relation>')
    assert "planned items" in get("relation").check_drawn("b0", Obj, [wrong])[0]

    class Two:
        kind = "relation"
        data = {"cols": EN, "rows": FR}
    assert get("relation").check_drawn("b0", Two, [leaf(f'<relation id="x" {TWO}></relation>')]) == []
    one = leaf(f'<relation id="x" cols="{",".join(EN)}"></relation>')
    assert "planned rows" in get("relation").check_drawn("b0", Two, [one])[0]


def test_one_room_and_one_score_scale_for_the_scene():
    a, b, c = scene('view="links"', f'weights="{RAW}"',
                    f'view="both" weights="{SOFT}" normalize="columns" focus="creature"')
    assert a.attrs["_room"] == b.attrs["_room"] == c.attrs["_room"] == \
        "grid=1;arcs=2;links2=0;rows=4;cols=4"
    assert a.attrs["_scale"] == "6"            # the largest raw weight anywhere in the scene
    d, e = scene(f'view="links" weights="{ALIGN}"', f'weights="{ALIGN}"', lists=TWO)
    assert d.attrs["_room"] == e.attrs["_room"] == "grid=1;arcs=0;links2=1;rows=3;cols=3"


# --- the picture --------------------------------------------------------------------------------
@manim
def test_items_stay_put_across_views():
    from konvey.stage.displays.relation.mobject import RelationBlock

    blocks = [RelationBlock(n) for n in scene('view="links"', f'weights="{RAW}"',
                                               f'view="links" weights="{SOFT}" normalize="columns" focus="creature"')]
    ref = [w.get_center() for w in blocks[0].words]
    for blk in blocks[1:]:
        assert np.allclose([w.get_center() for w in blk.words], ref, atol=1e-6)
        assert np.allclose(blk.canvas.get_center(), blocks[0].canvas.get_center())
        assert abs(blk.get_width() - blocks[0].get_width()) < 1e-6


@manim
def test_grid_has_columns_across_and_rows_down_with_dots_sized_by_weight():
    from konvey.stage.displays.relation.mobject import RelationBlock

    a = RelationBlock(leaf(f'<relation id="x" cols="fluffy,blue,creature,roamed" weights="{SOFT}" '
                           f'normalize="columns" mask="later"></relation>'))
    n = 4
    for q in range(n):     # a column sits under its item, a row beside its label
        assert abs(a.cell(0, q)[1].get_x() - a.words[q].get_x()) < 1e-6
    for k in range(n):
        assert abs(a.cell(k, 0)[1].get_y() - a.keys[k].get_y()) < 1e-6
        assert a.keys[k].get_right()[0] < a.lines.get_left()[0]
    assert a.cell(0, 2)[1].get_width() > a.cell(1, 2)[1].get_width() > a.cell(2, 2)[1].get_width()
    assert a.cell(3, 1)[1].get_fill_opacity() == 0 and a.cell(3, 1)[0].get_stroke_opacity() > 0   # masked
    assert a.cell(0, 3)[0].get_stroke_opacity() == 0                                              # open


@manim
def test_two_lists_grid_is_rows_by_cols_and_links_join_the_lines():
    from konvey.stage.displays.relation.mobject import RelationBlock

    g, l2 = [RelationBlock(n) for n in scene(f'weights="{ALIGN}" normalize="columns"',
                                             f'view="links" weights="{ALIGN}" normalize="columns"', lists=TWO)]
    assert len(g.keys) == 3 and len(g.cells) == 9 and not any(r.family_members_with_points() for r in g.rowwords)
    assert np.allclose([w.get_center() for w in g.words], [w.get_center() for w in l2.words])
    drawn = [k for k, p in enumerate(l2.links) if p.family_members_with_points()]
    assert len(drawn) == 9                    # no focus: every pair's line (all weights >= 0.05)
    the_le = l2.links[0 * 3 + 0][0]           # "the" (col 0) with "le" (row 0): 0.9, thick
    blue_le = l2.links[0 * 3 + 1][0]          # "blue" with "le": 0.05, thin
    assert the_le.get_stroke_width() > 3 * blue_le.get_stroke_width()
    for r in range(3):
        assert l2.rowwords[r].get_top()[1] < l2.words.get_bottom()[1]
    # the lines run from each row item up to its column item
    p = l2.links[2 * 3 + 1][0]                # row 2 "bleu" with column 1 "blue"
    assert abs(p.get_end()[0] - l2.words[1].get_x()) < 1e-6
    assert abs(p.get_start()[0] - l2.rowwords[2].get_x()) < 1e-6


@manim
def test_arrows_come_from_related_items_into_the_focus_and_labels_stay_clear():
    from konvey.stage.displays.relation.mobject import RelationBlock

    a = RelationBlock(leaf(f'<relation id="x" cols="fluffy,blue,creature,roamed" weights="{SOFT}" '
                           f'normalize="columns" mask="later" focus="creature" view="links"></relation>'))
    drawn = [j for j, g in enumerate(a.arrows) if g.family_members_with_points()]
    assert drawn == [0, 1]                    # not itself (0.01 is too small anyway), not the masked item
    for j in drawn:
        arrow, lab, _ = a.arrows[j]
        assert arrow.get_bottom()[1] >= a.words.get_top()[1] - 1e-6      # arcs over the items
        assert abs(arrow.get_end()[0] - a.words[2].get_x()) < a.words[2].get_width() / 2
        assert lab.get_bottom()[1] > a.words.get_top()[1]
    l0, l1 = a.arrows[0][1], a.arrows[1][1]
    assert l0.get_right()[0] < l1.get_left()[0]
    assert len(a.frame) == 1 and a.frame[0].get_top()[1] > a.words[2].get_top()[1]


@manim
def test_bad_weights_name_the_problem():
    from konvey.stage.displays.relation.mobject import RelationBlock

    with pytest.raises(BeatError, match="3 groups for 4 columns"):
        RelationBlock(leaf('<relation id="x" cols="a,b,c,d" weights="1,0,0,0;1,0,0,0;1,0,0,0"></relation>'))
    with pytest.raises(BeatError, match="sum to"):
        RelationBlock(leaf('<relation id="x" cols="a,b" weights="0.5,0.2;0,1" normalize="columns"></relation>'))
    with pytest.raises(BeatError, match="not one of the items"):
        RelationBlock(leaf('<relation id="x" cols="a,b" focus="c"></relation>'))
    with pytest.raises(BeatError, match="needs one list"):
        RelationBlock(leaf('<relation id="x" cols="a,b" rows="x,y" mask="later"></relation>'))


def _carriers(anim):
    from manimlib import UpdateFromAlphaFunc

    out = []
    for a in getattr(anim, "animations", [anim]):
        out += _carriers(a) if hasattr(a, "animations") else [a]
    return [a for a in out if isinstance(a, UpdateFromAlphaFunc)]


@manim
def test_morph_plays_the_mechanism_and_the_focus_weights_are_sources():
    from konvey.stage.displays.relation.mobject import RelationBlock, morph, sources

    words, raw, soft, arrows = [RelationBlock(n) for n in scene(
        'view="links"', f'weights="{RAW}"',
        f'weights="{SOFT}" normalize="columns" mask="later" focus="creature" numbers="true"',
        f'view="links" weights="{SOFT}" normalize="columns" mask="later" focus="creature"')]
    assert morph(words, raw) is not None
    assert len(_carriers(morph(raw, soft))) == 1                # the normalise sweep
    assert not _carriers(morph(soft, soft))
    assert [v for v, _ in sources(soft, raw)] == ["0.57", "0.42", "0.01", "0"]   # the focus column's cells
    assert [v for v, _ in sources(arrows, soft)] == ["0.57", "0.42"]             # the arcs drawn


@manim
def test_two_list_morphs_and_row_sweep():
    from konvey.stage.displays.relation.mobject import RelationBlock, morph

    links, grid, back = [RelationBlock(n) for n in scene(
        f'view="links" weights="{ALIGN}"', f'weights="{ALIGN}"', f'view="links" weights="{ALIGN}"', lists=TWO)]
    assert morph(links, grid) is not None and morph(grid, back) is not None
    raw, rows = [RelationBlock(n) for n in scene('weights="8,2;3,7"', 'weights="0.8,0.3;0.2,0.7" normalize="rows"',
                                                 lists='cols="said cat,said dog" rows="cat,dog"')]
    sweep = _carriers(morph(raw, rows))
    assert len(sweep) == 1


@manim
def test_two_list_sources_skip_missing_links():
    from konvey.stage.displays.relation.mobject import RelationBlock, sources

    blk, = [RelationBlock(n) for n in scene(f'view="links" weights="{ALIGN}" normalize="columns" focus="blue"',
                                            lists=TWO)]
    assert [v for v, _ in sources(blk, None)] == ["0.05", "0.1", "0.85"]
    none = RelationBlock(scene(f'view="links" weights="{ALIGN}"', lists=TWO)[0])
    assert sources(none, None) == []
