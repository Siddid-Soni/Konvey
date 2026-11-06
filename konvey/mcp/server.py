"""The Konvey MCP server.

A coding harness calls these tools to make a silent 3Blue1Brown-style explainer video. The
harness does the research, script, storyboard and beat HTML; Konvey supplies the reference,
the checks, the preview stills and the renderer.

Run it from the Konvey checkout:

    uv run --group mcp --group render --group layout konvey-mcp

It speaks MCP over stdio. Runs live in ``<workspace>/.konvey/runs/<id>``; the workspace is
``--workspace``, then ``KONVEY_WORKSPACE``, then the process cwd.

Long operations (runtime check, preview, render) run as detached jobs. A tool waits up to
``wait_seconds`` and then returns ``status="running"``; poll ``konvey_status``.
"""

from __future__ import annotations

import argparse
import importlib.util
import logging
import os
import shutil
import sys
from pathlib import Path

try:  # MCP 2.x (current)
    from mcp.server.mcpserver import MCPServer

    _MCP2 = True
except ImportError:  # MCP 1.x fallback
    from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore[no-redef]

    _MCP2 = False

from . import docs, jobs
from .check import check_static_run
from .runs import (Run, load_run, new_run, validate_scenes, workspace_root)

log = logging.getLogger("konvey.mcp")

INSTRUCTIONS = """\
Konvey turns a topic into a silent 3Blue1Brown-style explainer video. The harness does the
thinking and writes the beat HTML; Konvey checks, previews and renders it.

Workflow: konvey_new_run -> research + write plan.md -> konvey_guide / konvey_displays /
konvey_example / konvey_simulate -> write S1.html..S3.html -> konvey_check -> konvey_preview ->
fix -> konvey_render -> konvey_status. Do not render before the preview sheet tells the story.
Every beat needs a vo line; compute every number; colours are theme names, never hex.
"""

mcp = MCPServer(
    name="konvey",
    instructions=INSTRUCTIONS,
    **({"title": "Konvey explainer-video engine", "version": "0.1.0"} if _MCP2 else {}),
)


def _error(e: BaseException) -> dict:
    return {"ok": False, "error": f"{type(e).__name__}: {e}" if not str(e) else str(e)}


def _run(run_id: str, workspace: str | None) -> Run:
    return load_run(run_id, workspace)


def _stack() -> dict:
    """What is installed; a missing piece should fail now, not after a long render."""
    has_manim = importlib.util.find_spec("manimlib") is not None
    has_playwright = importlib.util.find_spec("playwright") is not None
    chromium = Path("/usr/bin/chromium").exists()   # konvey.stage.layout.CHROMIUM
    ffmpeg = bool(shutil.which("ffmpeg"))
    latex = bool(shutil.which("latex") or shutil.which("pdflatex") or shutil.which("tectonic"))
    missing = [name for name, ok in (("manimgl", has_manim), ("playwright", has_playwright),
                                     ("chromium", chromium), ("ffmpeg", ffmpeg), ("latex", latex))
               if not ok]
    return {"manimgl": has_manim, "playwright": has_playwright, "chromium": chromium,
            "ffmpeg": ffmpeg, "latex": latex, "missing": missing,
            "hint": ("install the render/layout groups and LaTeX: uv run --group mcp "
                     "--group render --group layout konvey-mcp") if missing else ""}


# --- setup and reference -----------------------------------------------------------------

@mcp.tool()
def konvey_new_run(topic: str, workspace: str | None = None, scenes: int = 3,
                   duration: float = 90.0, theme: str = "editorial",
                   highlight: str | None = None, slug: str | None = None) -> dict:
    """Create a run directory with run.json and S1.html … S3.html.

    Args:
        topic: What the video explains, in one line.
        workspace: Project directory for .konvey/ (default: KONVEY_WORKSPACE or cwd).
        scenes: Number of scenes, 1..3 (default 3).
        duration: Target length in seconds (default 90).
        theme: "editorial" (default) or "classic".
        highlight: Highlight colour name (c1..c5, accent, ink) or a hex colour.
        slug: Optional run id slug; otherwise a dated slug of the topic.

    Returns the run id, directory, scene file paths, and the render-stack report.
    """
    try:
        run = new_run(topic, workspace=workspace, scenes=scenes, duration=duration,
                      theme=theme, highlight=highlight, slug=slug)
    except (ValueError, OSError) as e:
        return _error(e)
    return {
        "ok": True,
        "run_id": run.id,
        "directory": str(run.directory),
        "workspace": str(workspace_root(workspace)),
        "topic": run.topic,
        "scene_count": run.data["scene_count"],
        "duration_sec": run.data["duration_sec"],
        "theme": run.data["theme"],
        "highlight": run.data["highlight"],
        "scenes": [{"id": sid, "file": str(run.scene_path(sid))} for sid in run.scene_ids()],
        "render_stack": _stack(),
        "next": 'konvey_guide("workflow")',
    }


