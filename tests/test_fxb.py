"""``<plot>`` as a first-class display: the plan kind, exact tracing, axes/ticks, labels, morph."""

import importlib.util
from types import SimpleNamespace

import numpy as np
import pytest

from konvey.stage.displays import for_kind
from konvey.stage.displays.plot import spec as S
from konvey.stage.parse import BeatError, parse_beats

HAS_MANIM = importlib.util.find_spec("manimlib") is not None
manim = pytest.mark.skipif(not HAS_MANIM, reason="needs manimgl (uv --group render)")


def leaf(html: str, i: str = "x"):
    return parse_beats(f"<beats><beat>{html}</beat></beats>")[0].leaves()[i]


# --- pure geometry ----------------------------------------------------------------------------
def test_expressions_are_normalised_and_still_never_evaluated():
    assert S.normalize("2x + 3(x+1) - 2pi") == "2*x + 3*(x+1) - 2*pi"
    assert S.normalize("4/π·sin(3x)") == "4/pi*sin(3*x)"
    assert abs(S.number("-2pi") + 2 * np.pi) < 1e-12 and S.number("pi/2") == np.pi / 2
    assert np.allclose(S.fn_of("1e-3*x")(np.array([2.0])), 0.002)
    with pytest.raises(BeatError):
        S.fn_of('__import__("os").system("true")')


def test_ticks_count_in_pi_when_the_range_is_in_pi():
    labels = [t for _, t in S.ticks(-2 * np.pi, 2 * np.pi, 9, True)]
    assert labels == ["−2π", "−π", "0", "π", "2π"]   # landmarks, as 3b1b numbers them
    assert [t for _, t in S.ticks(-np.pi, np.pi, 9, True)] == ["−π", "−π/2", "0", "π/2", "π"]
    assert [t for _, t in S.ticks(0, 10, 7, False)] == ["0", "5", "10"]
    assert [t for _, t in S.ticks(0, 10, 12, False)] == ["0", "2", "4", "6", "8", "10"]
    assert [t for _, t in S.ticks(-1, 1, 6, False)] == ["−1", "0", "1"]
    assert [t for _, t in S.ticks(-1, 1, 12, False)][0] == "−1.0"


def test_a_diverging_polynomial_leaves_cleanly_at_the_box():
    f = S.fn_of("x - x^3/6 + x^5/120 - x^7/5040")
    runs = S.trace(f, (-2 * np.pi, 2 * np.pi), (-2, 2), 10, 4.6)
    pts = np.concatenate(runs)
    assert pts[:, 1].min() >= -2 - 1e-9 and pts[:, 1].max() <= 2 + 1e-9
    ends = [r[k] for r in runs for k in (0, -1)]
    assert any(abs(abs(p[1]) - 2) < 1e-9 for p in ends)    # cut exactly at the top/bottom edge


def test_a_real_jump_is_cut_but_a_steep_curve_is_not():
    square = S.trace(S.fn_of("sign(sin(x))"), (-2 * np.pi, 2 * np.pi), (-1.5, 1.5), 10, 4.6)
    for r in square:   # no vertical smear: every piece stays at +1 or -1
        assert np.ptp(r[:, 1]) < 1e-9
    steep = S.trace(S.fn_of("tanh(40*x)"), (-1, 1), (-1.2, 1.2), 8, 4)
    assert len(steep) == 1 and np.abs(np.diff(steep[0][:, 1])).max() < 0.05


def test_roots_and_same_fn():
    supply = S.Curve("supply", "2 + x", S.fn_of("2 + x"))
    assert abs(S.roots(supply, 4, (0, 10))[0] - 2) < 1e-9
    assert S.same_fn(S.fn_of("x-x^3/6"), S.fn_of("x - x**3 / 6"), (-3, 3))
    assert not S.same_fn(S.fn_of("x"), S.fn_of("x - x^3/6"), (-3, 3))


def test_parse_reads_points_marks_gaps_and_shades():
    sp = S.parse({"fn": "demand: 10 - x; supply: 2 + x", "x": "0,10", "y": "0,10",
                  "points": "E: 4,supply", "mark": "y=4: ceiling", "gap": "supply,demand@y=4: shortage",
                  "shade": "demand,supply: 2,4: lost"})
    assert [c.label for c in sp.curves] == ["demand", "supply"]
    assert sp.points[0][2] is sp.curves[1] and sp.marks == [("y", 4.0, "ceiling")]
    assert sp.gaps[0][2:] == ("y", 4.0, "shortage") and sp.shades[0][2:4] == (2.0, 4.0)
    with pytest.raises(BeatError, match="neither a curve label"):
        S.parse({"fn": "a: x", "x": "0,1", "shade": "a,b: 0,1"})


