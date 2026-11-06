"""Worker process for one Konvey MCP job.

Started by :func:`konvey.mcp.jobs.start` as::

    python -m konvey.mcp.worker <kind> <run-dir> [args…]

with ``KONVEY_JOB_FILE`` pointing at the job's JSON. The worker owns that file while it
runs, updates it to ``running`` / ``done`` / ``failed``, and writes the result there. Its
stdout and stderr go to the job's log.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

from .runs import Run, atomic_write_json, now_iso


def _update(path: Path, **changes) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    data.update(changes)
    atomic_write_json(path, data)
    return data


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        print("usage: python -m konvey.mcp.worker <kind> <run-dir> [scenes…]", file=sys.stderr)
        return 2
    kind, run_dir, *rest = args
    job_file = os.environ.get("KONVEY_JOB_FILE")
    if not job_file:
        print("KONVEY_JOB_FILE is not set", file=sys.stderr)
        return 2
    job_path = Path(job_file)
    run = Run.from_dir(run_dir)
    _update(job_path, state="running", pid=os.getpid())

    try:
        if kind == "preview":
            from .preview import capture_run

            result = capture_run(run, rest or None)
        elif kind == "check":
            from .check import check_runtime_run

            result = check_runtime_run(run, rest or None)
        elif kind == "render":
            from .render import render_run

            preview = False
            fps = 24
            scenes = []
            i = 0
            while i < len(rest):
                if rest[i] == "--preview":
                    preview = True
                    i += 1
                elif rest[i] == "--fps" and i + 1 < len(rest):
                    fps = int(rest[i + 1])
                    i += 2
                else:
                    scenes.append(rest[i])
                    i += 1
            result = render_run(run, scenes or None, preview=preview, fps=fps)
        else:
            raise ValueError(f"unknown job kind {kind!r}")
    except BaseException as e:  # noqa: BLE001 - a bad worker must report, not vanish
        detail = traceback.format_exc()
        print(detail, file=sys.stderr)
        if kind == "render":
            try:
                fresh = Run.from_dir(run.directory)
                fresh.data["status"] = "failed"
                fresh.save()
            except Exception:  # noqa: BLE001 - the job error is the useful one
                pass
        _update(job_path, state="failed", finished_at=now_iso(),
                error=f"{type(e).__name__}: {e}", traceback=detail[-4000:])
        return 1

    _update(job_path, state="done", finished_at=now_iso(), result=result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
