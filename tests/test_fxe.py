"""The ``<scatter>`` display: points, groups, centroids, links and fitted lines on numbered axes
(plan kind ``scatter``)."""

import importlib.util
from types import SimpleNamespace

import numpy as np
import pytest

from konvey.stage import displays
from konvey.stage.parse import parse_beats

HAS_MANIM = importlib.util.find_spec("manimlib") is not None
manim = pytest.mark.skipif(not HAS_MANIM, reason="needs manimgl (uv --group render)")

PTS = "1,2; 2,1; 2,3; 3,2; 6,2; 7,3; 8,2; 7,1; 4,7; 5,8; 6,7; 5,9"
PLAN_PTS = [[1, 2], [2, 1], [2, 3], [3, 2], [6, 2], [7, 3], [8, 2], [7, 1], [4, 7], [5, 8], [6, 7], [5, 9]]


def leaf(html: str, i: str = "x"):
    return parse_beats(f"<beats><beat>{html}</beat></beats>")[0].leaves()[i]


def scatter(**attrs):
    attrs.setdefault("points", PTS)
    src = " ".join(f'{k}="{v}"' for k, v in attrs.items())
    return leaf(f'<scatter id="x" {src}></scatter>')


DISP = displays.get("scatter")


# --- the plan --------------------------------------------------------------------------
def test_scatter_is_a_plan_kind_with_docs():
    assert displays.for_kind("scatter") is DISP and "scatter" in displays.kinds()
    assert "`scatter`" in displays.fill_plan("{{plan_kinds}}")
    assert "<scatter>" in displays.agent3_sections()


def test_check_object_numbers_groups_and_centroids():
    ok = {"points": PLAN_PTS, "groups": [0] * 4 + [1, 1, 2, 2] + [1] * 4,
          "centroids": [[1, 1], [5, 3], [8, 1]], "links": True, "lines": [[0.5, 1]], "highlight": [4, 5]}
    assert DISP.check_object(ok) == []
    assert "3 entries for 12 points" in DISP.check_object({**ok, "groups": [0, 1, 2]})[0]
    assert "has no centroid" in DISP.check_object({**ok, "groups": [3] * 12})[0]
    assert DISP.check_object({**ok, "points": [[1, "a"]]})
    assert DISP.check_object({**ok, "highlight": [12]})
    assert DISP.check_object({"points": PLAN_PTS, "links": True})   # a link needs groups and centroids
    assert DISP.check_object({**ok, "lines": ["steep"]})
    assert DISP.check_object({"points": PLAN_PTS, "lines": ["x=4"]}) == []


def test_check_drawn_wants_planned_values_verbatim():
    obj = SimpleNamespace(kind="scatter", data={"points": PLAN_PTS, "centroids": [[2, 2], [5.5, 6]],
                                                "groups": [0] * 6 + [1] * 6, "lines": [[0.85, 1.1]]})
    good = scatter(centroids="2,2; 5.5,6", groups=",".join(["0"] * 6 + ["1"] * 6), lines="0.85,1.1")
    assert DISP.check_drawn("b0", obj, [good]) == []
    moved = scatter(centroids="2,2; 5,6", groups=",".join(["0"] * 6 + ["1"] * 6), lines="0.85,1.1")
    assert 'centroids="2; 2; 5.5; 6"' not in DISP.check_drawn("b0", obj, [moved])[0]
    assert '<scatter centroids="2,2; 5.5,6">' in DISP.check_drawn("b0", obj, [moved])[0]
    flat = scatter(centroids="2,2; 5.5,6", groups=",".join(["0"] * 6 + ["1"] * 6), lines="0.5,1")
    assert 'lines="0.85,1.1"' in DISP.check_drawn("b0", obj, [flat])[0]


# --- the block -------------------------------------------------------------------------
@manim
def test_scatter_colours_groups_and_labels_centroids_clear_of_dots():
    from konvey.stage.displays.scatter.mobject import ScatterBlock, _box, _overlap
    from konvey.stage.theme import current

    b = ScatterBlock(scatter(groups="0,0,0,0,1,1,2,2,1,1,1,1", centroids="2,2; 5.5,6; 7.5,1.5", links="on",
                             labels="A,B,C,D,E,F,G,H,I,J,K,L"))
    pal = current().palette
    assert len(b.points) == 12 and len(b.centroids) == 3 and all(m.has_points() for m in b.links)
    assert b.points[4][0].get_fill_color().lower() == pal[1].lower()
    assert b.points[6][0].get_fill_color().lower() == pal[2].lower()
    # every point and centroid sits at its data coordinates
    assert np.allclose(b.points[9][0].get_center(), b.c2p(5, 8))
    assert np.allclose(b.centroids[1][0].get_center(), b.c2p(5.5, 6))
    # the link of a point runs to its own centroid
    assert np.allclose(b.links[4].get_end(), b.c2p(5.5, 6))
    labels = [c[1] for c in b.centroids] + list(b.names)
    for i, a in enumerate(labels):
        for c in labels[i + 1:]:
            assert _overlap(_box(a), _box(c)) < 1e-6
        for p in b.points:
            assert _overlap(_box(a), _box(p[0])) < 1e-6


