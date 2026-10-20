"""Chromium layout pass (spec §6.3).

Every leaf is written into the page as a fixed-size box (its natural Manim
size, 1u = 100px). The browser solves flexbox/grid; we read back the boxes.
All beats go on one page load, one stage per beat.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from .parse import LEAF_TAGS, Beat, Node

PX_PER_UNIT = 100
STAGE_W, STAGE_H = 1422, 800
CHROMIUM = "/usr/bin/chromium"

BASE_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { width: %(w)dpx; }
.stage { position: absolute; left: 0; width: %(w)dpx; height: %(h)dpx;
         display: flex; flex-direction: column; overflow: hidden; }
.row { display: flex; flex-direction: row; }
.col { display: flex; flex-direction: column; }
.center { display: flex; align-items: center; justify-content: center; }
.grow { flex: 1 1 0; min-width: 0; min-height: 0; }
.leaf { flex: none; }
""" % {"w": STAGE_W, "h": STAGE_H}

_UNIT = re.compile(r"(-?\d*\.?\d+)u\b")


@dataclass
class Box:
    x: float  # centre, Manim units
    y: float
    w: float
    h: float


def _css(style: str) -> str:
    return _UNIT.sub(lambda m: f"{float(m.group(1)) * PX_PER_UNIT:g}px", style)


def _emit(node: Node, sizes: dict[str, tuple[float, float]]) -> str:
    style = _css(node.attrs.get("style", ""))
    cls = node.attrs.get("class", "")
    ident = f' id="{html.escape(node.id)}"' if node.id else ""
    if node.tag in LEAF_TAGS:
        w, h = sizes[node.id]
        style = f"width:{w * PX_PER_UNIT:.1f}px;height:{h * PX_PER_UNIT:.1f}px;{style}"
        return f'<div{ident} class="leaf {cls}" style="{style}"></div>'
    inner = "".join(_emit(c, sizes) for c in node.children)
    return f'<div{ident} class="{cls}" style="{style}">{inner}</div>'


def page_html(beats: list[Beat], sizes: dict[int, dict[str, tuple[float, float]]]) -> str:
    stages = []
    for b in beats:
        inner = "".join(_emit(n, sizes[b.index]) for n in b.overlay)
        style = _css(b.attrs.get("style", ""))
        stages.append(f'<div class="stage {b.attrs.get("class", "")}" id="__stage{b.index}" '
                      f'style="top:{b.index * STAGE_H}px;{style}">{inner}</div>')
    return f"<!doctype html><html><head><style>{BASE_CSS}</style></head><body>{''.join(stages)}</body></html>"


_READ_JS = """
(n) => {
  const out = [];
  for (let i = 0; i < n; i++) {
    const stage = document.getElementById('__stage' + i);
    const s = stage.getBoundingClientRect();
    const boxes = {}, problems = [];
    for (const el of stage.querySelectorAll('[id]')) {
      const r = el.getBoundingClientRect();
      boxes[el.id] = [r.left - s.left, r.top - s.top, r.width, r.height];
      if (el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1)
        problems.push(`#${el.id} overflows its box by ${el.scrollWidth - el.clientWidth}px x ${el.scrollHeight - el.clientHeight}px`);
      if (r.left < s.left - 1 || r.top < s.top - 1 || r.right > s.right + 1 || r.bottom > s.bottom + 1)
        problems.push(`#${el.id} is outside the stage: [${Math.round(r.left - s.left)}, ${Math.round(r.top - s.top)}, ${Math.round(r.width)}x${Math.round(r.height)}]`);
    }
    out.push({boxes, problems});
  }
  return out;
}
"""


def solve(beats: list[Beat], sizes, *, dump: str | None = None) -> list[dict[str, Box]]:
    """Lay out every beat; raise with per-beat, per-id messages on overflow."""
    from playwright.sync_api import sync_playwright

    page_src = page_html(beats, sizes)
    if dump:
        with open(dump, "w") as f:
            f.write(page_src)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        page = browser.new_page(viewport={"width": STAGE_W, "height": STAGE_H})
        page.set_content(page_src)
        raw = page.evaluate(_READ_JS, len(beats))
        browser.close()

    errors, result = [], []
    for b, r in zip(beats, raw):
        errors += [f"beat {b.index}: {msg}" for msg in r["problems"]]
        result.append({
            k: Box((x + w / 2) / PX_PER_UNIT - STAGE_W / 2 / PX_PER_UNIT,
                   STAGE_H / 2 / PX_PER_UNIT - (y + h / 2) / PX_PER_UNIT,
                   w / PX_PER_UNIT, h / PX_PER_UNIT)
            for k, (x, y, w, h) in r["boxes"].items()
        })
    if errors:
        raise ValueError("layout errors:\n- " + "\n- ".join(errors))
    return result
