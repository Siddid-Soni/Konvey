"""konvey.stage building blocks (spec §4.3): overlay data blocks and general 3D actors."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from konvey.schemas import Scene
from konvey.stage.check import check_runtime, check_static
from konvey.stage.parse import BeatError, parse_beats

HAS_MANIM = importlib.util.find_spec("manimlib") is not None
HAS_CHROMIUM = importlib.util.find_spec("playwright") is not None and Path("/usr/bin/chromium").exists()
FIXTURES = Path(__file__).parent / "fixtures"
manim = pytest.mark.skipif(not HAS_MANIM, reason="needs manimgl (uv --group render)")


def leaf(html: str, i: str = "x"):
    return parse_beats(f"<beats><beat>{html}</beat></beats>")[0].leaves()[i]


def world(html: str):
    from konvey.stage.field import FieldWorld

    beats = parse_beats(f"<beats><beat><world>{html}</world></beat></beats>")
    fw = FieldWorld(beats)
    fw.apply(fw.state_from(beats[0].world, None))
    return fw


# --- overlay blocks ------------------------------------------------------------------
@manim
def test_array_pointers_dim_highlight():
    from konvey.stage.displays.array.mobject import ArrayBlock
    from konvey.stage.theme import current

    a = ArrayBlock(leaf('<array id="x" values="4,8,15,16,23" highlight="2" dim="0-1" pointers="lo:0,mid:2,hi:4">'
                        '</array>'))
    assert len(a.cells) == 5 and len(a.index) == 5 and len(a.pointers) == 3
    for p, i in zip(a.pointers, (0, 2, 4)):   # each arrow sits right above its cell
        assert abs(p[0].get_center()[0] - a.cells[i].get_center()[0]) < 1e-6
        assert p[0].get_bottom()[1] > a.cells[i].get_top()[1]
    assert a.cells[0].get_opacity() < 0.5 and a.cells[3].get_opacity() > 0.5
    lit, plain = a.cells[2][0], a.cells[3][0]          # lit: its own outline in the accent, same fill
    assert lit.get_stroke_color().lower() == current().accent.lower() != plain.get_stroke_color().lower()
    assert lit.get_fill_color().lower() == plain.get_fill_color().lower()


@manim
def test_array_content_ignores_pointers_so_they_slide():
    from konvey.stage.displays.array.mobject import ArrayBlock

    a = ArrayBlock(leaf('<array id="x" values="1,2,3" pointers="i:0"></array>'))
    b = ArrayBlock(leaf('<array id="x" values="1,2,3" pointers="i:2" highlight="1"></array>'))
    c = ArrayBlock(leaf('<array id="x" values="1,2,4" pointers="i:2"></array>'))
    assert a.content == b.content != c.content


@manim
def test_array_errors_name_the_attribute():
    from konvey.stage.displays.array.mobject import ArrayBlock

    with pytest.raises(BeatError, match="outside 0..2"):
        ArrayBlock(leaf('<array id="x" values="1,2,3" pointers="lo:5"></array>'))


@manim
def test_array_chains_hang_below_their_cells_and_linked_cells_point_on():
    from konvey.stage.displays.array.mobject import ArrayBlock

    a = ArrayBlock(leaf('<array id="x" values=",,,," chains="1:cat>fox;3:dog" chain-highlight="1:1"></array>'))
    assert [k[:2] for k in a.chain_keys] == [(1, "cat"), (1, "fox"), (3, "dog")]
    cat, fox, dog = a.chain_items
    assert abs(cat.get_x() - a.cells[1].get_x()) < 1e-6 and cat.get_top()[1] < a.cells[1].get_bottom()[1]
    assert fox.get_top()[1] < cat.get_bottom()[1] and len(a.chain_links) == 3
    assert a.index.get_bottom()[1] > a.cells.get_top()[1]          # labels above, out of the lists' way
    lst = ArrayBlock(leaf('<array id="x" values="4,9,2" linked="true"></array>'))
    assert len(lst.links) == 4                                      # 3 arrows + the end mark
    with pytest.raises(BeatError, match="outside 0..4"):
        ArrayBlock(leaf('<array id="x" values=",,,," chains="7:cat"></array>'))


@manim
def test_an_item_joining_a_chain_drops_in_and_the_others_stay():
    from konvey.stage.displays.array.mobject import ArrayBlock, morph

    a = ArrayBlock(leaf('<array id="x" values=",,," chains="1:cat"></array>'))
    b = ArrayBlock(leaf('<array id="x" values=",,," chains="1:cat>fox;2:dog"></array>'))
    assert a.content != b.content
    target = b.chain_items[0].get_center().copy()
    anim = morph(a, b)
    anim.begin()
    anim.interpolate(1.0)
    assert np.allclose(a.chain_items[0].get_center(), target, atol=1e-3)   # cat is still cat


def test_plan_chains_must_be_drawn():
    from konvey.stage.displays.array import DISPLAY

    assert DISPLAY.check_object({"values": ["", ""], "chains": {"5": ["a"]}})
    assert DISPLAY.check_object({"values": ["", ""], "chains": {"1": [["a"]]}})
    assert not DISPLAY.check_object({"values": ["", ""], "chains": {"1": ["a", "b"]}})


@manim
def test_grid_rows_cols_and_mark():
    from konvey.stage.displays.grid.mobject import GridBlock
    from konvey.stage.theme import current

    g = GridBlock(leaf('<grid id="x" rows="2" cols="3" values="1,0,1;0,1,1" highlight-rows="1" mark="0,2"></grid>'))
    assert len(g.cells) == 6 and len(g.marker) == 1
    assert np.allclose(g.marker[0].get_center(), g.cells[2].get_center())
    accent = current().accent.lower()
    assert g.cells[3][0].get_stroke_color().lower() == accent != g.cells[0][0].get_stroke_color().lower()
    assert g.cells[3][0].get_fill_color().lower() == g.cells[0][0].get_fill_color().lower()
    with pytest.raises(BeatError, match="5 values for 2x3"):
        GridBlock(leaf('<grid id="x" rows="2" cols="3" values="1,2,3,4,5"></grid>'))


@manim
def test_chart_series_colours_legend_and_peak():
    from konvey.stage.displays.chart.mobject import ChartBlock
    from konvey.stage.theme import current

    c = ChartBlock(leaf('<chart id="x" series="A:1,5,2;B:3,3,3" x="0,10" mark="A:max"></chart>'))
    assert len(c.lines) == 2
    assert [ln.get_stroke_color().lower() for ln in c.lines] == [p.lower() for p in current().palette[:2]]
    guide, dot, label = c.marks[0]
    assert np.allclose(dot.get_center(), c.c2p(5, 5))   # A peaks at x=5 with 5
    assert label.text == "5"
    with pytest.raises(BeatError, match="same number"):
        ChartBlock(leaf('<chart id="x" series="A:1,2;B:1,2,3"></chart>'))
    with pytest.raises(BeatError, match="NAME:max"):
        ChartBlock(leaf('<chart id="x" series="A:1,2" mark="C:max"></chart>'))
    with pytest.raises(BeatError, match='series "deg" spans 15..90, outside y="0,0.7"'):
        ChartBlock(leaf('<chart id="x" series="deg:15,90;A:0.1,0.6" y="0,0.7"></chart>'))


@manim
def test_chart_stack_tops_are_cumulative():
    from konvey.stage.displays.chart.mobject import ChartBlock

    c = ChartBlock(leaf('<chart id="x" series="A:1,1;B:2,2" fill="stack"></chart>'))
    assert len(c.areas) == 2
    assert abs(c.lines[1].get_points()[0][1] - c.c2p(0, 3)[1]) < 1e-6


@manim
def test_negative_bars_point_down_from_the_baseline():
    from konvey.stage.displays.bars.mobject import BarsBlock

    b = BarsBlock(leaf('<bars id="x" labels="a,b,c" values="5,-6,7.2"></bars>'))
    base = b.baseline.get_center()[1]
    assert b.bars[0].get_bottom()[1] == pytest.approx(base, abs=1e-6)
    assert b.bars[1].get_top()[1] == pytest.approx(base, abs=1e-6)
    assert b.bars[1].get_bottom()[1] < base
    assert b.value_labels[1].get_top()[1] < b.bars[1].get_bottom()[1]   # "-6" under its bar
    assert b.bars[1].get_height() == pytest.approx(b.bars[0].get_height() * 6 / 5, rel=1e-3)


# --- 3D actors ---------------------------------------------------------------------------
@manim
def test_solid_rests_on_floor_and_shadow_area_is_exact():
    fw = world('<sphere id="s" r="1.5"></sphere><shadow id="sh" of="s"></shadow>')
    s = fw.raw_state("s")
    assert np.allclose(s["at"], [0, 0, 1.5])
    assert fw.values["sh.area"] == pytest.approx(np.pi * 1.5 ** 2, rel=0.01)


@manim
def test_solid_opacity_changes_per_beat():
    from konvey.stage.field import FieldWorld

    beats = parse_beats('<beats><beat><world><sphere id="s"></sphere></world></beat>'
                        '<beat><world><sphere id="s" opacity="0.3"></sphere></world></beat></beats>')
    fw = FieldWorld(beats)
    s0 = fw.state_from(beats[0].world, None)
    s1 = fw.state_from(beats[1].world, s0)
    fw.apply(s1)
    assert fw.actors["s"].body.get_opacity() == pytest.approx(0.3, abs=1e-3)


@manim
def test_slanted_light_stretches_the_shadow():
    straight = world('<solid id="b" shape="box" size="1,1,2"></solid><shadow id="sh" of="b"></shadow>')
    slant = world('<light id="l" dir="1,0,-1"></light>'
                  '<solid id="b" shape="box" size="1,1,2"></solid><shadow id="sh" of="b"></shadow>')
    assert straight.values["sh.area"] == pytest.approx(1.0, rel=0.01)
    assert slant.values["sh.area"] == pytest.approx(3.0, rel=0.01)   # 1 wide, 1 + 2 long


@manim
def test_field_on_sphere_finds_the_poles():
    fw = world('<sphere id="s" r="1" at="0,0,2"></sphere><field id="f" on="s" fn="-y; x; 0"></field>')
    zeros = fw.actors["f"].zeros[0]
    assert fw.values["f.zeros"] == 2
    assert sorted(round(z[2]) for z in zeros) == [-1, 1]


@manim
def test_field_on_floor_and_fn_errors():
    fw = world('<field id="f" fn="x; y" x="-2,2" y="-2,2"></field>')
    assert fw.values["f.zeros"] == 1
    with pytest.raises(BeatError, match='needs 3 components separated by ";"'):
        world('<sphere id="s"></sphere><field id="f" on="s" fn="x; y"></field>')
    with pytest.raises(BeatError, match="must name a <sphere id>"):
        world('<solid id="b" shape="box"></solid><field id="f" on="b" fn="x; y; z"></field>')


@manim
def test_light_must_point_down_and_shadow_needs_a_solid():
    with pytest.raises(BeatError, match="travel downward"):
        world('<light id="l" dir="0,0,1"></light>')
    with pytest.raises(BeatError, match='of="nope" must name'):
        world('<shadow id="sh" of="nope"></shadow>')


@manim
def test_label3d_follows_its_solid():
    fw = world('<sphere id="s" r="1" at="2,0,1"></sphere><label3d id="t" of="s" text="here"></label3d>')
    assert np.allclose(fw.actors["t"].at, [2, 0, 2.35])


@manim
def test_line3d_runs_surface_to_surface_and_follows_solids():
    fw = world('<sphere id="a" r="1" at="0,0,1"></sphere><sphere id="b" r="0.5" at="4,0,1"></sphere>'
               '<line3d id="l" from="a" to="b"></line3d>')
    pts = fw.actors["l"].line.get_points()
    assert np.allclose(pts[0], [1, 0, 1]) and np.allclose(pts[-1], [3.5, 0, 1])


@manim
def test_line3d_ends_can_change_and_interpolate():
    from konvey.stage.field import FieldWorld

    beats = parse_beats(
        '<beats><beat><world><sphere id="a" r="1" at="0,0,1"></sphere><sphere id="b" r="1" at="4,0,1"></sphere>'
        '<line3d id="l" from="a" to="b"></line3d></world></beat>'
        '<beat><world><sphere id="a" r="1" at="0,0,1"></sphere><sphere id="b" r="1" at="4,0,1"></sphere>'
        '<line3d id="l" from="a" to="0,4,1"></line3d></world></beat></beats>')
    fw = FieldWorld(beats)
    s0 = fw.state_from(beats[0].world, None)
    s1 = fw.state_from(beats[1].world, s0)
    mid = FieldWorld.lerp(s0, s1, 0.5)["l"]
    assert np.allclose(mid["to"], [2, 2, 1]) and np.isclose(mid["to_r"], 0.5)


@manim
def test_angle3d_marks_right_angles_with_a_square():
    fw = world('<angle3d id="g" at="0,0,0" from="2,0,0" to="0,2,0" r="0.5"></angle3d>')
    corners = fw.actors["g"].mob.get_anchors()
    assert any(np.allclose(c, [0.5, 0.5, 0]) for c in corners)   # the square's far corner


@manim
def test_line3d_errors_name_the_problem():
    with pytest.raises(BeatError, match='to="nope" must name'):
        world('<sphere id="a"></sphere><line3d id="l" from="a" to="nope"></line3d>')
    with pytest.raises(BeatError, match='needs from='):
        world('<line3d id="l" to="1,2,3"></line3d>')


@manim
def test_sphere_framing_uses_its_outline_not_its_box():
    from konvey.stage.world import fit_zoom

    fw = world('<sphere id="s" r="1" at="0,0,1"></sphere>')
    pts = np.array(fw.actors["s"].extent(fw.raw_state("s")))
    box = np.array([[x, y, z] for x in (-1.15, 1.15) for y in (-1.15, 1.15) for z in (0, 2.15)])
    assert fit_zoom(pts, -35, 62, (6, 4)) > 1.3 * fit_zoom(box, -35, 62, (6, 4))


def test_world_exits_fade_leaving_actors_only():
    from konvey.stage.world import WorldState, world_exits

    a = WorldState(show={"s": 1.0, "t": 1.0}, fields={"f": {"show": 1.0}, "g": {"show": 1.0}})
    b = WorldState(show={"t": 1.0}, fields={"f": None, "g": {"show": 1.0}})
    mid = world_exits(a, b)
    assert mid.show == {"s": 0.0, "t": 1.0}
    assert mid.fields["f"]["show"] == 0.0 and mid.fields["g"]["show"] == 1.0
    assert world_exits(b, b) is None


@pytest.mark.skipif(not (HAS_MANIM and HAS_CHROMIUM), reason="needs manimgl + Chromium")
def test_two_beat_blocks_and_world_play_headless(tmp_path):
    """Pointers slide, a chart enters, a field morphs and a solid moves, without crashing."""
    html = """<beats>
