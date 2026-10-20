"""Grid windows/heat and graph flows/edge values/weighted edges (fixer fxf)."""

import importlib.util

import numpy as np
import pytest

from konvey.schemas import ObjectSpec
from konvey.stage.parse import BeatError, parse_beats, prepare_beats
from konvey.validators import _object_problems

HAS_MANIM = importlib.util.find_spec("manimlib") is not None
manim = pytest.mark.skipif(not HAS_MANIM, reason="needs manimgl (uv --group render)")

IMG = "1,2,8,9,9;0,1,7,9,8;1,1,8,8,9;0,2,9,9,9;1,1,8,9,8"
K = "-1,0,1;-1,0,1;-1,0,1"


def leaf(html: str, i: str = "x"):
    return parse_beats(f"<beats><beat>{html}</beat></beats>")[0].leaves()[i]


def _anims(a):
    """Every animation inside a group (Succession included)."""
    out = [a]
    for sub in getattr(a, "animations", []):
        out += _anims(sub)
    return out


# --- plan checks (pure Python) ------------------------------------------------------------
def test_grid_plan_window_kernel_heat():
    ok = {"rows": 5, "cols": 5, "window": [1, 2, 3, 3], "kernel": [[1, 0, -1]] * 3, "heat": True}
    assert _object_problems(ObjectSpec(id="g", kind="grid", data=ok)) == []
    bad = lambda **d: _object_problems(ObjectSpec(id="g", kind="grid", data={"rows": 5, "cols": 5, **d}))  # noqa: E731
    assert "does not fit" in bad(window=[3, 3, 3, 3])[0]
    assert "kernel needs 9" in bad(window=[0, 0, 3, 3], kernel=[1, 2])[0]
    assert "needs a window" in bad(kernel=[1])[0]
    assert "heat" in bad(heat=[5, 1])[0]


def test_grid_window_drawn_check():
    from konvey.stage.displays import get

    obj = ObjectSpec(id="img", kind="grid", data={"rows": 5, "cols": 5, "window": [0, 1, 3, 3]})
    drawn = [leaf('<grid id="img" rows="5" cols="5" window="0,1,3,3"></grid>', "img")]
    assert get("grid").check_drawn("b0", obj, drawn) == []
    other = [leaf('<grid id="img" rows="5" cols="5" window="0,0,3,3"></grid>', "img")]
    assert 'window="0,1,3,3"' in get("grid").check_drawn("b0", obj, other)[0]


def test_heat_range_is_scene_wide():
    beats = parse_beats('<beats><beat><grid id="m" rows="1" cols="2" values="1," heat="true"></grid></beat>'
                        '<beat><grid id="m" rows="1" cols="2" values="1,9" heat="true"></grid></beat></beats>')
    prepare_beats(beats, strict=False)
    assert {b.leaves()["m"].attrs["_heat"] for b in beats} == {"1.0,9.0"}


def test_graph_plan_flow_edge_values_weighted():
    base = {"nodes": ["x", "h", "y"], "edges": [["x", "h", 0.5], ["h", "y", 0.8]]}
    p = lambda **d: _object_problems(ObjectSpec(id="n", kind="graph", data={**base, **d}))  # noqa: E731
    assert p(flow=["y", "h", "x"], edge_values={"h-y": -0.3}, strength=True) == []
    assert "no edge" in p(flow=["x", "y"])[0]
    assert "no edge between" in p(edge_values={"x-y": 1})[0]
    assert "number weight" in _object_problems(ObjectSpec(id="n", kind="graph", data={
        "nodes": ["a", "b"], "edges": [["a", "b"]], "weighted": True}))[0]
    assert "graph strength" in _object_problems(ObjectSpec(id="n", kind="graph", data={
        "nodes": ["a", "b"], "edges": [["a", "b"]], "strength": True}))[0]


def test_graph_drawn_check_needs_edge_values_and_flow():
    from konvey.stage.displays import get

    obj = ObjectSpec(id="n", kind="graph", data={"nodes": ["x", "h"], "edges": [["x", "h"]],
                                                 "edge_values": {"x-h": 0.2}, "flow": ["h", "x"]})
    good = leaf('<graph id="n" nodes="x:0,0;h:1,0" edges="x>h" edge-values="h-x:0.2" flow="h>x"></graph>', "n")
    assert get("graph").check_drawn("b1", obj, [good]) == []
    bare = leaf('<graph id="n" nodes="x:0,0;h:1,0" edges="x>h"></graph>', "n")
    assert len(get("graph").check_drawn("b1", obj, [bare])) == 2


