"""Render a run's ``agent3-S*.py`` scenes with manimgl and join them into ``video.mp4``.

    uv run --group render --group layout python -m konvey.render out/stage-shadows [--preview] [--theme NAME] \
        [--highlight COLOR]

``--theme`` rewrites each stage wrapper's recorded theme before rendering; ``--highlight`` its
highlight colour (a theme colour such as c2, or a hex; "" for the theme's accent).

Scenes render in parallel (``KONVEY_RENDER_JOBS``, default one per two cores, at most 8), drawn on the NVIDIA GPU of a hybrid laptop (PRIME
offload; manimgl's OpenGL context otherwise lands on the integrated GPU) and encoded with NVENC when ffmpeg can.
``KONVEY_RENDER_GPU=default`` keeps the system's GPU and libx264. On the 3070 Ti laptop, 3 HD scenes: 91 s one
after another on the iGPU with libx264, 29 s in parallel on the NVIDIA GPU with NVENC (~0.5 GB VRAM a scene;
NVENC's default rate makes ~3x bigger files).
"""

from __future__ import annotations

import functools
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
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


def scene_ids(out_dir: str | Path) -> list[str]:
    """The run's scenes (``S1``, ``S2`` ...), in the order they are joined."""
    return [py.stem.split("-")[-1] for py in _scene_files(out_dir)]


def _scene_files(out_dir: str | Path) -> list[Path]:
    """The run's stage wrappers in scene order (S2 before S10)."""
    def key(py: Path):
        m = re.search(r"S(\d+)$", py.stem)
        return (int(m.group(1)) if m else 0, py.stem)
    return sorted(Path(out_dir).glob("agent3-S*.py"), key=key)


def style_scenes(out_dir: str | Path, theme: str | None = None, highlight: str | None = None) -> None:
    """Record ``theme`` / ``highlight`` in every stage wrapper of the run (before any scene renders)."""
    for py in _scene_files(out_dir):
        if theme:
            set_theme(py, theme)
        if highlight is not None:
            set_highlight(py, highlight)


def _manimgl() -> str:
    """The manimgl of the running environment: a worker started as .venv-gpu/bin/mayu doesn't have that venv's bin
    on PATH, so a bare "manimgl" isn't found there."""
    here = Path(sys.executable).parent / "manimgl"
    return str(here) if here.exists() else "manimgl"


def render_scene(out_dir: str | Path, sid: str, preview: bool = False, log=print) -> Path:
    """Render one scene of a run to ``video/<sid>.mp4``. Scenes are independent (continuity reads the previous
    scene's beats, not its video), so any number of them can render at once."""
    out_dir = Path(out_dir).resolve()
    video_dir = out_dir / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    quality = ["-r", "854x480"] if preview else ["--hd"]
    env = {"PYTHONPATH": str(REPO_ROOT / "render"), **_env(), **_gpu_env()}
    codec = ["--vcodec", "h264_nvenc"] if _nvenc() else []
    cmd = [_manimgl(), str(out_dir / f"agent3-{sid}.py"), "SingleScene", "-w", *quality, *codec,
           "--video_dir", str(video_dir), "--file_name", sid]
    log(f"      rendering {sid} ...")
    with open(out_dir / f"render-{sid}.log", "w") as fh:
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT), stdout=fh, stderr=subprocess.STDOUT, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"{sid} failed to render; see {out_dir / f'render-{sid}.log'}")
    return video_dir / f"{sid}.mp4"


def concat(out_dir: str | Path, parts: list[Path]) -> Path:
    """Join the rendered scenes, in order, into ``<out_dir>/video.mp4`` (no re-encode)."""
    out_dir = Path(out_dir).resolve()
    video_dir = out_dir / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    listing = video_dir / "parts.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
    video = out_dir / "video.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-c", "copy", str(video)], check=True)
    return video


def render_run(out_dir: str | Path, preview: bool = False, log=print, theme: str | None = None,
               highlight: str | None = None) -> Path:
    out_dir = Path(out_dir).resolve()
    style_scenes(out_dir, theme, highlight)
    # each scene is one Python process on one core (the GPU draws, NVENC encodes): run many at once
    jobs = max(1, int(os.environ.get("KONVEY_RENDER_JOBS", str(min(8, max(1, (os.cpu_count() or 2) // 2))))))
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        parts = list(pool.map(lambda sid: render_scene(out_dir, sid, preview, log), scene_ids(out_dir)))
    return concat(out_dir, parts)


def _env() -> dict[str, str]:
    return dict(os.environ)


def _use_nvidia() -> bool:
    if os.environ.get("KONVEY_RENDER_GPU", "auto") == "default":
        return False
    return Path("/proc/driver/nvidia/version").exists()


def _gpu_env() -> dict[str, str]:
    """PRIME render offload: harmless where the NVIDIA GPU already drives the display."""
    if not _use_nvidia():
        return {}
    return {"__NV_PRIME_RENDER_OFFLOAD": "1", "__GLX_VENDOR_LIBRARY_NAME": "nvidia"}


@functools.cache
def _nvenc() -> bool:
    """Whether ffmpeg can encode with NVENC here: a build with it can still lack the driver or a free session."""
    if not _use_nvidia():
        return False
    probe = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=s=256x256:d=0.1", "-c:v", "h264_nvenc",
             "-f", "null", "-"]
    try:
        return subprocess.run(probe, capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


if __name__ == "__main__":
    args = sys.argv[1:]
    name = args[args.index("--theme") + 1] if "--theme" in args else None
    lit = args[args.index("--highlight") + 1] if "--highlight" in args else None
    print(render_run(args[0], preview="--preview" in args, theme=name, highlight=lit))
