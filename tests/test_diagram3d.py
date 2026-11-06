"""Block diagrams in the 3D world: layout, routing, repeats, per-beat state (konvey.stage.diagram3d)."""

import importlib.util

import numpy as np
import pytest

from konvey.stage.parse import BeatError, parse_beats

pytestmark = pytest.mark.skipif(importlib.util.find_spec("manimlib") is None, reason="needs manimgl")

TREE = ('<col dir="up" gap="0.3"><box id="a" text="In"></box>'
        '<repeat id="r" n="3" dir="up"><box id="b" text="Layer"></box></repeat>'
        '<box id="c" text="Out|put" shape="op"></box></col>'
        '<edge from="a" to="b"></edge><edge from="b" to="c" label="next"></edge>')


def world(*beats):
    from konvey.stage.field import FieldWorld

    bs = parse_beats("<beats>" + "".join(f"<beat><world>{b}</world></beat>" for b in beats) + "</beats>")
    fw = FieldWorld(bs)
    states, prev = [], None
    for b in bs:
        prev = fw.state_from(b.world, prev)
        states.append(prev)
    return fw, states


def test_column_up_stacks_bottom_to_top_and_repeats_copy_their_boxes():
    fw, (s,) = world(f'<diagram id="d">{TREE}</diagram>')
    d = fw.actors["d"]
    za, zb, zc = (d.items[k].rect[1] for k in "abc")
    assert za < zb < zc                                  # dir="up": the first child at the bottom
    assert sum(1 for b in d.blocks if b["item"].id == "b") == 3   # ×3: three copies when unfolded
    assert d.items["c"].rect[3] - d.items["c"].rect[1] > d.items["a"].rect[3] - d.items["a"].rect[1]  # two lines


def test_edges_route_straight_when_boxes_face_each_other_and_flows_follow_them():
    fw, (s,) = world(f'<diagram id="d" flow="a>b>c">{TREE}</diagram>')
    d = fw.actors["d"]
    pts = d.edges[0]["pts"]
    assert len(pts) == 2 and pts[0][0] == pytest.approx(pts[1][0])      # straight up
    assert s["d"]["ft"] == 0.0 and s["d"]["ft1"] == 1.0                 # a new flow runs during the line
    path = np.vstack(d._flow_path("a>b>c", None)[0][0])
    assert np.allclose(path[0], d.edges[0]["pts"][0]) and np.allclose(path[-1], d.edges[1]["pts"][-1])
    with pytest.raises(BeatError, match="no edge from c to a"):
        world(f'<diagram id="d" flow="c>a">{TREE}</diagram>')


def test_flow_clock_only_goes_forward_and_stages_run_in_order():
    fw, (a, b, c) = world(f'<diagram id="d" flow="a>b">{TREE}</diagram>',
                          '<diagram id="d" flow="a>b"></diagram>',
                          '<diagram id="d" flow="a>b | b>c"></diagram>')
    d = fw.actors["d"]
    assert (a["d"]["ft"], a["d"]["ft1"]) == (0.0, 1.0)
    assert b["d"]["ft"] == b["d"]["ft1"] == 1.0          # the same flow again: it stays lit, no rerun
    assert (c["d"]["ft"], c["d"]["ft1"]) == (1.0, 2.0)   # a new flow starts where the clock is
    assert d.starts[1] == d.flows.index("a>b | b>c")
    assert [len(st) for st in d._flow_path("a>b | b>c", None)] == [1, 1] and d.routes == 3


def test_a_later_beat_keeps_the_tree_and_changes_only_its_state():
    fw, (a, b) = world(f'<diagram id="d">{TREE}</diagram>',
                       '<diagram id="d" depth="1" unfold="1" highlight="r" focus="c"></diagram>')
    d = fw.actors["d"]
    lit = [bl["item"].id for bl, v in zip(d.blocks, b["d"]["lit"]) if v]
    assert lit == ["b", "b", "b"]                       # lighting a repeat lights what is inside it
    x0, z0, x1, z1 = d.items["c"].rect
    ext = np.array(d.extent(b["d"]))
    assert ext[:, 0].min() < x0 and ext[:, 0].max() > x1 and ext[:, 0].max() - ext[:, 0].min() < (x1 - x0) + 1
    with pytest.raises(BeatError, match="same in every beat"):
        world(f'<diagram id="d">{TREE}</diagram>', '<diagram id="d"><box id="z" text="z"></box></diagram>')


def test_diagram_children_only_inside_a_diagram():
    with pytest.raises(BeatError, match="belongs inside a <diagram>"):
        parse_beats('<beats><beat><world><box id="a" text="x"></box></world></beat></beats>')
