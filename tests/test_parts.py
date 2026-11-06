"""Parts by name (konvey.stage.parts), shots (konvey.stage.shots) and the 2D camera (view)."""

import importlib.util

import numpy as np
import pytest

from konvey.stage.parse import BeatError, parse_beats

HAS_MANIM = importlib.util.find_spec("manimlib") is not None
manim = pytest.mark.skipif(not HAS_MANIM, reason="needs manimgl (uv --group render)")


def build(html: str, i: str = "x"):
    from konvey.stage.overlay import build_leaf
    from konvey.stage.theme import use

    use("editorial", "")
    beat = parse_beats(f"<beats><beat>{html}</beat></beats>")[0]
    _BUILT[html] = mob = build_leaf(beat.leaves()[i], None)
    return mob


_BUILT: dict = {}


def part(html: str, name: str):
    """The part of the block built from ``html`` (the same block as ``build(html)`` returned)."""
    from konvey.stage.attach import resolve

    return resolve(f"x>{name}", {"x": _BUILT.get(html) or build(html)}, "test")


# --- parts ---------------------------------------------------------------------------
@manim
def test_array_parts_by_index_run_and_value():
    html = '<array id="x" values="4,8,15,16"></array>'
    a = build(html)
    assert part(html, "2") is a.cells[2]
    assert len(part(html, "1-3")) == 3
    assert part(html, "16") is a.cells[3]
    with pytest.raises(BeatError, match="has no part"):
        part(html, "9")


@manim
def test_grid_parts_cell_row_col_and_heading():
    html = '<grid id="x" rows="2" cols="3" values="1,2,3;4,5,6" row-labels="top,bottom" col-labels="a,b,c"></grid>'
    g = build(html)
    assert part(html, "1,2") is g.cells[5]
    assert len(part(html, "row 1")) == 3 and len(part(html, "col 0")) == 2
    assert part(html, "bottom")[0] is g.cells[3]
    assert part(html, "c")[1] is g.cells[5]
    with pytest.raises(BeatError):
        part(html, "2,0")


@manim
def test_graph_parts_node_and_edge_either_way():
    html = '<graph id="x" nodes="A:0,0;B:2,0;C:1,1" edges="A-B:3;B>C"></graph>'
    g = build(html)
    assert part(html, "B") is g.nodes[1]
    assert part(html, "B-A") is g.edges[0]
    assert part(html, "B>C") is g.edges[1]
    with pytest.raises(BeatError):
        part(html, "C>B")   # one-way edge named backwards


@manim
def test_bars_tex_text_and_plot_parts():
    assert part('<bars id="x" labels="mon,tue" values="3,5"></bars>', "tue") is not None
    t = part('<tex id="x">a^2 + b^2 = c^2</tex>', "c^2")
    assert len(t.family_members_with_points()) == 2
    w = part('<text id="x">the hidden middle part</text>', "middle part")
    assert len(w) == 2
    html = '<plot id="x" fn="f: x^2; g: x" x="-2,2" y="0,4"></plot>'
    p = build(html)
    from konvey.stage.displays.plot.mobject import Frame

    fr = Frame.of(p)
    assert np.allclose(part(html, "x=1").get_center(), fr.p(1, 1))
    assert np.allclose(part(html, "x=1.5 on g").get_center(), fr.p(1.5, 1.5))
    assert part(html, "g") is p.lines[1]
    with pytest.raises(BeatError):
        part(html, "x=1 on h")


@manim
def test_places_and_draw_parts():
    html = '<places id="x" parts="client,server" holds="server:req"></places>'
    assert part(html, "server") is not None
    assert part('<draw id="x"><rect id="r" x="1" y="1" w="1" h="1"></rect></draw>', "r") is not None


# --- shots ---------------------------------------------------------------------------
def _shape(nodes, depth=0):
    out = []
    for n in nodes:
        out.append(("  " * depth) + (n.id or n.tag))
        out += _shape(n.children, depth + 1) if n.tag in ("div", "section") else []
    return out


