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
MAX_PROMPT = 2_000
STREAM_IDLE = 3600.0


@asynccontextmanager
async def lifespan(_: FastAPI):
    with db.connect() as conn:
        db.ensure_schema(conn)
    yield


app = FastAPI(title="Konvey", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_methods=["*"], allow_headers=["*"],
                   allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"])


def _public(run: dict) -> dict:
    video = run.get("video")
    return {**run,
            "video": "/api/runs/%s/files/%s" % (run["id"], video) if video else None}


def _live_limit() -> int:
    try:
        return int(os.environ.get("KONVEY_WEB_MAX_RUNS", "3"))
    except ValueError:
        return 3


def _claim(prompt: str, model: str) -> str:
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
    """pid <= 0 is refused: killpg(0, ...) would signal this server's own group."""
    run = _row(run_id)
    pid = int(db.pid_of(run_id) or 0)
    if run["status"] != "running" or pid <= 0:
        raise HTTPException(409, "the run is not running")
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        db.update_run(run_id, status="failed", error="the worker is gone",
                      finished_at=datetime.now(timezone.utc))
        raise HTTPException(409, "the run is not running")
    except OSError:
        raise HTTPException(409, "the run is not running")
    return {"id": run_id, "status": "cancelling"}


_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
LOG_TAIL_BYTES = 4_000_000


@app.get("/api/runs/{run_id}/log", response_class=PlainTextResponse)
def run_log(run_id: str) -> str:
    _row(run_id)
    path = RUNS / run_id / "worker.log"
    if not path.is_file():
        return ""
    with path.open("rb") as f:
        f.seek(max(0, path.stat().st_size - LOG_TAIL_BYTES))
        data = f.read().decode("utf-8", "replace")
    return _ANSI.sub("", data).replace("\r", "\n")


@app.get("/api/runs/{run_id}/files/{name:path}")
def run_file(run_id: str, name: str) -> FileResponse:
    _row(run_id)
    path = (RUNS / run_id / name).resolve()
    if not path.is_relative_to(RUNS / run_id) or not path.is_file():
        raise HTTPException(404, name)
    # model-written HTML must not run on this origin
    media = "text/plain; charset=utf-8" if path.suffix in (".html", ".htm") else None
    return FileResponse(path, media_type=media, headers={"X-Content-Type-Options": "nosniff"})
EVENT_POLL = 0.4


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str, request: Request, after: int = 0) -> StreamingResponse:
    await asyncio.to_thread(_row, run_id)
    try:
        start = int(request.headers.get("last-event-id") or 0)
    except ValueError:
        start = after

    async def stream() -> AsyncIterator[str]:
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
                if not ended and not batch:
                    ended = await asyncio.to_thread(reader.status_of, run_id) != "running"
                if ended:
                    yield "event: end\ndata: {}\n\n"
                    return
                idle = 0.0 if batch else idle + EVENT_POLL
                if idle > STREAM_IDLE:
                    return
                await asyncio.sleep(EVENT_POLL)
        finally:
            reader.close()

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


DIST = REPO / "web" / "frontend" / "dist"
if DIST.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="app")
