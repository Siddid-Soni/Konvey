from __future__ import annotations

import os
import signal
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from . import db

REPO = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: python -m web.worker <run-id>", file=sys.stderr)
        return 2
    run_id = args[0]
    run = db.get_run(run_id)
    if not run:
        print(f"no run {run_id} in the database", file=sys.stderr)
        return 2
    run_dir = Path(os.environ.get("KONVEY_WEB_RUNS", REPO / "out" / "web")).resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    from konvey.pipeline import PipelineConfig, run_pipeline

    started = time.time()
    store: db.Store | None = None          # a connect failure here must still end the run
    signal.signal(signal.SIGTERM, lambda *_: _cancelled(run_id, store, started))
    try:
        store = db.Store(run_id)
        config = PipelineConfig(
            user_prompt=run["prompt"],
            out_dir=str(run_dir),
            verbose=True,
            probe=True,
            on_event=store.event,
        )
        result = run_pipeline(config)
        db.update_run(run_id, title=result.plan.title,
                      usd=config.cost_log.summary()["total"]["usd"])
        if os.environ.get("KONVEY_WEB_RENDER", "1") != "0":
            _render(run_dir, store)
        store.event("run.finished", seconds=round(time.time() - started, 1),
                    usd=config.cost_log.summary()["total"]["usd"],
                    rejected=sorted(result.rejected),
                    video="video.mp4" if (run_dir / "video.mp4").exists() else None)
        db.update_run(run_id, status="finished", finished_at=datetime.now(timezone.utc),
                      video="video.mp4" if (run_dir / "video.mp4").exists() else None)
        return 0
    except BaseException as e:  # noqa: BLE001 - the UI needs the reason, not a stack trace
        traceback.print_exc()
        frames = traceback.extract_tb(e.__traceback__)
        where = f"{frames[-1].filename}:{frames[-1].lineno}" if frames else ""
        error = f"{type(e).__name__}: {e}"
        if store:      # a store that failed to connect must not hide the row update below
            store.event("run.failed", error=error, where=where)
        db.update_run(run_id, status="failed", error=error,
                      finished_at=datetime.now(timezone.utc))
        return 1
    finally:
        if store:
            store.close()
        _trim(run_id)


def _cancelled(run_id: str, store: db.Store | None, started: float) -> None:
    """SIGTERM: record the cancel, mark the row, and leave without waiting for the threads."""
    try:
        sink = store or db.Store(run_id)
        sink.event("run.cancelled", seconds=round(time.time() - started, 1))
    except Exception:  # noqa: BLE001 - a store that cannot be had must not block the exit
        traceback.print_exc()
    try:
        db.update_run(run_id, status="cancelled", finished_at=datetime.now(timezone.utc))
        _trim(run_id)      # the deltas of a cancelled run are not worth replaying either
    finally:
        os._exit(0)


def _trim(run_id: str) -> None:
    try:
        db.trim_events(run_id)
    except Exception:  # noqa: BLE001 - housekeeping is not worth a failed run
        traceback.print_exc()


def _render(run_dir: Path, store: db.Store) -> None:
    from concurrent.futures import ThreadPoolExecutor

    try:
        from konvey.render import concat, render_scene, scene_ids
    except Exception as e:  # noqa: BLE001 - render stack is optional
        store.event("render.skipped", reason=f"{type(e).__name__}: {e}")
        return
    ids = scene_ids(run_dir)
    if not ids:
        store.event("render.skipped", reason="no scenes")
        return
    store.event("render.start", scenes=ids)
    try:
        jobs = max(1, min(3, int(os.environ.get("KONVEY_RENDER_JOBS", "2"))))
    except ValueError:  # a bad env var must not fail an otherwise good run
        print("KONVEY_RENDER_JOBS is not a number, rendering 2 at a time", flush=True)
        jobs = 2

    def one(sid: str):
        store.event("render.scene", scene=sid, state="rendering")
        try:
            path = render_scene(run_dir, sid, log=lambda m: print(m, flush=True))
            store.event("render.scene", scene=sid, state="done", file=path.name)
            return path
        except Exception as e:  # noqa: BLE001
            print(traceback.format_exc())
            store.event("render.scene", scene=sid, state="failed", error=str(e))
            return None

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        parts = [p for p in pool.map(one, ids) if p]
    if not parts:
        store.event("render.skipped", reason="no scene rendered")
        return
    try:
        video = concat(run_dir, parts)
    except Exception as e:  # noqa: BLE001 - the scenes are good; only the join is not
        print(traceback.format_exc())
        store.event("render.skipped", reason=f"the scenes could not be joined: {e}")
        return
    store.event("render.done", video=video.name)


if __name__ == "__main__":
    raise SystemExit(main())
