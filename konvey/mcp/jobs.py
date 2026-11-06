"""Detached jobs for long Konvey operations.

Preview, runtime check and render can outlast a client's MCP tool timeout (opencode's local
MCP default is 30 s). Each one runs in its own process, writes ``jobs/<id>.json`` and a log,
and survives the MCP server. The tools wait a little and then return the job id; the
harness polls ``status``.

    job = start(run, "preview", ["S1"], wait_seconds=20)
    status(run, job["job"]["id"])

State is on disk, so a server restart does not lose a running job.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .runs import REPO_ROOT, Run, atomic_write_json, now_iso, read_json

ACTIVE = {"queued", "running"}
LOG_LINES = 40


def _job_path(run: Run, job_id: str) -> Path:
    if not job_id or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in job_id):
        raise ValueError(f"invalid job id {job_id!r}")
    return run.jobs_dir() / f"{job_id}.json"


def _read(run: Run, job_id: str) -> dict:
    return read_json(_job_path(run, job_id))


def _write(run: Run, job_id: str, data: dict) -> Path:
    return atomic_write_json(_job_path(run, job_id), data)


def _alive(pid) -> bool:
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        state = Path(f"/proc/{pid}/stat").read_text().split()[2]
        if state == "Z":          # a crashed worker we have not reaped is not running
            return False
    except (OSError, IndexError):
        pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _tail(path: str | Path | None, lines: int = LOG_LINES) -> list[str]:
    if not path:
        return []
    path = Path(path)
    if not path.is_file():
        return []
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - 16384))
            text = fh.read().decode("utf-8", "replace")
    except OSError:
        return []
    return text.splitlines()[-lines:]


def _elapsed(job: dict) -> float | None:
    started = job.get("started_at")
    if not started:
        return None
    try:
        start = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
        end = job.get("finished_at")
        finish = (datetime.fromisoformat(str(end).replace("Z", "+00:00"))
                  if end else datetime.now(timezone.utc))
        return round((finish - start).total_seconds(), 1)
    except ValueError:
        return None


def latest_job(run: Run) -> dict | None:
    """The most recently started job of a run, if any."""
    directory = run.jobs_dir()
    if not directory.is_dir():
        return None
    jobs = []
    for path in directory.glob("*.json"):
        try:
            job = read_json(path)
            jobs.append((str(job.get("started_at") or ""), path.stat().st_mtime, job))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    if not jobs:
        return None
    return max(jobs, key=lambda t: (t[0], t[1]))[2]


def _fresh(run: Run) -> Run:
    """Reload run.json; a worker may have written newer status/artifacts."""
    try:
        return Run.from_dir(run.directory)
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return run


def _running(run: Run) -> dict | None:
    """The live job, if one is recorded on the run or is the newest job."""
    candidates = []
    active_id = run.data.get("active_job")
    if active_id:
        try:
            candidates.append(_read(run, str(active_id)))
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    newest = latest_job(run)
    if newest:
        candidates.append(newest)
    for job in candidates:
        if job.get("state") in ACTIVE and _alive(job.get("pid")):
            return job
    return None


def start(run: Run, kind: str, args: list[str] | None = None,
          wait_seconds: float = 0.0) -> dict:
    """Start a detached worker for ``kind`` and optionally wait up to ``wait_seconds``."""
    if not kind or not kind.isalpha():
        raise ValueError(f"invalid job kind {kind!r}")
    run = _fresh(run)
    running = _running(run)
    if running is not None:
        return {"ok": False, "status": "busy", "job": running,
                "error": f"{running.get('kind')} job {running.get('id')} is already running"}

    args = [str(a) for a in (args or [])]
    stamp = int(time.time() * 1000)
    job_id = f"{kind}-{stamp}"
    path = _job_path(run, job_id)
    log_path = run.jobs_dir() / f"{job_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    job = {
        "id": job_id,
        "kind": kind,
        "state": "queued",
        "pid": None,
        "started_at": now_iso(),
        "finished_at": None,
        "result": None,
        "error": None,
        "log": str(log_path),
    }
    _write(run, job_id, job)

    env = {**os.environ, "KONVEY_JOB_ID": job_id, "KONVEY_JOB_FILE": str(path)}
    pythonpath = [str(REPO_ROOT)]
    if os.environ.get("PYTHONPATH"):
        pythonpath.append(os.environ["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    try:
        with log_path.open("ab") as log:
            proc = subprocess.Popen(
                [sys.executable, "-m", "konvey.mcp.worker", kind, str(run.directory), *args],
                cwd=str(REPO_ROOT), env=env, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
    except OSError as e:
        job.update(state="failed", finished_at=now_iso(), error=f"could not start worker: {e}")
        _write(run, job_id, job)
        return {"ok": False, "status": "failed", "job": job, "error": job["error"]}

    # The worker may already have finished; only fill in a pid while it is still active.
    current = _read(run, job_id)
    if current.get("state") in ACTIVE:
        current["pid"] = proc.pid
        current["state"] = "running"
        _write(run, job_id, current)
        job = current
    run = _fresh(run)   # do not overwrite status/artifacts a fast worker already wrote
    run.data["active_job"] = job_id
    run.save()

    if wait_seconds and wait_seconds > 0:
        return wait(run, job_id, wait_seconds)
    return {"ok": True, "status": "running", "job": job}


def status(run: Run, job_id: str | None = None) -> dict:
    """The job's state, reconciled with the worker process, plus its log tail."""
    job_id = job_id or run.data.get("active_job")
    if not job_id:
        run = _fresh(run)
        newest = latest_job(run)
        if not newest:
            return {"id": None, "kind": None, "state": "none", "log_tail": [],
                    "run_status": run.data.get("status"), "artifacts": run.data.get("artifacts", {})}
        job_id = str(newest["id"])
    job = _read(run, job_id)
    if job.get("state") in ACTIVE and job.get("pid") and not _alive(job.get("pid")):
        job.update(state="failed", finished_at=job.get("finished_at") or now_iso(),
                   error=job.get("error") or "worker exited without reporting; see the log")
        _write(run, job_id, job)
    if job.get("state") not in ACTIVE and run.data.get("active_job") == job_id:
        fresh = _fresh(run)
        fresh.data["active_job"] = None
        fresh.save()
        run.data = fresh.data
    job = dict(job)
    job["log_tail"] = _tail(job.get("log"))
    job["elapsed_sec"] = _elapsed(job)
    job["run_status"] = run.data.get("status")
    job["artifacts"] = run.data.get("artifacts", {})
    return job


