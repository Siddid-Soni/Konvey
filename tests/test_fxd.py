"""``<plane>``: a coordinate plane, arrows, a matrix acting on it (konvey/stage/displays/plane)."""

import importlib.util

import numpy as np
import pytest

from konvey.schemas import ObjectSpec
from konvey.stage import displays
from konvey.stage.displays.plane import _carry_range, named_pairs, nice_range, parse_angle, parse_matrix
from konvey.stage.parse import BeatError, parse_beats, prepare_beats

HAS_MANIM = importlib.util.find_spec("manimlib") is not None
manim = pytest.mark.skipif(not HAS_MANIM, reason="needs manimgl (uv --group render)")
PLANE = displays.get("plane")


def leaf(html: str, i: str = "x"):
    return parse_beats(f"<beats><beat>{html}</beat></beats>")[0].leaves()[i]


def obj(**data):
    return ObjectSpec(id="pl", kind="plane", data=data)


# --- pure: parsing, range, plan checks ------------------------------------------------------
def test_parsers():
    assert named_pairs("v:1,1; w:1,-1", "vectors=") == [("v", (1.0, 1.0)), ("w", (1.0, -1.0))]
    assert named_pairs("1,1; 1,-1", "lines=", need_name=False) == [("", (1.0, 1.0)), ("", (1.0, -1.0))]
    assert parse_matrix("2,1;1,2") == parse_matrix("[[2,1],[1,2]]") == ((2, 1), (1, 2))
    assert parse_angle("e^{i\\theta}:45") == ("e^{i\\theta}", 45.0) and parse_angle("90") == ("", 90.0)
    for bad in ("v:1", "v:1,1; v:2,2", "v:a,b"):
        with pytest.raises(BeatError):
            named_pairs(bad, "vectors=")
    with pytest.raises(BeatError):
        parse_matrix("1,2,3;4,5,6")


def test_range_holds_the_content_symmetric_and_wider_than_tall():
    x0, x1, y0, y1, step = nice_range([(0, 0), (1, 1), (3, 3), (1, -1)])
    assert (y0, y1, step) == (-4, 4, 1) and x1 == -x0 and x1 > y1
    assert nice_range([(1, 0), (0, 1), (-1, 0), (0, -1)])[2:] == (-1.5, 1.5, 0.5)   # the unit circle


def test_one_range_and_colours_for_the_scene():
    beats = parse_beats('<beats><beat><plane id="p" vectors="v:1,0"></plane></beat>'
                        '<beat><plane id="p" vectors="v:1,0;w:0,1" matrix="3,0;0,3"></plane></beat></beats>')
    _carry_range(beats)
    a, b = (bt.leaves()["p"].attrs for bt in beats)
    assert a["_range"] == b["_range"] and float(a["_range"].split(",")[3]) >= 3   # (3, 0) fits in beat 0 too
    assert a["_colors"] == b["_colors"] == "v,w"


def test_check_object():
    assert PLANE.check_object({}) and "at least one" in PLANE.check_object({})[0]
    assert PLANE.check_object({"vectors": {"v": [1, 0]}, "matrix": [[2, 1], [1, 2]], "angle": 45}) == []
    assert PLANE.check_object({"vectors": {"v": [1]}})
    assert PLANE.check_object({"vectors": {"v": [1, 0]}, "points": {"V": [2, 2]}})       # name used twice
    assert PLANE.check_object({"matrix": [[1, 2, 3], [4, 5, 6]]})
    assert PLANE.check_object({"lines": [[0, 0]]})
    assert PLANE.check_object({"angle": "half a turn"})


def test_check_drawn_wants_the_planned_values():
    o = obj(vectors={"v": [1, 0]}, matrix=[[2, 1], [1, 2]])
    good = leaf('<plane id="x" vectors="v:1,0" matrix="2,1;1,2" coords="true"></plane>')
    drawn_after = leaf('<plane id="x" vectors="v:2,1" matrix="2,1;1,2"></plane>')   # wrote A v, not v
    no_matrix = leaf('<plane id="x" vectors="v:1,0"></plane>')
    assert PLANE.check_drawn("b0", o, [good]) == []
    for n in (drawn_after, no_matrix):
        (msg,) = PLANE.check_drawn("b0", o, [n])
        assert 'vectors="v:1,0"' in msg and 'matrix="2,1;1,2"' in msg
    assert PLANE.check_drawn("b0", obj(angle=45), [leaf('<plane id="x" angle="z:45"></plane>')]) == []
    assert PLANE.check_drawn("b0", obj(angle=45), [leaf('<plane id="x" angle="z:90"></plane>')])


