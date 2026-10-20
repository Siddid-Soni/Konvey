"""Render a run's ``agent3-S*.py`` scenes with manimgl and join them into ``video.mp4``.

    uv run --group render --group layout python -m konvey.render out/stage-shadows [--preview] [--theme NAME] \
        [--highlight COLOR]

``--theme`` rewrites each stage wrapper's recorded theme before rendering; ``--highlight`` its
highlight colour (a theme colour such as c2, or a hex; "" for the theme's accent).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def set_theme(py: Path, theme: str) -> None:
    """Point a stage wrapper at ``theme`` (adds the line to wrappers written before themes)."""
    from .stage.theme import get_theme

    get_theme(theme)
    src = py.read_text(encoding="utf-8")
    if "StageScene" not in src and "SpeechScene" not in src:   # SpeechScene: narrated runs
        return
    line = f"    theme = {theme!r}\n"
    src, n = re.subn(r"^    theme = .*\n", line, src, flags=re.M)
    if not n:
        src = src.rstrip("\n") + "\n" + line
    py.write_text(src, encoding="utf-8")


def set_highlight(py: Path, color: str) -> None:
    """Record the video's highlight colour in a stage wrapper (``""`` puts back the accent)."""
    src = py.read_text(encoding="utf-8")
    if "StageScene" not in src and "SpeechScene" not in src:
        return
    line = f"    highlight = {color!r}\n"
    src, n = re.subn(r"^    highlight = .*\n", line, src, flags=re.M)
    if not n:
        src = src.rstrip("\n") + "\n" + line
    py.write_text(src, encoding="utf-8")


def render_run(out_dir: str | Path, preview: bool = False, log=print, theme: str | None = None,
               highlight: str | None = None) -> Path:
    out_dir = Path(out_dir).resolve()
    video_dir = out_dir / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    parts = []
    for py in sorted(out_dir.glob("agent3-S*.py")):
        sid = py.stem.split("-")[-1]
        if theme:
            set_theme(py, theme)
        if highlight is not None:
            set_highlight(py, highlight)
        quality = ["-r", "854x480"] if preview else ["--hd"]
        cmd = ["manimgl", str(py), "SingleScene", "-w", *quality,
               "--video_dir", str(video_dir), "--file_name", sid]
        log(f"      rendering {sid} ...")
        with open(out_dir / f"render-{sid}.log", "w") as fh:
            proc = subprocess.run(cmd, cwd=str(REPO_ROOT), stdout=fh, stderr=subprocess.STDOUT,
                                  env={"PYTHONPATH": str(REPO_ROOT / "render"), **_env()})
        if proc.returncode != 0:
            raise RuntimeError(f"{sid} failed to render; see {out_dir / f'render-{sid}.log'}")
        parts.append(video_dir / f"{sid}.mp4")
    listing = video_dir / "parts.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
    video = out_dir / "video.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-c", "copy", str(video)], check=True)
    return video


def _env() -> dict[str, str]:
    import os

    return dict(os.environ)


if __name__ == "__main__":
    args = sys.argv[1:]
    name = args[args.index("--theme") + 1] if "--theme" in args else None
    lit = args[args.index("--highlight") + 1] if "--highlight" in args else None
    print(render_run(args[0], preview="--preview" in args, theme=name, highlight=lit))
