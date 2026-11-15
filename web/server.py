"""Web API for Konvey: start a run, watch it live.

Postgres owns the state (``web/schema.sql``); the run directory owns the media. A run is a
detached process that only writes events:

    POST /api/runs                  {prompt} -> {id, ...}       start
    GET  /api/runs                  list runs
    GET  /api/runs/{id}             status + video
    GET  /api/runs/{id}/events      SSE over the event table (reconnect with Last-Event-ID)
    GET  /api/runs/{id}/files/{p}   beats HTML, JSON, video.mp4
    POST /api/runs/{id}/cancel      kill the run's process group

    docker compose up -d postgres
    uv run --group web --group render --group layout uvicorn web.server:app --reload

The API has no authentication: it starts runs that spend money and kills their process groups.
Keep it on the loopback interface (uvicorn's default) and do not expose the port.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import signal
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse

from . import db

REPO = Path(__file__).resolve().parents[1]
RUNS = Path(os.environ.get("KONVEY_WEB_RUNS", REPO / "out" / "web")).resolve()
MAX_PROMPT = 2_000   # a topic, not a document: every prompt is also a model input
STREAM_IDLE = 3600.0  # seconds of no events before an open stream gives up


@asynccontextmanager
async def lifespan(_: FastAPI):
    with db.connect() as conn:      # the compose initdb does this too; this covers a reuse
        db.ensure_schema(conn)
    yield


# the app is served same-origin from frontend/dist, so only `npm run dev` needs cors
app = FastAPI(title="Konvey", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_methods=["*"], allow_headers=["*"],
                   allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"])


def _public(run: dict) -> dict:
    video = run.get("video")
    return {**run,
            "video": "/api/runs/%s/files/%s" % (run["id"], video) if video else None}


def _live_limit() -> int:
    """How many runs may be going at once (``KONVEY_WEB_MAX_RUNS``, 0 = no cap). Read per call,
    so setting the env later still counts."""
    try:
        return int(os.environ.get("KONVEY_WEB_MAX_RUNS", "3"))
    except ValueError:
        return 3


def _claim(prompt: str, model: str) -> str:
    """Insert the run's row; the insert is the claim, so two requests cannot take one id."""
    limit = _live_limit()
    if limit and sum(r["status"] == "running" for r in db.list_runs(50)) >= limit:
        raise HTTPException(429, f"{limit} runs are already going; wait for one to finish")
    stamp = time.strftime("%y%m%d-%H%M%S")
    for attempt in range(5):
        run_id = stamp if attempt == 0 else f"{stamp}-{secrets.token_hex(2)}"
        if db.create_run(run_id, prompt, model):
            return run_id
    raise HTTPException(503, "could not allocate a run id")


def _spawn(run_id: str, render: bool) -> subprocess.Popen:
    """Start the run's worker, detached, its output going to <run>/worker.log."""
    path = RUNS / run_id
    path.mkdir(parents=True, exist_ok=True)
    with (path / "worker.log").open("ab") as log:
        return subprocess.Popen(
            [sys.executable, "-m", "web.worker", run_id],
            cwd=str(REPO), stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            env={**os.environ, "PYTHONUNBUFFERED": "1",
                 "KONVEY_WEB_RENDER": "1" if render else "0"},
            start_new_session=True,
        )


def _row(run_id: str) -> dict:
    run = db.get_run(run_id) if run_id and all(c in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in run_id) else None
    if not run:
        raise HTTPException(404, f"no run {run_id!r}")
    return run


@app.get("/api/health")
def health() -> dict:
    runs = db.list_runs(50)
    return {"ok": True, "runs": len(runs), "latest": runs[0]["id"] if runs else None,
            "model": os.environ.get("OPENCODE_MODEL_ID", ""),
            "provider": os.environ.get("KONVEY_PROVIDER", ""),
            "key": bool(os.environ.get("OPENCODE_API_KEY") or os.environ.get("MINIMAX_API_KEY"))}


@app.get("/api/runs")
def list_runs() -> list[dict]:
    return [_public(r) for r in db.list_runs()]