# --- mobjects ---------------------------------------------------------------------------------
@manim
def test_grid_window_frames_cells_and_kernel_sits_inside():
    from konvey.stage.displays.grid.mobject import GridBlock

    g = GridBlock(leaf(f'<grid id="x" rows="5" cols="5" values="{IMG}" window="1,2,3,3" kernel="{K}"></grid>'))
    frame, weights = g.window
    assert len(weights) == 9
    first, last = g.cells[1 * 5 + 2][0], g.cells[3 * 5 + 4][0]
    assert frame.get_left()[0] < first.get_left()[0] and frame.get_right()[0] > last.get_right()[0]
    for w, (i, j) in zip(weights, [(i, j) for i in range(3) for j in range(3)]):
        box = g.cells[(1 + i) * 5 + 2 + j][0]
        assert box.get_left()[0] < w.get_center()[0] < box.get_right()[0]
    with pytest.raises(BeatError, match="window"):
        GridBlock(leaf('<grid id="x" rows="2" cols="2" values="1,2,3,4" window="1,1,2,2"></grid>'))
    with pytest.raises(BeatError, match="4 weights"):
        GridBlock(leaf('<grid id="x" rows="2" cols="2" values="1,2,3,4" window="0,0,1,1" kernel="1,2,3,4"></grid>'))


@manim
def test_grid_heat_colours_by_value_with_readable_text():
    from konvey.stage.displays.grid.mobject import GridBlock
    from konvey.stage.theme import current

    g = GridBlock(leaf('<grid id="x" rows="1" cols="3" values="0,5,10" heat="true"></grid>'))
    fills = [c[0].get_fill_color().lower() for c in g.cells]
    assert len(set(fills)) == 3 and fills[2] == current().accent.lower()
    assert g.cells[2][1].get_fill_color().lower() == current().bg.lower()     # dark text on the bright cell


@manim
def test_grid_window_slides_cell_by_cell_and_cells_fill_in_order():
    from manimlib import Succession
    from konvey.stage.displays.grid.mobject import GridBlock, morph

    a = GridBlock(leaf(f'<grid id="x" rows="5" cols="5" values="{IMG}" window="0,2,3,3" kernel="{K}"></grid>'))
    b = GridBlock(leaf(f'<grid id="x" rows="5" cols="5" values="{IMG}" window="1,1,3,3" kernel="{K}"></grid>'))
    slide = next(x for x in _anims(morph(a, b)) if isinstance(x, Succession))
    assert len(slide.animations) == 2                  # (1,0) then (1,1): reading order
    f0 = GridBlock(leaf('<grid id="y" rows="1" cols="3" values="1,," heat="true"></grid>', "y"))
    f1 = GridBlock(leaf('<grid id="y" rows="1" cols="3" values="1,2,3" heat="true"></grid>', "y"))
    flashes = [x for x in _anims(morph(f0, f1)) if getattr(x, "remover", False)]
    assert len(flashes) == 2                           # one flash per newly filled cell


@manim
def test_graph_value_label_clears_a_wide_label_and_long_names_widen_the_node():
    from konvey.stage.displays.graph.mobject import GraphBlock

    g = GraphBlock(leaf('<graph id="x" nodes="x:0,0;h:2,0;yhat:4,0" edges="x>h;h>yhat" '
                        'values="yhat:0.497967;x:1.0"></graph>'))
    node, val = g.nodes[2], g.values[2]
    assert val.get_left()[0] > node.get_right()[0]          # beside the node, not on it
    wide = GraphBlock(leaf('<graph id="x" nodes="activation:0,0;output:3,0" edges="activation-output"></graph>'))
    assert wide.nodes[0][0].get_width() > wide.nodes[0][0].get_height()   # a stadium, not a squashed name
    assert wide.nodes[0][1].get_width() < wide.nodes[0][0].get_width()


@manim
def test_graph_edge_values_weighted_and_antiparallel_edges():
    from konvey.stage.displays.graph.mobject import GraphBlock

    g = GraphBlock(leaf('<graph id="x" nodes="a:0,0;b:3,0" edges="a>b:0.9;b>a:0.1" strength="true" '
                        'edge-values="b-a:-0.3"></graph>'))
    assert g.edge_text == ["-0.3", ""]
    thick, thin = (e[0].get_stroke_width() for e in g.edges)
    assert thick > thin
    assert abs(g.edges[0][0].get_center()[1] - g.edges[1][0].get_center()[1]) > 0.1   # side by side
    with pytest.raises(BeatError, match="number weight"):
        GraphBlock(leaf('<graph id="x" nodes="a,b" edges="a-b" weighted="true"></graph>'))
    with pytest.raises(BeatError, match="strength"):
        GraphBlock(leaf('<graph id="x" nodes="a,b" edges="a-b" strength="true"></graph>'))
    # weighted: costs or distances on the edges, shown as numbers; every edge as thick as the next
    roads = GraphBlock(leaf('<graph id="x" nodes="a:0,0;b:3,0;c:3,2" edges="a-b:7;b-c:1" weighted="true"></graph>'))
    assert len({e[0].get_stroke_width() for e in roads.edges}) == 1
    with pytest.raises(BeatError, match="flow"):
        GraphBlock(leaf('<graph id="x" nodes="a,b,c" edges="a-b" flow="a>c"></graph>'))


