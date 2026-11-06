"""Render orchestration: wrappers, parallel calls, concat, target copy, artifacts."""

from __future__ import annotations

import pytest

from konvey import render as engine
from konvey.mcp import render, runs

HTML = """<beats>
<beat vo="One." shot="title"><h1 id="t">One</h1></beat>
</beats>"""


def _run(tmp_path, scenes=2):
    run = runs.new_run("Render test", workspace=tmp_path, scenes=scenes)
    for sid in run.scene_ids():
        run.scene_path(sid).write_text(HTML)
    return run


def _fake_engine(monkeypatch):
    calls = []

    def fake_render(out_dir, sid, preview, fps):
        calls.append({"out_dir": out_dir, "sid": sid, "preview": preview, "fps": fps})
        video = out_dir / "video" / f"{sid}.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(f"{sid}:{preview}:{fps}".encode())
        return video

    def fake_concat(out_dir, parts):
        joined = out_dir / "video.mp4"
        joined.write_bytes(b"joined:" + b",".join(p.name.encode() for p in parts))
        return joined

    monkeypatch.setattr(render, "_render_scene", fake_render)
    monkeypatch.setattr(engine, "concat", fake_concat)
    return calls


def test_render_run_writes_the_video_and_marks_the_run_done(monkeypatch, tmp_path):
    run = _run(tmp_path)
    calls = _fake_engine(monkeypatch)
    result = render.render_run(run)
    assert result["ok"] is True
    assert result["scenes"] == ["S1", "S2"]
    assert result["video"] == str(run.directory / "video.mp4")
    assert (run.directory / "video.mp4").is_file()
    assert (run.engine_dir() / "agent3-S1.py").is_file()
    assert (run.engine_dir() / "agent3-S2.py").is_file()
    assert 'default_camera_config = {"fps": 24}' in (run.engine_dir() / "agent3-S1.py").read_text()
    assert {c["sid"] for c in calls} == {"S1", "S2"}
    assert all(c["preview"] is False for c in calls)
    assert all(c["fps"] == 24 for c in calls)
    assert result["fps"] == 24
    fresh = runs.Run.from_dir(run.directory)
    assert fresh.data["status"] == "done"
    assert fresh.data["artifacts"]["video"] == str(run.directory / "video.mp4")
    assert fresh.data["artifacts"]["render_scenes"] == ["S1", "S2"]
    assert fresh.data["artifacts"]["fps"] == 24


def test_a_custom_fps_is_passed_to_every_scene(monkeypatch, tmp_path):
    run = _run(tmp_path)
    calls = _fake_engine(monkeypatch)
    result = render.render_run(run, fps=30)
    assert result["fps"] == 30
    assert all(c["fps"] == 30 for c in calls)


def test_an_invalid_fps_is_rejected(tmp_path):
    run = _run(tmp_path)
    for bad in (5, 61, "fast"):
        with pytest.raises(ValueError):
            render.render_run(run, fps=bad)


def test_a_preview_render_produces_video_preview_and_keeps_the_status(monkeypatch, tmp_path):
    run = _run(tmp_path)
    calls = _fake_engine(monkeypatch)
    result = render.render_run(run, preview=True)
    assert result["preview"] is True
    assert (run.directory / "video-preview.mp4").is_file()
    assert all(c["preview"] is True for c in calls)
    fresh = runs.Run.from_dir(run.directory)
    assert fresh.data["status"] == "previewed"
    assert fresh.data["artifacts"]["video_preview"] == str(run.directory / "video-preview.mp4")


def test_a_subset_render_only_joins_those_scenes(monkeypatch, tmp_path):
    run = _run(tmp_path, scenes=3)
    calls = _fake_engine(monkeypatch)
    result = render.render_run(run, ["S2"])
    assert result["scenes"] == ["S2"]
    assert [c["sid"] for c in calls] == ["S2"]
    assert runs.Run.from_dir(run.directory).data["status"] == "rendered-partial"


def test_no_scene_selection_is_rejected(tmp_path):
    run = _run(tmp_path)
    with pytest.raises(ValueError):
        render.render_run(run, [])
    with pytest.raises(ValueError):
        render.render_run(run, ["S9"])
