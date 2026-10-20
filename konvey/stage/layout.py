"""Chromium layout pass (spec §6.3).

Every leaf is written into the page as a fixed-size box (its natural Manim
size, 1u = 100px). The browser solves flexbox/grid; we read back the boxes.
All beats go on one page load, one stage per beat.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from . import displays
from .attach import attached
from .parse import LEAF_TAGS, Beat, Node
from .theme import current

PX_PER_UNIT = 100
STAGE_W, STAGE_H = 1422, 800
CHROMIUM = "/usr/bin/chromium"

BASE_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { width: %(w)dpx; }
.stage { position: absolute; left: 0; width: %(w)dpx; height: %(h)dpx;
         display: flex; flex-direction: column; overflow: hidden; }
.row { display: flex; flex-direction: row; }
.wrap { flex-wrap: wrap; align-content: center; }
.col { display: flex; flex-direction: column; }
.center { display: flex; align-items: center; justify-content: center; }
.grow { flex: 1 1 0; min-width: 0; min-height: 0; }
/* An empty grow box is a 3D view placeholder: fill the cross axis too, even in .center. */
.grow:empty { align-self: stretch; }
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


def _emit(node: Node, sizes: dict[str, tuple[float, float]], parent: str = "") -> str:
    style = _css(node.attrs.get("style", ""))
    cls = node.attrs.get("class", "")
    ident = f' id="{html.escape(node.id)}"' if node.id else ""
    if node.tag in LEAF_TAGS:
        w, h = sizes[node.id]
        if node.tag in WIDE and not attached(node):   # a line spans its row or column; its height stays
            span = "align-self:stretch;" if "col" in parent.split() else "flex:1 1 auto;align-self:center;"   # flex rows by default
            style = f"min-width:{w * PX_PER_UNIT:.1f}px;height:{h * PX_PER_UNIT:.1f}px;{span}{style}"
        else:
            style = f"width:{w * PX_PER_UNIT:.1f}px;height:{h * PX_PER_UNIT:.1f}px;{style}"
        if attached(node):   # placed against another element after layout: takes no room
            style += ";position:absolute;left:0;top:0"
        grow = " growable" if growable(node) else ""
        return f'<div{ident} class="leaf{grow} {cls}" style="{style}"></div>'
    inner = "".join(_emit(c, sizes, cls) for c in node.children)
    return f'<div{ident} class="{cls}" style="{style}">{inner}</div>'


def page_html(beats: list[Beat], sizes: dict[int, dict[str, tuple[float, float]]]) -> str:
    from .view import page_size

    stages, top = [], 0
    for b in beats:
        inner = "".join(_emit(n, sizes[b.index]) for n in b.overlay)
        style = _css(b.attrs.get("style", ""))
        pw, ph = page_size(b.attrs)   # a page larger than the frame (the 2D camera moves over it)
        stages.append(f'<div class="stage {b.attrs.get("class", "")}" id="__stage{b.index}" '
                      f'style="top:{top}px;width:{pw * STAGE_W:.0f}px;height:{ph * STAGE_H:.0f}px;'
                      f'{style}">{inner}</div>')
        top += round(ph * STAGE_H)
    return f"<!doctype html><html><head><style>{BASE_CSS}</style></head><body>{''.join(stages)}</body></html>"


SAFE_PX = 55  # letterbox bars cover this much at the top and bottom once opened

_READ_JS = """
([n, safe]) => {
  const name = (el) => el.id ? `#${el.id}` :
    `<div class="${el.className}"> in ${el.parentElement.id ? '#' + el.parentElement.id : 'the beat'}`;
  const out = [];
  for (let i = 0; i < n; i++) {
    const stage = document.getElementById('__stage' + i);
    const s = stage.getBoundingClientRect();
    const boxes = {}, problems = [], over = [];
    for (const el of stage.querySelectorAll('*')) {
      const r = el.getBoundingClientRect();
      if (el.id) boxes[el.id] = [r.left - s.left, r.top - s.top, r.width, r.height];
      if (getComputedStyle(el).position === 'absolute') continue;
      // A child must sit inside its container on all four sides.
      const p = el.parentElement.getBoundingClientRect();
      const out_ = {top: p.top - r.top, bottom: r.bottom - p.bottom, left: p.left - r.left, right: r.right - p.right};
      const sides = Object.entries(out_).filter(([, v]) => v > 1).map(([k, v]) => `${k} by ${Math.round(v)}px`);
      if (sides.length) {
        problems.push(`${name(el)} sticks out of its container (${sides.join(', ')}); give it less content, a smaller size=, or more room`);
        // For the auto-shrink pass: which leaves could make room, and how much is missing.
        const own = el.classList.contains('leaf') ? [el] : [...el.querySelectorAll('.leaf')];
        const near = [...el.parentElement.querySelectorAll('.leaf')];
        const ids = (list) => list.map((x) => x.id).filter(Boolean);
        over.push({own: ids(own), near: ids(near),
                   ox: Math.max(0, out_.left) + Math.max(0, out_.right),
                   oy: Math.max(0, out_.top) + Math.max(0, out_.bottom)});
      }
      if (el.classList.contains('leaf') && (r.top - s.top < safe - 1 || s.bottom - r.bottom < safe - 1))
        problems.push(`${name(el)} is under the letterbox bars (top/bottom ${safe}px are covered); keep beat padding >= 0.75u`);
    }
    // a growable leaf alone in its container: the room it could take
    const room = {}, roomwh = {};
    for (const el of stage.querySelectorAll('.growable')) {
      // a formula row (pictures with operators between) grows as one: the row's room over
      // what its children take together
      const row = el.closest('.formula');
      if (row && el.id) {
        const kids = [...row.children].map((k) => k.getBoundingClientRect());
        const uw = Math.max(...kids.map((k) => k.right)) - Math.min(...kids.map((k) => k.left));
        const uh = Math.max(...kids.map((k) => k.bottom)) - Math.min(...kids.map((k) => k.top));
        const r = row.getBoundingClientRect();
        room[el.id] = 0.92 * Math.min(r.width / Math.max(uw, 1), r.height / Math.max(uh, 1));
        continue;
      }
      const par = el.parentElement;
      if (!el.id || par === stage || par.children.length !== 1) continue;
      const r = el.getBoundingClientRect(), p = par.getBoundingClientRect();
      room[el.id] = Math.min(p.width / Math.max(r.width, 1), p.height / Math.max(r.height, 1));
      roomwh[el.id] = [p.width / Math.max(r.width, 1), p.height / Math.max(r.height, 1)];
    }
    out.push({boxes, problems: [...new Set(problems)], over, room, roomwh});
  }
  return out;
}
"""


# Visual blocks scale down cleanly; text never shrinks (it would fall under the minimum sizes).
SHRINK_FLOOR = {d.tag: d.shrink for d in displays.all_displays() if d.shrink}
SHRINK_PASSES = 5


LOOSEN = 0.4   # rendering a beat that still overflows: its floors drop to this × theirs (smaller, never overlapping)


def _shrink(beats: list[Beat], sizes, raw, natural, loosen: float = 1.0) -> bool:
    """Make room by scaling overflowing visual blocks (or their visual siblings) down,
    never below SHRINK_FLOOR of their natural size. When those are all at their floor, the
    beat's largest block that can still shrink gives up the room instead (a picture carried
    over from the last scene, too tall for a table under it); a steady block shrinks by the
    same factor in every beat, so it keeps one size. With ``loosen`` < 1 (a render, after the
    normal passes left a beat overflowing) the floors drop by that factor for that beat alone, so
    its pictures get smaller instead of being drawn over each other. Returns True if anything
    changed."""
    changed = False
    for b, r in zip(beats, raw):
        tags = {i: n.tag for i, n in b.leaves().items()}

        def room(i):   # can still shrink
            return tags.get(i) in SHRINK_FLOOR and i in sizes[b.index] and \
                sizes[b.index][i][0] > natural[b.index][i][0] * SHRINK_FLOOR[tags[i]] * loosen + 1e-4

        for o in r["over"]:
            cands = [i for i in o["own"] if room(i)] or [i for i in o["near"] if room(i)]
            if not cands:
                big = max((i for i in sizes[b.index] if room(i)),
                          key=lambda i: sizes[b.index][i][0] * sizes[b.index][i][1], default=None)
                cands = [big] if big else []
            for i in cands:
                w, h = sizes[b.index][i]
                f = min(1 - o["ox"] / (w * 100) if o["ox"] else 1, 1 - o["oy"] / (h * 100) if o["oy"] else 1)
                f = max(f - 0.01, 0.8)                      # at most 20% per pass; converge over passes
                w0, h0 = natural[b.index][i]
                floor = SHRINK_FLOOR[tags[i]] * loosen
                nw = max(w * f, w0 * floor)
                if nw < w - 1e-4:
                    k = nw / w
                    owners = [b] if loosen < 1 or i in o["own"] + o["near"] or tags[i] not in STEADY_SCALE else \
                        [c for c in beats if i in sizes[c.index]]
                    for c in owners:
                        cw, _ = sizes[c.index][i]
                        cw0, ch0 = natural[c.index][i]
                        cw = max(cw * k, cw0 * floor)
                        sizes[c.index][i] = (cw, ch0 * cw / cw0)
                    changed = True
    return changed


# Blocks whose size does not depend on their content: one id keeps one scale in every beat, so a
# readout appearing beside it in one beat does not make it jump smaller and back.
STEADY_SCALE = tuple(d.tag for d in displays.all_displays() if d.steady)


GROW_MAX = 1.6      # a picture grows at most this much past its natural size
GROW = {d.tag: (GROW_MAX if d.grow is True else float(d.grow)) for d in displays.all_displays() if d.grow}
# In a shot the picture takes the room its composition leaves (3b1b sizes his main picture to the
# frame: set_width(FRAME_WIDTH - 1)); the room is the real limit, this only stops a speck of a
# picture being blown up into a few giant strokes.
SHOT_GROW = {"full": 4.0, "compare": 4.0, "derive": 4.0, "question": 4.0}


def growable(n) -> bool:
    """A display that may take spare room: its kind grows, or a shot put it in a formula row."""
    return n.tag in GROW or n.attrs.get("_grow") == "1"
PICTURES = {d.tag for d in displays.all_displays() if d.picture}   # the picture is the shot: it may take the stage


# Axes-based pictures can take any proportions without distorting what they show (3b1b sizes his
# axes to the room: Axes(width=..., height=...)); after growing, they also take the spare room in
# the other direction, up to this change of aspect. A plane takes it too: its circles stay round,
# its axes run on to the box's edges (scene._redrawn), as 3b1b's axes span the frame.
STRETCH = {"plot", "chart", "scatter", "bars", "plane"}
STRETCH_MAX = 1.8
# Pictures rebuilt at the size they are given rather than scaled to it, so their text keeps its
# size (scene._redrawn); the block keeps its drawn area as ``view``.
REDRAW = {"plane", "numberline"}
# Pictures that take their column's whole width at their own height (a number line), as 3b1b
# stacks number lines of one length; rebuilt at that width (scene._redrawn).
WIDE = {"numberline"}


def _composition(b: Beat) -> tuple:
    """What shares the screen in a beat: its shot and the ids of its loose leaves."""
    return (b.attrs.get("shot", ""), tuple(sorted(i for i, n in b.leaves().items() if "of" not in n.attrs)))


def _grow(beats: list[Beat], sizes, raw) -> bool:
    """A picture alone in its container takes the spare room (Agent 3 often leaves a plot at a
    small default), by one factor per composition: the least room any beat with the same shot
    and the same things on screen gives it, so it holds its size while the beats look alike and
    glides to a new size when the composition changes (a readout joins, full → derive), which is
    meant, not a jump. A beat that overflows does not stop the others growing. True if anything
    changed."""
    room: dict[tuple, float] = {}
    for b, r in zip(beats, raw):
        if r.get("over"):
            continue
        comp = _composition(b)
        for i, n in b.leaves().items():
            if growable(n) and i in sizes[b.index]:     # not alone in some beat: it keeps its size
                top = SHOT_GROW.get(comp[0], GROW.get(n.tag, GROW_MAX))
                key = (i, comp) if comp[0] else (i, "")
                room[key] = min(room.get(key, top), r.get("room", {}).get(i, 1.0) * 0.97)
    # pictures side by side in a shot share one scale (compared things, a matrix × a vector):
    # one growing alone makes it look bigger than it is
    for b in beats:
        comp = _composition(b)
        if not comp[0]:
            continue
        pics = [i for i, n in b.leaves().items() if n.tag in PICTURES and (i, comp) in room
                and "of" not in n.attrs]
        if len(pics) < 2:
            continue
        least = min(room[i, comp] for i in pics)
        for i in pics:
            room[i, comp] = least
    # an axes picture alone in its row also takes the room left in the other direction
    extra: dict[tuple, tuple[float, float]] = {}
    for b, r in zip(beats, raw):
        comp = _composition(b)
        if r.get("over") or not comp[0]:
            continue
        pics = [i for i, n in b.leaves().items() if n.tag in PICTURES and "of" not in n.attrs]
        for i, n in b.leaves().items():
            if n.tag in STRETCH and pics == [i] and i in r.get("roomwh", {}) and (i, comp) in room:
                f = room[i, comp]
                rw, rh = (x * 0.97 for x in r["roomwh"][i])
                ew, eh = min(rw, f * STRETCH_MAX) / f, min(rh, f * STRETCH_MAX) / f
                old = extra.get((i, comp), (ew, eh))
                extra[i, comp] = (max(1.0, min(old[0], ew)), max(1.0, min(old[1], eh)))
    changed = False
    for b, r in zip(beats, raw):
        if r.get("over"):
            continue
        comp = _composition(b)
        for i in list(sizes[b.index]):
            key = (i, comp) if comp[0] else (i, "")
            f = room.get(key) or 1.0
            ew, eh = extra.get(key, (1.0, 1.0))
            if f > 1.02 or ew > 1.02 or eh > 1.02:
                w, h = sizes[b.index][i]
                sizes[b.index][i] = (w * f * ew, h * f * eh)
                changed = True
    return changed


STEADY_OUTLIER = 0.8   # a beat needing less than this × the median scale shrinks on its own


def _steady(beats: list[Beat], sizes, natural) -> bool:
    """Give each steady block one scale across the scene's beats: the smallest the beats needed,
    leaving out a beat that needs far less than the rest (a chart stacked under the system in the
    last beat); that beat keeps its own smaller scale rather than shrinking the whole scene.
    True if anything changed."""
    need: dict[str, list[float]] = {}
    for b in beats:
        for i, n in b.leaves().items():
            if n.tag in STEADY_SCALE and i in sizes[b.index] and natural[b.index][i][0] > 0:
                need.setdefault(i, []).append(min(1.0, sizes[b.index][i][0] / natural[b.index][i][0]))
    scale: dict[str, float] = {}
    for i, ks in need.items():
        mid = sorted(ks)[(len(ks) - 1) // 2]   # the lower median: an outlier is a minority of beats
        scale[i] = min([k for k in ks if k >= mid * STEADY_OUTLIER], default=min(ks))
    changed = False
    for b in beats:
        for i, n in b.leaves().items():
            if i in scale and i in sizes[b.index]:
                w0, h0 = natural[b.index][i]
                if sizes[b.index][i][0] > w0 * scale[i] + 1e-4:
                    sizes[b.index][i] = (w0 * scale[i], h0 * scale[i])
                    changed = True
    return changed


HOLD_STILL = 0.6    # units: a steady block that lands this close to its last place stays put


def _overlap(a: Box, b: Box) -> bool:
    return abs(a.x - b.x) * 2 < a.w + b.w - 1e-3 and abs(a.y - b.y) * 2 < a.h + b.h - 1e-3


def _inside(inner: Box, outer: Box) -> bool:
    """A container (the div around the block) holds the block; it is no obstacle."""
    return (abs(inner.x - outer.x) * 2 <= outer.w - inner.w + 1e-3 and
            abs(inner.y - outer.y) * 2 <= outer.h - inner.h + 1e-3) or \
           (abs(inner.x - outer.x) * 2 <= inner.w - outer.w + 1e-3 and
            abs(inner.y - outer.y) * 2 <= inner.h - outer.h + 1e-3)


def _hold_still(beats: list[Beat], result: list[dict[str, Box]]) -> None:
    """A steady block (a system, a drawing) gets one place for the whole scene: a readout that
    appears under it in one beat, or a caption that wraps, re-centres the page, and a block that
    creeps between beats makes its wires seem to move (and a packet runs beside them). The place
    is the one that collides with nothing in the most beats (the most crowded beat's own place
    wins a tie); beats where it would collide keep their own."""
    by_id: dict[str, list[int]] = {}
    for k, b in enumerate(beats):
        for i, n in b.leaves().items():
            if n.tag in STEADY_SCALE and i in result[k]:
                by_id.setdefault(i, []).append(k)
    for i, ks in by_id.items():
        def clear(cand: Box, k: int) -> bool:
            own = result[k][i]
            if abs(own.w - cand.w) > 0.02 or abs(own.h - cand.h) > 0.02:
                return False
            others = [o for j, o in result[k].items() if j != i and not _inside(o, own) and not _inside(o, cand)]
            return not any(_overlap(cand, o) for o in others)

        crowd = {k: len(result[k]) for k in ks}
        cands = sorted({(round(result[k][i].x, 3), round(result[k][i].y, 3)): k for k in ks}.items(),
                       key=lambda kv: -crowd[kv[1]])
        best, best_n = None, -1
        for (x, y), k in cands:
            cand = Box(x, y, result[k][i].w, result[k][i].h)
            n = sum(clear(cand, kk) for kk in ks)
            if n > best_n:
                best, best_n = cand, n
        if best is None:
            continue
        for k in ks:
            if clear(best, k):
                result[k][i] = Box(best.x, best.y, result[k][i].w, result[k][i].h)


def _space_hint(b: Beat, sizes) -> list[str]:
    """Name the block taking the beat's room: the overflowing one is often at its smallest
    already, and shrinking it further (what the plain message suggests) cannot help."""
    tall = sorted(((h, w, i) for i, (w, h) in sizes[b.index].items()), reverse=True)
    if not tall or tall[0][0] < 2.5:
        return []
    h, w, i = tall[0]
    return [f"#{i} takes {h:.1f}u of the {STAGE_H / PX_PER_UNIT:.0f}u stage height and cannot shrink "
            "more: show fewer blocks in this beat (drop a readout or move it to another beat), or put "
            "the others beside it in a row"]


def solve(beats: list[Beat], sizes, *, dump: str | None = None,
          strict: bool = True) -> list[dict[str, Box]]:
    """Lay out every beat. Visual blocks that do not fit are scaled down (up to
    SHRINK_FLOOR) and the page re-solved; what still overflows raises with per-beat,
    per-id messages when ``strict`` (checking), and only warns otherwise.
    ``sizes`` is updated in place with the sizes used."""
    from playwright.sync_api import sync_playwright

    natural = {k: dict(v) for k, v in sizes.items()}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        page = browser.new_page(viewport={"width": STAGE_W, "height": STAGE_H})
        safe = SAFE_PX if current().letterbox else 0
        for k in range(SHRINK_PASSES):
            page_src = page_html(beats, sizes)
            page.set_content(page_src)
            raw = page.evaluate(_READ_JS, [len(beats), safe])
            last = k == SHRINK_PASSES - 1
            if last or not any(r["over"] for r in raw) or not _shrink(beats, sizes, raw, natural):
                break
        if not strict and any(r["over"] for r in raw):
            for _ in range(2 * SHRINK_PASSES):   # a render: what still overflows gets smaller, never drawn over
                if not _shrink(beats, sizes, raw, natural, loosen=LOOSEN):
                    break
                page.set_content(page_html(beats, sizes))
                raw = page.evaluate(_READ_JS, [len(beats), safe])
                if not any(r["over"] for r in raw):
                    break
        if _steady(beats, sizes, natural):
            page_src = page_html(beats, sizes)
            page.set_content(page_src)
            raw = page.evaluate(_READ_JS, [len(beats), safe])
        if _grow(beats, sizes, raw):
            page_src = page_html(beats, sizes)
            page.set_content(page_src)
            raw = page.evaluate(_READ_JS, [len(beats), safe])
        browser.close()
    if dump:
        with open(dump, "w") as f:
            f.write(page_src)

    errors, result = [], []
    for b, r in zip(beats, raw):
        errors += [f"beat {b.index}: {msg}" for msg in r["problems"]]
        if r["over"]:
            errors += [f"beat {b.index}: {hint}" for hint in _space_hint(b, sizes)]
        result.append({
            k: Box((x + w / 2) / PX_PER_UNIT - STAGE_W / 2 / PX_PER_UNIT,
                   STAGE_H / 2 / PX_PER_UNIT - (y + h / 2) / PX_PER_UNIT,
                   w / PX_PER_UNIT, h / PX_PER_UNIT)
            for k, (x, y, w, h) in r["boxes"].items()
        })
    _hold_still(beats, result)
    if errors and strict:
        raise ValueError("layout errors:\n- " + "\n- ".join(errors))
    if errors:
        print("layout warnings:\n- " + "\n- ".join(errors), flush=True)
    return result
