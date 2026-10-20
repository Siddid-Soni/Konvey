"""layout="tree" and look="pages" for <graph> (konvey.stage.displays.graph)."""

from konvey.stage.displays.graph.mobject import PAGE_CELL, _tree
from konvey.stage.tree import Node


def _node(nodes: str, edges: str, look: str = "") -> Node:
    attrs = {"id": "g", "layout": "tree", "nodes": nodes, "edges": edges}
    if look:
        attrs["look"] = look
    return Node("graph", attrs)


def test_children_hang_one_level_below_their_parent_centred_under_it():
    pos = _tree(_node("A,B,C,D,E", "A-B;A-C;B-D;B-E"))
    assert pos["B"][1] == pos["C"][1] < pos["A"][1]
    assert pos["D"][1] == pos["E"][1] < pos["B"][1]
    assert abs(pos["B"][0] - (pos["D"][0] + pos["E"][0]) / 2) < 1e-9     # a parent centres over its children
    assert pos["D"][0] < pos["E"][0] < pos["C"][0]                       # children left to right, as written


def test_wide_pages_never_overlap():
    pos = _tree(_node("17 35,4 9 12,20 28,40 51 66", "17 35-4 9 12;17 35-20 28;17 35-40 51 66", look="pages"))
    leaves = ["4 9 12", "20 28", "40 51 66"]
    for a, b in zip(leaves, leaves[1:]):
        right_a = pos[a][0] + PAGE_CELL * len(a.split()) / 2
        left_b = pos[b][0] - PAGE_CELL * len(b.split()) / 2
        assert right_a < left_b


def test_a_node_with_two_parents_is_an_error():
    import pytest
    from konvey.stage.tree import BeatError

    with pytest.raises(BeatError, match="two parents"):
        _tree(_node("A,B,C", "A-C;B-C"))
