"""``<path>`` (manimgl): a line through points of a picture, drawn once the picture is fitted
(``attach``). Two points make a segment; ``extend`` carries it across the picture (a tangent, a
line of constant momentum); ``closed`` + ``fill`` make a shaded region; ``dashed`` a drop to an
axis. Growing ``through`` from one beat to the next draws only the new stretch."""

from __future__ import annotations

import json
import math

from manimlib import *  # noqa: F401,F403

from ... import marks
from ...tree import Node
from ..base import Block

KEYS = ("on", "through", "closed", "fill", "extend", "dashed", "around", "label", "color", "dim", "size", "width")


def _on(node: Node, key: str) -> bool:
    return node.attrs.get(key, "").strip().lower() in ("true", "1", "yes", key)


class PathBlock(Block):
    tag = "path"

    def __init__(self, node: Node):
        super().__init__()
        self.xy: list = []
        self.add(Dot(radius=0.01).set_opacity(0))
        self.content = json.dumps(["path", {k: node.attrs.get(k) for k in KEYS}])


def build(node: Node, world=None) -> PathBlock:
    return PathBlock(node)


def _dashed(pts: list[np.ndarray], dash: float = 0.14, gap: float = 0.1, counts: list[int] | None = None) -> VMobject:
    """Dashes along the polyline; ``counts`` fixes how many per segment (a moving dashed line keeps
    its dashes, so they slide instead of being re-matched point by point)."""
    m = VMobject()
    m.counts = []
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        L = float(np.linalg.norm(b - a))
        n = counts[i] if counts and i < len(counts) else max(1, int(L / (dash + gap)))
        m.counts.append(n)
        for k in range(n):
            s, e = a + (b - a) * (k / n), a + (b - a) * min(1.0, (k + dash / (dash + gap)) / n)
            m.start_new_path(s)
            m.add_line_to(e)
    return m


