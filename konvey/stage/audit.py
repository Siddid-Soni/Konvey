"""Frame audit (runtime check only): what the viewer actually sees at the end of each beat's
transition, measured on screen. Layout checks every overlay box on its own; nothing else
knows where the 3D world and the labels pinned to it land, so a world drawn over the headline,
a label on top of a readout, or a crowded screen passed every check. Each problem names the
beat, the elements and a fix, and goes back to Agent 3 like a layout error.

Coverage is measured on a coarse grid over the screen (0.1 units per cell): a solid covers its
projected outline, a line or arrow a thin band along its path, a face its polygon; text covers
its box.
"""

from __future__ import annotations

import numpy as np
from matplotlib.path import Path as MPath
from scipy.spatial import ConvexHull, QhullError

from manimlib import FRAME_HEIGHT, FRAME_WIDTH, Mobject

CELL = 0.1
LINE_HALF = 0.07                # half-width of a drawn line on screen, in units
MIN_OVERLAP = 0.08              # units^2 of a world body over a text box that counts
MAX_TEXT_ITEMS = 9              # text-bearing things on screen at once (subtitle excluded)

_xs = np.arange(-FRAME_WIDTH / 2 + CELL / 2, FRAME_WIDTH / 2, CELL)
_ys = np.arange(-FRAME_HEIGHT / 2 + CELL / 2, FRAME_HEIGHT / 2, CELL)
GX, GY = np.meshgrid(_xs, _ys)
GRID = np.c_[GX.ravel(), GY.ravel()]


def rect_of(mob: Mobject) -> tuple[float, float, float, float] | None:
    """(x0, y0, x1, y1) from the points themselves (a cached bounding box can be stale)."""
    pts = [m.get_points() for m in mob.get_family() if m.has_points()]
    if not pts:
        return None
    p = np.vstack(pts)
    if not np.isfinite(p).all():
        return None
    return float(p[:, 0].min()), float(p[:, 1].min()), float(p[:, 0].max()), float(p[:, 1].max())


def _rect_mask(r, shrink: float = 0.03) -> np.ndarray:
    x0, y0, x1, y1 = r
    return ((GRID[:, 0] > x0 + shrink) & (GRID[:, 0] < x1 - shrink)
            & (GRID[:, 1] > y0 + shrink) & (GRID[:, 1] < y1 - shrink))


def _poly_mask(pts2: np.ndarray) -> np.ndarray:
    if len(pts2) < 3:
        return np.zeros(len(GRID), bool)
    try:
        hull = pts2[ConvexHull(pts2).vertices]
    except (QhullError, ValueError):
        return np.zeros(len(GRID), bool)
    return MPath(hull).contains_points(GRID)


def _line_mask(path2: np.ndarray, half: float = LINE_HALF) -> np.ndarray:
    m = np.zeros(len(GRID), bool)
    for a, b in zip(path2[:-1], path2[1:]):
        d = b - a
        L2 = float(d @ d)
        if L2 < 1e-12:
            continue
        t = np.clip(((GRID - a) @ d) / L2, 0, 1)
        m |= np.linalg.norm(GRID - (a + t[:, None] * d), axis=1) < half
    return m


def _overlap(r1, r2) -> float:
    w = min(r1[2], r2[2]) - max(r1[0], r2[0])
    h = min(r1[3], r2[3]) - max(r1[1], r2[1])
    return max(w, 0) * max(h, 0)