# --- the plan kind -------------------------------------------------------------------------
def test_plot_is_a_plan_kind_with_checks():
    d = for_kind("plot")
    assert d is not None and d.tag == "plot" and set(d.needs) == {"fns", "x"}
    ok = {"fns": {"sin x": "sin(x)", "T_3": "x - x^3/6"}, "x": ["-2*pi", "2*pi"], "y": [-2, 2]}
    assert d.check_object(ok) == []
    assert any("not" in p or "only" in p for p in d.check_object({**ok, "fns": {"f": "os.system(1)"}}))
    assert any("nothing would show" in p for p in d.check_object({**ok, "fns": {"f": "x + 100"}}))
    assert any("points" in p for p in d.check_object({**ok, "points": {"P": [1]}}))


def test_check_drawn_wants_the_planned_functions_and_range():
    d = for_kind("plot")
    obj = SimpleNamespace(kind="plot", data={"fns": {"T_3": "x - x^3/6"}, "x": ["-2*pi", "2*pi"],
                                             "points": {"P": [1, 1]}})
    good = leaf('<plot id="x" fn="T_3: x-x**3/6" x="-2pi,2pi" y="-2,2" points="P: 1,T_3"></plot>')
    assert d.check_drawn("b0", obj, [good]) == []
    narrow = leaf('<plot id="x" fn="T_3: x - x^3/6" x="0,3" y="-2,2" points="P: 1,T_3"></plot>')
    assert "x range" in d.check_drawn("b0", obj, [narrow])[0]
    other = leaf('<plot id="x" fn="T_1: x" x="-2pi,2pi" y="-2,2"></plot>')
    assert "needs <plot" in d.check_drawn("b0", obj, [other])[0]


# --- the mobject -----------------------------------------------------------------------------
@manim
def test_axes_cross_at_the_origin_with_numbered_ticks():
    from konvey.stage.displays.plot.mobject import PlotBlock

    p = PlotBlock(leaf('<plot id="x" fn="sin x: sin(x)" x="-2pi,2pi" y="-2,2" w="10" h="4"></plot>'))
    y_axis = p.axes[1].get_center()
    assert abs(y_axis[0] - 5.0) < 1e-6                       # x = 0 is the middle of -2pi..2pi
    assert abs(p.axes[0].get_center()[1] - 2.0) < 1e-6       # y = 0 is the middle of -2..2
    texts = [t[3].plot_text for t in p.ticks]
    assert "π" in texts and "−2π" in texts and "0" not in texts   # no "0" where the axes meet
    pts = p.lines[0].get_points()
    assert pts[:, 1].min() >= -1e-6 and pts[:, 1].max() <= 4 + 1e-6


@manim
def test_labels_do_not_overlap_each_other():
    from konvey.stage.displays.plot.mobject import PlotBlock

    p = PlotBlock(leaf('<plot id="x" fn="demand: 10 - x; supply: 2 + x" x="0,10" y="0,10" points="E: 4,6" '
                       'mark="y=4: ceiling" gap="supply,demand@y=4: shortage" xlabel="quantity" ylabel="price" '
                       'w="7" h="4.6"></plot>'))
    boxes = [(m.get_corner(DL_), m.get_corner(UR_)) for m in (*p.labels, *p.names, *p.tick_labels)]
    for i, (a0, a1) in enumerate(boxes):
        for b0, b1 in boxes[i + 1:]:
            ox = min(a1[0], b1[0]) - max(a0[0], b0[0])
            oy = min(a1[1], b1[1]) - max(a0[1], b0[1])
            assert ox <= 1e-6 or oy <= 1e-6


DL_, UR_ = np.array([-1, -1, 0]), np.array([1, 1, 0])


@manim
def test_morph_grows_the_curve_and_slides_the_marker():
    from konvey.stage.displays.plot.mobject import PlotBlock, _Morph, morph

    a = PlotBlock(leaf('<plot id="x" fn="sin x: sin(x); T_1: x" x="-2pi,2pi" y="-2,2" mark="x=1: a"></plot>'))
    b = PlotBlock(leaf('<plot id="x" fn="sin x: sin(x); T_3: x - x^3/6" x="-2pi,2pi" y="-2,2" '
                       'mark="x=2: a"></plot>'))
    assert a.content != b.content and morph(a, b) is not None
    m = _Morph(a, b)
    assert len(m.curves) == 2 and m.curves[1][:2] == (1, 1)   # T_1 turns into T_3 (same slot)
    m.update(None, 0.5)
    assert a.get_opacity() == 0                                  # the moving copy stands in for it
    x_mid = m.marks[0][2].get_center()[0]
    assert a.marks[0].get_center()[0] < x_mid < b.marks[0].get_center()[0]
    m.update(None, 1.0)
    assert np.allclose(m.marks[0][2].get_center(), b.marks[0].get_center())