@manim
def test_graph_flow_sends_one_packet_per_leg_only_when_new():
    from konvey.stage.displays.graph.mobject import GraphBlock, morph

    base = 'nodes="x:0,0;h:2,0;y:4,0" edges="x>h;h>y"'
    a = GraphBlock(leaf(f'<graph id="g" {base} values="x:1"></graph>', "g"))
    b = GraphBlock(leaf(f'<graph id="g" {base} values="x:1;h:0.6;y:0.4" flow="x>h>y"></graph>', "g"))
    c = GraphBlock(leaf(f'<graph id="g" {base} values="x:1;h:0.6;y:0.4" edge-values="h-y:-0.1" '
                        'flow="x>h>y"></graph>', "g"))
    packets = lambda m: [x for x in _anims(m) if getattr(x, "remover", False)]  # noqa: E731
    assert len(packets(morph(a, b))) == 2
    assert packets(morph(b, c)) == []                   # the same flow again does not replay
    assert np.allclose(b.leg("h", "x")[1], b.leg("x", "h")[2])


@manim
def test_grid_smaller_size_makes_shorter_cells_and_chips_fit():
    from konvey.stage.displays.grid.mobject import GridBlock

    big = GridBlock(leaf('<grid id="x" rows="5" cols="5" values="' + IMG + '"></grid>'))
    small = GridBlock(leaf(f'<grid id="x" rows="5" cols="5" values="{IMG}" size="18" window="0,0,3,3" kernel="{K}"></grid>'))
    assert small.get_height() < 0.7 * big.get_height()       # size= buys room, not only smaller digits
    for chip, k in zip(small.window[1], range(9)):
        assert chip.get_width() < small.cells[k][0].get_width() * 0.5


HAS_CHROMIUM = importlib.util.find_spec("playwright") is not None and __import__("pathlib").Path("/usr/bin/chromium").exists()


@pytest.mark.skipif(not (HAS_MANIM and HAS_CHROMIUM), reason="needs manimgl + Chromium")
def test_two_big_grids_side_by_side_shrink_to_fit(tmp_path):
    """A 5x5 board with a window next to a 3x3 grid (under a headline and a formula, a third
    grid below; or at size 40): the grids scale down to their room instead of the beat being
    rejected (a run was rejected for this after two repairs)."""
    from konvey.stage.check import check_runtime

    def beat(size, extra):
        return ('<beat vo="x." t="1" style="padding: 0.5u 0.6u; gap: 0.2u"><h3 id="t">Title</h3>'
                + extra[0] + '<div class="grow row center" style="gap: 0.8u">'
                f'<grid id="img" rows="5" cols="5" values="{IMG}" window="0,0,3,3" kernel="{K}" size="{size}"></grid>'
                f'<grid id="k" rows="3" cols="3" values="{K}" size="{size}"></grid></div>' + extra[1] + '</beat>')
    tex = '<tex id="r" size="26">S_{i,j} = \\sum_a \\sum_b K_{a,b} I_{i+a,j+b}</tex>'
    fm = '<div class="row center"><grid id="fm" rows="3" cols="3" values=",,;,,;,," heat="true" size="18"></grid></div>'
    html = "<beats>" + beat(18, (tex, fm)) + beat(40, ("", "")) + "</beats>"
    assert check_runtime(html, tmp_path, "S2") == []


@manim
def test_graph_unknown_value_draws_nothing_and_lone_graphs_grow():
    from konvey.stage.displays import get
    from konvey.stage.displays.graph.mobject import GraphBlock

    chain = GraphBlock(leaf('<graph id="x" nodes="x:0,0;h:3,0;y:6,0" edges="x>h;h>y" values="x:1;h:?;y:None"></graph>'))
    assert chain.value_text == ["1", "", ""]                       # no stray "?" by h
    assert get("graph").grow and get("grid").grow                  # the layout scales a lone one into its room


@manim
def test_graph_sparse_chain_grows_its_nodes_and_labels_clear_them():
    from konvey.stage.displays.graph.mobject import NODE_R, GraphBlock

    chain = GraphBlock(leaf('<graph id="x" nodes="x:0,0;h:3,0;y:6,0" edges="x>h:0.5;h>y:0.8" '
                            'values="x:1;h:0.622459;y:0.497967" edge-values="h-y:-0.62" w="9" h="2"></graph>'))
    dense = GraphBlock(leaf('<graph id="x" nodes="A,B,C,D,E,F,G,H" edges="A-B"></graph>'))
    assert 1.4 * NODE_R < chain.nodes[0][0].get_height() / 2 <= 1.6 * NODE_R + 1e-6
    assert abs(dense.nodes[0][0].get_height() - 2 * NODE_R) < 1e-6
    for n, v in zip(chain.nodes, chain.values):       # values clear of their nodes
        assert v.get_bottom()[1] > n.get_top()[1] or v.get_left()[0] > n.get_right()[0] \
            or v.get_right()[0] < n.get_left()[0]
    line = chain.edges[1][0]
    assert chain.weights[1].get_bottom()[1] > line.get_center()[1] > chain.edge_labels[1].get_top()[1]