<beat vo="One." style="padding: 0.5u 0.6u; gap: 0.2u">
  <h2 id="t">Start</h2>
  <div class="grow row center" style="gap: 0.5u"><div id="view" class="grow"></div>
    <array id="a" values="1,2,3,4" pointers="i:0"></array></div>
  <world><sphere id="s" r="1"></sphere><field id="f" on="s" fn="-y; x; 0"></field>
    <light id="l" dir="0.5,0,-1"></light><shadow id="sh" of="s"></shadow>
    <label3d id="lab" of="s" text="north"></label3d></world>
  <camera focus="view"></camera>
</beat>
<beat vo="Two." style="padding: 0.5u 0.6u; gap: 0.2u">
  <h2 id="t">Start</h2>
  <div class="grow row center" style="gap: 0.5u"><div id="view" class="grow"></div>
    <array id="a" values="1,2,3,4" pointers="i:3" highlight="3"></array>
    <chart id="c" series="A:1,2,4;B:4,2,1" x="0,2" mark="A:max" w="3" h="2"></chart></div>
  <world><sphere id="s" r="1" at="1,0,1.5"></sphere><field id="f" on="s" fn="1; 0; 0"></field>
    <light id="l" dir="0.5,0,-1"></light><shadow id="sh" of="s"></shadow>
    <label3d id="lab" of="s" text="north"></label3d></world>
  <camera focus="view"></camera>