def test_derive_shot_puts_picture_left_words_right():
    b = parse_beats('<beats><beat shot="derive" caption="none"><tex id="eq">x</tex>'
                    '<bars id="b" labels="a" values="1"></bars><text id="t">why</text>'
                    '<ring id="r" of="b"></ring></beat></beats>')[0]
    left, right = b.overlay[0].children
    assert [c.children[0].id for c in left.children] == ["b"]
    assert [c.id for c in right.children] == ["eq", "t"]
    assert b.overlay[-1].id == "r"   # marks stay on their parts, outside the composition


def test_a_compare_shot_with_one_picture_lays_out_like_full():
    one = parse_beats('<beats><beat shot="compare"><bars id="b" labels="a" values="1"></bars>'
                      '<text id="t">a note</text></beat></beats>')[0]
    full = parse_beats('<beats><beat shot="full"><bars id="b" labels="a" values="1"></bars>'
                       '<text id="t">a note</text></beat></beats>')[0]
    assert [c.attrs.get("class") for c in one.overlay[0].children] == [c.attrs.get("class") for c in full.overlay[0].children]
    assert set(one.leaves()) == set(full.leaves())


def test_shot_errors_name_the_fix():
    with pytest.raises(BeatError, match='shot="title"'):
        parse_beats('<beats><beat shot="full"><text id="t">only words</text></beat></beats>')
    with pytest.raises(BeatError, match="use one of"):
        parse_beats('<beats><beat shot="wide"><text id="t">x</text></beat></beats>')
    with pytest.raises(BeatError, match="question"):
        parse_beats('<beats><beat shot="question"><bars id="b" labels="a" values="1"></bars></beat></beats>')


def test_shot_with_world_gives_it_the_view_box():
    b = parse_beats('<beats><beat shot="derive" caption="none"><tex id="eq">x</tex>'
                    '<world><sphere id="s" r="1"></sphere></world></beat></beats>')[0]
    assert "view" in "".join(_shape(b.overlay))


def test_shot_flattens_written_containers():
    b = parse_beats('<beats><beat shot="full" caption="none"><div class="row"><div>'
                    '<bars id="b" labels="a" values="1"></bars></div></div></beat></beats>')[0]
    assert [x.strip() for x in _shape(b.overlay)] == ["div", "div", "b"]


# --- camera --------------------------------------------------------------------------
def test_page_size_bounds():
    from konvey.stage.view import page_size

    assert page_size({}) == (1.0, 1.0) and page_size({"page": "2,1"}) == (2.0, 1.0)
    for bad in ("0.5,1", "5,1", "wide"):
        with pytest.raises(BeatError):
            page_size({"page": bad})


@manim
def test_camera_frames_part_with_its_attachments_clear_of_bars():
    from manimlib import FRAME_HEIGHT

    from konvey.stage import view

    beat = parse_beats('<beats><beat view="x>1" caption="none"><array id="x" values="1,2,3"></array>'
                       '<text id="n" of="x>1">note</text></beat></beats>')[0]
    nodes = beat.leaves()
    mobs = {"x": build('<array id="x" values="1,2,3"></array>'), "n": build('<text id="x">note</text>')}
    mobs["n"].next_to(mobs["x"].cells[1], np.array([0, 1, 0]))
    (x0, y0, x1, y1), region = view.framed(beat, nodes, mobs)
    assert not region and y1 >= mobs["n"].get_top()[1] - 1e-6   # the note is in the frame
    c, z = view.camera(beat, nodes, mobs, bars=0.55)
    assert (y1 - y0) * z <= FRAME_HEIGHT - 1.1 + 1e-6
    beat.attrs["view"] = "nowhere"
    with pytest.raises(BeatError, match="names no element"):
        view.camera(beat, nodes, mobs)


@manim
def test_focus_dims_all_but_the_named_part():
    from konvey.stage import view

    beat = parse_beats('<beats><beat focus="x>2" caption="none"><array id="x" values="1,2,3"></array>'
                       '<text id="t">other</text></beat></beats>')[0]
    mobs = {"x": build('<array id="x" values="1,2,3"></array>'), "t": build('<text id="x">other</text>')}

    def alpha(m):
        return max(float(sm.data["fill_rgba"][:, 3].max()) for sm in m.get_family()
                   if sm.has_points() and len(sm.data["fill_rgba"]))
    before = alpha(mobs["x"].cells[2])
    view.apply_focus(beat.attrs, beat.leaves(), mobs, 0)
    assert alpha(mobs["x"].cells[2]) == pytest.approx(before)
    assert alpha(mobs["t"]) < 0.5 and alpha(mobs["x"].cells[0]) < 0.5


