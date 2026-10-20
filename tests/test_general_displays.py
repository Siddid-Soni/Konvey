"""General pieces that replaced ``<relation>``: a grid with named rows/columns, dots, strikes and
a line-by-line sweep; a graph laid out in one or two rows (arcs, a matching)."""

import importlib.util

import pytest

from konvey.stage.displays import get
from konvey.stage.parse import BeatError, parse_beats, prepare_beats

HAS_MANIM = importlib.util.find_spec("manimlib") is not None
manim = pytest.mark.skipif(not HAS_MANIM, reason="needs manimgl (uv --group render)")

G = 'rows="3" cols="3" row-labels="cat,dog,fox" col-labels="said cat,said dog,said fox"'


def scene(*tags: str):
    beats = parse_beats("<beats>" + "".join(f"<beat>{t}</beat>" for t in tags) + "</beats>")
    prepare_beats(beats)
    return [list(b.leaves().values())[0] for b in beats]


def test_grid_plan_checks_labels_dots_strike_sweep():
    check = get("grid").check_object
    ok = {"rows": 2, "cols": 2, "values": [[1, 2], [3, 4]], "row_labels": ["a", "b"], "col_labels": ["x", "y"],
          "cells": "dots", "strike": "below", "sweep": "columns"}
    assert check(ok) == []
    assert "row_labels" in check({**ok, "row_labels": ["a"]})[0]
    assert "cells" in check({**ok, "cells": "bars"})[0]
    assert "sweep" in check({**ok, "sweep": "diagonal"})[0]
    assert "strike" in check({**ok, "strike": [[5, 5]]})[0]


def test_grid_drawn_needs_the_planned_names():
    class Obj:
        kind = "grid"
        data = {"rows": 3, "cols": 3, "row_labels": ["cat", "dog", "fox"], "cells": "dots"}
    good, = scene(f'<grid id="g" {G} cells="dots"></grid>')
    assert get("grid").check_drawn("b0", Obj, [good]) == []
    bare, = scene('<grid id="g" rows="3" cols="3"></grid>')
    got = " ".join(get("grid").check_drawn("b0", Obj, [bare]))
    assert 'row-labels="cat,dog,fox"' in got and 'cells="dots"' in got


def test_graph_plan_checks_layout():
    check = get("graph").check_object
    assert check({"nodes": ["a", "b"], "edges": [["a", "b", 1]], "layout": "line"}) == []
    assert "layout" in check({"nodes": ["a"], "edges": [], "layout": "circle"})[0]
    assert "lines" in check({"nodes": ["a", "x"], "edges": [], "layout": "two-lines"})[0]


@manim
def test_grid_names_dots_and_strikes():
    from konvey.stage.displays.grid.mobject import GridBlock

    g = GridBlock(scene(f'<grid id="g" {G} values="8,1,1;2,6,2;1,1,4" cells="dots" strike="above"></grid>')[0])
    assert len(g.col_heads) == 3 and len(g.row_heads) == 3
    for c in range(3):                                   # names over their columns, beside their rows
        assert abs(g.col_heads[c].get_x() - g.cells[c].get_x()) < 1e-6
        assert g.col_heads[c].get_bottom()[1] > g.cells[c].get_top()[1]
        assert g.row_heads[c].get_right()[0] < g.cells[c * 3].get_left()[0]
    assert g.cells[0][2].get_width() > g.cells[4][2].get_width() > g.cells[8][2].get_width()   # 8 > 6 > 4
    assert g.cells[1][3].get_stroke_opacity() > 0 and g.cells[3][3].get_stroke_opacity() == 0  # above: struck
    assert g.cells[1][2].get_fill_opacity() == 0                                                # struck: no dot
    with pytest.raises(BeatError, match="row-labels has 2 names"):
        GridBlock(scene('<grid id="g" rows="3" cols="1" row-labels="a,b"></grid>')[0])


