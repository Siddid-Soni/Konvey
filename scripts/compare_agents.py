"""Run topics through the 3-, 2- and 1-agent stage pipelines and compare them.

    uv run --group render --group layout python scripts/compare_agents.py --only T11 --only T12 \
        --agents 3 --agents 2 --agents 1 --model-id deepseek-v4.1-flash --out out/cmp-run1 [--jobs 3] [--open]

Each (topic, agents) pair goes to <out>/<slug>/a<N>/ (run.log, video.mp4, timings.json for 1/2).
Prints a table (status, wall time, model calls, repairs) and writes <out>/sheet.png: one row
per (topic, agents), four frames each, plus <out>/summary.json.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import topics as T  # noqa: E402  (load_topics, frames, FRAMES/FRAME_W/FRAME_H)

REPO = T.REPO


def run_one(topic: dict, agents: int, out_root: Path, model_id: str | None, theme: str) -> dict:
    out = out_root / topic["slug"] / f"a{agents}"
    out.mkdir(parents=True, exist_ok=True)
    if agents == 3:
        cmd = [sys.executable, "run_konvey.py", "--prompt", topic["prompt"],
               "--theme", theme, "--render", "--out-dir", str(out)]
    else:
        cmd = [sys.executable, "run_konvey_lean.py", "--agents", str(agents), "--prompt", topic["prompt"],
               "--theme", theme, "--render", "--out-dir", str(out)]
    if model_id:
        cmd += ["--model-id", model_id]
    start = time.time()
    with open(out / "run.log", "w") as log:
        proc = subprocess.run(cmd, cwd=str(REPO), stdout=log, stderr=subprocess.STDOUT, env=dict(os.environ))
    video = out / "video.mp4"
    timings = json.loads((out / "timings.json").read_text()) if (out / "timings.json").exists() else {}
    cost = json.loads((out / "cost.json").read_text())["total"] if (out / "cost.json").exists() else {}
    rejected = sorted(p.name.split(".")[0].removeprefix("agent3-") for p in out.glob("agent3-S*.problems.txt"))
    repairs = (out / "repair-log.txt").read_text().count("## ") if (out / "repair-log.txt").exists() else None
    return {"id": f"{topic['id']}-a{agents}", "slug": topic["slug"], "agents": agents, "rc": proc.returncode,
            "secs": round(time.time() - start), "video": video if video.exists() and video.stat().st_mtime >= start else None,
            "rejected": rejected, "repairs": repairs, "timings": timings, "cost": cost}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--only", action="append", default=[], help="topic id; repeatable")
    p.add_argument("--pair", action="append", default=[], help="TOPIC:AGENTS, e.g. T11:1; repeatable")
    p.add_argument("--agents", action="append", type=int, choices=[1, 2, 3], help="repeatable (default 3,2,1)")
    p.add_argument("--model-id")
    p.add_argument("--theme", default="editorial")
    p.add_argument("--jobs", type=int, default=3)
    p.add_argument("--out", required=True)
    p.add_argument("--open", action="store_true")
    args = p.parse_args()
    out_root = (REPO / args.out).resolve()
    T.OUT = out_root
    topics = [t for t in T.load_topics() if t["id"] in args.only]
    pairs = [(t, a) for t in topics for a in (args.agents or [3, 2, 1])]
    by_id = {t["id"]: t for t in T.load_topics()}
    pairs += [(by_id[tid], int(a)) for tid, a in (x.split(":") for x in args.pair)]
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(lambda ta: run_one(*ta, out_root, args.model_id, args.theme), pairs))
    for r in results:
        status = "ok" if r["video"] and not r["rejected"] else "PROBLEM"
        calls = r["timings"].get("model_calls", "-")
        usd = r["cost"].get("usd")
        cost = "n/a" if usd is None else f"${usd:.4f}"
        print(f"{r['id']:8} {r['slug']:20} {status:8} rc={r['rc']} {r['secs']:5}s calls={calls} cost={cost} "
              f"repairs={r['repairs']} rejected={r['rejected'] or '-'}", flush=True)
    (out_root / "summary.json").write_text(json.dumps(
        [{**r, "video": str(r["video"]) if r["video"] else None} for r in results], indent=2))
    sheet = T.contact_sheet(results)
    print(sheet)
    if args.open:
        subprocess.Popen(["imv", str(sheet)], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