def wait(run: Run, job_id: str, timeout: float) -> dict:
    """Poll ``status`` until the job finishes or ``timeout`` seconds pass."""
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        job = status(run, job_id)
        if job.get("state") not in ACTIVE:
            return {"ok": job.get("state") == "done", "status": job.get("state"), "job": job}
        if time.monotonic() >= deadline:
            return {"ok": True, "status": "running", "job": job}
        time.sleep(0.25)


def cancel(run: Run, job_id: str | None = None, grace: float = 5.0) -> dict:
    """Stop a job's process group and mark it cancelled."""
    job_id = job_id or run.data.get("active_job")
    if not job_id:
        return {"ok": False, "status": "none", "error": "no job to cancel"}
    job = _read(run, job_id)
    if job.get("state") not in ACTIVE:
        return {"ok": True, "status": job.get("state"), "job": job}

    pid = job.get("pid")
    if _alive(pid):
        try:
            os.killpg(os.getpgid(int(pid)), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                os.kill(int(pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                pass
        deadline = time.monotonic() + max(0.0, grace)
        while time.monotonic() < deadline and _alive(pid):
            time.sleep(0.1)
        if _alive(pid):
            try:
                os.killpg(os.getpgid(int(pid)), signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                try:
                    os.kill(int(pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError):
                    pass

    job.update(state="cancelled", finished_at=now_iso(), error="cancelled")
    _write(run, job_id, job)
    run = _fresh(run)
    if run.data.get("active_job") == job_id:
        run.data["active_job"] = None
        run.save()
    return {"ok": True, "status": "cancelled", "job": job}
