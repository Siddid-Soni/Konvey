"""Per-beat preview stills for a Konvey run.

The harness reviews the video before paying for a render. This module plays each scene
headless with the engine's own layout and animations, saves the frame at the end of every
beat, and tiles them into one labelled sheet.

    # all scenes of a run
    uv run --group render --group layout python -m konvey.mcp.preview out/run-dir

    # one scene
    uv run --group render --group layout python -m konvey.mcp.preview out/run-dir S2

The still capture is a ``StageScene`` subclass: it overrides ``_hold`` and calls
``get_image()`` after each beat, so the engine needs no preview hook of its own. The
parent process never imports manimgl; each scene is captured in a subprocess, as
``konvey.stage.check`` already does.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .runs import (REPO_ROOT, Run, atomic_write_json, now_iso, validate_scenes,
                   write_engine_wrappers)

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
TILE_W, TILE_H = 400, 225
CAPTION_H = 52
COLS = 4
HEADER_H = 58


# --- subprocess side: play one scene and save a still per beat --------------------------

def _capture_worker(html_path: str | Path, out_dir: str | Path, sid: str, theme: str,
                    highlight: str | None, prelude: str | Path | None) -> dict:
    """Play one scene with animations skipped and save every beat's end frame.

    Runs inside a subprocess (manimgl has global state and wants a fresh process). Returns
    the beats captured so far even when a later beat fails, so the harness can review the
    good part and fix the named beat.
    """
    beats_meta: list[dict] = []
    # manimgl parses sys.argv at import time; our --capture arguments are not its own.
    saved_argv = sys.argv
    sys.argv = sys.argv[:1]
    try:
        from konvey.stage.scene import StageScene, beat_hold
    except Exception as e:  # noqa: BLE001 - the render stack may not be installed
        return {"ok": False, "beats": [],
                "error": f"render stack unavailable: {type(e).__name__}: {e}"}
    finally:
        sys.argv = saved_argv

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _beats = str(html_path)
    _prelude = str(prelude) if prelude else ""
    _theme = theme
    _highlight = highlight or ""
    _scene = sid

    class _Stills(StageScene):
        beats_file = _beats
        prelude_file = _prelude
        theme = _theme
        highlight = _highlight
        still_dir = out_dir
        scene_id = _scene

        def _hold(self, b, on_screen, nodes, ws, cs):
            super()._hold(b, on_screen, nodes, ws, cs)
            if self.has_prelude and b.index == 0:
                return  # the carried-over frame is the previous scene's last beat
            n = b.index - (1 if self.has_prelude else 0)
            still = self.still_dir / f"{self.scene_id}-beat-{n:02d}.png"
            self.update_frame(force_draw=True)
            image = self.get_image()
            if image is None:
                raise RuntimeError("the renderer returned no frame")
            image.save(still)
            t = _number(b.attrs.get("t"), 1.6)
            beats_meta.append({
                "scene": self.scene_id,
                "beat": n,
                "vo": b.attrs.get("vo", ""),
                "t": t,
                "hold": round(beat_hold(b), 2),
                "seconds": round(t + 0.4 + beat_hold(b), 2),
                "still": str(still),
            })

    try:
        _Stills(skip_animations=True, file_writer_config={"write_to_movie": False}).run()
        return {"ok": True, "beats": beats_meta}
    except Exception as e:  # noqa: BLE001 - everything goes back to the harness
        import traceback

        return {"ok": False, "beats": beats_meta,
                "error": f"{type(e).__name__}: {e}",
                "traceback": traceback.format_exc()[-4000:]}


def _number(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _gpu_env() -> dict[str, str]:
    """PRIME offload, exactly as a normal render uses it."""
    try:
        from konvey.render import _gpu_env as gpu_env

        return gpu_env()
    except Exception:  # noqa: BLE001 - never block previews on GPU detection
        return {}


def _capture_subprocess(html_path: Path, out_dir: Path, sid: str, theme: str,
                        highlight: str | None, prelude: Path | None,
                        timeout: float) -> dict:
    cmd = [sys.executable, "-m", "konvey.mcp.preview", "--capture",
           str(html_path), str(out_dir), sid, theme, highlight or "",
           str(prelude) if prelude else ""]
    pythonpath = [str(REPO_ROOT)]
    if os.environ.get("PYTHONPATH"):
        pythonpath.append(os.environ["PYTHONPATH"])
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(pythonpath), **_gpu_env()}
    try:
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True,
                              timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return {"ok": False, "beats": [], "error": f"preview timed out after {timeout:.0f}s"}
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith("PREVIEW_RESULT "):
            try:
                return json.loads(line[len("PREVIEW_RESULT "):])
            except json.JSONDecodeError:
                break
    tail = (proc.stderr or proc.stdout).strip().splitlines()[-8:]
    return {"ok": False, "beats": [],
            "error": "preview crashed: " + " | ".join(tail) if tail else "preview crashed"}


# --- parent side: every scene, then one sheet ------------------------------------------

def _font(size: int):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except OSError:
        try:
            return ImageFont.load_default(size=size)
        except TypeError:  # Pillow before 10.1
            return ImageFont.load_default()


def make_sheet(path: str | Path, beats: list[dict], topic: str = "", run_id: str = "") -> Path | None:
    """Tile the beat stills into one labelled PNG. Returns None when there is nothing to show."""
    rows = [b for b in beats if b.get("still") and Path(b["still"]).is_file()]
    if not rows:
        return None
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = min(COLS, len(rows))
    height = HEADER_H + ((len(rows) + cols - 1) // cols) * (TILE_H + CAPTION_H)
    sheet = Image.new("RGB", (cols * TILE_W, height), (20, 20, 20))
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 9), topic or run_id or "Konvey preview", fill="white", font=_font(17))
    draw.text((12, 32), f"{len(rows)} beat{'s' if len(rows) != 1 else ''}  ·  {run_id}",
              fill=(170, 170, 170), font=_font(12))

    for i, beat in enumerate(rows):
        x = (i % cols) * TILE_W
        y = HEADER_H + (i // cols) * (TILE_H + CAPTION_H)
        try:
            with Image.open(beat["still"]) as image:
                image = image.convert("RGB")
                image.thumbnail((TILE_W, TILE_H), Image.LANCZOS)
                sheet.paste(image, (x + (TILE_W - image.width) // 2,
                                    y + (TILE_H - image.height) // 2))
        except OSError:
            pass
        draw.rectangle([x, y, x + TILE_W - 1, y + TILE_H - 1], outline=(58, 58, 58))
        label = f'{beat.get("scene", "?")} b{beat.get("beat", "?")} · {beat.get("seconds", "?")}s'
        draw.text((x + 6, y + TILE_H + 4), label, fill="white", font=_font(13))
        vo = (beat.get("vo") or "").strip()
        if vo:
            lines = textwrap.wrap(vo, width=58)[:2]
            draw.multiline_text((x + 6, y + TILE_H + 20), "\n".join(lines),
                                fill=(165, 165, 165), font=_font(11), spacing=2)
    sheet.save(path)
    return path


def capture_run(run: Run, scenes=None, timeout: float = 240.0) -> dict:
    """Capture stills for the requested scenes and write ``preview/sheet.png`` + ``index.json``."""
    ids = validate_scenes(run, scenes)
    wrappers = write_engine_wrappers(run, ids)
    out_dir = run.preview_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    for sid in ids:  # a re-preview replaces that scene's stills
        for old in out_dir.glob(f"{sid}-beat-*.png"):
            old.unlink(missing_ok=True)
    all_ids = run.scene_ids()
    all_beats: list[dict] = []
    scenes_out: dict[str, dict] = {}
    ok = True

    for sid in ids:
        position = all_ids.index(sid)
        previous = all_ids[position - 1] if position else None
        prelude = (run.engine_dir() / f"agent3-{previous}.html") if previous else None
        html = wrappers[sid].with_suffix(".html")
        result = _capture_subprocess(html, out_dir, sid, str(run.data["theme"]),
                                     run.data.get("highlight"), prelude, timeout)
        beats = result.get("beats", [])
        all_beats.extend(beats)
        problems = []
        if not result.get("ok"):
            problems.append(result.get("error") or "preview failed")
        if not beats and not problems:
            problems.append("no beats captured")
        scenes_out[sid] = {"ok": not problems,
                           "stills": [b["still"] for b in beats],
                           "problems": problems}
        ok = ok and not problems

    order = {sid: i for i, sid in enumerate(all_ids)}
    all_beats.sort(key=lambda b: (order.get(b.get("scene"), 99), b.get("beat", 0)))
    sheet = make_sheet(out_dir / "sheet.png", all_beats, run.topic, run.id)
    index = out_dir / "index.json"
    atomic_write_json(index, {
        "run_id": run.id,
        "topic": run.topic,
        "generated_at": now_iso(),
        "beats": all_beats,
    })

    artifacts = run.data.setdefault("artifacts", {})
    if sheet is not None:
        artifacts["sheet"] = str(sheet)
    artifacts["preview_index"] = str(index)
    artifacts["stills"] = len(all_beats)
    if ok and ids == all_ids:
        run.data["status"] = "previewed"
    run.save()

    return {
        "ok": ok,
        "sheet": str(sheet) if sheet is not None else None,
        "index": str(index),
        "scenes": scenes_out,
        "beats": all_beats,
    }


# --- CLI ------------------------------------------------------------------------------

def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["--capture"]:
        if len(args) < 7:
            print("usage: python -m konvey.mcp.preview --capture <html> <out> <sid> <theme> "
                  "<highlight|''> <prelude|''>", file=sys.stderr)
            return 2
        html, out, sid, theme, highlight, prelude = args[1:7]
        result = _capture_worker(html, out, sid, theme, highlight or None,
                                 prelude or None)
        print("PREVIEW_RESULT " + json.dumps(result), flush=True)
        return 0 if result.get("ok") else 1

    parser = argparse.ArgumentParser(description="Per-beat preview stills for a Konvey run")
    parser.add_argument("run_dir", help="The run directory (with run.json and S1.html …)")
    parser.add_argument("scenes", nargs="*", help="Scene ids to capture (default: all)")
    parser.add_argument("--timeout", type=float, default=240.0, help="Seconds per scene")
    ns = parser.parse_args(args)
    run = Run.from_dir(ns.run_dir)
    result = capture_run(run, ns.scenes or None, timeout=ns.timeout)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
