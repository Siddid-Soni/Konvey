"""Render the theme fixtures (tests/fixtures/theme-*.html) in every theme and stitch
one labelled sheet: one row per theme, one column per fixture.

    uv run --group render --group layout python scripts/theme_sheet.py [--open] [--theme NAME ...]

Writes out/themes/sheet.png (and the per-frame PNGs next to it).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from konvey.stage.theme import THEMES  # noqa: E402

FIXTURES = sorted((REPO / "tests/fixtures").glob("theme-*.html"))   # --fixtures overrides
W, H = 960, 540

WRAPPER = '''import sys
sys.path.insert(0, {root!r})
from konvey.stage.scene import StageScene


class SingleScene(StageScene):
    beats_file = {beats!r}
    theme = {theme!r}
'''


def render_frame(fixture: Path, theme: str, out: Path) -> Path:
    work = out / f"{theme}-{fixture.stem}"
    work.mkdir(parents=True, exist_ok=True)
    beats = work / "beats.html"
    shutil.copy(fixture, beats)
    py = work / "scene.py"
    py.write_text(WRAPPER.format(root=str(REPO), beats=str(beats), theme=theme))
    cmd = ["manimgl", str(py), "SingleScene", "-w", "-s", "-r", f"{W}x{H}",
           "--video_dir", str(work), "--file_name", "frame"]
    proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True,
                          env={**__import__("os").environ, "PYTHONPATH": str(REPO / "render")})
    pngs = sorted(work.rglob("*.png"), key=lambda p: p.stat().st_mtime)
    if proc.returncode != 0 or not pngs:
        raise RuntimeError(f"{theme}/{fixture.name} failed:\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")
    return pngs[-1]


def sheet(frames: dict[tuple[str, str], Path], themes: list[str], out: Path) -> Path:
    cols = [f.stem for f in FIXTURES]
    inputs, labelled = [], []
    for r, t in enumerate(themes):
        for c, name in enumerate(cols):
            inputs += ["-i", str(frames[t, name])]
            k = r * len(cols) + c
            labelled.append(f"[{k}:v]scale={W}:{H},drawtext=text='{t} / {name}':x=12:y=H-30:"
                            f"fontcolor=white:fontsize=18:box=1:boxcolor=black@0.6[v{k}]")
    n = len(themes) * len(cols)
    layout = "|".join(f"{c * W}_{r * H}" for r in range(len(themes)) for c in range(len(cols)))
    graph = ";".join(labelled) + ";" + "".join(f"[v{k}]" for k in range(n))
    graph += f"xstack=inputs={n}:layout={layout}" if n > 1 else "null"
    path = out / "sheet.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph, str(path)], check=True)
    return path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--theme", action="append", choices=list(THEMES))
    p.add_argument("--open", action="store_true", help="show the sheet with imv")
    p.add_argument("--fixtures", default="theme-*.html", help="glob in tests/fixtures (default theme-*.html)")
    args = p.parse_args()
    global FIXTURES
    FIXTURES = sorted((REPO / "tests/fixtures").glob(args.fixtures))
    themes = args.theme or list(THEMES)
    out = REPO / "out/themes"
    out.mkdir(parents=True, exist_ok=True)
    frames = {(t, f.stem): render_frame(f, t, out) for t in themes for f in FIXTURES}
    path = sheet(frames, themes, out)
    print(path)
    if args.open:
        subprocess.Popen(["imv", str(path)], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
