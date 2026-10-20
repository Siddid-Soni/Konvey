"""konvey.stage: beat parsing, static grounding checks, Chromium layout, runtime check."""

import importlib.util
import re
from pathlib import Path

import pytest

from konvey.pipeline import extract_beats
from konvey.schemas import Scene
from konvey.stage.check import check_runtime, check_static
from konvey.stage.parse import BeatError, parse_beats

REPO = Path(__file__).resolve().parent.parent
HAS_MANIM = importlib.util.find_spec("manimlib") is not None
HAS_CHROMIUM = importlib.util.find_spec("playwright") is not None and Path("/usr/bin/chromium").exists()

SCENE = Scene.model_validate({
    "id": "S2", "purpose": "build", "duration_sec": 20,
    "vo_script": ["Face-on the shadow is a square.", "Corner-on it is a hexagon."],
    "beats": [
        {"vo_line": "Face-on the shadow is a square.",
         "objects": [{"id": "eq", "kind": "tex", "data": {"tex": "A = s^2 = 1"}}],
         "animation": {"type": "Write", "code_hint": "Write(eq)", "run_time": 1}},
        {"vo_line": "Corner-on it is a hexagon.",
         "objects": [{"id": "chart", "kind": "bars", "data": {"labels": ["face", "corner"], "values": [1, 1.73]}}],
         "animation": {"type": "FadeIn", "code_hint": "FadeIn(chart)", "run_time": 1}},
    ],
})

GOOD = """<beats>
<beat vo="Face-on the shadow is a square." style="padding: 0.75u 0.8u">
  <h3 id="title">Shadows</h3><tex id="eq">A = s^2 = 1</tex>
</beat>
<beat vo="Corner-on it is a hexagon." style="padding: 0.75u 0.8u">
  <h3 id="title">Shadows</h3><bars id="chart" labels="face,corner" values="1,1.73"></bars>
</beat>
</beats>"""


def test_parse_no_subtitle_unless_asked_and_ids():
    beats = parse_beats(GOOD)
    assert len(beats) == 2
    leaves = beats[0].leaves()
    assert set(leaves) == {"title", "eq"}        # voiced videos: no subtitle by default
    assert leaves["eq"].segments[0][0] == "A = s^2 = 1"
    asked = parse_beats(GOOD.replace("<beat ", '<beat caption="auto" ', 1))[0].leaves()
    assert asked["cap"].text == "Face-on the shadow is a square."


def test_parse_errors_are_written_for_the_llm():
    with pytest.raises(BeatError, match="unknown tag <span>"):
        parse_beats("<beats><beat><span>x</span></beat></beats>")
    with pytest.raises(BeatError, match="needs an id"):
        parse_beats("<beats><beat><text>x</text></beat></beats>")


def test_check_static_accepts_grounded_beats():
    assert check_static(GOOD, SCENE) == []


def test_check_static_reports_missing_vo_and_data():
    bad = GOOD.replace('vo="Corner-on it is a hexagon."', 'vo="Something else."').replace("s^2 = 1", "s^2")
    problems = check_static(bad, SCENE)
    assert any("plan beat 1: no <beat vo=" in p for p in problems)
    assert any("'eq'" in p and "not drawn verbatim" in p for p in problems)


def test_extract_beats_strips_fences():
    assert extract_beats("```html\n" + GOOD + "\n```").startswith("<beats>")


@pytest.mark.skipif(not HAS_MANIM, reason="needs manimgl (uv --group render)")
def test_plot_fn_is_parsed_not_evaluated():
    from konvey.stage.expr import parse_fn

    assert abs(parse_fn("exp(-x^2/2)/sqrt(2*pi)")(0) - 0.3989) < 1e-3
    with pytest.raises(BeatError):
        parse_fn('__import__("os").system("true")')


@pytest.mark.skipif(not HAS_CHROMIUM, reason="needs playwright + /usr/bin/chromium")
def test_layout_reports_overflow_per_beat_and_id():
    """tex shrinks to at most 70% (6u -> 4.2u), so a 4u card still overflows, by 20px."""
    from konvey.stage import layout

    beats = parse_beats('<beats><beat><div class="row"><div id="card" class="col card" style="width:4u">'
                        '<tex id="f">x</tex></div></div></beat></beats>')
    with pytest.raises(ValueError, match=r"beat 0: #f sticks out of its container \(right by 20px\)"):
        layout.solve(beats, {0: {"f": (6.0, 1.0), "cap": (1.0, 0.3)}})


