"""The MCP tool wrappers: setup, static checks, job handoff, protocol registration."""

from __future__ import annotations

import asyncio
import json

import pytest

pytest.importorskip("mcp")

from konvey.mcp import runs, server  # noqa: E402

GOOD = """<beats>
<beat vo="One clear line." shot="title"><h1 id="t">One</h1></beat>
<beat vo="A second clear line." shot="title"><h1 id="t">Two</h1></beat>
<beat vo="A third clear line." shot="title"><h1 id="t">Three</h1></beat>
</beats>"""


def _new(tmp_path, scenes=3):
    result = server.konvey_new_run("Server test", workspace=str(tmp_path), scenes=scenes)
    assert result["ok"] is True
    run = runs.load_run(result["run_id"], workspace=tmp_path)
    for sid in run.scene_ids():
        run.scene_path(sid).write_text(GOOD)
    return result["run_id"], run


def test_all_ten_tools_are_registered():
    tools = asyncio.run(server.mcp.list_tools())
    names = {tool.name for tool in tools}
    assert names == {
        "konvey_new_run", "konvey_guide", "konvey_displays", "konvey_example",
        "konvey_simulate", "konvey_check", "konvey_preview", "konvey_render",
        "konvey_status", "konvey_cancel",
    }


def test_new_run_reports_paths_and_the_render_stack(tmp_path):
    result = server.konvey_new_run("A topic", workspace=str(tmp_path), duration=45)
    assert result["ok"] is True
    assert result["duration_sec"] == 45
    assert [s["id"] for s in result["scenes"]] == ["S1", "S2", "S3"]
    assert all("file" in s for s in result["scenes"])
    assert set(result["render_stack"]) >= {"manimgl", "chromium", "ffmpeg", "latex"}


def test_new_run_rejects_bad_options(tmp_path):
    result = server.konvey_new_run("", workspace=str(tmp_path))
    assert result["ok"] is False
    result = server.konvey_new_run("A topic", workspace=str(tmp_path), scenes=9)
    assert result["ok"] is False


def test_static_check_and_status(tmp_path):
    run_id, _ = _new(tmp_path)
    result = server.konvey_check(run_id, runtime=False, workspace=str(tmp_path))
    assert result["ok"] is True
    assert result["status"] == "done"
    assert result["runtime"] is None
    status = server.konvey_status(run_id, workspace=str(tmp_path))
    assert status["state"] == "none"
    assert status["run_status"] == "draft"


def test_a_static_failure_does_not_start_a_runtime_job(tmp_path, monkeypatch):
    run_id, run = _new(tmp_path)
    run.scene_path("S1").write_text(GOOD.replace('vo="One clear line."', ""))
    called = []
    monkeypatch.setattr(server.jobs, "start", lambda *a, **k: called.append(a))
    result = server.konvey_check(run_id, runtime=True, workspace=str(tmp_path))
    assert result["ok"] is False
    assert result["status"] == "done"
    assert result["runtime"] is None
    assert called == []


def test_check_merges_a_done_runtime_job(tmp_path, monkeypatch):
    run_id, _ = _new(tmp_path)

    def fake_start(run, kind, ids, wait_seconds=0):
        return {"status": "done", "job": {
            "id": "check-1",
            "result": {"ok": True, "checked_runtime": True,
                       "scenes": {sid: {"ok": True, "problems": []} for sid in ids}},
        }}

    monkeypatch.setattr(server.jobs, "start", fake_start)
    result = server.konvey_check(run_id, runtime=True, workspace=str(tmp_path))
    assert result["status"] == "done"
    assert result["ok"] is True
    assert result["runtime"]["checked_runtime"] is True
    assert all(scene["runtime"]["ok"] for scene in result["scenes"].values())


def test_a_running_runtime_job_returns_the_static_result_and_a_job_id(tmp_path, monkeypatch):
    run_id, _ = _new(tmp_path)
    monkeypatch.setattr(server.jobs, "start",
                        lambda *a, **k: {"status": "running", "job": {"id": "check-2"}})
    result = server.konvey_check(run_id, runtime=True, workspace=str(tmp_path))
    assert result["status"] == "running"
    assert result["job_id"] == "check-2"
    assert result["ok"] is True          # the static layer passed
    assert result["runtime"] is None


def test_render_is_blocked_by_static_errors_unless_forced(tmp_path, monkeypatch):
    run_id, run = _new(tmp_path)
    run.scene_path("S2").write_text(GOOD.replace('vo="A second clear line."', ""))
    monkeypatch.setattr(server.jobs, "start", lambda *a, **k: pytest.fail("render started"))
    blocked = server.konvey_render(run_id, workspace=str(tmp_path))
    assert blocked["ok"] is False
    assert blocked["status"] == "blocked"
    assert blocked["static"]["ok"] is False


def test_render_hands_a_good_run_to_a_job(tmp_path, monkeypatch):
    run_id, _ = _new(tmp_path)
    seen = {}

    def fake_start(run, kind, args, wait_seconds=0):
        seen.update(kind=kind, args=args)
        return {"status": "running", "job": {"id": "render-1"}}

    monkeypatch.setattr(server.jobs, "start", fake_start)
    result = server.konvey_render(run_id, preview=True, workspace=str(tmp_path))
    assert result["status"] == "running"
    assert result["job_id"] == "render-1"
    assert seen["kind"] == "render"
    assert "--preview" in seen["args"]
    assert "--fps" in seen["args"]
    assert "24" in seen["args"]


def test_render_rejects_an_invalid_fps_before_starting_a_job(tmp_path, monkeypatch):
    run_id, _ = _new(tmp_path)
    monkeypatch.setattr(server.jobs, "start", lambda *a, **k: pytest.fail("render started"))
    result = server.konvey_render(run_id, fps=5, workspace=str(tmp_path))
    assert result["ok"] is False
    assert "fps" in result["error"]


def test_preview_returns_the_job_result_when_it_finishes(tmp_path, monkeypatch):
    run_id, _ = _new(tmp_path)
    monkeypatch.setattr(server.jobs, "start", lambda *a, **k: {
        "status": "done", "job": {"id": "preview-1", "result": {
            "ok": True, "sheet": "/tmp/sheet.png", "index": "/tmp/index.json",
            "beats": [], "scenes": {}}}})
    result = server.konvey_preview(run_id, workspace=str(tmp_path))
    assert result["status"] == "done"
    assert result["sheet"] == "/tmp/sheet.png"


def test_reference_tools_return_content(tmp_path):
    assert "editorial" in server.konvey_guide("themes")
    displays = server.konvey_displays(kind="plot")
    assert displays["displays"][0]["tag"] == "plot"
    example = server.konvey_example(kind="plot")
    assert example["ok"] is True
    values = json.loads(server.konvey_simulate("blocks", '{"mass": 100}', "end"))
    assert "end" in values


def test_protocol_call_returns_text_content():
    result = asyncio.run(server.mcp.call_tool("konvey_guide", {"section": "themes"}))
    assert result.content
    assert "editorial" in result.content[0].text
