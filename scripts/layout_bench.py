"""How well scenes use the canvas, across every Director example (one per display genre).

    __NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia \
    uv run --group render --group layout python scripts/layout_bench.py OUT_DIR [name ...]
    ... OUT_DIR --runs out/run-a out/run-b      # generated scenes instead: each run's S2

Each example's <beats> (or each run's agent3-S2, as the Director wrote it) is rendered at 480p; frames every 2 s give the fill (the share of the frame
the drawn content spans, from its 1st to 99th percentile pixels) and the layout check gives the
overflow problems (things that stick out of their room and get drawn over each other). Writes
OUT_DIR/bench.json and OUT_DIR/sheet.png (one frame per example: its fullest beat's end).
"""
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.argv, ARGS = sys.argv[:1], sys.argv[1:]   # manimgl parses sys.argv when the check imports it

from konvey.stage.check import check_runtime, wrapper_source  # noqa: E402
from konvey.stage.examples import load_examples  # noqa: E402


def fill(png: Path) -> float | None:
    """The main picture's share of the canvas: the largest drawn region (strokes within ~2% of
    the frame of each other merged into one) as its bounding box over the area inside the bars.
    A heading in a corner or a readout off to the side is its own region and does not count."""
    from scipy import ndimage

    a = np.asarray(Image.open(png).convert("L")).astype(int)
    a = a[int(a.shape[0] * 0.09):int(a.shape[0] * 0.91)]   # inside the letterbox bars
    m = np.abs(a - np.median(a)) > 18
    if m.sum() < 30:
        return None
    r = max(2, int(a.shape[1] * 0.012))
    merged = ndimage.binary_dilation(m, iterations=r)
    labels, n = ndimage.label(merged)
    best = 0.0
    for sl in ndimage.find_objects(labels):
        h, w = sl[0].stop - sl[0].start - 2 * r, sl[1].stop - sl[1].start - 2 * r
        best = max(best, max(h, 0) * max(w, 0) / (a.shape[0] * a.shape[1]))
    return float(best)


def box_share(page: Path) -> list[float]:
    """Per beat, the largest picture's layout box over the stage inside its padding (the room a
    picture can have): what the engine gave the main picture, whatever its strokes look like."""
    from konvey.stage import layout as L
    from konvey.stage.parse import parse_beats

    dump = page.with_name(page.stem + ".layout.html")
    if not dump.exists():
        return []
    beats = parse_beats(page.read_text())
    stages = re.split(r'<div class="stage[^"]*" id="__stage\d+"', dump.read_text())[1:]
    inner = (L.STAGE_W - 2 * 80) * (L.STAGE_H - 2 * 75)
    out = []
    for b, st in zip(beats, stages):
        pics = {i for i, n in b.leaves().items() if n.tag in L.PICTURES and "of" not in n.attrs}
        sizes = [float(w) * float(h) for i, w, h in re.findall(
            r'<div id="([^"]+)" class="leaf[^"]*" style="width:([0-9.]+)px;height:([0-9.]+)px', st) if i in pics]
        out.append(min(1.0, max(sizes, default=0.0) / inner))
    return out


def run(item, out: Path) -> dict:
    name, html = item
    d = out / name
    d.mkdir(parents=True, exist_ok=True)
    page = d / "scene.html"
    page.write_text(html)
    page.with_suffix(".py").write_text(wrapper_source(page))
    problems = [p for p in check_runtime(html, d / "check", "S2") if "sticks out" in p or "cannot shrink" in p
                or "overlap" in p]
    log = open(d / "render.log", "w")
    proc = subprocess.run(["manimgl", str(page.with_suffix(".py")), "SingleScene", "-w", "-r", "854x480",
                           "--video_dir", str(d), "--file_name", "v"], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                          env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "render")})
    video = d / "v.mp4"
    if proc.returncode or not video.exists():
        return {"name": name, "error": "render failed (render.log)"}
    for f in d.glob("f*.png"):
        f.unlink()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "fps=1/2", str(d / "f%03d.png")], check=True)
    frames = sorted(d.glob("f*.png"))
    fills = [(f, x) for f in frames if (x := fill(f)) is not None]
    best = max(fills, key=lambda t: t[1])[0] if fills else None
    vals = [x for _, x in fills]
    boxes = box_share(page)
    return {"name": name, "box_median": float(np.median(boxes)) if boxes else 0.0,
            "fill_median": float(np.median(vals)) if vals else 0.0,
            "fill_max": float(max(vals)) if vals else 0.0, "overflow": len(problems), "problems": problems[:6],
            "still": str(best) if best else None}


def sheet(rows: list[dict], path: Path) -> None:
    from PIL import ImageDraw

    tiles = [r for r in rows if r.get("still")]
    cols, tw, th = 4, 427, 240
    img = Image.new("RGB", (cols * tw, ((len(tiles) + cols - 1) // cols) * (th + 22)), "black")
    draw = ImageDraw.Draw(img)
    for i, r in enumerate(tiles):
        x, y = (i % cols) * tw, (i // cols) * (th + 22)
        img.paste(Image.open(r["still"]).resize((tw, th)), (x, y + 22))
        draw.text((x + 6, y + 4), f'{r["name"]}  box {r["box_median"]:.0%}  overflow {r["overflow"]}', fill="white")
    img.save(path)


def main() -> int:
    out = Path(ARGS[0]).resolve()
    if "--runs" in ARGS:
        items = []
        for r in map(Path, ARGS[ARGS.index("--runs") + 1:]):
            page = r / "agent3-S2.tagged.html"
            page = page if page.exists() else r / "agent3-S2.html"
            items.append((r.name, page.read_text()))
    else:
        names = set(ARGS[1:])
        items = [(e.name, re.findall(r"```html\n(.*?)```", e.body, re.S)[0]) for e in load_examples()
                 if not names or e.name in names]
    with ThreadPoolExecutor(2) as pool:
        rows = list(pool.map(lambda it: run(it, out), items))
    ok = [r for r in rows if "error" not in r]
    summary = {"examples": len(rows), "failed": [r["name"] for r in rows if "error" in r],
               "box_median": float(np.median([r["box_median"] for r in ok])) if ok else 0.0,
               "box_under_30pct": sum(r["box_median"] < 0.3 for r in ok),
               "fill_median": float(np.median([r["fill_median"] for r in ok])) if ok else 0.0,
               "under_25pct": sum(r["fill_median"] < 0.25 for r in ok), "overflow_beats": sum(r["overflow"] for r in ok)}
    (out / "bench.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
    sheet(ok, out / "sheet.png")
    print(json.dumps(summary))
    for r in sorted(ok, key=lambda r: r["box_median"]):
        print(f'{r["name"]:22s} box {r["box_median"]:.0%}  ink {r["fill_median"]:.0%}  overflow {r["overflow"]}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
