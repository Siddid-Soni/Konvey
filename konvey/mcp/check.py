"""Checks for a Konvey run: the engine's static and runtime checks plus MCP rules.

``check_static_run`` is fast and runs in the MCP process. ``check_runtime_run`` plays each
scene headless and belongs in a job (it starts manimgl). The server runs the static layer
first, then submits the runtime layer so a 30 s client timeout cannot lose the work.

    python -m konvey.mcp.check out/run-dir [S1 S2] [--no-runtime]
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from types import SimpleNamespace

from ..stage import theme as themes
from ..stage.check import check_runtime, check_static
from ..stage.parse import BeatError, parse_beats, prepare_beats
from .runs import Run, validate_scenes

WORDS_PER_SEC = 2.7       # the stage's narration pace (konvey/stage/scene.py)
MIN_BEATS, MAX_BEATS = 3, 15
MAX_VO_WORDS = 22
PLACEHOLDERS = ("TODO", "FIXME", "TBD", "LOREM IPSUM")
_STATIC_LOCK = threading.Lock()   # themes.use() is process-global


def _number(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _hold(beat) -> float:
    words = len((beat.attrs.get("vo") or "").split())
    return max(1.5, words / WORDS_PER_SEC - _number(beat.attrs.get("t"), 1.6))


def _estimate(beats) -> float:
    return sum(_number(b.attrs.get("t"), 1.6) + 0.4 + _hold(b) for b in beats)


def _mcp_rules(run: Run, sid: str, html: str, static: list[str]) -> tuple[list[str], list[str]]:
    """Errors and warnings the engine's static check does not cover."""
    errors: list[str] = []
    warnings: list[str] = []
    if any(p.startswith("parse error") for p in static):
        return errors, warnings
    try:
        beats = parse_beats(html)
        prepare_beats(beats)
    except (BeatError, ValueError) as e:
        return [f"parse error: {e}"], warnings
    if not beats:
        return ["scene has no <beat> elements"], warnings

    for b in beats:
        vo = (b.attrs.get("vo") or "").strip()
        if not vo:
            errors.append(f"beat {b.index}: <beat> needs a vo line")
        elif len(vo.split()) > MAX_VO_WORDS:
            warnings.append(f"beat {b.index}: vo is {len(vo.split())} words; aim for {MAX_VO_WORDS} or fewer")
        for mark in PLACEHOLDERS:
            if mark in b.attrs.get("vo", "").upper():
                errors.append(f"beat {b.index}: vo contains the placeholder {mark!r}")

    try:
        text = run.scene_path(sid).read_text(encoding="utf-8").upper()
        for mark in PLACEHOLDERS:
            if mark in text:
                errors.append(f"scene contains the placeholder {mark!r}")
    except OSError:
        pass

    if len(beats) < MIN_BEATS:
        warnings.append(f"scene has {len(beats)} beats; a 30 s scene is usually {MIN_BEATS}–{MAX_BEATS}")
    elif len(beats) > MAX_BEATS:
        warnings.append(f"scene has {len(beats)} beats; split it or aim for {MAX_BEATS} or fewer")

    target = float(run.data.get("duration_sec", 90)) / max(1, len(run.scene_ids()))
    seconds = _estimate(beats)
    if seconds < 0.5 * target or seconds > 1.8 * target:
        warnings.append(f"scene is about {seconds:.0f}s; the target is about {target:.0f}s")

    # The engine's letterbox-close rule names S3; with 1-2 scenes the last scene is not S3.
    all_ids = run.scene_ids()
    if len(all_ids) != 3:
        static[:] = [p for p in static
                     if 'letterbox="close" only on the last beat of S3' not in p]
        for b in beats:
            if b.attrs.get("letterbox") == "close" and not (
                    sid == all_ids[-1] and b.index == len(beats) - 1):
                errors.append(f'beat {b.index}: letterbox="close" only on the last beat of '
                              f"{all_ids[-1]}")
    return errors, warnings


def check_static_run(run: Run, scenes=None) -> dict:
    """Fast checks: parse, theme, sizes, engine rules, and the MCP beat rules."""
    with _STATIC_LOCK:
        ids = validate_scenes(run, scenes)
        themes.use(str(run.data["theme"]), run.data.get("highlight"))
        scenes_out = {}
        ok = True
        for sid in ids:
            html = run.read_scene(sid)
            try:
                problems = check_static(html, SimpleNamespace(id=sid, beats=[]))
            except Exception as e:  # noqa: BLE001 - a malformed scene is a check result
                problems = [f"static check failed: {type(e).__name__}: {e}"]
            errors, warnings = _mcp_rules(run, sid, html, problems)
            scene_ok = not problems and not errors
            scenes_out[sid] = {
                "ok": scene_ok,
                "static": problems,
                "errors": errors,
                "warnings": warnings,
            }
            ok = ok and scene_ok
        return {"ok": ok, "checked_runtime": False, "scenes": scenes_out,
                "problems": sum(len(s["static"]) + len(s["errors"]) for s in scenes_out.values()),
                "warnings": sum(len(s["warnings"]) for s in scenes_out.values())}


def check_runtime_run(run: Run, scenes=None, timeout: float = 300.0) -> dict:
    """Play each scene headless and collect layout, LaTeX, attribute and frame problems."""
    ids = validate_scenes(run, scenes)
    themes.use(str(run.data["theme"]), run.data.get("highlight"))
    all_ids = run.scene_ids()
    scenes_out = {}
    ok = True
    for sid in ids:
        position = all_ids.index(sid)
        previous = all_ids[position - 1] if position else None
        prelude = None
        if previous:
            try:
                prelude = run.read_scene(previous)
            except OSError:
                prelude = None
        workdir = run.engine_dir() / "check" / sid
        try:
            problems = check_runtime(run.read_scene(sid), workdir, sid,
                                     timeout=timeout, prelude_html=prelude)
        except Exception as e:  # noqa: BLE001 - a render-stack failure is a check result
            problems = [f"runtime check failed: {type(e).__name__}: {e}"]
        scenes_out[sid] = {"ok": not problems, "problems": problems}
        ok = ok and not problems
    return {"ok": ok, "checked_runtime": True, "scenes": scenes_out,
            "problems": sum(len(s["problems"]) for s in scenes_out.values())}


def check_run(run: Run, scenes=None, runtime: bool = True, timeout: float = 300.0) -> dict:
    """Static + runtime in one call (the runtime layer is usually run as a job)."""
    static = check_static_run(run, scenes)
    if not runtime:
        return {"ok": static["ok"], "checked_runtime": False, "static": static,
                "runtime": None, "scenes": static["scenes"]}
    runtime_result = check_runtime_run(run, scenes, timeout=timeout)
    scenes = {sid: {**static["scenes"].get(sid, {}), "runtime": runtime_result["scenes"].get(sid, {})}
              for sid in static["scenes"]}
    return {"ok": static["ok"] and runtime_result["ok"], "checked_runtime": True,
            "static": static, "runtime": runtime_result, "scenes": scenes,
            "problems": static["problems"] + runtime_result["problems"],
            "warnings": static["warnings"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check a Konvey run")
    parser.add_argument("run_dir")
    parser.add_argument("scenes", nargs="*", help="Scene ids (default: all)")
    parser.add_argument("--no-runtime", action="store_true", help="Skip the headless play")
    parser.add_argument("--timeout", type=float, default=300.0, help="Seconds per scene")
    ns = parser.parse_args(sys.argv[1:] if argv is None else argv)
    run = Run.from_dir(ns.run_dir)
    result = check_run(run, ns.scenes or None, runtime=not ns.no_runtime, timeout=ns.timeout)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
