"""Render a run's scenes with manimgl and join them into ``video.mp4``.

The MCP server starts this in a detached job. The worker writes the engine wrappers, renders
the requested scenes in parallel (``KONVEY_RENDER_JOBS``, default 3), joins them with
``konvey.render.concat``, and copies the result to the run root.

    python -m konvey.mcp.render out/run-dir [S1 S2] [--preview]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from konvey import render as engine_render

from .runs import Run, now_iso, validate_scenes, write_engine_wrappers


def _render_scene(out_dir: Path, sid: str, preview: bool, fps: int) -> Path:
    """Render one scene, like ``konvey.render.render_scene`` but with a configurable fps.

    The 30 fps default is smooth but pays for every transition frame; 24 fps is ~20% fewer
    frames and looks fine for a math explainer. Holds are cheap either way.
    """
    video_dir = out_dir / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    quality = ["-r", "854x480"] if preview else ["--hd"]
    env = {"PYTHONPATH": str(engine_render.REPO_ROOT / "render"),
           **engine_render._env(), **engine_render._gpu_env()}
    codec = ["--vcodec", "h264_nvenc"] if engine_render._nvenc() else []
    cmd = [engine_render._manimgl(), str(out_dir / f"agent3-{sid}.py"), "SingleScene", "-w",
           *quality, *codec,
           "--video_dir", str(video_dir), "--file_name", sid]
    print(f"      rendering {sid} at {fps} fps ...", flush=True)
    with open(out_dir / f"render-{sid}.log", "w") as fh:
        proc = subprocess.run(cmd, cwd=str(engine_render.REPO_ROOT), stdout=fh,
                              stderr=subprocess.STDOUT, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"{sid} failed to render; see {out_dir / f'render-{sid}.log'}")
    return video_dir / f"{sid}.mp4"


def render_run(run: Run, scenes=None, preview: bool = False, fps: int = 24) -> dict:
    """Render the requested scenes and join them. Raises if a scene fails.

    ``fps`` defaults to 24 for the MCP path (the CLI's default is 30). Use 30 when smooth
    camera moves matter more than render time; use 20 for a quick draft.
    """
    try:
        fps = int(fps)
    except (TypeError, ValueError):
        raise ValueError("fps must be an integer") from None
    if not 10 <= fps <= 60:
        raise ValueError("fps must be between 10 and 60")
    ids = validate_scenes(run, scenes)
    write_engine_wrappers(run, ids, fps=fps)
    out_dir = run.engine_dir()
    workers = max(1, int(os.environ.get("KONVEY_RENDER_JOBS", "3")))
    started = time.monotonic()

    run.data["status"] = "rendering"
    run.save()

    def one(sid: str) -> Path:
        return _render_scene(out_dir, sid, preview, fps)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        parts = list(pool.map(one, ids))
    joined = engine_render.concat(out_dir, parts)

    suffix = "video-preview.mp4" if preview else "video.mp4"
    target = run.directory / suffix
    shutil.copyfile(joined, target)
    elapsed = round(time.monotonic() - started, 1)

    artifacts = run.data.setdefault("artifacts", {})
    artifacts["video_preview" if preview else "video"] = str(target)
    artifacts["rendered_at"] = now_iso()
    artifacts["render_scenes"] = ids
    artifacts["fps"] = fps
    all_ids = run.scene_ids()
    if not preview and ids == all_ids:
        run.data["status"] = "done"
    else:
        run.data["status"] = "previewed" if preview else "rendered-partial"
    run.save()

    return {
        "ok": True,
        "video": str(target),
        "preview": preview,
        "scenes": ids,
        "fps": fps,
        "elapsed_sec": elapsed,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Render a Konvey run")
    parser.add_argument("run_dir")
    parser.add_argument("scenes", nargs="*", help="Scene ids (default: all)")
    parser.add_argument("--preview", action="store_true", help="Render at 480p")
    parser.add_argument("--fps", type=int, default=24, help="Frame rate (default 24; 30 is smoother)")
    ns = parser.parse_args(sys.argv[1:] if argv is None else argv)
    run = Run.from_dir(ns.run_dir)
    result = render_run(run, ns.scenes or None, preview=ns.preview, fps=ns.fps)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
