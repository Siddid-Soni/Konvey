"""Postgres store for the web app: runs and their event stream.

The pipeline knows nothing about this. It is handed ``Store.event`` as
``PipelineConfig.on_event`` and calls it with an event type and a few fields; this module
writes the row. Media stay on disk (the run directory); these tables own the state, so the API
can be restarted, a browser can replay any run from ``seq = 1``, and a dropped connection
reconnects with ``seq > last``.

    docker compose up -d postgres
    uv run --group web python -m web.db --check     # connect, create the tables, list runs
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

DSN = os.environ.get("KONVEY_DATABASE_URL", "postgresql://konvey:konvey@127.0.0.1:5432/konvey")
SCHEMA = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
FIELDS = ("status", "finished_at", "usd", "title", "video", "error", "pid", "model")


def connect():
    import psycopg

    conn = psycopg.connect(DSN, autocommit=True, connect_timeout=10)
    conn.row_factory = psycopg.rows.dict_row
    return conn


def ensure_schema(conn) -> None:
    conn.execute(SCHEMA)


def _discard(conn) -> None:
    """Close a connection we are abandoning; it may already be broken, so nothing may escape."""
    try:
        if conn is not None:
            conn.close()
    except Exception:  # noqa: BLE001 - the socket is gone either way
        pass


# --- reads (the API) ---------------------------------------------------------


def list_runs(limit: int = 50) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "select id, prompt, status, created, model, usd, title, video, error"
            " from runs order by created desc limit %s", (limit,)).fetchall()
    return [_jsonable(r) for r in rows]


def get_run(run_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "select id, prompt, status, created, model, usd, title, video, error, pid"
            " from runs where id = %s", (run_id,)).fetchone()
    return _jsonable(row) if row else None


def pid_of(run_id: str) -> int | None:
    with connect() as conn:
        row = conn.execute("select pid from runs where id = %s", (run_id,)).fetchone()
    return row["pid"] if row else None


def status_of(run_id: str) -> str | None:
    with connect() as conn:
        return _status(conn, run_id)


def events_after(run_id: str, after: int, limit: int = 1000) -> list[dict]:
    with connect() as conn:
        return _events(conn, run_id, after, limit)


def _status(conn, run_id: str) -> str | None:
    row = conn.execute("select status from runs where id = %s", (run_id,)).fetchone()
    return row["status"] if row else None


def _events(conn, run_id: str, after: int, limit: int) -> list[dict]:
    rows = conn.execute(
        "select seq, t, type, data from events where run_id = %s and seq > %s"
        " order by seq limit %s", (run_id, after, limit)).fetchall()
    return [{"seq": r["seq"], "t": r["t"], "type": r["type"], **r["data"]} for r in rows]


def _jsonable(row: dict) -> dict:
    out = dict(row)
    if out.get("created") is not None:
        out["created"] = out["created"].timestamp()
    if out.get("finished_at") is not None:
        out["finished_at"] = out["finished_at"].timestamp()
    out.pop("pid", None)
    return out


class Reader:
    """One SSE stream's polls: a single connection, reused until the stream ends.

    The stream asks for new events four times a second, so a connection per poll both blocks
    the event loop and leaves Postgres with a socket per open browser. Queries run in worker
    threads (``asyncio.to_thread``), hence the lock around connect, query and reconnect.
    """

    def __init__(self) -> None:
        self.conn = None
        self.lock = threading.Lock()

    def _call(self, fn):
        with self.lock:
            try:
                return fn(self._conn())
            except Exception:  # noqa: BLE001 - typically a socket that died since the last poll
                _discard(self.conn)
                self.conn = None
                return fn(self._conn())  # one fresh connection; a second failure is real

    def _conn(self):
        if self.conn is None:
            self.conn = connect()
        return self.conn

    def events_after(self, run_id: str, after: int, limit: int = 1000) -> list[dict]:
        return self._call(lambda conn: _events(conn, run_id, after, limit))

    def status_of(self, run_id: str) -> str | None:
        return self._call(lambda conn: _status(conn, run_id))

    def close(self) -> None:
        with self.lock:
            _discard(self.conn)
            self.conn = None


# --- writes (the worker) -----------------------------------------------------


def create_run(run_id: str, prompt: str, model: str = "", pid: int | None = None) -> bool:
    """True when this call inserted the row, False when the id was already taken."""
    with connect() as conn:
        row = conn.execute(
            "insert into runs (id, prompt, model, pid) values (%s, %s, %s, %s)"
            " on conflict (id) do nothing returning id", (run_id, prompt, model, pid)).fetchone()
    return row is not None


def update_run(run_id: str, **fields: Any) -> None:
    keys = [k for k in fields if k in FIELDS]
    if not keys:
        return
    sets = ", ".join(f"{k} = %s" for k in keys)
    with connect() as conn:
        conn.execute(f"update runs set {sets} where id = %s",  # noqa: S608 - keys are whitelisted
                     (*(fields[k] for k in keys), run_id))


def trim_events(run_id: str) -> None:
    """A run is over: drop its per-token deltas, keep the milestones a page replays."""
    with connect() as conn:
        conn.execute("delete from events where run_id = %s and type = %s", (run_id, "agent.delta"))


class Store:
    """One run's event sink: owns a connection and the per-run sequence number.

    Called from the pipeline's thread pool (three scenes at once), so the insert is
    serialised; a run only ever has one writer, which is what keeps ``seq`` monotonic.

    Reporting is best-effort: a run must not die because the database blinked, so a failed
    insert is a stderr line (rate-limited, a dead database would otherwise print every delta)
    and the connection is dropped for the next event to re-open. The sequence number still
    advances, so a lost event leaves a gap rather than a duplicate ``seq``.
    """

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.conn = None
        # reentrant: the SIGTERM handler runs in the main thread, which may itself be inside
        # ``event`` (a cancel that lands mid-insert must not wait forever on its own lock)
        self.lock = threading.RLock()
        # per run, from 1, with exactly one writer: create_run only lets one caller win the id
        self.seq = 0
        self.t0 = time.monotonic()
        self.warned = 0.0

    def event(self, type: str, **data: Any) -> None:
        with self.lock:
            self.seq += 1
            try:
                if self.conn is None:
                    self.conn = connect()
                self.conn.execute(
                    "insert into events (run_id, seq, t, type, data) values (%s, %s, %s, %s, %s)",
                    (self.run_id, self.seq, round(time.monotonic() - self.t0, 2), type,
                     json.dumps(data, ensure_ascii=False)))
            except Exception as e:  # noqa: BLE001 - best-effort: never break the run
                _discard(self.conn)
                self.conn = None
                self._warn(e)

    def _warn(self, err: Exception) -> None:
        now = time.monotonic()
        if now - self.warned > 10:      # one line per 10s: a dead database writes 3 deltas a second
            self.warned = now
            print(f"[web.db] event store unavailable: {type(err).__name__}: {err}"
                  f" (run {self.run_id})", file=sys.stderr, flush=True)

    def close(self) -> None:
        with self.lock:
            _discard(self.conn)
            self.conn = None


if __name__ == "__main__":
    with connect() as conn:
        ensure_schema(conn)
    if "--check" in sys.argv:
        print("ok", DSN, len(list_runs()), "runs")