@app.post("/api/runs")
async def start_run(request: Request) -> dict:
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(400, "the body is not JSON")
    if not isinstance(body, dict):
        raise HTTPException(400, "the body must be a JSON object")
    prompt = str(body.get("prompt", "")).strip()
    if not prompt:
        raise HTTPException(400, "prompt is required")
    if len(prompt) > MAX_PROMPT:
        raise HTTPException(400, f"the prompt is longer than {MAX_PROMPT} characters")
    model = os.environ.get("OPENCODE_MODEL_ID") or os.environ.get("KONVEY_MODEL_ID", "")
    # a database connect and a fork are quick, not quick enough to hold the event loop
    run_id = await asyncio.to_thread(_claim, prompt, model)
    try:
        proc = await asyncio.to_thread(_spawn, run_id, bool(body.get("render", True)))
    except OSError as e:   # no worker: the row must not be left saying "running"
        await asyncio.to_thread(db.update_run, run_id, status="failed",
                                error=f"could not start the worker: {e}")
        raise HTTPException(503, "could not start the worker")
    await asyncio.to_thread(db.update_run, run_id, pid=proc.pid)
    return _public(await asyncio.to_thread(_row, run_id))


@app.get("/api/runs/{run_id}")
def run_status(run_id: str) -> dict:
    return _public(_row(run_id))


@app.post("/api/runs/{run_id}/cancel")
def cancel(run_id: str) -> dict:
    """SIGTERM the run's process group, but only while it is really running.

    a null or zero pid (imported runs, a worker that never recorded one) is not a pid to
    signal: ``killpg(0, ...)`` would hit this server's own group, and every in-flight worker
    with it. the worker turns the signal into ``run.cancelled`` plus the finished row.
    """
    run = _row(run_id)
    pid = int(db.pid_of(run_id) or 0)
    if run["status"] != "running" or pid <= 0:
        raise HTTPException(409, "the run is not running")
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:   # the worker died on its own: the row is what is stale
        db.update_run(run_id, status="failed", error="the worker is gone",
                      finished_at=datetime.now(timezone.utc))
        raise HTTPException(409, "the run is not running")
    except OSError:
        raise HTTPException(409, "the run is not running")
    return {"id": run_id, "status": "cancelling"}


_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
LOG_TAIL_BYTES = 4_000_000   # the end of a long run's output; the start is in worker.log on disk


@app.get("/api/runs/{run_id}/log", response_class=PlainTextResponse)
def run_log(run_id: str) -> str:
    """The worker's full output (what the pipeline printed, tracebacks included), as plain text."""
    _row(run_id)
    path = RUNS / run_id / "worker.log"
    if not path.is_file():
        return ""
    with path.open("rb") as f:          # the tail only: a long run's log is not read whole
        f.seek(max(0, path.stat().st_size - LOG_TAIL_BYTES))
        data = f.read().decode("utf-8", "replace")
    return _ANSI.sub("", data).replace("\r", "\n")


@app.get("/api/runs/{run_id}/files/{name:path}")
def run_file(run_id: str, name: str) -> FileResponse:
    _row(run_id)
    path = (RUNS / run_id / name).resolve()
    if not path.is_relative_to(RUNS / run_id) or not path.is_file():   # `..` out of the run
        raise HTTPException(404, name)
    # beats HTML is model-written: served as text, never as a page on this origin (it would run)
    media = "text/plain; charset=utf-8" if path.suffix in (".html", ".htm") else None
    return FileResponse(path, media_type=media, headers={"X-Content-Type-Options": "nosniff"})


EVENT_POLL = 0.4      # seconds between two polls of one stream: one row loop, one connection


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str, request: Request, after: int = 0) -> StreamingResponse:
    await asyncio.to_thread(_row, run_id)   # 404 before the stream starts
    try:
        start = int(request.headers.get("last-event-id") or 0)
    except ValueError:                      # a header we cannot read: replay from the top
        start = after

    async def stream() -> AsyncIterator[str]:
        # one connection for the whole stream, and none of it on the event loop
        reader, sent, idle = db.Reader(), start, 0.0
        try:
            while True:
                if await request.is_disconnected():
                    return
                batch = await asyncio.to_thread(reader.events_after, run_id, sent)
                for event in batch:
                    sent = event["seq"]
                    yield f"id: {sent}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                ended = any(e.get("type") in ("run.finished", "run.failed", "run.cancelled")
                            for e in batch)
                if not ended and not batch:   # fresh status: a cancel ends the stream at once
                    ended = await asyncio.to_thread(reader.status_of, run_id) != "running"
                if ended:
                    yield "event: end\ndata: {}\n\n"
                    return
                idle = 0.0 if batch else idle + EVENT_POLL   # quiet for an hour: let it go
                if idle > STREAM_IDLE:
                    return
                await asyncio.sleep(EVENT_POLL)
        finally:
            reader.close()

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# built frontend, when there is one: uvicorn then serves the whole app on one port
DIST = REPO / "web" / "frontend" / "dist"
if DIST.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="app")
