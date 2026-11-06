"""Static/runtime checks for a run, and the MCP beat rules."""

from __future__ import annotations

from konvey.mcp import check, runs

GOOD = """<beats>
<beat vo="One clear line." shot="title"><h1 id="t">One</h1></beat>
<beat vo="A second clear line." shot="title"><h1 id="t">Two</h1></beat>
<beat vo="A third clear line." shot="title"><h1 id="t">Three</h1></beat>
</beats>"""


def _run(tmp_path, scenes=3, theme="editorial"):
    run = runs.new_run("Check test", workspace=tmp_path, scenes=scenes, theme=theme)
    for sid in run.scene_ids():
        run.scene_path(sid).write_text(GOOD)
    return run


def test_a_good_scene_passes_static_checks(tmp_path):
    run = _run(tmp_path)
    result = check.check_static_run(run)
    assert result["ok"] is True
    assert result["problems"] == 0
    assert result["checked_runtime"] is False
    for scene in result["scenes"].values():
        assert scene["static"] == [] and scene["errors"] == []


def test_a_beat_without_vo_is_an_error(tmp_path):
    run = _run(tmp_path)
    run.scene_path("S2").write_text(GOOD.replace('vo="One clear line."', ""))
    result = check.check_static_run(run, ["S2"])
    assert result["ok"] is False
    assert any("needs a vo line" in e for e in result["scenes"]["S2"]["errors"])


def test_hex_colour_and_small_text_are_static_problems(tmp_path):
    run = _run(tmp_path)
    run.scene_path("S1").write_text(GOOD.replace('id="t"', 'id="t" color="#ff0000" size="10"'))
    result = check.check_static_run(run, ["S1"])
    assert result["ok"] is False
    problems = "\n".join(result["scenes"]["S1"]["static"])
    assert "use a theme colour name" in problems
    assert "too small to read" in problems


def test_placeholders_are_errors(tmp_path):
    run = _run(tmp_path)
    run.scene_path("S1").write_text(GOOD.replace("One", "TODO"))
    result = check.check_static_run(run, ["S1"])
    assert result["ok"] is False
    assert any("placeholder" in e for e in result["scenes"]["S1"]["errors"])


def test_a_two_scene_run_closes_the_letterbox_on_its_own_last_scene(tmp_path):
    run = _run(tmp_path, scenes=2, theme="classic")
    run.scene_path("S2").write_text(
        '<beats><beat vo="A."><h1 id="t">A</h1></beat>'
        '<beat vo="B." letterbox="close"><h1 id="t">B</h1></beat></beats>')
    result = check.check_static_run(run, ["S2"])
    assert not any('last beat of S3' in p for p in result["scenes"]["S2"]["static"])
    assert result["scenes"]["S2"]["errors"] == []


def test_a_two_scene_run_rejects_an_early_letterbox_close(tmp_path):
    run = _run(tmp_path, scenes=2, theme="classic")
    run.scene_path("S1").write_text(
        '<beats><beat vo="Open." letterbox="open"><h1 id="t">A</h1></beat>'
        '<beat vo="Close." letterbox="close"><h1 id="t">B</h1></beat></beats>')
    result = check.check_static_run(run, ["S1"])
    assert any('last beat of S2' in e for e in result["scenes"]["S1"]["errors"])


def test_runtime_checks_each_scene_with_the_previous_scene_as_prelude(monkeypatch, tmp_path):
    run = _run(tmp_path)
    seen = {}

    def fake_runtime(html, workdir, sid, timeout=300.0, prelude_html=None):
        seen[sid] = prelude_html
        return ["boom"] if sid == "S2" else []

    monkeypatch.setattr(check, "check_runtime", fake_runtime)
    result = check.check_runtime_run(run)
    assert result["ok"] is False
    assert result["scenes"]["S2"]["problems"] == ["boom"]
    assert seen["S1"] is None
    assert seen["S2"] == run.read_scene("S1")
    assert seen["S3"] == run.read_scene("S2")


def test_check_run_can_stop_after_the_static_layer(tmp_path):
    run = _run(tmp_path)
    result = check.check_run(run, runtime=False)
    assert result["ok"] is True
    assert result["runtime"] is None
    assert result["checked_runtime"] is False