@mcp.tool()
def konvey_guide(section: str | None = None) -> str:
    """The Director reference, the MCP workflow, and how to review and fix scenes.

    Call with no section for the index. Useful sections: workflow, beats, shots, camera,
    parts, overlay, world, rules, themes, sims, marks, checks, review. "all" returns the
    whole reference (large; fetch it only when you need it).
    """
    return docs.guide(section)


@mcp.tool()
def konvey_displays(tag: str | None = None, kind: str | None = None) -> dict:
    """The overlay display catalog.

    No arguments: every tag with a one-line summary and an example to look at. With `tag`:
    that display's full attributes and docs. With `kind`: every display that draws that
    plan kind (plot, tex, places, graph, sim, …).
    """
    try:
        return docs.display_catalog(tag, kind)
    except (ValueError, OSError) as e:
        return _error(e)


@mcp.tool()
def konvey_example(name: str | None = None, kind: str | None = None,
                   genre: str | None = None) -> dict:
    """One worked scene from the Director's examples.

    No arguments: the example index. Otherwise the first example matching `name`, `kind` or
    `genre`. Copy its structure and display choices, never its topic, numbers or wording.
    """
    try:
        return docs.example(name, kind, genre)
    except (ValueError, OSError) as e:
        return _error(e)


@mcp.tool()
def konvey_simulate(rule: str | None = None, settings: str = "{}",
                    times: str = "end") -> str:
    """Run one of the engine's exact simulations, or list the rules.

    Call with no rule for the rule list and every setting (blocks, drop, spread, pendulum,
    circles, line, heat, walk). With a rule, `settings` is a JSON object and `times` is
    "end" or comma-separated model times. Use this for every number a `<sim>` shows.
    """
    try:
        return docs.simulate(rule, settings, times)
    except (ValueError, TypeError, OSError) as e:
        return f"ERROR: {e}"


# --- checks, preview, render --------------------------------------------------------------

@mcp.tool()
def konvey_check(run_id: str, scenes: list[str] | None = None, runtime: bool = True,
                 wait_seconds: float = 20.0, workspace: str | None = None) -> dict:
    """Check the beat HTML: static rules now, the headless play as a job.

    Static covers parsing, sizes, theme colours, display rules, and the MCP rules (vo on
    every beat, beat count, duration estimate, placeholders). Runtime lays out and plays
    each scene, catching overflow, LaTeX and frame-audit problems. If static fails, runtime
    is not started. If the runtime job outlasts `wait_seconds`, poll konvey_status.
    """
    try:
        run = _run(run_id, workspace)
        ids = validate_scenes(run, scenes)
        static = check_static_run(run, ids)
    except (ValueError, FileNotFoundError, OSError) as e:
        return _error(e)
    if not static["ok"] or not runtime:
        return {**static, "status": "done", "runtime": None}
    started = jobs.start(run, "check", ids, wait_seconds=wait_seconds)
    if started.get("status") == "done":
        result = (started.get("job") or {}).get("result") or {}
        merged = {sid: {**scene, "runtime": result.get("scenes", {}).get(sid, {})}
                  for sid, scene in static["scenes"].items()}
        return {**static, "scenes": merged, "runtime": result,
                "ok": static["ok"] and bool(result.get("ok")),
                "status": "done", "job": started.get("job")}
    if started.get("status") == "busy":
        return {**static, "status": "busy", "error": started.get("error"),
                "job": started.get("job"), "runtime": None}
    return {**static, "status": started.get("status", "running"),
            "job": started.get("job"), "job_id": (started.get("job") or {}).get("id"),
            "runtime": None}


