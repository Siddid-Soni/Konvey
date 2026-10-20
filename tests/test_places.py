"""``<places>`` (was ``<system>``): places that hold things, things moving between them; new
layouts (column, grid), explicit or no links (things jump), more shapes, and the old name."""

import importlib.util

import pytest

from konvey.stage import displays
from konvey.stage.parse import BeatError, parse_beats, prepare_beats

HAS_MANIM = importlib.util.find_spec("manimlib") is not None
manim = pytest.mark.skipif(not HAS_MANIM, reason="needs manimgl (uv --group render)")


def leaf(html: str):
    beats = parse_beats(f"<beats><beat>{html}</beat></beats>")
    prepare_beats(beats)
    return list(beats[0].leaves().values())[0]


def test_old_system_name_still_reads():
    node = leaf('<system id="s" parts="a,b"></system>')
    assert node.tag == "places"
    assert displays.for_kind("system") is displays.get("places") is displays.get("system")
    assert "system" not in displays.kinds()            # the prompts only show the new name


def test_plan_checks_layout_and_links():
    check = displays.get("places").check_object
    assert check({"parts": ["a", "b", "c"], "layout": "column"}) == []
    assert check({"parts": list("abcdef"), "layout": "grid", "links": "none"}) == []
    assert check({"parts": ["a", "b", "c"], "links": [["a", "c"]]}) == []
    assert "layout" in check({"parts": ["a", "b"], "layout": "spiral"})[0]
    assert "links" in check({"parts": ["a", "b"], "links": [["a", "z"]]})[0]
    assert "no nested lists" in check({"parts": ["a", ["b", "c"]], "layout": "column"})[0]


def test_plan_layout_and_links_are_written_into_the_tag():
    class Obj:
        id, kind = "p", "places"
        data = {"parts": ["a", "b"], "layout": "column", "links": "none", "holds": {"a": ["1"]}}
    body = displays.get("places").apply_plan('<places id="p" parts="x,y"></places>', Obj)
    assert 'layout="column"' in body and 'links="none"' in body and 'holds="a:1"' in body
    old = displays.get("places").apply_plan('<system id="p" parts="x,y"></system>', Obj)
    assert old.startswith("<places ")


@manim
def test_column_grid_links_and_hops():
    from konvey.stage.displays.places.mobject import PlacesBlock

    col = PlacesBlock(leaf('<places id="m" parts="reg,cache,ram" layout="column"></places>'))
    ys = [col.centre(p)[1] for p in col.parts]
    assert ys[0] > ys[1] > ys[2] and len(col.links) == 2          # stacked, each wired to the next
    name = col.boxes[0][1]
    assert name.get_right()[0] < col.box_of["reg"].get_left()[0]   # the name at the left
    grid = PlacesBlock(leaf('<places id="g" parts="a,b,c,d" layout="grid" links="none" '
                            'shapes="a:circle;b:bin"></places>'))
    xs = sorted({round(grid.centre(p)[0], 3) for p in grid.parts})
    assert len(xs) == 2 and not grid.links                        # 2 x 2, no wires
    pts, wires = grid.route("a", "d")
    assert not wires and len(pts) > 5                             # a jump in an arc
    assert not any(grid._covers(o, q, name=True) for o in ("b", "c") for q in pts)   # clear of the others
    assert not any(grid._covers(e, q) for e in ("a", "d") for q in pts[1:-1])          # from outline to outline
    row = PlacesBlock(leaf('<places id="r" parts="a,b,c" links="a-c"></places>'))
    assert set(row.links) == {frozenset(("a", "c"))}
    with pytest.raises(BeatError, match="links"):
        PlacesBlock(leaf('<places id="r" parts="a,b" links="a-z"></places>'))


@manim
def test_items_jump_between_unlinked_places():
    from manimlib import UpdateFromAlphaFunc

    from konvey.stage.displays.places.mobject import PlacesBlock, morph

    beats = parse_beats('<beats><beat><places id="p" parts="a,b,c" links="none"><item id="c" in="a" text="coin">'
                        '</item></places></beat><beat><places id="p" parts="a,b,c" links="none"><item id="c" in="c" '
                        'text="coin"></item></places></beat></beats>')
    prepare_beats(beats)
    a, b = [PlacesBlock(list(x.leaves().values())[0]) for x in beats]

    def flat(anim):
        out = []
        for x in getattr(anim, "animations", [anim]):
            out += flat(x) if hasattr(x, "animations") else [x]
        return out
    assert any(isinstance(x, UpdateFromAlphaFunc) for x in flat(morph(a, b)))   # the coin travels