def world_marks(field, frame) -> list[tuple[str, str, np.ndarray]]:
    """(id, tag, coverage mask) of every visible world body, as drawn on screen now."""
    from .solids import project

    proj = lambda pts: np.array([project(frame, p)[:2] for p in pts])  # noqa: E731
    marks = []
    for i, ns in field.nodes.items():
        tag, st = ns[0].tag, field.raw_state(i)
        if not st or st.get("show", 0) < 0.5:
            continue
        a = field.actors.get(i)
        if tag in ("sphere", "solid"):
            pts = a.body_points()
            pts = pts[:: max(1, len(pts) // 400)]
            marks.append((i, tag, _poly_mask(proj(pts))))
        elif tag == "line3d" and a.st is not None:
            marks.append((i, tag, _line_mask(proj(a._path(a.st)))))
        elif tag == "face3d":
            marks.append((i, tag, _poly_mask(proj(st["pts"]))))
        elif tag == "axes3d":
            ax = field.mobs[i][0]
            for axis in ax.get_axes():
                marks.append((i, tag, _line_mask(proj(axis.get_start_and_end()), 0.03)))
        elif tag == "surface":
            marks.append((i, tag, _poly_mask(proj(np.array(field.extent({i: st}))))))
    return marks


def pinned_labels(field) -> list[tuple[str, Mobject]]:
    """Text pinned to 3D points (label3d, line/face labels, axis names), as (owner id, text)."""
    out = []
    for i, a in field.actors.items():
        st = field.raw_state(i)
        if not st or st.get("show", 0) < 0.5:
            continue
        lab = a.mob if field.nodes[i][0].tag == "label3d" else getattr(a, "label", None)
        if lab is not None:
            out.append((i, lab))
    return out


def audit_beat(index: int, leaves: dict, mobs: dict, field, frame, focus_ok: bool) -> list[str]:
    """Problems in beat ``index`` as it looks once its transition has finished.
    ``leaves``: id -> Node of the overlay leaves; ``mobs``: id -> their mobjects on screen."""
    where = f"beat {index}"
    problems = []
    texts = {i: (leaves[i], rect_of(mobs[i])) for i in leaves if i in mobs}
    texts = {i: (n, r) for i, (n, r) in texts.items() if r is not None}
    marks = world_marks(field, frame) if field.nodes else []
    if marks and not focus_ok:
        problems.append(f"{where}: <camera> has no focus=, so the 3D world is framed on the whole "
                        'screen, under the text; add an empty <div id="view" class="grow"> where the '
                        'world should go and <camera … focus="view">')
    # 1. the world drawn over text
    hits: dict[str, list[str]] = {}
    for i, tag, m in marks:
        for j, (n, r) in texts.items():
            if (m & _rect_mask(r)).sum() * CELL * CELL >= MIN_OVERLAP:
                hits.setdefault(f"<{tag} id={i}>", []).append(f"<{n.tag} id={j}>")
    for body, over in hits.items():
        problems.append(f"{where}: {body} is drawn over {', '.join(over)}: keep the world inside its "
                        "view box (make the box bigger, show fewer or smaller things in 3D, keep "
                        "coordinates small, or leave this actor out of the beat)")
    # 2. pinned labels on text, and on each other
    labels = [(i, lab, rect_of(lab)) for i, lab in pinned_labels(field)]
    labels = [(i, lab, r) for i, lab, r in labels if r is not None]
    for i, lab, r in labels:
        area = (r[2] - r[0]) * (r[3] - r[1])
        over = [f"<{n.tag} id={j}>" for j, (n, rr) in texts.items() if _overlap(r, rr) > 0.25 * area]
        if over:
            problems.append(f"{where}: the label of {i} lands on {', '.join(over)}: drop the label "
                            "(the text already says it) or pin it elsewhere (at=\"x,y,z\")")
    for k, (i, _, r) in enumerate(labels):
        for j, _, rr in labels[k + 1:]:
            if _overlap(r, rr) > 0.3 * min((r[2] - r[0]) * (r[3] - r[1]), (rr[2] - rr[0]) * (rr[3] - rr[1])):
                problems.append(f"{where}: the labels of {i} and {j} overlap; keep one, or pin them apart")
    # 3. too much at once
    n_text = sum(1 for i, (n, _) in texts.items() if n.tag != "caption") + len(labels)
    if n_text > MAX_TEXT_ITEMS:
        problems.append(f"{where}: {n_text} pieces of text on screen at once (headline, readouts, "
                        f"labels); at most {MAX_TEXT_ITEMS}: the subtitle already says the line, so "
                        "show only what the eye needs now")
    return problems