@manim
def test_morph_ends_exactly_on_the_new_plot():
    from konvey.stage.displays.plot.mobject import PlotBlock, _Morph

    a = PlotBlock(leaf('<plot id="x" fn="f: 4/pi*sin(x)" x="-2pi,2pi" y="-1.6,1.6" points="P: 1,f"></plot>'))
    b = PlotBlock(leaf('<plot id="x" fn="f: 4/pi*(sin(x) + sin(3x)/3)" x="-2pi,2pi" y="-1.6,1.6" '
                       'points="P: 2,f"></plot>'))
    m = _Morph(a, b)
    m.update(None, 0.5)
    mid = m.curves[0][2].get_points()
    m.update(None, 1.0)
    assert np.allclose(m.curves[0][2].get_points(), b.lines[0].get_points())
    assert not np.allclose(mid[: len(mid) // 2].mean(0), b.lines[0].get_points()[: len(mid) // 2].mean(0))
    assert np.allclose(m.points[0][2].get_center(), b.dots[0].get_center())   # the dot slid along f


# --- round 2: labels from real runs, axis names that stay ------------------------------------
def test_labels_typeset_what_models_write():
    L = S.label_form
    assert L("P_11") == ("tex", "P_{11}") and L("P_11(1)") == ("tex", "P_{11}(1)")
    assert L("partial_sum") == ("text", "partial sum")
    assert L("S_N(x)") == ("tex", "S_{N}(x)") and L("x_new") == ("tex", "x_{\\text{new}}")
    assert L("sin x") == ("text", "sin x") and L("$e^x$") == ("tex", "e^x")


def test_axis_names_carry_across_beats_and_a_scene_cut():
    from konvey.stage.parse import prepare_beats
    from konvey.stage.scene import _adopt_ids

    s2 = parse_beats('<beats><beat><plot id="curves" fn="demand: 100-2x" x="0,50" y="0,120" '
                     'xlabel="price P" ylabel="quantity Q"></plot></beat></beats>')
    s3 = parse_beats('<beats><beat><plot id="market" fn="demand: 100-2*x; supply: 20+4*x" x="0,50" '
                     'y="0,120" xlabel="quantity" ylabel="price"></plot></beat>'
                     '<beat><plot id="market" fn="demand: 100-2*x" x="0,50" y="0,120"></plot></beat></beats>')
    last = s2[-1]
    _adopt_ids(last, s3[0])
    prepare_beats([last, *s3], strict=False)
    for b in s3:
        n = b.leaves()["market"]
        assert (n.attrs["xlabel"], n.attrs["ylabel"]) == ("price P", "quantity Q")


@manim
def test_label_mobjects_set_subscripts_whole():
    from konvey.stage.displays.plot.mobject import _label

    assert type(_label("P_11", 30, "#ffffff")).__name__ == "Tex"
    assert type(_label("partial_sum", 30, "#ffffff")).__name__ == "Text"


@manim
def test_an_unlabelled_shade_moves_between_beats():
    from konvey.stage.displays.plot.mobject import PlotBlock, morph

    a, b = (PlotBlock(leaf(f'<plot id="x" fn="1/i: 1/x" x="1,8" y="0,1" shade="1/i,0: {r}"></plot>'))
            for r in ("1,2", "3,4"))
    anim = morph(a, b)
    anim.begin()
    anim.interpolate(0.5)   # no label in either beat: nothing to move, and no crash


def test_steps_slide_and_live_numbers_parse():
    sp = S.parse({"fn": "sin x: sin(x); S_1 | S_2: sin(x) | sin(x) + sin(3x)/3", "x": "-3,3",
                  "slide": "0 -> 2", "drop": "true"})
    c = sp.curves[1]
    assert c.label == "S_1" and [l for l, _ in c.steps] == ["S_1", "S_2"]
    assert sp.curve("S_2") is c and sp.slide == (0.0, 2.0) and sp.drop
    assert S.fill("error {gap} at {x}", gap=0.0026, x=2) == "error 0.0026 at 2"
    assert [S.live_value(v) for v in (2047, 2.718281, -1, 3.3e-7)] == ["2047", "2.718", "−1", "0.00000033"]
    with pytest.raises(BeatError):
        S.parse({"fn": "S: sin(x) | ", "x": "-3,3"})
    with pytest.raises(BeatError):
        S.parse({"fn": "x", "x": "-3,3", "slide": "0 to 2"})


@manim
def test_a_stage_moves_what_sat_at_the_slide_start():
    from konvey.stage.displays.plot.mobject import _stage

    a = {"id": "p", "fn": "f | g: x | x^2", "x": "-3,3", "points": "A: 0,f", "gap": "f,g@x=0: e {gap}",
         "slide": "0 -> 2"}
    st = _stage(a, 1, (0.0, 2.0))
    assert st["fn"] == "g: x^2" and "slide" not in st
    assert st["points"] == "A: 2.0,g" and st["gap"] == "g,g@x=2.0: e {gap}"