@manim
def test_scatter_range_holds_the_data_with_equal_units():
    from konvey.stage.displays.scatter.mobject import ScatterBlock

    b = ScatterBlock(scatter())
    assert b.xr[0] <= 1 and b.xr[1] > 8 and b.yr[0] <= 1 and b.yr[1] > 9
    ux = (b.c2p(1, 0) - b.c2p(0, 0))[0]
    uy = (b.c2p(0, 1) - b.c2p(0, 0))[1]
    assert abs(ux - uy) < 1e-6                    # a distance reads the same both ways


@manim
def test_scatter_line_is_clipped_to_the_plot():
    from konvey.stage.displays.scatter.mobject import ScatterBlock

    b = ScatterBlock(scatter(lines="2,0; x=4"))
    lo, hi = b.c2p(b.xr[0], b.yr[0]), b.c2p(b.xr[1], b.yr[1])
    for line in b.lines:
        for p in (line.get_start(), line.get_end()):
            assert lo[0] - 1e-6 <= p[0] <= hi[0] + 1e-6 and lo[1] - 1e-6 <= p[1] <= hi[1] + 1e-6
    assert abs(b.lines[1].get_start()[0] - b.c2p(4, 0)[0]) < 1e-6


@manim
def test_scatter_errors_name_the_attribute():
    from konvey.stage.displays.scatter.mobject import ScatterBlock
    from konvey.stage.tree import BeatError

    with pytest.raises(BeatError, match="one group number"):
        ScatterBlock(scatter(groups="0,1"))
    with pytest.raises(BeatError, match="has no centroid"):
        ScatterBlock(scatter(groups=",".join(["3"] * 12), centroids="1,1"))
    with pytest.raises(BeatError, match="not a point"):
        ScatterBlock(scatter(points="1,2; 3"))
    with pytest.raises(BeatError, match="links"):
        ScatterBlock(scatter(links="on"))


@manim
def test_scatter_morph_pulses_only_points_that_switch_group():
    from konvey.stage.displays.scatter.mobject import ScatterBlock, _Pulse, morph

    before = ScatterBlock(scatter(groups="0,0,0,0,1,1,2,2,1,1,1,1", centroids="2,2; 5.5,6; 7.5,1.5", links="on"))
    after = ScatterBlock(scatter(groups="0,0,0,0,2,2,2,2,1,1,1,1", centroids="2,2; 5,7.75; 7,2", links="on"))
    assert before.content != after.content
    anims = morph(before, after).animations
    pulsed = [a for a in anims if isinstance(a, _Pulse)]
    assert sorted(id(a.mobject) for a in pulsed) == sorted(id(before.points[i]) for i in (4, 5))
    first = morph(ScatterBlock(scatter(centroids="1,1; 5,3; 8,1")), before).animations
    assert not [a for a in first if isinstance(a, _Pulse)]   # a first colour is no switch

    fit0, fit1 = ScatterBlock(scatter(lines="0.3,3")), ScatterBlock(scatter(lines="0.85,1.1"))
    slide = [a for a in morph(fit0, fit1).animations if a.mobject is fit0.lines[0]]
    assert slide and type(slide[0]).__name__ == "UpdateFromAlphaFunc"
    slide[0].begin()
    slide[0].interpolate(1.0)                     # ends exactly on the new line
    assert np.allclose(fit0.lines[0].get_start(), fit1.lines[0].get_start(), atol=1e-6)


@manim
def test_scatter_point_on_its_centroid_draws_without_a_link():
    """A real run: a one-point cluster has its centroid on the point (a zero-length link),
    which crashed manimgl with a bare AssertionError that Agent 3 could not act on."""
    from konvey.stage.displays.scatter.mobject import ScatterBlock, build, morph
    from konvey.stage.tree import BeatError

    attrs = dict(points="1,1; 2,1; 1,2; 6,1; 7,2; 4,6", groups="0,0,0,1,1,2", links="on", x="0,8", y="0,7")
    b = build(scatter(centroids="1.333,1.333; 6.5,1.5; 4,6", **attrs))
    assert not b.links[5].has_points() and b.links[0].has_points()
    a = ScatterBlock(scatter(centroids="1,1; 6,1; 4,5", **attrs))
    assert morph(a, b).animations                 # the link fades as the centroid lands on the point
    with pytest.raises(BeatError, match="widen x="):
        build(scatter(centroids="1,1; 6,1; 9,6", **attrs))
    with pytest.raises(BeatError, match='"low,high"'):
        build(scatter(centroids="1,1; 6,1; 4,6", **{**attrs, "x": "8,0"}))


@manim
def test_scatter_centroids_on_top_but_see_through_and_small_w_h_is_a_floor():
    from konvey.stage.displays.scatter.mobject import MIN_H, ScatterBlock

    b = ScatterBlock(scatter(groups=",".join(["0"] * 12), centroids="5,8", w="3", h="2"))
    # every centre drawn the same way (on top); a point lying on one shows through it
    assert list(b.submobjects).index(b.centroids) > list(b.submobjects).index(b.points)
    assert b.centroids[0][0].get_fill_opacity() < 0.5
    assert b.axes.get_height() > 0.9 * MIN_H       # not the 2 units Agent 3 wrote