@manim
def test_focus_keeps_a_formula_built_from_the_focused_part():
    from konvey.stage import view

    beat = parse_beats('<beats><beat focus="x>1" caption="none"><array id="x" values="1,2,3"></array>'
                       '<tex id="e" from="2: x>1">2 + 0</tex><text id="t">other</text></beat></beats>')[0]
    mobs = {"x": build('<array id="x" values="1,2,3"></array>'), "e": build('<tex id="x">2 + 0</tex>'),
            "t": build('<text id="x">other</text>')}
    view.apply_focus(beat.attrs, beat.leaves(), mobs, 0)
    lit = lambda m: max(float(sm.data["fill_rgba"][:, 3].max()) for sm in m.get_family()  # noqa: E731
                        if sm.has_points() and len(sm.data["fill_rgba"]))
    assert lit(mobs["e"]) > 0.9 and lit(mobs["t"]) < 0.5


@manim
def test_explicit_zoom_never_cuts_the_framed_part_off():
    from konvey.stage import view

    beat = parse_beats('<beats><beat view="x" zoom="4" caption="none"><array id="x" values="1,2,3,4,5,6"></array>'
                       '</beat></beats>')[0]
    mobs = {"x": build('<array id="x" values="1,2,3,4,5,6"></array>')}
    _, z = view.camera(beat, beat.leaves(), mobs)
    from manimlib import FRAME_WIDTH
    assert mobs["x"].get_width() * z <= FRAME_WIDTH


@manim
def test_brace_on_a_point_says_what_to_use():
    from konvey.stage.attach import place

    beat = parse_beats('<beats><beat caption="none"><plot id="p" fn="f: x" x="0,2" y="0,2"></plot>'
                       '<brace id="b" of="p>x=1"></brace></beat></beats>')[0]
    mobs = {"p": build('<plot id="x" fn="f: x" x="0,2" y="0,2"></plot>'), "b": build('<brace id="x" of="p>x=1"></brace>')}
    with pytest.raises(BeatError, match="is a point"):
        place(beat.leaves(), mobs)


def test_inline_operator_stays_between_the_pictures():
    b = parse_beats('<beats><beat shot="derive" caption="none"><grid id="m" rows="1" cols="1" values="2"></grid>'
                    '<tex id="op" inline>\\times</tex><vector id="v" values="1"></vector>'
                    '<tex id="eq">2</tex></beat></beats>')[0]
    left, right = b.overlay[0].children
    assert [w.children[0].id for w in left.children] == ["m", "op", "v"]
    assert [n.id for n in right.children] == ["eq"]
    assert "formula" in left.attrs["class"]           # one formula: packed, grown as one
    assert {w.children[0].attrs.get("_grow") for w in left.children if w.children[0].id != "op"} == {"1"}


@manim
def test_grid_matrix_look_has_brackets_and_no_boxes():
    g = build('<grid id="x" look="matrix" rows="2" cols="2" values="1,2;3,4" highlight-rows="0"></grid>')
    assert len(g.brackets) == 2
    assert float(g.cells[3][0].data["stroke_rgba"][:, 3].max()) == 0   # unlit cell: no box
    assert float(g.cells[0][0].data["stroke_rgba"][:, 3].max()) > 0    # lit row keeps its frame


@manim
def test_zoom_hides_a_neighbour_the_frame_would_cut():
    from konvey.stage import view

    beat = parse_beats('<beats><beat view="x" caption="none"><array id="x" values="1"></array>'
                       '<text id="t">neighbour</text></beat></beats>')[0]
    mobs = {"x": build('<array id="x" values="1"></array>'), "t": build('<text id="x">neighbour</text>')}
    mobs["t"].move_to(mobs["x"].get_right() + np.array([mobs["t"].get_width() / 2 + 0.3, 0, 0]))
    nodes = beat.leaves()
    c, z = view.camera(beat, nodes, mobs)
    view.apply_camera(beat.attrs, nodes, mobs, c, z)
    view.hide_cut(beat, nodes, mobs)
    alpha = lambda m: max(float(sm.data["fill_rgba"][:, 3].max()) for sm in m.get_family()  # noqa: E731
                          if sm.has_points() and len(sm.data["fill_rgba"]))
    assert alpha(mobs["t"]) == 0 and alpha(mobs["x"].cells[0]) > 0


