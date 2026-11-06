"""Motion fixes (fxc): number readouts count or slide, unrelated formulas never blend, a drawing
keeps its frame over beats and scene cuts, shapes turn along arcs, draw labels stay readable."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from konvey.stage.parse import parse_beats, prepare_beats

HAS_MANIM = importlib.util.find_spec("manimlib") is not None
manim = pytest.mark.skipif(not HAS_MANIM, reason="needs manimgl (uv --group render)")


def leaf(html: str, i: str = "x"):
    return parse_beats(f"<beats><beat>{html}</beat></beats>")[0].leaves()[i]


def kinds(anim):
    out = []
    for a in getattr(anim, "animations", [anim]):
        out += kinds(a) if type(a).__name__ == "AnimationGroup" else [type(a).__name__]
    return out


# --- <draw> frame carried over beats and scene cuts (pure Python) -----------------------------
def _draw_beats(*frames_and_bodies):
    return "<beats>" + "".join(f'<beat><draw id="d" {f}>{b}</draw></beat>' for f, b in frames_and_bodies) + "</beats>"


def test_draw_keeps_its_first_frame_and_widens_only_when_shapes_fall_out():
    dot = '<circle id="p" x="{}" y="0" r="0.1"/>'
    beats = parse_beats(_draw_beats(('w="4" h="4" x="-2,2" y="-2,2"', dot.format(1)),
                                    ('w="8" h="5" x="-1.5,1.5" y="-1,1"', dot.format(0.5)),   # fits: carried
                                    ('', dot.format(1.5)),                                     # defaults: carried
                                    ('w="4" h="4" x="-2,2" y="-2,2"', dot.format(5))))         # out: widens
    prepare_beats(beats, strict=True)
    d = [b.leaves()["d"].attrs for b in beats]
    assert [(a["w"], a["h"], a["x"], a["y"]) for a in d[:3]] == [("4", "4", "-2,2", "-2,2")] * 2 + [("4", "4", "-2,2", "-2,2")]
    assert (d[3]["w"], d[3]["h"]) == ("4", "4") and d[3]["x"] == "-2,5.1"


def test_draw_shapes_take_ids_of_the_same_shapes_over_a_cut():
    from konvey.stage.scene import _adopt_ids

    prev = parse_beats('<beats><beat><draw id="plane" w="4" h="4"><line id="re" from="0,2" to="4,2"/>'
                       '<circle id="z" x="3" y="2" r="0.1"/></draw></beat></beats>')[0]
    first = parse_beats('<beats><beat><draw id="board" w="6" h="3"><line id="xaxis" from="0,2" to="4,2" color="muted"/>'
                        '<circle id="pt" x="1" y="2" r="0.1"/></draw></beat></beats>')[0]
    _adopt_ids(prev, first)
    d = prev.leaves()["board"]       # one draw each side: the same drawing
    assert [c.id for c in d.children] == ["xaxis", "pt"]   # same geometry; the only dot left each side


def test_scene_beats_follow_the_prelude_chain(tmp_path):
    from konvey.stage.scene import scene_beats

    wrapper = 'prelude_file = str(Path(__file__).with_name("{}"))\n'
    body = '<circle id="p" x="0" y="0" r="0.1"/>'
    for k, frame in ((1, 'w="4" h="4" x="-2,2" y="-2,2"'), (2, 'w="8" h="5" x="-1,1" y="-1,1"'), (3, 'w="6" h="6"')):
        (tmp_path / f"agent3-S{k}.html").write_text(_draw_beats((frame, body)))
        (tmp_path / f"agent3-S{k}.py").write_text(wrapper.format(f"agent3-S{k - 1}.html") if k > 1 else 'prelude_file = ""\n')
    s2 = scene_beats(tmp_path / "agent3-S2.html")     # as S3's opening beat sees it: S1's frame, via S2
    assert s2[-1].leaves()["d"].attrs["w"] == "4" and s2[-1].leaves()["d"].attrs["x"] == "-2,2"


# --- <number> ---------------------------------------------------------------------------------
@manim
def test_number_counts_with_the_same_unit_and_slides_otherwise():
    from konvey.stage.displays.number.mobject import NumberBlock
    from konvey.stage.motion import morph

    def n(v, unit="deg", label="angle"):
        return NumberBlock(leaf(f'<number id="x" value="{v}" unit="{unit}" label="{label}"></number>'))

    k = kinds(morph(n(45), n(90)))
    assert k == ["UpdateFromAlphaFunc", "Transform"]          # counts; the label stays put
    k = kinds(morph(n("0.833333", ""), n("5/6", "")))
    assert k[:2] == ["FadeOut", "FadeIn"]                     # not a number: out, then in
    k = kinds(morph(n(45, "deg"), n(45, "rad")))
    assert "UpdateFromAlphaFunc" not in k                     # another unit is another value
    k = kinds(morph(n(1, label="steps"), n(1, label="turns")))
    assert k == ["Transform", "FadeOut", "FadeIn"]


@manim
def test_number_count_ends_on_the_new_value():
    from konvey.stage.displays.number.mobject import NumberBlock
    from konvey.stage.motion import morph

    a = NumberBlock(leaf('<number id="x" value="45" unit="deg" label="angle"></number>'))
    b = NumberBlock(leaf('<number id="x" value="90" unit="deg" label="angle"></number>'))
    anim = morph(a, b).animations[0]
    anim.begin()
    anim.interpolate(1.0)
    assert anim.mobject.get_width() == pytest.approx(b.value.get_width(), rel=0.02)


# --- <tex> ------------------------------------------------------------------------------------
@manim
def test_tex_morphs_related_formulas_and_swaps_unrelated_ones():
    from konvey.stage.displays.tex.mobject import shared_runs
    from konvey.stage.motion import morph
    from konvey.stage.overlay import build_leaf

    def t(s):
        return build_leaf(leaf(f'<tex id="x">{s}</tex>'), None)

    a, b = t(r"\sin x \approx x"), t(r"\sin x \approx x - \frac{x^3}{6}")
    assert shared_runs(a, b)[1]
    k = kinds(morph(a, b))
    assert "Transform" in k and "FadeOutToPoint" not in k and "FadeInFromPoint" not in k
    u, v = t(r"a^2 + b^2 = c^2"), t(r"e^{i\pi} + 1 = 0")
    assert not shared_runs(u, v)[1]
    assert kinds(morph(u, v)) == ["FadeOut", "FadeIn"]


# --- <value> ----------------------------------------------------------------------------------
@manim
def test_value_relabel_fades_out_before_in():
    from konvey.stage.displays.value.mobject import Value

    class W:
        values = {"s.area": 1.0}

    from konvey.stage.displays.value.mobject import morph

    a = Value(leaf('<value id="x" bind="s.area" label="area"></value>'), W())
    b = Value(leaf('<value id="x" bind="s.area" label="shadow area"></value>'), W())
    assert kinds(morph(a, a.copy())) == ["Transform"]
    assert kinds(morph(a, b)) == ["UpdateFromAlphaFunc"] * 4


# --- <draw> turning along arcs -------------------------------------------------------------
def _clock(deg, extra="", around=""):
    x, y = np.cos(np.radians(deg)), np.sin(np.radians(deg))
    return leaf(f'<draw id="x" w="4" h="4" x="-2,2" y="-2,2"><circle id="ring" x="0" y="0" r="1" fill="none"/>'
                f'<line id="spoke" from="0,0" to="{x:.6f},{y:.6f}"/>'
                f'<circle id="pt" x="{x:.6f}" y="{y:.6f}" r="0.06"{around}/>'
                f'<label id="lab" x="{1.3 * x:.6f}" y="{1.3 * y:.6f}" text="z"/>{extra}</draw>')


@manim
def test_draw_spoke_and_point_turn_along_the_circle():
    from konvey.stage.displays.draw.mobject import DrawBlock, _turn

    a, b = DrawBlock(_clock(0)), DrawBlock(_clock(90))
    assert _turn(a, b, "spoke", [])[1] == pytest.approx(90)
    assert _turn(a, b, "pt", [])[1] == pytest.approx(90)          # on the drawn ring
    assert _turn(a, b, "lab", [((0, 0), 90.0)])[1] == pytest.approx(90, abs=1)   # rides along
    assert _turn(a, b, "ring", []) is None
    from konvey.stage.displays.draw.mobject import morph

    anim = morph(a, b)
    anim.begin()
    anim.interpolate(0.5)            # half way: the spoke keeps its length, the point stays on the ring
    tip = a.items["pt"][0].get_center()
    centre = a.to_screen(0, 0)
    assert np.linalg.norm(tip - centre) == pytest.approx(np.linalg.norm(a.to_screen(1, 0) - centre), rel=0.03)
    spoke = a.items["spoke"][0][0].get_points()
    assert np.linalg.norm(spoke[-1] - spoke[0]) == pytest.approx(np.linalg.norm(a.to_screen(1, 0) - centre), rel=0.03)


@manim
def test_draw_around_turns_any_shape_and_slide_stays_straight():
    from konvey.stage.displays.draw.mobject import DrawBlock, _turn, morph

    def box(x, y, move=""):
        return DrawBlock(leaf(f'<draw id="x" w="4" h="4" x="-2,2" y="-2,2"><rect id="b" x="{x}" y="{y}" w="0.3" '
                              f'h="0.3" around="0,0"{move}/></draw>'))
    assert _turn(box(1, 0), box(0, 1), "b", [])[1] == pytest.approx(90)
    assert _turn(box(1, 0), box(-1, 0), "b", [])[1] == pytest.approx(180)   # half a turn: counter-clockwise
    anim = morph(box(1, 0), box(0, 1, ' move="slide"'))
    assert all(getattr(x, "path_arc", 0) == 0 for x in anim.animations)


@manim
def test_draw_angle_mark_sweeps():
    from konvey.stage.displays.draw.mobject import DrawBlock, morph

    def mark(to):
        return DrawBlock(leaf(f'<draw id="x" w="4" h="4" x="-2,2" y="-2,2"><arc id="a" x="0" y="0" r="1" '
                              f'from="0" to="{to}"/></draw>'))
    a, b = mark(30), mark(120)
    anim = morph(a, b)
    anim.begin()
    anim.interpolate(0.5)
    rim = a.items["a"][0].get_points()
    assert np.allclose(np.linalg.norm(rim[:, :2] - a.to_screen(0, 0)[:2], axis=1), 1, atol=0.02)   # still an arc


# --- <draw> labels ------------------------------------------------------------------------------
@manim
def test_draw_labels_step_off_each_other_and_strokes():
    from konvey.stage.displays.draw.mobject import DrawBlock, _box, _overlap

    d = DrawBlock(leaf('<draw id="x" w="8" h="4.4" x="0,10" y="0,10">'
                       '<circle id="p3" x="1" y="2" r="0.16"/><label id="l3" x="1.6" y="2.4" text="(1,2)"/>'
                       '<label id="m1" x="0.9" y="2.2" text="(1.3333, 1.3333)"/>'
                       '<line id="ax" from="0,5" to="10,5"/><label id="on" x="5" y="5" text="on the line"/></draw>'))
    l3, m1, on = (d.items[k][0] for k in ("l3", "m1", "on"))
    assert _overlap(_box(l3), _box(m1)) == 0
    y = d.items["ax"][0][0].get_center()[1]
    b = _box(on)
    assert not (b[2] < y < b[3])                       # off the stroke


@manim
def test_draw_labels_keep_a_readable_size_when_the_page_shrinks_the_drawing():
    from konvey.stage.displays.draw.mobject import MIN_LABEL, DrawBlock

    d = DrawBlock(leaf('<draw id="x" w="8" h="4"><label id="t" x="4" y="2" text="Hi" size="12"/>'
                       '<rect id="r" x="2" y="2" w="1" h="1"/></draw>'))
    ref = DrawBlock(leaf(f'<draw id="x" w="8" h="4"><label id="t" x="4" y="2" text="Hi" size="{MIN_LABEL}"/></draw>'))
    h = ref.items["t"].get_height()
    assert d.items["t"].get_height() == pytest.approx(h, rel=0.01)    # size below the minimum is raised
    d.scale(0.5)
    assert d.items["t"].get_height() == pytest.approx(h, rel=0.01)    # and survives the page's shrink
    assert d.items["r"].get_width() == pytest.approx(0.5, rel=0.01)   # the picture itself shrinks


@manim
def test_draw_circle_and_arc_can_be_dashed_outlines():
    from manimlib import DashedVMobject

    from konvey.stage.displays.draw.mobject import DrawBlock
    d = DrawBlock(leaf('<draw id="x" w="4" h="4" x="-2,2" y="-2,2"><circle id="ring" x="0" y="0" r="1" '
                       'fill="0.5" dashed="true"/><arc id="ang" x="0" y="0" r="0.5" from="0" to="60" dashed="true"/>'
                       '<circle id="solid" x="1" y="1" r="0.3"/></draw>'))
    ring, ang, solid = (d.items[i][0] for i in ("ring", "ang", "solid"))
    assert isinstance(ring, DashedVMobject) and isinstance(ang, DashedVMobject)
    assert not isinstance(solid, DashedVMobject)
    assert all(dash.get_fill_opacity() == 0 for dash in ring)
