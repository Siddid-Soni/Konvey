"""Import web runs that were written as files (meta.json + events.jsonl) into Postgres.

A one-off migration for run directories the early prototype wrote (nothing in the repo writes
that pair any more). Idempotent: run dirs stay on disk for the media, the rows come from what
that prototype recorded.

    uv run --group web python -m spikes.web_import_files            # all of out/web
    uv run --group web python -m spikes.web_import_files --dry-run
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from web import db

REPO = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    runs_dir = Path(os.environ.get("KONVEY_WEB_RUNS", REPO / "out" / "web")).resolve()
    dry = "--dry-run" in args
    imported = 0
    if not runs_dir.is_dir():
        print(f"no run directory at {runs_dir}, nothing to import")
        return 0
    for path in sorted(p for p in runs_dir.iterdir() if (p / "meta.json").exists()):
        meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
        events = []
        if (path / "events.jsonl").exists():
            events = [json.loads(line) for line in
                      (path / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        print(f"{path.name}: {meta.get('status')} · {len(events)} events · {meta.get('prompt','')[:60]}")
        if dry:
            continue
        db.create_run(path.name, meta.get("prompt", ""), meta.get("model", ""))
        mtime = (path / "meta.json").stat().st_mtime   # fallback, not a 1970 run
        created = datetime.fromtimestamp(meta.get("created") or mtime, tz=timezone.utc)
        db.update_run(path.name, status=meta.get("status", "finished"), usd=meta.get("usd"),
                      title=meta.get("title"),
                      video="video.mp4" if (path / "video.mp4").exists() else None,
                      error=meta.get("error", "") or None)
        with db.connect() as conn:      # keep the recorded start time and the exact seq
            conn.execute("update runs set created = %s where id = %s", (created, path.name))
            for event in events:
                seq = event.get("seq")
                if not seq:
                    continue
                body = {k: v for k, v in event.items() if k not in ("seq", "t", "type")}
                conn.execute(
                    "insert into events (run_id, seq, t, type, data) values (%s, %s, %s, %s, %s)"
                    " on conflict do nothing",
                    (path.name, seq, event.get("t", 0.0), event.get("type", "?"),
                     json.dumps(body, ensure_ascii=False)))
        imported += 1
    print(f"imported {imported} runs" + (" (dry run)" if dry else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