</beat>
</beats>"""
    assert check_runtime(html, tmp_path, "S1") == []


# --- plan + checker -------------------------------------------------------------------------
def test_plan_kinds_validate():
    from konvey.schemas import ObjectSpec
    from konvey.validators import _object_problems

    ok = [ObjectSpec(id="a", kind="array", data={"values": [1, 2]}),
          ObjectSpec(id="c", kind="chart", data={"series": {"S": [1, 2], "I": [3, 4]}}),
          ObjectSpec(id="s", kind="solid", data={"shape": "cone"}),
          ObjectSpec(id="f", kind="field", data={"fn": "-y; x; 0"}),
          ObjectSpec(id="g", kind="grid", data={"rows": 2, "cols": 2, "values": [1, 0, 0, 1]})]
    assert all(_object_problems(o) == [] for o in ok)
    assert "same number" in _object_problems(ObjectSpec(id="c", kind="chart", data={"series": {"S": [1], "I": [3, 4]}}))[0]
    assert "3 values for 2x2" in _object_problems(ObjectSpec(id="g", kind="grid", data={"rows": 2, "cols": 2, "values": [1, 0, 1]}))[0]
    assert "use one of sphere" in _object_problems(ObjectSpec(id="s", kind="solid", data={"shape": "torus"}))[0]


SCENE = Scene.model_validate({
    "id": "S1", "purpose": "hook", "duration_sec": 10,
    "vo_script": ["Watch the curves."],
    "beats": [{"vo_line": "Watch the curves.",
               "objects": [{"id": "c", "kind": "chart", "data": {"series": {"A": [1, 2.5], "B": [3, 0]}}},
                           {"id": "a", "kind": "array", "data": {"values": [7, 9]}}],
               "animation": {"type": "FadeIn", "code_hint": "FadeIn(c)", "run_time": 1}}],
})


def test_check_static_wants_chart_and_array_data_verbatim():
    good = ('<beats><beat vo="Watch the curves."><chart id="c" series="A:1,2.5;B:3,0"></chart>'
            '<array id="a" values="7,9"></array></beat></beats>')
    assert check_static(good, SCENE) == []
    bad = good.replace("A:1,2.5", "A:1,2.4").replace('values="7,9"', 'values="7,8"')
    problems = check_static(bad, SCENE)
    assert any("series 'A' verbatim" in p for p in problems)
    assert any('<array values="7,9">' in p for p in problems)


@manim
def test_tex_norm_bars_are_typeset():
    from konvey.stage.displays.tex import tex_safe
    from konvey.stage.overlay import build_leaf

    assert tex_safe(r"\|v\| = 1") == r"\Vert v\Vert  = 1"
    build_leaf(leaf(r'<tex id="x">\lim_{q \to p} \|v(q)-v(p)\| = 0</tex>'), None)   # LaTeX would fail on \|


def test_stage_addendum_reaches_agent_1():
    from konvey.prompts import build_agent_instructions

    assert "renderer = stage" in build_agent_instructions(1, "few-shot")


@manim
def test_chart_and_plot_ranges_away_from_zero_keep_their_size():
    from konvey.stage.displays.chart.mobject import ChartBlock
    from konvey.stage.displays.plot.mobject import build as build_plot

    c = ChartBlock(leaf('<chart id="x" series="A:6,8,57" x="81,89" y="0,60" w="6" h="2.8"></chart>'))
    assert c.get_width() < 8.5
    p = build_plot(leaf('<plot id="x" x="100,110" y="50,60" fn="x - 50" w="5" h="3"></plot>'))
    assert p.get_width() < 5.8 and p.get_height() < 3.6   # the box plus its tick numbers


def test_planned_numbers_compare_as_numbers():
    from konvey.stage.match import same_values as _same_values

    assert _same_values([1048576, 20], "1048576,20")
    assert _same_values([0.5, 2], "0.50, 2.0")
    assert not _same_values([1048576, 20], "1048000,20")
    assert not _same_values([1, 2], "1,2,3")
    assert _same_values(["A", "B"], "A, B")


@manim
def test_tex_spacing_with_text_is_typeset():
    from konvey.stage.overlay import build_leaf

    build_leaf(leaf(r'<tex id="x">\text{a}_k/2, \; \text{b}_k \: c</tex>'), None)


def test_bar_numbers_never_show_scientific_notation():
    from konvey.stage.displays.base import _fmt

    assert [_fmt(v, None) for v in (1048576, 12742.0, 20, 0.53, 2.5)] == ["1,048,576", "12,742", "20", "0.53", "2.5"]
    assert _fmt(0.5, "{:.1f}") == "0.5"


@manim
@pytest.mark.parametrize("shape,faces,extra", [
    ("tetrahedron", 4, ""), ("box", 6, ""), ("octahedron", 8, ""), ("dodecahedron", 12, ""),
    ("icosahedron", 20, ""), ("prism", 7, 'sides="5"'), ("pyramid", 5, 'sides="4"')])
def test_flat_solids_have_their_faces_and_rest_on_the_floor(shape, faces, extra):
    w = world(f'<solid id="p" shape="{shape}" {extra}></solid>')
    solid = w.actors["p"]
    assert len(solid.body) == faces
    assert solid.body_points()[:, 2].min() == pytest.approx(0.0, abs=1e-3)   # resting, not sunk


@manim
def test_graph_block_parts_and_errors():
    from konvey.stage.displays.graph.mobject import GraphBlock

    g = GraphBlock(leaf('<graph id="x" nodes="A:0,0;B:2,0;C:1,1" edges="A-B:4;B>C;A-C:1" '
                        'highlight="A" path="A-C" values="A:0;B:∞"></graph>'))
    assert (len(g.nodes), len(g.edges), len(g.weights), len(g.values)) == (3, 3, 3, 3)
    assert g.value_text == ["0", "∞", ""]
    assert len(GraphBlock(leaf('<graph id="x" nodes="A,B,C,D" edges="A-B"></graph>')).nodes) == 4
    with pytest.raises(BeatError, match='no node named "Z"'):
        GraphBlock(leaf('<graph id="x" nodes="A,B" edges="A-Z"></graph>'))
    with pytest.raises(BeatError, match="path"):
        GraphBlock(leaf('<graph id="x" nodes="A,B" edges="A-B" path="A-Q"></graph>'))


@manim
def test_face3d_keeps_its_corner_count_and_line_on_needs_a_sphere():
    from konvey.stage.field import FieldWorld

    beats = parse_beats('<beats><beat><world><face3d id="f" points="0,0,0;1,0,0;0,1,0"></face3d></world></beat>'
                        '<beat><world><face3d id="f" points="0,0,0;1,0,0;1,1,0;0,1,0"></face3d></world></beat></beats>')
    with pytest.raises(BeatError, match="same number of corners"):
        FieldWorld(beats)
    with pytest.raises(BeatError, match="must name a <sphere id>"):
        world('<solid id="b" shape="box"></solid><line3d id="l" on="b" from="0,0,2" to="1,0,1"></line3d>')


@manim
def test_best_view_sees_vectors_without_foreshortening():
    from konvey.stage.world import _view_axes, best_view

    u, v = np.array([2.0, 1, 0]), np.array([0.0, 1, 2])
    o = np.zeros(3)
    th, ph = best_view(np.array([o, u, v]), [(o, u), (o, v)])
    R = _view_axes(th, ph)[:, :2]
    ratios = [np.linalg.norm(w @ R) / np.linalg.norm(w) for w in (u, v)]
    assert min(ratios) > 0.9                       # both arrows read at nearly full length
    # with a third arrow perpendicular to both, no view is perfect, but none is lost
    n = np.cross(u, v) / 2
    th, ph = best_view(np.array([o, u, v, n]), [(o, u), (o, v), (o, n)])
    R = _view_axes(th, ph)[:, :2]
    assert min(np.linalg.norm(w @ R) / np.linalg.norm(w) for w in (u, v, n)) > 0.6


@pytest.mark.skipif(not (HAS_MANIM and HAS_CHROMIUM), reason="needs manimgl + Chromium")
def test_frame_audit_catches_labels_on_text_and_crowding(tmp_path):
    """A label pinned to a solid that lands on a readout, and a crowded screen, are reported."""
    readouts = "".join(f'<text id="r{k}" size="26">item {k}</text>' for k in range(9))
    html = f"""<beats>