# --- manim: the block and its motion --------------------------------------------------------
@manim
def test_matrix_sends_the_arrow_and_lines_stay():
    from konvey.stage.displays.plane.mobject import PlaneBlock

    a = PlaneBlock(leaf('<plane id="x" vectors="v:1,0" lines="1,0" x="-4,4" y="-3,3"></plane>'))
    b = PlaneBlock(leaf('<plane id="x" vectors="v:1,0" lines="1,0" x="-4,4" y="-3,3" matrix="2,1;1,2"></plane>'))
    u = a.spec.unit
    tip = lambda blk: blk.submobjects[10][0][1].get_points()[0]   # arrows -> v -> head -> its point  # noqa: E731
    assert np.allclose(tip(a)[:2], np.array([1, 0]) * u, atol=1e-6)
    assert np.allclose(tip(b)[:2], np.array([2, 1]) * u, atol=1e-6)
    line = lambda blk: blk.submobjects[7][0].get_points()  # noqa: E731
    assert np.allclose(line(a), line(b))
    assert a.content != b.content


@manim
def test_labels_do_not_overlap():
    from konvey.stage.displays.plane.mobject import PlaneBlock, _boxes_overlap

    p = PlaneBlock(leaf('<plane id="x" vectors="a:1,1; b:1,0.8; c:1,-1" lines="1,1; 1,-1" coords="true"></plane>'))
    labs = [m for m in p.submobjects[-1] if m.get_fill_opacity() > 0.5]
    boxes = [(*m.get_center()[:2], m.get_width(), m.get_height()) for m in labs]
    assert len(boxes) == 3
    assert all(_boxes_overlap(boxes[i], boxes[j]) < 1e-3 for i in range(3) for j in range(i + 1, 3))


@manim
def test_out_of_range_names_the_vector():
    from konvey.stage.displays.plane.mobject import PlaneBlock

    with pytest.raises(BeatError, match=r"v lands at \(6, 6\)"):
        PlaneBlock(leaf('<plane id="x" vectors="v:2,2" matrix="3,0;0,3" x="-4,4" y="-3,3"></plane>'))


@manim
def test_morph_keeps_its_structure_and_turns_along_the_circle():
    from konvey.stage.displays.plane.mobject import PlaneBlock, _mix, draw, grid_sources, morph

    beats = parse_beats('<beats>'
                        '<beat><plane id="x" circle="true" angle="z:0" projections="true"></plane></beat>'
                        '<beat><plane id="x" circle="true" angle="z:180" projections="true" theta="π"></plane></beat>'
                        '</beats>')
    prepare_beats(beats)
    old, new = (PlaneBlock(b.leaves()["x"]) for b in beats)
    assert morph(old, new) is not None
    grid = grid_sources(old.spec.rng, [old.spec.m])
    shapes = [len(draw(_mix(old.spec, new.spec, t), grid, old.offsets)[0].get_family()) for t in (0, 0.3, 1)]
    assert len(set(shapes)) == 1                                   # manimgl draws a fixed structure only
    half = _mix(old.spec, new.spec, 0.5)
    assert abs(half.angle.xy[0] - 90) < 1e-9                       # along the arc, not across the chord


@manim
def test_matrix_morph_moves_every_grid_line():
    from konvey.stage.displays.plane.mobject import PlaneBlock, _mix, draw, grid_sources

    beats = parse_beats('<beats><beat><plane id="x" vectors="v:1,1"></plane></beat>'
                        '<beat><plane id="x" vectors="v:1,1" matrix="2,1;1,2"></plane></beat></beats>')
    prepare_beats(beats)
    old, new = (PlaneBlock(b.leaves()["x"]) for b in beats)
    grid = grid_sources(old.spec.rng, [old.spec.m + (new.spec.m - old.spec.m) * s for s in np.linspace(0, 1, 9)])
    pts = lambda t: [m.get_points().copy() for m in draw(_mix(old.spec, new.spec, t), grid)[0][6]]  # noqa: E731
    a, mid = pts(0), pts(0.5)
    moved = sum(not np.allclose(p, q) for p, q in zip(a, mid) if len(p) and len(q))
    assert moved > 0.8 * len(a)


def test_id_like_names_are_rejected_with_a_hint():
    (msg,) = PLANE.check_object({"vectors": {"p11": [1, 1]}})
    assert "e_1" in msg and "p11" in msg
    assert PLANE.check_object({"vectors": {"p1m1": [1, -1], "sum": [2, 1]}})
    assert PLANE.check_object({"vectors": {"v": [1, 0], "e1": [1, 1], "Av": [2, 1], "e_2": [1, -1]}}) == []


@manim
def test_names_are_set_as_maths():
    from konvey.stage.displays.plane.mobject import _tex

    assert _tex("v_11") == "v_{11}" and _tex("sum") == r"\text{sum}"
    assert _tex(r"e^{i\theta}") == r"e^{i\theta}" and _tex("Av") == "Av" and _tex(r"\cos\theta") == r"\cos\theta"


@manim
def test_a_point_on_the_circle_goes_round_it():
    from konvey.stage.displays.plane.mobject import _between

    x, y = _between((1, 0), (0, 1), 0.5)
    assert abs(x - 0.7071) < 1e-3 and abs(y - 0.7071) < 1e-3       # on the circle, not on the chord
    assert _between((1, 0), (3, 0), 0.5) == (2, 0)                   # a stretch goes straight