@manim
def test_grid_sweep_strike_and_sources():
    from manimlib import UpdateFromAlphaFunc

    from konvey.stage.displays.grid.mobject import GridBlock, morph, sources

    raw, norm, lit = [GridBlock(n) for n in scene(
        f'<grid id="g" {G} values="40,8,2;6,30,4;3,5,22"></grid>',
        f'<grid id="g" {G} values="0.8,0.16,0.04;0.15,0.75,0.1;0.1,0.17,0.73" sweep="rows" op="÷ total"></grid>',
        f'<grid id="g" {G} values="0.8,0.16,0.04;0.15,0.75,0.1;0.1,0.17,0.73" highlight-rows="2"></grid>')]

    def carriers(anim):
        out = []
        for a in getattr(anim, "animations", [anim]):
            out += carriers(a) if hasattr(a, "animations") else [a]
        return [a for a in out if isinstance(a, UpdateFromAlphaFunc)]
    assert len(carriers(morph(raw, norm))) == 1           # one sweeping frame, no per-cell flashes
    assert [v for v, _ in sources(lit, norm)] == ["0.1", "0.17", "0.73"]


@manim
def test_graph_line_layout_arcs_land_on_the_target_and_two_lines_stack():
    from konvey.stage.displays.graph.mobject import GraphBlock, morph

    a, b = [GraphBlock(n) for n in scene(
        '<graph id="s" nodes="the,cat,sat,it" layout="line" edges="the>it:0.1;cat>it:0.8" strength="true"></graph>',
        '<graph id="s" nodes="the,cat,sat,it" layout="line" edges="cat>it:0.8;sat>it:0.1" strength="true"></graph>')]
    ys = {round(n.get_y(), 6) for n in a.nodes}
    assert len(ys) == 1                                       # one row
    assert all(a.nodes[i].get_x() < a.nodes[i + 1].get_x() for i in range(3))
    for e in a.edges:                                         # arcs above the row, ending over "it"
        assert e[0].get_top()[1] > a.nodes.get_top()[1]
        assert abs(e[0].get_end()[0] - a.nodes[3].get_x()) < a.nodes[3].get_width() / 2
    assert a.edges[1][0].get_stroke_width() > a.edges[0][0].get_stroke_width()
    assert morph(a, b) is not None                            # other edges: the nodes stay
    two = GraphBlock(scene('<graph id="m" nodes="the,cat|le,chat" layout="two-lines" edges="the-le:0.9;cat-chat:0.9" '
                           'strength="true" weight-labels="false"></graph>')[0])
    assert two.nodes[0].get_y() > two.nodes[2].get_y()
    assert not any(w.family_members_with_points() for w in two.weights)
    with pytest.raises(BeatError, match="two-lines"):
        GraphBlock(scene('<graph id="m" nodes="a,b" layout="two-lines" edges=""></graph>')[0])



@manim
def test_graph_line_layouts_light_a_node_and_a_route():
    from konvey.stage.displays.graph.mobject import GraphBlock
    from konvey.stage.theme import current

    for lay, nodes in (("line", "a,b,c"), ("two-lines", "a,b|c")):
        g = GraphBlock(scene(f'<graph id="g" nodes="{nodes}" layout="{lay}" edges="a-c;b-c" '
                             'highlight="c" path="a-c" lit-color="c4"></graph>')[0])
        assert g.lc != current().accent and len(g.nodes) == 3

CROWD = '<collection id="c" look="units"><li count="23"></li></collection>'
SPLIT = ('<collection id="c" look="units"><li count="2" mark>same</li>'
         '<li count="21">rest</li></collection>')


@manim
def test_collection_small_crowd_fills_its_box_and_keeps_its_rows():
    from konvey.stage.displays.collection.mobject import CollectionBlock

    alone = CollectionBlock(scene(CROWD)[0])
    assert alone.units[0][2].get_width() > 0.9            # bigger than the old 0.9-unit cap
    a, b = (CollectionBlock(n) for n in scene(CROWD, SPLIT))   # a later beat names two groups
    rows = lambda blk: len({round(u.get_y(), 3) for _, _, u in blk.units})
    assert rows(a) == rows(b)                              # no reflow when the legend appears
    assert abs(a.units[0][2].get_width() - b.units[0][2].get_width()) < 1e-6