<beat vo="One." style="padding: 0.5u 0.6u; gap: 0.2u">
  <h2 id="t">Counts</h2>
  <div class="row center" style="gap: 0.3u">{readouts}</div>
  <div id="view" class="grow"></div>
  <world><solid id="p" shape="octahedron" r="1.2"></solid>
    <label3d id="tag" of="p" text="a very long floating label"></label3d></world>
  <camera show="p"></camera>
</beat>
</beats>"""
    problems = " ".join(check_runtime(html, tmp_path, "S1"))
    assert "pieces of text on screen at once" in problems
    assert "has no focus" not in problems            # the one empty box was taken as the view


@pytest.mark.skipif(not (HAS_MANIM and HAS_CHROMIUM), reason="needs manimgl + Chromium")
def test_frame_audit_wants_focus_when_it_cannot_guess(tmp_path):
    html = """<beats>
<beat vo="One." style="padding: 0.5u 0.6u; gap: 0.2u">
  <h2 id="t">Two boxes</h2>
  <div class="grow row"><div id="a" class="grow"></div><div id="b" class="grow"></div></div>
  <world><sphere id="s" r="1"></sphere></world>
  <camera></camera>
</beat>
</beats>"""
    assert "has no focus" in " ".join(check_runtime(html, tmp_path, "S1"))


@manim
def test_empty_array_number_readout_and_size_scaled_cells():
    from konvey.stage.displays.array.mobject import ArrayBlock
    from konvey.stage.displays.number.mobject import NumberBlock

    empty = ArrayBlock(leaf('<array id="x"></array>'))
    assert len(empty.cells) == 0 and len(empty.empty) == 1          # a bare peg, not an error
    small, big = (ArrayBlock(leaf(f'<array id="x" values="1,2,3" size="{s}"></array>')) for s in (20, 30))
    assert small.cells.get_width() < 0.75 * big.cells.get_width()   # size= shrinks the cells
    n = NumberBlock(leaf('<number id="x" value="13" label="moves"></number>'))
    assert len(n) == 2
    with pytest.raises(BeatError, match="needs value"):
        NumberBlock(leaf('<number id="x" label="moves"></number>'))


def test_cut_solo_reply_is_detected():
    from konvey.lean import _reply_is_cut

    assert _reply_is_cut('<research>{"knowledge": {"topic": "x"')
    assert _reply_is_cut('<research>{}</research><scene id="S1"><beats><beat vo="a">')
    assert not _reply_is_cut('<research>{}</research><scene id="S1"><beats></beats></scene>')


# --- coordinate-built pictures: hull solids and <draw> ------------------------------------
@manim
def test_hull_solid_from_corners_shadow_and_errors():
    # oblique pyramid: tip over a corner of a 2x2 base, height 2
    fw = world('<solid id="p" shape="hull" points="0,0,0; 2,0,0; 2,2,0; 0,2,0; 0,0,2"></solid>'
               '<shadow id="sh" of="p"></shadow>')
    a, st = fw.actors["p"], fw.raw_state("p")
    assert len(a.body) == 5                       # square base + 4 triangles
    assert len(a.edges) == 8
    assert fw.values["sh.area"] == pytest.approx(4.0, rel=0.01)
    assert np.allclose(st["at"], [0.8, 0.8, 0.4])
    with pytest.raises(BeatError, match="flat"):
        world('<solid id="p" shape="hull" points="0,0,0; 1,0,0; 0,1,0; 1,1,0"></solid>')
    with pytest.raises(BeatError, match="4 or more"):
        world('<solid id="p" shape="hull" points="0,0,0; 1,0,0; 0,1,1"></solid>')


@manim
def test_hull_corners_slide_between_beats_and_at_shifts_it():
    from konvey.stage.field import FieldWorld

    beats = parse_beats(
        '<beats><beat><world><solid id="p" shape="hull" points="0,0,0; 2,0,0; 0,2,0; 0,0,2"></solid></world></beat>'
        '<beat><world><solid id="p" shape="hull" points="0,0,0; 2,0,0; 0,2,0; 0,0,4" at="1,0,0"></solid>'
        '</world></beat></beats>')
    fw = FieldWorld(beats)
    s0 = fw.state_from(beats[0].world, None)
    s1 = fw.state_from(beats[1].world, s0)
    mid = FieldWorld.lerp(s0, s1, 0.5)
    fw.apply(mid)
    top = fw.actors["p"].body_points()[:, 2].max()
    assert top == pytest.approx(3.0, abs=1e-6)
    assert fw.actors["p"].body_points()[:, 0].min() == pytest.approx(0.5, abs=1e-6)
    bad = parse_beats(
        '<beats><beat><world><solid id="p" shape="hull" points="0,0,0; 2,0,0; 0,2,0; 0,0,2"></solid></world></beat>'
        '<beat><world><solid id="p" shape="hull" points="0,0,0; 2,0,0; 0,2,0; 0,0,2; 2,2,2"></solid>'
        '</world></beat></beats>')
    with pytest.raises(BeatError, match="same number of corners"):
        FieldWorld(bad)


def test_draw_children_parse_inside_the_canvas_only():
    n = leaf('<draw id="x" w="6" h="3"><rect id="a" x="1" y="1" w="1" h="0.5"/>'
             '<label id="t" x="3" y="2" text="hi"></label></draw>')
    assert [c.tag for c in n.children] == ["rect", "label"]
    with pytest.raises(BeatError, match="inside a <draw>"):
        parse_beats('<beats><beat><rect id="a"></rect></beat></beats>')
    with pytest.raises(BeatError, match="only"):
        parse_beats('<beats><beat><draw id="x"><text id="y">no</text></draw></beat></beats>')


@manim
def test_draw_block_maps_coordinates_and_morphs_by_id():
    from manimlib import AnimationGroup

    from konvey.stage.displays.draw.mobject import DrawBlock
    from konvey.stage.motion import morph

    def disks(x):
        return DrawBlock(leaf(f'<draw id="x" w="8" h="4" x="0,12" y="0,6">'
                              f'<rect id="peg" x="6" y="3" w="0.2" h="5" color="muted"/>'
                              f'<rect id="d1" x="{x}" y="0.5" w="2" h="0.5" label="1"/></draw>'))
    a, b = disks(2), disks(10)
    assert a.get_width() == pytest.approx(8) and a.get_height() == pytest.approx(4)   # whole canvas
    assert a.items["d1"][0].get_center()[0] == pytest.approx(2 * 8 / 12 - 4)
    anim = morph(a, b)
    assert isinstance(anim, AnimationGroup)
    moves = [x for x in anim.animations if type(x).__name__ == "Transform"]
    assert any(abs(getattr(x, "path_arc", 0)) > 0 for x in moves)      # long move hops over
    assert not any(type(x).__name__ in ("FadeIn", "FadeOut") for x in anim.animations)
    with pytest.raises(BeatError, match="two shapes"):
        DrawBlock(leaf('<draw id="x"><circle id="a" x="1" y="1" r="1"/><circle id="a" x="2" y="1" r="1"/></draw>'))
    with pytest.raises(BeatError, match="needs r="):
        DrawBlock(leaf('<draw id="x"><circle id="a" x="1" y="1"/></draw>'))


@manim
def test_draw_move_attribute_slides_or_hops():
    from konvey.stage.displays.draw.mobject import DrawBlock
    from konvey.stage.motion import morph

    def token(x, move=""):
        m = f' move="{move}"' if move else ""
        return DrawBlock(leaf(f'<draw id="x" w="8" h="4" x="0,20" y="0,8">'
                              f'<rect id="msg" x="{x}" y="3" w="3" h="1" label="get"{m}/></draw>'))

    def arcs(a, b):
        return [abs(getattr(x, "path_arc", 0)) for x in morph(a, b).animations
                if type(x).__name__ == "Transform"]

    assert max(arcs(token(2), token(17))) > 0                  # auto: a long move hops
    assert max(arcs(token(2), token(17, "slide"))) == 0        # slide: straight along the wire
    assert max(arcs(token(2), token(3, "hop"))) > 0            # hop: arcs even when short
    with pytest.raises(BeatError, match='move="fly"'):
        token(2, "fly")


def test_plan_hull_and_drawing_kinds():
    from konvey.schemas import ObjectSpec
    from konvey.stage.examples import load_examples, scene_kinds, select
    from konvey.validators import _object_problems

    hull = ObjectSpec(id="p", kind="solid", data={"shape": "hull", "points": [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]]})
    assert _object_problems(hull) == []
    assert "needs data['points']" in _object_problems(ObjectSpec(id="p", kind="solid", data={"shape": "hull"}))[0]
    assert _object_problems(ObjectSpec(id="d", kind="drawing", data={"shows": "disks on pegs"})) == []
    assert "needs data['shows']" in _object_problems(ObjectSpec(id="d", kind="drawing", data={}))[0]
    scene = Scene.model_validate({"id": "S1", "purpose": "hook", "duration_sec": 10, "vo_script": ["x"],
                                  "beats": [{"vo_line": "x", "objects": [hull.model_dump()]}]})
    assert "hull" in scene_kinds(scene)
    assert {e.name for e in select(scene, "cut a cube into pyramids")} == {"world3d-cut", "world3d-hull"}
    assert {"drawing-stack", "world3d-hull"} <= {e.name for e in load_examples()}


def test_check_static_wants_planned_drawing_labels():
    scene = Scene.model_validate({
        "id": "S1", "purpose": "hook", "duration_sec": 10, "vo_script": ["Two disks."],
        "beats": [{"vo_line": "Two disks.",
                   "objects": [{"id": "h", "kind": "drawing", "data": {"shows": "disks", "labels": ["1", "2"]}}]}]})
    good = ('<beats><beat vo="Two disks."><draw id="h"><rect id="a" x="1" y="1" w="1" h="1" label="1"/>'
            '<label id="b" x="2" y="2" text="2"/></draw></beat></beats>')
    assert check_static(good, scene) == []
    assert "missing ['2']" in check_static(good.replace('text="2"', 'text="3"'), scene)[0]


def _system_beat(vo, at, label, store, extra=()):
    return {"vo_line": vo, "objects": [
        {"id": "sys", "kind": "system", "data": {"parts": ["client", "server"], "holds": {"server": store},
                                                 "items": [{"id": "req", "in": at, "text": label}]}},
        *extra]}


def _plan(*beats):
    from konvey.schemas import ScenePlan

    scenes = [{"id": sid, "purpose": "build", "duration_sec": 10, "vo_script": ["x"],
               "beats": list(beats) if sid == "S1" else [{"vo_line": "x", "objects": [
                   {"id": "t", "kind": "text", "data": {"text": "x"}}]}]} for sid in ("S1", "S2", "S3")]
    return ScenePlan.model_validate({"title": "t", "scenes": scenes})


def test_plan_system_state_is_validated():
    from konvey.schemas import ObjectSpec
    from konvey.stage.displays.places import system_state
    from konvey.validators import ValidationError, _object_problems, check_plan_displays as check_plan_drawings

    def problems(**data):
        return _object_problems(ObjectSpec(id="d", kind="system", data=data))

    req = {"id": "req", "in": "server", "text": "GET /a"}
    ok = {"parts": ["client", "server"], "holds": {"server": [3, 5.0]},
          "items": [req, {"id": "resp", "in": "client", "from": "server", "text": "200 OK", "lines": ["name: mug"]}]}
    assert problems(**ok) == []
    parts, items, holds = system_state(ok)
    assert holds == {"server": ["3", "5"]} and items[1]["lines"] == ["name: mug"] and items[1]["from"] == "server"
    assert "not one of parts" in problems(parts=["client", "server"], items=[{**req, "in": "wire"}])[0]
    assert "rest inside a part" in problems(parts=["a", "b"], items=[{"id": "x", "on": "a-b", "text": "t"}])[0]
    assert "sender" in problems(parts=["a", "b"], items=[{"id": "x", "in": "a", "from": "a", "text": "t"}])[0]
    assert "too long for a slot" in problems(parts=["a", "b"], holds={"a": ["cache: www.example.com = 203.0.113.70"]})[0]
    assert "too long" in problems(parts=["client", "server"], items=[{**req, "text": "x" * 30}])[0]
    assert "distinct ids" in problems(parts=["client", "server"], items=[req, req])[0]
    assert "no 'token'" in problems(parts=["client", "server"], token={"at": "client", "label": "x"})[0]
    assert "belong to kind 'system'" in _object_problems(
        ObjectSpec(id="d", kind="drawing", data={"shows": "x", "parts": ["a", "b"]}))[0]

    check_plan_drawings(_plan(_system_beat("a", "client", "GET /a", ["3"]),
                              _system_beat("b", "server", "GET /a", ["3"])))
    check_plan_drawings(_plan(_system_beat("a", "client", "GET /a", ["3"]),   # a filler beat: noted only
                              _system_beat("b", "client", "GET /a", ["3"])))
    assert system_state({"parts": ["a", "b"], "items": [
        {"id": "s", "in": "a", "text": "SYN", "lines": ["SYN", "seq 1000"]}]})[1][0]["lines"] == ["seq 1000"]
    with pytest.raises(ValidationError, match="repeats what the places"):
        check_plan_drawings(_plan(_system_beat("a", "client", "GET /a", ["3"], extra=[
            {"id": "t", "kind": "text", "data": {"text": "GET /a"}}])))
    fan = lambda vo, at: {"vo_line": vo, "objects": [{"id": "lb", "kind": "system", "data": {  # noqa: E731
        "parts": ["client", "balancer", ["a", "b"]], "items": [{"id": "r", "in": at, "text": "req"}]}}]}
    with pytest.raises(ValidationError, match="NEW item"):           # request 1 is not request 2 moved on
        check_plan_drawings(_plan(fan("x", "a"), fan("y", "b")))
    with pytest.raises(ValidationError, match="left the screen"):     # a system stays once shown
        check_plan_drawings(_plan(_system_beat("a", "client", "GET /a", ["3"]),
                                  {"vo_line": "b", "objects": [{"id": "c", "kind": "bars",
                                                                "data": {"labels": ["a"], "values": [1]}}]}))


def test_system_keeps_its_look_across_beats():
    from konvey.stage.displays.places import carry_system_look

    beats = parse_beats('<beats><beat><system id="s" parts="a,b" shapes="b:cylinder" w="11"></system></beat>'
                        '<beat><system id="s" parts="a,b"></system></beat></beats>')
    carry_system_look(beats)
    assert beats[1].leaves()["s"].attrs["shapes"] == "b:cylinder" and beats[1].leaves()["s"].attrs["w"] == "11"
    flip = parse_beats('<beats><beat><system id="s" parts="a,b"></system></beat>'
                       '<beat><system id="s" parts="a,b" shapes="b:cylinder"></system></beat></beats>')
    with pytest.raises(BeatError, match="keep their look"):
        carry_system_look(flip)
    carry_system_look(flip, strict=False)                       # a previous scene only hands it down


def test_planned_system_state_is_written_into_the_html():
    from konvey.stage.check import apply_plan_state

    scene = Scene.model_validate({
        "id": "S1", "purpose": "hook", "duration_sec": 10, "vo_script": ["Ask."],
        "beats": [_system_beat("Ask.", "server", "GET /a", ["3", "5"])]})
    html = ('<beats><beat vo="Ask."><system id="sys" parts="client,server" holds="server:3" shapes="server:cylinder" '
            'highlight="server:3; server:9"><item id="req" in="client" text="GET" style="pill" color="c2"></item>'
            '</system></beat></beats>')
    out = apply_plan_state(html, scene)
    assert check_static(out, scene) == []
    assert 'holds="server:3|5"' in out and 'shapes="server:cylinder"' in out      # the look is kept
    assert 'style="pill"' in out and 'color="c2"' in out and 'in="server"' in out
    assert 'highlight="server:3"' in out                                         # 9 is not held any more


def test_steady_blocks_keep_one_scale_across_beats():
    from konvey.stage.layout import _steady

    beats = parse_beats('<beats><beat><system id="s" parts="a,b"></system></beat>'
                        '<beat><system id="s" parts="a,b"></system><text id="t">x</text></beat></beats>')
    natural = {0: {"s": (12.0, 4.0)}, 1: {"s": (12.0, 4.0), "t": (1.0, 0.5)}}
    sizes = {0: {"s": (12.0, 4.0)}, 1: {"s": (9.0, 3.0), "t": (1.0, 0.5)}}   # beat 1 had to shrink it
    assert _steady(beats, sizes, natural)
    assert sizes[0]["s"] == pytest.approx((9.0, 3.0)) and sizes[1]["t"] == (1.0, 0.5)
    assert not _steady(beats, sizes, natural)


def test_steady_scale_leaves_out_a_beat_that_needs_far_less():
    from konvey.stage.layout import _steady

    beats = parse_beats("<beats>" + '<beat><system id="s" parts="a,b"></system></beat>' * 3
                        + '<beat><system id="s" parts="a,b"></system><bars id="c" labels="x" values="1"></bars></beat>'
                        + "</beats>")
    natural = {k: {"s": (12.0, 4.0)} for k in range(4)}
    sizes = {0: {"s": (12.0, 4.0)}, 1: {"s": (11.4, 3.8)}, 2: {"s": (12.0, 4.0)},
             3: {"s": (6.0, 2.0)}}                       # the chart under it halves the system
    assert _steady(beats, sizes, natural)
    assert sizes[0]["s"] == pytest.approx((11.4, 3.8)) and sizes[2]["s"] == pytest.approx((11.4, 3.8))
    assert sizes[3]["s"] == (6.0, 2.0)                   # only that beat is small


def test_check_static_wants_the_planned_system_state():
    scene = Scene.model_validate({
        "id": "S1", "purpose": "hook", "duration_sec": 10, "vo_script": ["a", "b"],
        "beats": [_system_beat("Ask.", "client", "GET /a", ["3"]), _system_beat("Sent.", "server", "GET /a", ["3"])]})

    def doc(in2="server", holds2="server:3", id2="req"):
        return ('<beats><beat vo="Ask."><system id="sys" parts="client,server" holds="server:3" shapes="server:cylinder">'
                '<item id="req" in="client" text="GET /a" style="pill" color="c2"></item></system></beat>'
                f'<beat vo="Sent."><system id="sys" parts="client,server" holds="{holds2}" shapes="server:cylinder">'
                f'<item id="{id2}" in="{in2}" text="GET /a"></item></system></beat></beats>')

    assert check_static(doc(), scene) == []                      # style, colour, shapes are free
    wrong = check_static(doc(in2="client"), scene)
    assert len(wrong) == 1 and 'in="client"' in wrong[0] and 'in="server"' in wrong[0]
    assert "holds=" in check_static(doc(holds2="server:4"), scene)[0]
    assert "items" in check_static(doc(id2="req2"), scene)[0]   # a new id would not travel
    assert "draw it as <places" in check_static('<beats><beat vo="Ask."><h2 id="t">x</h2></beat>'
                                                '<beat vo="Sent."><h2 id="t">y</h2></beat></beats>', scene)[0]


@manim
def test_system_block_items_travel_by_id():
    from konvey.stage.displays.places.mobject import PlacesBlock
    from konvey.stage.displays.places.mobject import _via
    from konvey.stage.motion import morph

    def sys_(items, holds="store:1|5|8", extra=""):
        return PlacesBlock(leaf(f'<system id="x" parts="client,server,store" holds="{holds}"{extra}>{items}</system>'))

    req = '<item id="req" {} text="GET /a" style="pill"></item>'
    a, b = sys_(req.format('in="client"')), sys_(req.format('in="server"'), extra=' shapes="store:cylinder"')
    assert a.get_width() == pytest.approx(12) and a.get_height() == pytest.approx(4.2)
    xs = [box[0].get_center()[0] for box in a.boxes]
    assert xs == sorted(xs) and np.allclose(np.diff(xs), np.diff(xs)[0])    # equal spacing
    assert abs(a.items["req"].get_center()[0] - xs[0]) < 1e-6
    assert abs(b.items["req"].get_center()[0] - xs[1]) < 1e-6
    anim = morph(a, b)
    assert any(type(x).__name__ == "AnimationGroup" for x in anim.animations)    # sent as a packet
    # between parts the packet leaves through the facing side, runs along the wire, enters
    ports, wires = b.route("client", "server")
    assert wires == [frozenset({"client", "server"})]
    through, used = b.route("client", "store")                    # through the server
    assert len(through) == 4 and len(used) == 2
    assert ports[0][0] == pytest.approx(xs[0] + b.geom["client"]["bw"] / 2)
    assert ports[1][0] == pytest.approx(xs[1] - b.geom["server"]["bw"] / 2)
    path = _via(np.array([0.0, 1.0, 0]), np.array([4.0, 1.0, 0]), [np.array([1.0, 0, 0]), np.array([3.0, 0, 0])])
    pt = np.zeros((1, 3))
    mid = path(pt + [0, 1, 0], pt + [4, 1, 0], 0.5)[0]
    assert mid[1] == pytest.approx(0.0) and 1 <= mid[0] <= 3
    fan = PlacesBlock(leaf('<system id="x" parts="client,balancer,a|b|c" highlight="b" notes="b:down">'
                           '<item id="r" in="c" from="balancer" text="GET /"></item></system>'))
    assert len(fan.wires) == 4 and fan.geom["a"]["x"] == fan.geom["c"]["x"] > fan.geom["balancer"]["x"]
    assert fan.geom["a"]["bw"] > fan.geom["balancer"]["bw"]                 # the column is wider
    assert fan.geom["a"]["y"] > fan.geom["b"]["y"] > fan.geom["c"]["y"]
    two = sys_('<item id="r" in="client" text="ask the resolver for the address"></item>')
    assert "\n" not in "x" and len(two.items["r"][1].submobjects) > 0     # wrapped, not rejected
    card = sys_('<item id="resp" in="server" text="200 OK" lines="name: mug|price: 4.0" style="card"></item>')
    assert len(card.items["resp"][1][2]) == 2                                # header, rule, two lines
    with pytest.raises(BeatError, match="too long"):
        sys_('<item id="r" in="client" text="' + "x" * 80 + '"></item>')
    with pytest.raises(BeatError, match="rest inside a part"):
        sys_('<item id="r" on="client-server" text="x"></item>')
    with pytest.raises(BeatError, match="from= names the sender"):
        sys_('<item id="r" in="client" from="client" text="x"></item>')
    with pytest.raises(BeatError, match="in=.*or on="):
        sys_('<item id="r" text="x"></item>')
    with pytest.raises(BeatError, match="belongs inside a <places>"):
        parse_beats('<beats><beat><item id="a"></item></beat></beats>')


@manim
def test_draw_paints_in_order_and_z_lifts():
    from konvey.stage.displays.draw.mobject import DrawBlock

    d = DrawBlock(leaf('<draw id="x"><rect id="disk" x="2" y="1" w="2" h="0.5" z="1"/>'
                       '<line id="peg" from="2,0" to="2,3"/><circle id="c" x="5" y="2" r="0.5"/></draw>'))
    order = [next(i for i, it in d.items.items() if it is m) for m in d.submobjects[1:]]
    assert order == ["peg", "c", "disk"]            # z=1 last, the rest in document order
    # each shape is its own shader batch, so a line never paints over a fill drawn after it
    ids = [m.uniforms["anti_alias_width"] for m in d.submobjects[1:]]
    assert len(set(ids)) == 3


@manim
def test_draw_arc_marks_an_angle_and_cells_typeset_latex():
    from manimlib import Tex

    from konvey.stage.displays.draw.mobject import DrawBlock
    from konvey.stage.displays.grid.mobject import GridBlock

    d = DrawBlock(leaf('<draw id="x" w="4" h="4"><arc id="a" x="0" y="0" r="1" from="0" to="90" label="90°"/>'
                       '<arc id="w" x="2" y="2" r="1" from="180" to="270" fill="0.4"/></draw>'))
    rim = d.items["a"][0].get_points()
    assert np.allclose(np.linalg.norm(rim[:, :2] - [-2, -2], axis=1), 1, atol=1e-3)   # canvas 0,0 -> -2,-2
    assert d.items["w"][0].get_fill_opacity() == pytest.approx(0.4)
    with pytest.raises(BeatError, match="two different angles"):
        DrawBlock(leaf('<draw id="x"><arc id="a" x="0" y="0" r="1" from="30" to="30"/></draw>'))
    g = GridBlock(leaf('<grid id="x" rows="1" cols="2" values="\\cos\\theta,1"></grid>'))
    assert isinstance(g.cells[0][1], Tex) and not isinstance(g.cells[1][1], Tex)


@manim
def test_fading_solid_draws_after_opaque_ones():
    from konvey.stage.field import FieldWorld

    beats = parse_beats('<beats><beat><world><solid id="a" shape="box"></solid>'
                        '<solid id="b" shape="box" size="1"></solid></world></beat></beats>')
    fw = FieldWorld(beats)
    s = fw.state_from(beats[0].world, None)
    s["a"] = {**s["a"], "show": 0.5}          # a fading in
    fw.apply(s)
    assert fw.group.submobjects.index(fw.mobs["a"]) > fw.group.submobjects.index(fw.mobs["b"])


def test_plan_beats_with_only_readouts_are_rejected():
    from konvey.schemas import ScenePlan
    from konvey.validators import ValidationError, check_plan_pictures

    def plan(kinds_per_beat):
        scene = lambda sid, kpb: {  # noqa: E731
            "id": sid, "purpose": "hook", "duration_sec": 10, "vo_script": ["x"],
            "beats": [{"vo_line": f"b{i}", "objects": [{"id": f"o{i}{k}", "kind": k} for k in ks]}
                      for i, ks in enumerate(kpb)]}
        ok = [["bars"]]
        return ScenePlan.model_validate({"title": "t", "scenes": [scene("S1", kinds_per_beat),
                                                                 scene("S2", ok), scene("S3", ok)]})
    check_plan_pictures(plan([["number"], ["bars", "number"], ["bars"]]))
    with pytest.raises(ValidationError, match=r"beats \[0, 1\] show only"):
        check_plan_pictures(plan([["number", "tex"], ["number"], ["bars"]]))


def test_hull_points_repeat_shorthand_and_cut_off_beats_message():
    from konvey.pipeline import extract_beats
    from konvey.stage.parse import Node
    from konvey.stage.displays.tex import bare_tex_words as _bare_tex_words
    from konvey.validators import ValidationError

    if HAS_MANIM:
        from konvey.stage.solids import hull_points

        pts = hull_points(Node("solid", {"id": "c", "points": "0,0,0*3; 1,0,0; 0,1,0; 0,0,1"}))
        assert len(pts) == 6 and (pts[:3] == 0).all()
    with pytest.raises(ValidationError, match="cut off before </beats>"):
        extract_beats("<beats><beat vo='x'>")
    assert _bare_tex_words(r"\begin{pmatrix} 0 & 1 \end{pmatrix}") == []


@manim
def test_list_values_may_hold_commas_when_split_by_bars():
    from konvey.stage.match import fmt_list, same_values, split_list
    from konvey.stage.overlay import build_leaf

    planned = ["T1", "committed, kept", "T2", "loser"]
    assert fmt_list(planned) == "T1|committed, kept|T2|loser"
    assert same_values(planned, fmt_list(planned))
    assert split_list("1,0;0,1", rows=True) == ["1", "0", "0", "1"]
    assert split_list("a|b, c;d|e", rows=True) == ["a", "b, c", "d", "e"]
    grid = build_leaf(leaf('<grid id="x" rows="2" cols="2" values="T1|committed, kept|T2|loser"></grid>'), None)
    assert grid is not None


@manim
def test_cells_widen_for_long_values_and_tex_spacing_keeps_semicolons():
    from konvey.stage.displays.tex import tex_safe
    from konvey.stage.overlay import build_leaf

    short = build_leaf(leaf('<array id="x" values="3,8,1"></array>'), None)
    long_ = build_leaf(leaf('<array id="x" values="1 T1 A 100->70,3 T1 commit"></array>'), None)
    assert long_.cells[0][0].get_width() > 2 * short.cells[0][0].get_width()
    assert long_.cells[0][1].get_width() > long_.cells[0][0].get_width() * 0.6   # text kept near its size
    grid = build_leaf(leaf('<grid id="x" rows="2" cols="2" values="T1|committed, kept|T2|undone"></grid>'), None)
    assert grid.cells[1][0].get_width() > grid.cells[0][0].get_width()          # only the long column widens
    assert "mskip 5mu" in tex_safe(r"a \; b") and "\\\\" not in tex_safe(r"a \; b")
    assert tex_safe("a; b") == "a; b"


@manim
def test_ring_wires_every_peer_and_no_wire_runs_through_a_box():
    from manimlib import DL, UR
    from konvey.stage.overlay import build_leaf

    ring = build_leaf(leaf('<system id="x" parts="client,S1|S2|S3|S4|S5" layout="ring" '
                           'holds="S3:term 2|leader"></system>'), None)
    peers = ["S1", "S2", "S3", "S4", "S5"]
    for i, a in enumerate(peers):
        for b in peers[i + 1:]:
            assert len(ring.route(a, b)[1]) == 1           # peers talk directly
    assert len(ring.route("client", "S3")[1]) == 1         # the client too, round the ring if need be
    for link, wire in ring.wire_mob.items():
        for p, box in ring.box_of.items():
            if p in link:
                continue
            (x0, y0, _), (x1, y1, _) = box.get_corner(DL), box.get_corner(UR)
            assert not any(x0 < q[0] < x1 and y0 < q[1] < y1 for q in wire.get_anchors()), (link, p)
    with pytest.raises(BeatError):
        build_leaf(leaf('<system id="x" parts="a,b" layout="ring"></system>'), None)


@manim
def test_infinity_is_drawn_as_the_symbol():
    from konvey.stage.displays.base import _label

    assert _label("INF", 30, "#ffffff").text == "∞" and _label("-inf", 30, "#ffffff").text == "-∞"