@manim
def test_matrix_look_is_spaced_like_a_vector():
    g = build('<grid id="x" look="matrix" rows="2" cols="1" values="1;2"></grid>')
    v = build('<vector id="x" values="1,2"></vector>')
    assert abs(g.brackets.get_height() - v.brackets.get_height()) < 0.02


@manim
def test_plot_labels_the_corner_where_axes_meet_once():
    p = build('<plot id="x" fn="f: x^2" x="-2,2" y="0,4"></plot>')
    zeros = [(axis, v) for axis, v, _, lab in p.ticks if abs(v) < 1e-9]
    assert zeros == [("x", 0.0)]


@manim
def test_ring_is_a_circle_around_a_point_and_a_box_around_a_row():
    from konvey.stage.attach import place
    from manimlib import Circle

    for of, circle in (("x>1", True), ("x>0-3", False)):
        beat = parse_beats(f'<beats><beat><array id="x" values="1,2,3,4"></array><ring id="r" of="{of}"></ring>'
                           '</beat></beats>')[0]
        mobs = {"x": build('<array id="x" values="1,2,3,4"></array>'), "r": build(f'<ring id="x" of="{of}"></ring>')}
        place(beat.leaves(), mobs)
        assert isinstance(mobs["r"][0], Circle) == circle


@manim
def test_chart_series_and_plane_vector_tip():
    c = build('<chart id="x" series="up:1,2,3;down:3,2,1"></chart>')
    assert part('<chart id="x" series="up:1,2,3;down:3,2,1"></chart>', "down") is c.lines[1]
    html = '<plane id="x" vectors="v:1,0; w:0,1" matrix="2,0;0,1" x="-3,3" y="-3,3"></plane>'
    p = build(html)
    v, w = part(html, "v").get_center(), part(html, "w").get_center()
    k = p.view.get_width() / 6
    c = p.view.get_center()
    assert np.allclose(v[:2], c[:2] + [2 * k, 0]) and np.allclose(w[:2], c[:2] + [0, k])


@manim
def test_formula_symbol_means_its_first_occurrence():
    html = '<tex id="x">1 + 15 = 16</tex>'
    t = build(html)
    first = part(html, "1")
    assert len(first.family_members_with_points()) == 1 and first.get_center()[0] < t.get_center()[0] - 0.5
    assert part(html, "1#2").get_center()[0] > first.get_center()[0]
    with pytest.raises(BeatError):
        part(html, "1#9")


def _placed(html: str):
    from konvey.stage.attach import place
    from konvey.stage.overlay import build_leaf
    from konvey.stage.theme import use

    use("editorial", "")
    beat = parse_beats(f"<beats><beat>{html}</beat></beats>")[0]
    nodes = beat.leaves()
    mobs = {i: build_leaf(n, None) for i, n in nodes.items()}
    place(nodes, mobs)
    return mobs


@manim
def test_brace_steps_past_the_index_numbers():
    mobs = _placed('<array id="a" values="1,2,3"></array><brace id="b" of="a>0-2"></brace>')
    assert mobs["b"][0].get_top()[1] < mobs["a"].index.get_bottom()[1] + 1e-6


@manim
def test_arrow_bends_over_the_cells_between():
    from manimlib import normalize

    mobs = _placed('<array id="a" values="1,2,3,4"></array><arrow id="r" from="a>0" to="a>3"></arrow>')
    arrow, cells = mobs["r"][0], mobs["a"].cells
    above = arrow.get_bottom()[1] >= cells[1].get_top()[1] - 0.15   # over the cells between
    below = arrow.get_top()[1] <= cells[1].get_bottom()[1] + 0.15
    assert above or below