def test_collection_reserves_legend_room_only_for_a_shown_legend():
    named = scene(CROWD, SPLIT)
    assert all(n.attrs.get("_legend") == "1" for n in named)
    piles = scene(CROWD, SPLIT.replace('look="units"', 'look="bins"'))   # bins name piles underneath
    assert not any(n.attrs.get("_legend") for n in piles)


STACKS = ('<collection id="s" look="stacks"><li>left <li size="3">3</li><li size="1">1</li></li>'
          '<li count="0">mid</li><li>right <li size="2">2</li></li></collection>')


@manim
def test_collection_stacks_piles_bottom_up_by_width_and_hops_a_moved_member():
    from konvey.stage.displays.collection.mobject import CollectionBlock, morph

    a, b = (CollectionBlock(n) for n in scene(STACKS, STACKS.replace('<li size="1">1</li></li><li count="0">mid</li>',
                                                                   '</li><li>mid <li size="1">1</li></li>')))
    units = {m.text: u for _, m, u in a.units}
    assert units["3"].get_y() < units["1"].get_y()                     # listed bottom to top
    assert units["3"].get_width() > units["2"].get_width() > units["1"].get_width()
    assert len(a.back) == len(b.back) == 6                               # a post and a base per group
    moved = {m.text: u for _, m, u in b.units}["1"]
    assert abs(moved.get_x() - units["1"].get_x()) > 0.5
    assert abs(moved.get_height() - units["1"].get_height()) < 1e-6      # same thickness on any pile
    anim = morph(a, b)
    assert type(anim.animations[0]).__name__ == "Transform"              # posts drawn first, under the move
    assert any(type(x).__name__ == "UpdateFromAlphaFunc" for x in anim.animations)


@manim
def test_highlight_colour_per_video_and_per_element(tmp_path):
    from konvey.render import set_highlight
    from konvey.stage import theme
    from konvey.stage.displays.array.mobject import ArrayBlock

    try:
        th = theme.use("editorial", "c2")
        assert th.lit == th.palette[1] != th.accent
        a = ArrayBlock(scene('<array id="a" values="1,2,3" highlight="1"></array>')[0])
        assert a.cells[1][0].get_stroke_color().lower() == th.palette[1].lower()
        b = ArrayBlock(scene('<array id="a" values="1,2,3" highlight="1" lit-color="#ff0000"></array>')[0])
        assert b.cells[1][0].get_stroke_color().lower() == "#ff0000"
        assert a.content != b.content                       # only the colour changed: still redrawn
        with pytest.raises(BeatError, match="lit-color"):
            ArrayBlock(scene('<array id="a" values="1" highlight="0" lit-color="nope"></array>')[0])
    finally:
        theme.use("editorial")
    py = tmp_path / "agent3-S1.py"
    py.write_text("class SingleScene(StageScene):\n    theme = 'editorial'\n")
    set_highlight(py, "c3")
    set_highlight(py, "#ffd166")                            # replaced, not added twice
    assert py.read_text().count("highlight =") == 1 and "'#ffd166'" in py.read_text()


@manim
def test_graph_nodes_listed_in_another_order_keep_their_own_places():
    """S1 lists A,B,C and S2 A,C,B (same map): B must not turn into C. A town added later
    fades in; every kept town moves to where the new beat puts it."""
    import numpy as np

    from konvey.stage.displays.graph.mobject import GraphBlock
    from konvey.stage.motion import morph     # the path a beat takes, display hook first

    a, b = (GraphBlock(n) for n in scene(
        '<graph id="g" nodes="A:0,0;B:2,2;C:2,-1" edges="A-B:4;A-C:2;B-C:1"></graph>',
        '<graph id="g" nodes="A:0,0;C:3,-1;B:2,2;D:4,1" edges="A-C:2;C-B:1;A-B:4;B-D:5"></graph>'))
    want = {n: b.nodes[b.names.index(n)].get_center().copy() for n in "ABC"}
    anim = morph(a, b)
    anim.begin()
    anim.interpolate(1.0)
    for n in "ABC":
        assert np.allclose(a.nodes[a.names.index(n)].get_center(), want[n], atol=1e-3), n