@pytest.mark.skipif(not HAS_CHROMIUM, reason="needs playwright + /usr/bin/chromium")
def test_layout_shrinks_visual_blocks_that_slightly_overflow():
    from konvey.stage import layout

    beats = parse_beats('<beats><beat><div class="row" style="width:6u; height:3u">'
                        '<chart id="c" series="A:1,2"></chart><h3 id="t">Label</h3></div></beat></beats>')
    sizes = {0: {"c": (5.0, 3.2), "t": (1.5, 0.5), "cap": (1.0, 0.3)}}
    boxes = layout.solve(beats, sizes)               # no error: the chart made room
    w, h = sizes[0]["c"]
    assert w <= 4.5 + 1e-6 and h / w == pytest.approx(3.2 / 5.0)
    assert boxes[0]["t"].w == pytest.approx(1.5)     # text keeps its size


@pytest.mark.skipif(not HAS_CHROMIUM, reason="needs playwright + /usr/bin/chromium")
def test_layout_never_shrinks_text():
    from konvey.stage import layout

    beats = parse_beats('<beats><beat><div class="row" style="width:3u"><text id="t">x</text></div></beat></beats>')
    with pytest.raises(ValueError, match="#t sticks out"):
        layout.solve(beats, {0: {"t": (3.4, 0.5), "cap": (1.0, 0.3)}})


@pytest.fixture
def classic():
    from konvey.stage import theme

    theme.use("classic")
    yield
    theme.use(theme.DEFAULT)


def test_letterbox_only_opens_in_s1_and_closes_in_s3(classic):
    html = GOOD.replace('<beat vo="Face-on', '<beat letterbox="open" vo="Face-on')
    problems = check_static(html, SCENE)  # SCENE is S2
    assert any('letterbox="open" only on the first beat of S1' in p for p in problems)


def test_letterbox_is_ignored_without_bars():
    html = GOOD.replace('<beat vo="Face-on', '<beat letterbox="open" vo="Face-on')
    assert check_static(html, SCENE) == []   # editorial has no letterbox


def test_theme_colour_resolution():
    from konvey.stage.theme import CLASSIC, EDITORIAL, get_theme

    t = EDITORIAL
    assert t.color("accent") == t.accent and t.color("c3") == t.palette[2]
    assert t.color(None) == t.ink and t.color(None, "muted") == t.muted
    assert t.color("#FF5555") in t.palette        # editorial snaps hex onto its palette
    assert CLASSIC.color("#123456") == "#123456"
    assert t.color("red") in t.palette            # nearest warm palette entry, not raw red
    assert t.color("blue") == "#7F96B8"           # slate blue
    assert t.color("white") == t.ink and t.color("grey") == t.muted
    assert CLASSIC.color("blue") == "#3b82f6"
    with pytest.raises(ValueError, match="use one of ink, muted, accent, c1"):
        t.color("chartreuse-ish")
    with pytest.raises(ValueError, match="c1..c5"):
        t.color("c9")
    with pytest.raises(ValueError, match="available: editorial, classic"):
        get_theme("neon")


def test_hex_colour_is_flagged_with_theme_names():
    html = GOOD.replace('<tex id="eq">', '<tex id="eq" color="#ff0000">')
    assert any("use a theme colour name (ink, muted, accent, c1" in p for p in check_static(html, SCENE))


def test_wrapper_records_theme_and_render_can_swap_it(tmp_path, classic):
    from konvey.render import set_theme
    from konvey.stage.check import wrapper_source

    py = tmp_path / "agent3-S2.py"
    py.write_text(wrapper_source(tmp_path / "agent3-S2.html"))
    assert "theme = 'classic'" in py.read_text()
    set_theme(py, "editorial")
    src = py.read_text()
    assert "theme = 'editorial'" in src and "classic" not in src and "agent3-S1.html" in src


