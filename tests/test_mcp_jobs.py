"""Detached MCP jobs: start, status reconciliation, wait, cancel."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from konvey.mcp import jobs, runs
from konvey.mcp.runs import atomic_write_json, now_iso


def _run(tmp_path):
    return runs.new_run("A test topic", workspace=tmp_path, scenes=1)


def _job(run, job_id, **overrides):
    job = {
        "id": job_id,
        "kind": "preview",
        "state": "running",
        "pid": 999999,
        "started_at": now_iso(),
        "finished_at": None,
        "result": None,
        "error": None,
        "log": str(run.jobs_dir() / f"{job_id}.log"),
    }
    job.update(overrides)
    run.jobs_dir().mkdir(parents=True, exist_ok=True)
    atomic_write_json(run.jobs_dir() / f"{job_id}.json", job)
    run.data["active_job"] = job_id
    run.save()
    return job


def test_status_without_jobs_is_quiet(tmp_path):
    run = _run(tmp_path)
    status = jobs.status(run)
    assert status["state"] == "none"
    assert status["log_tail"] == []
    assert status["run_status"] == "draft"


def test_a_dead_worker_is_reconciled_to_failed_with_the_log_tail(tmp_path):
    run = _run(tmp_path)
    log = run.jobs_dir() / "preview-1.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("first\nlast line\n")
    _job(run, "preview-1", pid=999999)
    status = jobs.status(run, "preview-1")
    assert status["state"] == "failed"
    assert "worker exited" in status["error"]
    assert status["log_tail"] == ["first", "last line"]
    assert status["elapsed_sec"] is not None
    assert runs.Run.from_dir(run.directory).data["active_job"] is None


def test_wait_returns_a_finished_job(tmp_path):
    run = _run(tmp_path)
    _job(run, "preview-2", state="done", pid=None, finished_at=now_iso(),
         result={"ok": True, "beats": []})
    waited = jobs.wait(run, "preview-2", 0.1)
    assert waited["ok"] is True
    assert waited["status"] == "done"
    assert waited["job"]["result"]["ok"] is True


def test_a_live_job_blocks_another_start(tmp_path):
    run = _run(tmp_path)
    _job(run, "preview-3", pid=os.getpid())
    result = jobs.start(run, "preview", ["S1"])
    assert result["status"] == "busy"
    assert "already running" in result["error"]


def test_cancel_stops_the_worker_process_group(tmp_path):
    run = _run(tmp_path)
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                            start_new_session=True)
    try:
        _job(run, "preview-4", pid=proc.pid)
        result = jobs.cancel(run, "preview-4", grace=1)
        assert result["status"] == "cancelled"
        proc.wait(timeout=5)
        assert proc.poll() is not None
        assert runs.Run.from_dir(run.directory).data["active_job"] is None
    finally:
        if proc.poll() is None:
            proc.kill()


def test_unknown_job_ids_are_rejected(tmp_path):
    run = _run(tmp_path)
    with pytest.raises(ValueError):
        jobs.status(run, "../escape")


def test_start_and_the_worker_round_trip(tmp_path):
    """The real worker path, without manimgl: a scene that cannot preview reports a result."""
    run = _run(tmp_path)
    result = jobs.start(run, "preview", ["S1"], wait_seconds=20)
    job = result["job"]
    if job["state"] in jobs.ACTIVE:
        job = jobs.wait(run, job["id"], 20)["job"]
    assert job["state"] == "done"
    assert job["result"]["ok"] is False          # no render stack in the base env
    assert job["elapsed_sec"] is not None
    assert jobs.latest_job(run)["id"] == job["id"]