@mcp.tool()
def konvey_preview(run_id: str, scenes: list[str] | None = None,
                   wait_seconds: float = 25.0, workspace: str | None = None) -> dict:
    """Render one still per beat and a labelled contact sheet, without encoding the video.

    Writes preview/sheet.png and preview/index.json. Open the sheet first, then individual
    stills for weak beats. If the job outlasts `wait_seconds`, poll konvey_status.
    """
    try:
        run = _run(run_id, workspace)
        ids = validate_scenes(run, scenes)
    except (ValueError, FileNotFoundError, OSError) as e:
        return _error(e)
    started = jobs.start(run, "preview", ids, wait_seconds=wait_seconds)
    if started.get("status") == "done":
        result = (started.get("job") or {}).get("result") or {}
        return {**result, "status": "done", "job": started.get("job")}
    if started.get("status") == "busy":
        return {"ok": False, "status": "busy", "error": started.get("error"),
                "job": started.get("job")}
    return {"ok": True, "status": started.get("status", "running"), "sheet": None,
            "job": started.get("job"), "job_id": (started.get("job") or {}).get("id")}


@mcp.tool()
def konvey_render(run_id: str, scenes: list[str] | None = None, preview: bool = False,
                  force: bool = False, fps: int = 24, wait_seconds: float = 0.0,
                  workspace: str | None = None) -> dict:
    """Render the scenes with manimgl and join them into video.mp4.

    `fps` defaults to 24: about 20% fewer frames than 30, still smooth enough for a math
    explainer. Use 30 when camera moves matter more than render time, 20 for a quick draft.
    The static check gates the render (pass `force=True` to override). Runs as a detached
    job; poll konvey_status(run_id). `preview=True` produces a 480p preview video.
    """
    try:
        fps = int(fps)
    except (TypeError, ValueError):
        return {"ok": False, "error": "fps must be an integer"}
    if not 10 <= fps <= 60:
        return {"ok": False, "error": "fps must be between 10 and 60"}
    try:
        run = _run(run_id, workspace)
        ids = validate_scenes(run, scenes)
        static = check_static_run(run, ids)
    except (ValueError, FileNotFoundError, OSError) as e:
        return _error(e)
    if not static["ok"] and not force:
        return {"ok": False, "status": "blocked", "static": static,
                "error": "static checks failed; fix them or pass force=True"}
    args = list(ids) + (["--preview"] if preview else []) + ["--fps", str(fps)]
    started = jobs.start(run, "render", args, wait_seconds=wait_seconds)
    if started.get("status") == "done":
        result = (started.get("job") or {}).get("result") or {}
        return {**result, "status": "done", "job": started.get("job")}
    if started.get("status") == "busy":
        return {"ok": False, "status": "busy", "error": started.get("error"),
                "job": started.get("job")}
    return {"ok": True, "status": started.get("status", "running"),
            "job": started.get("job"), "job_id": (started.get("job") or {}).get("id")}


@mcp.tool()
def konvey_status(run_id: str, job_id: str | None = None,
                  workspace: str | None = None) -> dict:
    """Poll a run's latest job (or a named job): state, log tail, elapsed time, artifacts.

    Use this after a tool returns status="running", and to recover a render after a server
    restart. State is on disk, so nothing is lost.
    """
    try:
        return jobs.status(_run(run_id, workspace), job_id)
    except (ValueError, FileNotFoundError, OSError) as e:
        return _error(e)


@mcp.tool()
def konvey_cancel(run_id: str, job_id: str | None = None,
                  workspace: str | None = None) -> dict:
    """Stop a run's active job (SIGTERM, then SIGKILL) and mark it cancelled."""
    try:
        return jobs.cancel(_run(run_id, workspace), job_id)
    except (ValueError, FileNotFoundError, OSError) as e:
        return _error(e)


# --- entry point -------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Konvey MCP server (stdio by default)")
    parser.add_argument("--workspace", default=None,
                        help="Project directory for .konvey/ (default: KONVEY_WORKSPACE or cwd)")
    parser.add_argument("--transport", default="stdio",
                        choices=["stdio", "sse", "streamable-http"],
                        help="MCP transport (default: stdio)")
    ns = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if ns.workspace:
        os.environ["KONVEY_WORKSPACE"] = str(Path(ns.workspace).expanduser().resolve())
    logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log.info("konvey MCP: workspace %s", workspace_root())
    mcp.run(transport=ns.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
