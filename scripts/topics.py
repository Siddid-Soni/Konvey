"""Multi-topic dev loop (spec §4.6): run the stage pipeline on every topic in topics.toml,
render each video, and build one labelled contact sheet.

    uv run --group render --group layout python scripts/topics.py [--only T3] [--theme editorial]
        [--rerender] [--jobs 2] [--open]

Each topic goes to out/topics/<slug>/ (run.log, repair-log.txt, video.mp4); the sheet is
out/topics/sheet.png: one row per topic, four frames each. ``--rerender`` re-renders the
existing beats without calling the model.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "out" / "topics"   # --out overrides
FRAME_W, FRAME_H, FRAMES = 640, 360, 4


def load_topics() -> list[dict]:
    return tomllib.loads((REPO / "topics.toml").read_text())["topic"]


def run_topic(topic: dict, theme: str, rerender: bool, model_id: str | None = None) -> dict:
    out = OUT / topic["slug"]
    out.mkdir(parents=True, exist_ok=True)
    if rerender:
        cmd = [sys.executable, "-m", "konvey.render", str(out), "--theme", theme]
    else:
        for stale in [*out.glob("agent3-S*.problems.txt"), out / "repair-log.txt", out / "video.mp4"]:
            stale.unlink(missing_ok=True)
        cmd = [sys.executable, "run_konvey.py", "--prompt", topic["prompt"],
               "--theme", theme, "--render", "--out-dir", str(out)]
        if model_id:
            cmd += ["--model-id", model_id]
    start = time.time()
    with open(out / ("rerender.log" if rerender else "run.log"), "w") as log:
        proc = subprocess.run(cmd, cwd=str(REPO), stdout=log, stderr=subprocess.STDOUT, env=dict(os.environ))
    rejected = sorted(p.stem.split("-")[-1].split(".")[0] for p in out.glob("agent3-S*.problems.txt"))
    repairs = (out / "repair-log.txt").read_text().count("## ") if (out / "repair-log.txt").exists() else 0
    usd = json.loads((out / "cost.json").read_text())["total"]["usd"] if (out / "cost.json").exists() else None
    video = out / "video.mp4"
    return {"id": topic["id"], "slug": topic["slug"], "rc": proc.returncode, "secs": time.time() - start,
            "video": video if video.exists() and video.stat().st_mtime >= start else None,
            "rejected": rejected, "repairs": repairs, "usd": usd}


def duration(video: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          str(video)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def frames(result: dict, tmp: Path) -> list[Path]:
    paths = []
    for k in range(FRAMES):
        p = tmp / f"{result['id']}-{k}.png"
        label = f"{result['id']} {result['slug']}"
        if result["video"]:
            d = duration(result["video"])
            t = d * (k + 0.75) / FRAMES
            vf = (f"scale={FRAME_W}:{FRAME_H},drawtext=text='{label}  t={t:.1f}s':x=8:y={FRAME_H - 22}:"
                  "fontcolor=white:fontsize=15:box=1:boxcolor=black@0.6")
            cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(result["video"]),
                   "-frames:v", "1", "-vf", vf, str(p)]
        else:
            vf = f"drawtext=text='{label} - no video (see run.log)':x=20:y=20:fontcolor=white:fontsize=20"
            cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                   f"color=c=0x301010:s={FRAME_W}x{FRAME_H}", "-frames:v", "1", "-vf", vf, str(p)]
        subprocess.run(cmd, check=True)
        paths.append(p)
    return paths


def contact_sheet(results: list[dict]) -> Path:
    tmp = OUT / "frames"
    tmp.mkdir(parents=True, exist_ok=True)
    tiles = [p for r in results for p in frames(r, tmp)]
    rows = len(results)
    layout = "|".join(f"{c * FRAME_W}_{r * FRAME_H}" for r in range(rows) for c in range(FRAMES))
    inputs = [x for p in tiles for x in ("-i", str(p))]
    sheet = OUT / "sheet.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex",
                    f"xstack=inputs={len(tiles)}:layout={layout}", str(sheet)], check=True)
    return sheet


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--only", action="append", help="topic id (T1..T5); repeatable")
    p.add_argument("--theme", default="editorial")
    p.add_argument("--rerender", action="store_true", help="re-render existing beats, no model calls")
    p.add_argument("--jobs", type=int, default=2, help="topics in parallel (the model is the bottleneck)")
    p.add_argument("--open", action="store_true", help="show the contact sheet with imv")
    p.add_argument("--model-id", help="model for every agent, e.g. mimo-v2.6-flash (default: from .env)")
    p.add_argument("--out", help="output root (default out/topics)")
    args = p.parse_args()
    global OUT
    if args.out:
        OUT = (REPO / args.out).resolve()
    topics = [t for t in load_topics() if not args.only or t["id"] in args.only]
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(lambda t: run_topic(t, args.theme, args.rerender, args.model_id), topics))
    for r in results:
        status = "ok" if r["video"] and not r["rejected"] else "PROBLEM"
        cost = "n/a" if r["usd"] is None else f"${r['usd']:.4f}"
        print(f"{r['id']} {r['slug']:24} {status:8} rc={r['rc']} repairs={r['repairs']} cost={cost} "
              f"rejected={r['rejected'] or '-'} {r['secs']:.0f}s", flush=True)
    sheet = contact_sheet(results)
    print(sheet)
    if args.open:
        subprocess.Popen(["imv", str(sheet)], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0 if all(r["video"] and not r["rejected"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