def test_text_below_min_size_is_rejected():
    html = GOOD.replace('<h3 id="title">', '<h3 id="title" size="18">', 1)
    assert any("too small to read" in p for p in check_static(html, SCENE))


def test_plan_rejects_long_vo_lines():
    import json

    from konvey.validators import ValidationError, validate_scene_plan

    plan = json.loads((REPO / "tests/fixtures/examples/example-06-shadows-cube-average/agent2-output.json").read_text())
    long_line = " ".join(["word"] * 25)
    plan["scenes"][0]["vo_script"][0] = long_line
    plan["scenes"][0]["beats"][0]["vo_line"] = long_line
    with pytest.raises(ValidationError, match="25 words"):
        validate_scene_plan(plan)


@pytest.mark.skipif(not HAS_MANIM, reason="needs manimgl (uv --group render)")
def test_previous_scene_actors_adopt_this_scenes_ids():
    from konvey.stage.scene import _adopt_ids

    prev = parse_beats('<beats><beat><world><surface id="valley" fn="x^2"></surface>'
                       '<point id="hiker" on="valley" at="4,0"></point></world>'
                       '<value id="v" bind="hiker.slope" label="slope"></value></beat></beats>')[0]
    first = parse_beats('<beats><beat><world><surface id="bowl" fn="x^2+y^2"></surface>'
                        '<point id="ball" on="bowl" at="4,0"></point></world></beat></beats>')[0]
    _adopt_ids(prev, first)
    assert set(prev.world) == {"bowl", "ball"}
    assert prev.world["ball"].attrs["on"] == "bowl"
    assert prev.leaves()["v"].attrs["bind"] == "ball.slope"


@pytest.mark.skipif(not HAS_MANIM, reason="needs manimgl (uv --group render)")
def test_previous_scene_hulls_adopt_only_ids_with_as_many_corners():
    from konvey.stage.scene import _adopt_ids

    cube = "0,0,0*3; 1,0,0*3; 0,1,0*3; 1,1,0*3; 0,0,1*3; 1,0,1*3; 0,1,1*3; 1,1,1*3"
    prev = parse_beats(f'<beats><beat><world><solid id="body" shape="hull" points="{cube}"></solid>'
                       '</world></beat></beats>')[0]
    first = parse_beats('<beats><beat><world><solid id="piece" shape="hull" points="0,0,0; 1,0,0; 0,1,0; 0,0,1">'
                        f'</solid><solid id="cube" shape="hull" points="{cube}"></solid></world></beat></beats>')[0]
    _adopt_ids(prev, first)
    assert set(prev.world) == {"cube"}


@pytest.mark.skipif(not HAS_MANIM, reason="needs manimgl (uv --group render)")
def test_previous_scene_points_end_where_the_scene_left_them():
    """S2 opens on S1's last frame; a point placed (or descended) earlier must be there."""
    from konvey.stage.scene import _settle_points

    beats = parse_beats('<beats><beat><world><surface id="s" fn="x^2" x="-6,6" y="-3,3"></surface>'
                        '<point id="p" on="s" at="5,0" descend="0.1" steps="2"></point></world></beat>'
                        '<beat><world><surface id="s" fn="x^2" x="-6,6" y="-3,3"></surface>'
                        '<point id="p" on="s"></point></world></beat></beats>')
    _settle_points(beats)
    x, y = (float(v) for v in beats[-1].world["p"].attrs["at"].split(","))
    assert abs(x - 3.2) < 1e-6 and y == 0   # 5 -> 4 -> 3.2 with lr 0.1 on x^2


@pytest.mark.skipif(not HAS_MANIM, reason="needs manimgl (uv --group render)")
def test_slope_readout_is_exact():
    from konvey.stage.field import FieldWorld

    b = parse_beats('<beats><beat><world><surface id="s" fn="x^2" x="-6,6" y="-3,3"></surface>'
                    '<point id="p" on="s" at="5,0"></point></world></beat></beats>')
    fw = FieldWorld(b)
    fw.apply(fw.state_from(b[0].world, None))
    assert abs(fw.values["p.slope"] - 10) < 1e-6 and fw.values["p.f"] == 25