def _inside(p, poly) -> bool:
    """Ray casting: is point p inside the polygon?"""
    x, y, hit = p[0], p[1], False
    for (x0, y0, _), (x1, y1, _) in zip(poly, [*poly[1:], poly[0]]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            hit = not hit
    return hit


def _in_region(lab, pts, centre, boxes, pad: float = 0.12) -> None:
    """A region's name inside it, in the corner of its bounds farthest from the picture's centre
    that holds the whole name (3b1b's "End zone" sits at the wedge's wide end, against the axis);
    with no corner that fits, at its middle."""
    from ...attach import clear

    lo, hi = np.min(pts, axis=0), np.max(pts, axis=0)
    w, h = lab.get_width(), lab.get_height()
    best = None
    for sx in (-1, 1):
        for sy in (-1, 1):
            c = np.array([(lo[0] + pad + w / 2) if sx < 0 else (hi[0] - pad - w / 2),
                          (lo[1] + pad + h / 2) if sy < 0 else (hi[1] - pad - h / 2), 0.0])
            corners = [c + np.array([dx * w / 2, dy * h / 2, 0.0]) for dx in (-1, 1) for dy in (-1, 1)]
            if not all(_inside(q, pts) for q in corners):
                continue
            lab.move_to(c)
            score = float(np.linalg.norm(c - centre)) - (0 if clear(lab, boxes) else 5)
            if best is None or score > best[0]:
                best = (score, c)
    lab.move_to(best[1] if best else np.mean(pts, axis=0))


def _capsule(a: np.ndarray, b: np.ndarray, r: float) -> VMobject:
    """A rounded outline around the segment a-b, as 3b1b circles a diagonal of a table."""
    d = b - a
    ang = math.atan2(d[1], d[0])
    pts = []
    for c, start in ((b, ang - PI / 2), (a, ang + PI / 2)):
        pts += [c + r * np.array([math.cos(start + t), math.sin(start + t), 0.0]) for t in np.linspace(0, PI, 24)]
    m = VMobject().set_points_as_corners([*pts, pts[0]])
    return m


def attach(node: Node, mob: PathBlock, resolve, obstacles=lambda *skip: []) -> PathBlock:
    where = f"<path id={node.id}>"
    pic = marks.host(node, resolve, where)
    mob.xy = marks.points(node.attrs.get("through", ""), lambda r: resolve(r), where, "through")
    pts = marks.screen(pic, mob.xy)
    if len(pts) == 1:
        pts = pts * 2
    if _on(node, "extend") and len(pts) == 2 and hasattr(pic, "bounds"):
        pts = list(marks.clip_to(pts[0], pts[1], pic.bounds()))
    color, alpha = marks.style(node, "ink")
    try:
        width = float(node.attrs.get("width", 2))
    except ValueError:
        width = 2.0
    closed = _on(node, "closed") or bool(node.attrs.get("fill", "").strip())
    if closed and hasattr(pic, "bounds"):
        pts = marks.clip_polygon(pts, pic.bounds()) or pts
    if _on(node, "around") and len(pts) == 2:
        unit = float(np.linalg.norm(np.asarray(pic.point(1, 0)) - np.asarray(pic.point(0, 0))))
        line = _capsule(pts[0], pts[1], min(0.8, max(0.25, 0.42 * unit)))   # circles a run (a diagonal of cells)
    elif _on(node, "dashed"):
        mob.dash_pts = pts + ([pts[0]] if closed else [])
        line = _dashed(mob.dash_pts)
    else:
        line = VMobject().set_points_as_corners(pts + ([pts[0]] if closed else []))
    line.set_stroke(color, width, alpha)
    fill = node.attrs.get("fill", "").strip()
    if closed and fill and fill.lower() not in ("false", "no", "none"):
        from ...theme import current

        fc = color if fill.lower() in ("true", "yes") else current().color(fill)
        area = Polygon(*pts).set_fill(fc, 0.22 * alpha).set_stroke(width=0)
        line.set_stroke(fc, width, 0.8 * alpha)
        parts = [area, line]
    else:
        parts = [VMobject().set_points_as_corners([pts[0], pts[0]]).set_stroke(width=0), line]
    if node.attrs.get("label", "").strip():
        lab = marks.halo(marks.label(node.attrs["label"], marks.size(node), color).set_fill(opacity=alpha), alpha)
        if closed:
            _in_region(lab, pts, pic.get_center(), obstacles())
        else:
            a, b = pts[-2], pts[-1]
            mid = (a + b) / 2
            d = b - a
            normal = np.array([-d[1], d[0], 0.0])
            if np.dot(normal, mid - pic.get_center()) < 0:
                normal = -normal
            marks.place_label(lab, mid, normal, obstacles(), gap=0.14)
        parts.append(lab)
    mob.set_submobjects(parts)
    return mob


def enter(node: Node, mob: PathBlock, run_time: float) -> Animation:
    anims = [FadeIn(mob[0]), ShowCreation(mob[1], rate_func=linear)]
    anims += [FadeIn(m) for m in mob[2:]]
    return AnimationGroup(*anims, run_time=min(run_time * 0.8, 1.2 + 0.25 * len(mob.xy)))


def move(old: PathBlock, new: PathBlock) -> Animation:
    """The same path on a picture laid out again: a dashed line keeps its dashes while it slides
    (a plain Transform re-matched different dash counts point by point: broken solid bits)."""
    if getattr(old, "dash_pts", None) and getattr(new, "dash_pts", None) and len(old) == len(new) \
            and len(old.dash_pts) == len(new.dash_pts):
        target = new.copy()
        dashes = _dashed(new.dash_pts, counts=old[1].counts).match_style(new[1])
        target.set_submobjects([target[0], dashes, *target[2:]])
        return Transform(old, target)
    return Transform(old, new)


def morph(old: PathBlock, new: PathBlock, sources=None) -> Animation | None:
    """``through`` grew (the old points come first): only the new stretch is drawn, at a
    steady pace, so a bounce path adds one hop per beat. A dashed line that moves (its picture
    was laid out again) slides with its dashes. Anything else reshapes."""
    if getattr(old, "dash_pts", None) and getattr(new, "dash_pts", None) and len(old) == len(new) \
            and len(old.dash_pts) == len(new.dash_pts):
        target = _dashed(new.dash_pts, counts=old[1].counts).match_style(new[1])
        return AnimationGroup(Transform(old[1], target), Transform(old[0], new[0]),
                              *(FadeTransform(a, b) for a, b in zip(old[2:], new[2:])))
    n0, n1 = len(old.xy), len(new.xy)
    if not (1 < n0 < n1 and all(np.allclose(a, b) for a, b in zip(old.xy, new.xy))) or len(old) != len(new):
        return None
    f0 = (n0 - 1) / (n1 - 1)
    line = new[1].copy()

    def grow(m, t):
        m.pointwise_become_partial(line, 0, f0 + (1 - f0) * t)

    old[1].become(line)                     # same structure as the full line, drawn up to f0 at once
    anims = [UpdateFromAlphaFunc(old[1], grow), Transform(old[0], new[0])]
    anims += [FadeTransform(a, b) for a, b in zip(old[2:], new[2:])]
    return AnimationGroup(*anims)
