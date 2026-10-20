"""``<plane>``: a coordinate plane, arrows from the origin and a matrix acting on it (manimgl).

The picture is drawn from a plain description (``Spec``) by :func:`draw`, so a change between two
beats can be drawn at any moment in between: a matrix acting moves every grid line from where it
was to where the matrix sends it (the 3Blue1Brown linear-transformation picture), an arrow's tip
slides, a point on the unit circle turns along the circle and its projections follow."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace

import numpy as np

from manimlib import *  # noqa: F401,F403

from ...match import squash
from ...theme import current
from ...tree import BeatError, Node
from ..base import Block
from . import _on, apply, named_pairs, parse_angle, parse_matrix, range_of

H = 4.6            # natural height (u) unless h= is given; the layout grows it into spare room
MAX_W = 9.0        # natural width cap (u)
MAX_GRID = 80      # moving grid lines per direction (the stride doubles beyond)
TIP = 0.24         # arrow head length (u)
ARC_R = 0.42       # angle arc radius (u)


@dataclass
class Item:
    name: str
    xy: tuple[float, float]
    color: str
    alpha: float = 1.0
    labels: list[tuple[str, float]] = field(default_factory=list)   # (text, alpha): old and new while changing


@dataclass
class Spec:
    rng: tuple[float, float, float, float, float]   # x0, x1, y0, y1, grid step
    unit: float                                      # u per plane unit
    m: np.ndarray                                    # the matrix acting (identity when none)
    vectors: list[Item]
    points: list[Item]
    lines: list[Item]                                # directions through the origin; never transformed
    circle: float                                    # opacity of the unit circle
    angle: Item | None                               # xy = (degrees, 0)
    proj: float                                      # opacity of the projections
    arc: list[tuple[str, float]]                     # the angle's label at its arc
    complex: bool
    size: float


# --- labels -----------------------------------------------------------------------------------
_CACHE: dict = {}
GREEK = {"θ": r"\theta ", "π": r"\pi ", "φ": r"\varphi ", "λ": r"\lambda ", "α": r"\alpha ", "β": r"\beta "}


def _tex(text: str) -> str:
    """A name as math: Greek letters as commands, a subscript of several characters braced
    (``v_11`` -> ``v_{11}``), a word of three or more letters upright (``sum`` -> ``\\text{sum}``)."""
    for k, v in GREEK.items():
        text = text.replace(k, v)
    text = text.replace("−", "-").strip().strip("$")
    text = re.sub(r"_([A-Za-z0-9]{2,})", r"_{\1}", text)
    return re.sub(r"(?<![\\A-Za-z])([A-Za-z]{3,})", lambda m: m.group(1) if m.group(1) in TEX_WORDS
                  else r"\text{" + m.group(1) + "}", text)


TEX_WORDS = {"cos", "sin", "tan", "log", "exp"}   # words after a backslash are commands anyway


def label(text: str, size: float, color: str) -> Mobject:
    """Math-set text (names, coordinates, ticks), built once per (text, size, colour)."""
    key = (text, round(size, 2), color)
    if key not in _CACHE:
        try:
            _CACHE[key] = Tex(_tex(text), font_size=size).set_fill(color, 1)
        except Exception as e:  # noqa: BLE001 - LaTeX errors come back to Agent 3 by name
            raise BeatError(f"plane label {text!r} is not valid LaTeX: {str(e).strip()[:120]}") from e
    return _CACHE[key].copy()


def _num(v: float) -> str:
    return f"{v:.0f}" if abs(v - round(v)) < 1e-9 else f"{v:.2f}".rstrip("0").rstrip(".")


def _tick(v: float, imaginary: bool) -> str:
    if not imaginary:
        return _num(v)
    return {1: "i", -1: "-i"}.get(v, f"{_num(v)}i") if abs(v - round(v)) < 1e-9 else f"{_num(v)}i"


# --- geometry ---------------------------------------------------------------------------------
def _clip(p, q, rng):
    """Liang–Barsky: the part of segment p-q inside the range's rectangle, or None."""
    x0, x1, y0, y1 = rng[:4]
    t0, t1 = 0.0, 1.0
    dx, dy = q[0] - p[0], q[1] - p[1]
    for a, b in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if abs(a) < 1e-12:
            if b < 0:
                return None
            continue
        r = b / a
        if a < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return None
    return (p[0] + t0 * dx, p[1] + t0 * dy), (p[0] + t1 * dx, p[1] + t1 * dy)


def grid_sources(rng, mats) -> list[tuple[tuple, tuple, bool]]:
    """Grid lines (in the plane's own coordinates, before the matrix) that land in view under any
    of ``mats``: a matrix that squeezes the plane pulls far lines in. [(start, end, is_axis)]."""
    x0, x1, y0, y1, step = rng
    big = 6 * max(abs(x0), abs(x1), abs(y0), abs(y1))
    corners = np.array([[x0, y0], [x1, y0], [x0, y1], [x1, y1]], float)
    lo, hi = np.array([x0, y0], float), np.array([x1, y1], float)
    for m in mats:
        if abs(np.linalg.det(m)) < 1e-6:
            lo, hi = np.minimum(lo, -big), np.maximum(hi, big)
            continue
        pre = corners @ np.linalg.inv(m).T
        lo, hi = np.minimum(lo, pre.min(axis=0)), np.maximum(hi, pre.max(axis=0))
    lo, hi = np.maximum(lo, -big), np.minimum(hi, big)
    stride = step
    while max((hi - lo) / stride) > MAX_GRID:
        stride *= 2
    out = []
    for k in range(math.ceil(lo[0] / stride - 1e-9), math.floor(hi[0] / stride + 1e-9) + 1):
        out.append(((k * stride, lo[1]), (k * stride, hi[1]), k == 0))
    for k in range(math.ceil(lo[1] / stride - 1e-9), math.floor(hi[1] / stride + 1e-9) + 1):
        out.append(((lo[0], k * stride), (hi[0], k * stride), k == 0))
    return out


def _seg(a, b) -> VMobject:
    return VMobject().set_points_as_corners([a, b])


def _dashes(a, b, n: int = 9) -> VMobject:
    """A dashed line as one path of n dashes, so its structure never changes as it grows."""
    m = VMobject()
    d = b - a
    for k in range(n):
        s, e = a + d * (k / n), a + d * ((k + 0.55) / n)
        m.start_new_path(s)
        m.add_line_to(e)
    return m


def _arrow(tail, tip, color, alpha, width=5.0) -> VGroup:
    d = tip - tail
    n = np.linalg.norm(d)
    u = d / n if n > 1e-9 else RIGHT
    k = min(1.0, n / (TIP * 1.4)) if n > 1e-9 else 0.0     # a short arrow gets a smaller head
    side = np.array([-u[1], u[0], 0]) * 0.11 * k
    base = tip - u * TIP * k
    shaft = _seg(tail, base + u * 0.02).set_stroke(color, width, alpha if n > 1e-3 else 0)
    head = Polygon(tip, base + side, base - side).set_fill(color, alpha if n > 1e-3 else 0).set_stroke(width=0)
    return VGroup(shaft, head)


def _boxes_overlap(a, b) -> float:
    ox = min(a[0] + a[2] / 2, b[0] + b[2] / 2) - max(a[0] - a[2] / 2, b[0] - b[2] / 2)
    oy = min(a[1] + a[3] / 2, b[1] + b[3] / 2) - max(a[1] - a[3] / 2, b[1] - b[3] / 2)
    return max(0.0, ox) * max(0.0, oy)


def _place(mob: Mobject, anchor, out, obstacles, marks, half) -> np.ndarray:
    """Put a label next to ``anchor`` (a tip, a point), preferring the side ``out`` points to; the
    spot that covers the fewest other labels, arrows and lines, inside the view. -> its offset."""
    w, h = mob.get_width() + 0.08, mob.get_height() + 0.06
    u = out / (np.linalg.norm(out) or 1)
    n = np.array([-u[1], u[0], 0])
    best, best_score = None, np.inf
    dirs = [d / np.linalg.norm(d) for d in (u, (u + n) / 1.414, (u - n) / 1.414, n, -n, -u,
                                            UP, DOWN, LEFT, RIGHT, UL, UR, DL, DR)]
    dirs.sort(key=lambda d: -float(np.dot(d, u)))      # outward first, back towards the origin last
    for k, d in enumerate(dirs):
        r = 0.12 + 0.5 * (abs(d[0]) * w + abs(d[1]) * h)
        c = anchor + d * r
        box = (c[0], c[1], w, h)
        score = 0.02 * k + sum(10 * _boxes_overlap(box, o) for o in obstacles)
        score += sum(0.4 for p in marks if abs(p[0] - c[0]) < w / 2 and abs(p[1] - c[1]) < h / 2)
        score += 5 * (max(0, abs(c[0]) + w / 2 - half[0]) + max(0, abs(c[1]) + h / 2 - half[1]))
        if score < best_score:
            best, best_score = c - anchor, score
    return best


def draw(spec: Spec, grid=None, offsets: dict | None = None) -> tuple[VGroup, dict]:
    """The picture for ``spec`` at natural size, the view centred on ORIGIN. ``grid``: the moving
    grid's source lines (fixed during a change, so the structure stays the same); ``offsets``:
    label offsets to use instead of placing them (a change keeps labels beside their tips).
    -> (picture, offsets used)."""
    th = current()
    x0, x1, y0, y1, step = spec.rng
    u = spec.unit
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    half = np.array([(x1 - x0) * u / 2, (y1 - y0) * u / 2])

    def at(p) -> np.ndarray:
        return np.array([(p[0] - cx) * u, (p[1] - cy) * u, 0.0])

    m = spec.m
    mapped = lambda p: (m[0, 0] * p[0] + m[0, 1] * p[1], m[1, 0] * p[0] + m[1, 1] * p[1])  # noqa: E731
    size = spec.size
    view = Rectangle(half[0] * 2, half[1] * 2).set_stroke(width=0).set_fill(opacity=0)

    # the fixed plane: faint grid, axes, numbered ticks
    back = VGroup()
    for k in range(math.ceil(x0 / step - 1e-9), math.floor(x1 / step + 1e-9) + 1):
        back.add(_seg(at((k * step, y0)), at((k * step, y1))))
    for k in range(math.ceil(y0 / step - 1e-9), math.floor(y1 / step + 1e-9) + 1):
        back.add(_seg(at((x0, k * step)), at((x1, k * step))))
    back.set_stroke(th.muted, 1, 0.28)
    axes = VGroup()
    if y0 <= 0 <= y1:
        axes.add(_seg(at((x0, 0)), at((x1, 0))))
    if x0 <= 0 <= x1:
        axes.add(_seg(at((0, y0)), at((0, y1))))
    axes.set_stroke(th.ink, 2, 0.75)
    tick_fs = 0.85 * size
    ticks, tick_labels = VMobject(), VGroup()
    ax_y = min(max(0.0, y0), y1)
    ax_x = min(max(0.0, x0), x1)
    for axis in "xy":
        lo, hi = (x0, x1) if axis == "x" else (y0, y1)
        vals = [k * step for k in range(math.ceil(lo / step - 1e-9), math.floor(hi / step + 1e-9) + 1)]
        vals = [v for v in vals if abs(v) > 1e-9 and lo + 1e-9 < v < hi - 1e-9]
        probe = label(_tick(max(vals, key=abs, default=1), axis == "y" and spec.complex), tick_fs, th.muted)
        room = (probe.get_width() if axis == "x" else probe.get_height()) + 0.14
        every = max(1, math.ceil(room / (step * u)))
        for v in vals:
            p = at((v, ax_y)) if axis == "x" else at((ax_x, v))
            d = UP * 0.06 if axis == "x" else RIGHT * 0.06
            ticks.start_new_path(p - d)
            ticks.add_line_to(p + d)
            if round(v / step) % every:
                continue
            lab = label(_tick(v, axis == "y" and spec.complex), tick_fs, th.muted)
            lab.next_to(p, DOWN if axis == "x" else LEFT, buff=0.1)
            tick_labels.add(lab.set_stroke(th.bg, 4, 1, behind=True))   # readable across grid lines
    ticks.set_stroke(th.ink, 1.5, 0.75)
    names = VGroup()
    if spec.complex:
        for t, p, d in (("\\mathrm{Re}", at((x1, ax_y)), UL), ("\\mathrm{Im}", at((ax_x, y1)), DR)):
            names.add(label(t, 0.95 * size, th.muted).next_to(p, d, buff=0.1).shift(LEFT * 0.05 if d is UL else ORIGIN))

    # lines through the origin (a span, an eigen-direction): they stay put when the matrix acts
    lines = VGroup()
    for it in spec.lines:
        d = np.array(it.xy, float) / (np.linalg.norm(it.xy) or 1)
        far = 4 * max(abs(x0), abs(x1), abs(y0), abs(y1))
        c = _clip(tuple(-far * d), tuple(far * d), spec.rng)
        seg = _seg(at(c[0]), at(c[1])) if c else _seg(at((0, 0)), at((0, 0)))
        lines.add(seg.set_stroke(it.color, 2.5, 0.75 * it.alpha))

    # the moving grid: every line goes where the matrix sends it, cut at the view
    moving = VGroup()
    for p, q, axis in grid if grid is not None else grid_sources(spec.rng, [m]):
        c = _clip(mapped(p), mapped(q), spec.rng)
        seg = _seg(at(c[0]), at(c[1])) if c else _seg(at((0, 0)), at((0, 0)))
        moving.add(seg.set_stroke(th.palette[0], 2.6 if axis else 1.6, (0.9 if axis else 0.55) if c else 0))

    ring = VMobject().set_points_as_corners(
        [at(mapped((math.cos(a), math.sin(a)))) for a in np.linspace(0, TAU, 97)])
    ring.set_stroke(th.ink, 2.5, 0.8 * spec.circle).set_fill(opacity=0)

    placed: list[tuple] = [(lab.get_center()[0], lab.get_center()[1], lab.get_width(), lab.get_height())
                           for lab in [*tick_labels, *names]]
    # what a label should not cover: arrows, lines, axes, the circle (points every ~0.08 u)
    marks = []

    def mark(a, b):
        n = max(2, int(np.linalg.norm(b - a) / 0.08))
        marks.extend(a + (b - a) * s for s in np.linspace(0, 1, n))
    for it in spec.vectors:
        mark(at((0, 0)), at(mapped(it.xy)))
    if spec.angle is not None:
        r = math.radians(spec.angle.xy[0])
        mark(at((0, 0)), at(mapped((math.cos(r), math.sin(r)))))
    for ln in [*lines, *axes]:
        pts = ln.get_points()
        if len(pts):
            mark(pts[0], pts[-1])
    if spec.circle > 0.5:
        marks.extend(ring.get_points()[::2])
    out_offsets: dict = {}
    content_labels = VGroup()

    def put(key, texts, anchor, out, color, alpha):
        labs = [label(t, 1.2 * size, color) for t, _ in texts]
        if not labs:
            return
        off = (offsets or {}).get(key)
        if off is None:
            off = _place(labs[-1], anchor, out, placed, marks, half)
        out_offsets[key] = off
        for lab, (_, a) in zip(labs, texts):
            lab.move_to(anchor + off)
            lab.set_fill(opacity=a * alpha).set_stroke(th.bg, 5, a * alpha, behind=True)
            content_labels.add(lab)
        if alpha > 0.5:
            c = anchor + off
            placed.append((c[0], c[1], labs[-1].get_width(), labs[-1].get_height()))

    # a point on the unit circle at an angle, with its projections on the axes
    turn = VGroup()
    if spec.angle is not None:
        a = spec.angle
        rad = math.radians(a.xy[0])
        p = mapped((math.cos(rad), math.sin(rad)))
        o, tip = at((0, 0)), at(p)
        foot_x, foot_y = at((p[0], 0)), at((0, p[1]))
        r = min(ARC_R, 0.35 * u)
        arc = Arc(0, rad if abs(rad) > 1e-3 else 1e-3, radius=r, arc_center=o)
        arc.set_stroke(th.ink, 2.5, a.alpha * (1 if abs(a.xy[0]) > 1 else 0)).set_fill(opacity=0)
        proj = a.alpha * spec.proj
        cos_c, sin_c = th.palette[2], th.palette[1]
        len_x, len_y = abs(foot_x[0] - o[0]), abs(foot_y[1] - o[1])
        fade = lambda L: min(1.0, L / 0.35)  # noqa: E731 - a projection shorter than its label fades out
        turn.add(arc,
                 _dashes(tip, foot_y).set_stroke(th.muted, 2, proj),
                 _seg(o, foot_x).set_stroke(cos_c, 6, proj),
                 _seg(foot_x, tip).set_stroke(sin_c, 6, proj),     # the right triangle's legs
                 _arrow(o, tip, th.accent, a.alpha),
                 Dot(tip, radius=0.075).set_fill(th.accent, a.alpha))
        if spec.arc:
            mid = rad / 2
            for t, al in spec.arc:
                lab = label(t, 1.1 * size, th.ink)
                lab.move_to(o + np.array([math.cos(mid), math.sin(mid), 0]) * (r + 0.1 + 0.5 * max(lab.get_width(), lab.get_height())))
                lab.set_fill(opacity=al * a.alpha * (1 if abs(a.xy[0]) > 12 else abs(a.xy[0]) / 12))
                lab.set_stroke(th.bg, 5, al * a.alpha, behind=True)
                content_labels.add(lab)
                placed.append((*lab.get_center()[:2], lab.get_width(), lab.get_height()))
        if proj > 0.5:
            mark(o, foot_x)
            mark(foot_x, tip)
        side = 1 if p[1] >= 0 else -1
        for t, foot, d, L, c in ((r"\cos\theta", (o + foot_x) / 2, DOWN * side, len_x, cos_c),
                                 (r"\sin\theta", (foot_x + tip) / 2, RIGHT * (1 if p[0] >= 0 else -1), len_y, sin_c)):
            lab = label(t, 1.05 * size, c)
            lab.next_to(foot, d, buff=0.12)
            al = proj * fade(L)
            lab.set_fill(opacity=al).set_stroke(th.bg, 5, al, behind=True)
            content_labels.add(lab)
            if al > 0.5:
                placed.append((*lab.get_center()[:2], lab.get_width(), lab.get_height()))
        put(("a",), a.labels, tip, tip - o if np.linalg.norm(tip - o) > 1e-6 else RIGHT, th.accent, a.alpha)

    arrows, dots = VGroup(), VGroup()
    for it in spec.vectors:
        tip = at(mapped(it.xy))
        arrows.add(_arrow(at((0, 0)), tip, it.color, it.alpha))
        put(("v", it.name), it.labels, tip, tip - at((0, 0)) if np.linalg.norm(tip) > 1e-6 else UR, it.color, it.alpha)
    for it in spec.points:
        p = at(mapped(it.xy))
        dots.add(Dot(p, radius=0.08).set_fill(it.color, it.alpha))
        put(("p", it.name), it.labels, p, p - at((0, 0)) if np.linalg.norm(p) > 1e-6 else UR, it.color, it.alpha)

    # a tick number under a content label, an arrow tip or a point is hidden (they say more)
    tips = [at(mapped(it.xy)) for it in [*spec.vectors, *spec.points] if it.alpha > 0.3]
    if spec.angle is not None and spec.angle.alpha > 0.3:
        r = math.radians(spec.angle.xy[0])
        tips.append(at(mapped((math.cos(r), math.sin(r)))))
    for lab in tick_labels:
        box = (*lab.get_center()[:2], lab.get_width(), lab.get_height())
        if any(_boxes_overlap(box, (q[0], q[1], 0.3, 0.3)) > 0 for q in tips) or any(_boxes_overlap(box, (*c.get_center()[:2], c.get_width() + 0.16, c.get_height() + 0.12)) > 1e-4
               for c in content_labels if c.get_fill_opacity() > 0.3):
            lab.set_fill(opacity=0).set_stroke(opacity=0, behind=True)
    pic = VGroup(view, back, axes, ticks, tick_labels, names, moving, lines, ring, turn, arrows, dots, content_labels)
    return pic, out_offsets


# --- the block --------------------------------------------------------------------------------
def _colors(node: Node, names: list[str]) -> dict[str, str]:
    th = current()
    cycle = [th.accent, th.palette[2], th.palette[1], th.palette[3], th.palette[4]]
    order = [n for n in node.attrs.get("_colors", "").split(",") if n] or []
    order += [n for n in names if n not in order]
    return {n: cycle[k % len(cycle)] for k, n in enumerate(order)}


def spec_of(node: Node) -> Spec:
    """The beat's ``<plane>`` as a Spec (labels at full opacity)."""
    a = node.attrs
    what = f"<plane id={node.id}>"
    try:
        vectors = named_pairs(a.get("vectors", ""), f"{what} vectors=")
        points = named_pairs(a.get("points", ""), f"{what} points=")
        lines = named_pairs(a.get("lines", ""), f"{what} lines=", need_name=False)
        mat = parse_matrix(a.get("matrix", ""))
        ang = parse_angle(a.get("angle", ""))
    except BeatError as e:
        raise BeatError(f"{what}: {e}") from e
    clash = {squash(n) for n, _ in vectors} & {squash(n) for n, _ in points}
    if clash:
        raise BeatError(f"{what}: {sorted(clash)} is both a vector and a point; give each its own name")
    for name, d in lines:
        if abs(d[0]) < 1e-12 and abs(d[1]) < 1e-12:
            raise BeatError(f'{what} lines="{a["lines"]}": a line needs a direction other than 0,0')
    if a.get("_range"):
        rng = tuple(float(v) for v in a["_range"].split(","))
    else:
        rng = range_of([node])
    x0, x1, y0, y1, _ = rng
    for name, p in [*vectors, *points]:
        q = apply(mat, p)
        if not (x0 - 1e-9 <= q[0] <= x1 + 1e-9 and y0 - 1e-9 <= q[1] <= y1 + 1e-9):
            raise BeatError(f"{what}: {name} lands at ({_num(q[0])}, {_num(q[1])}), outside "
                            f'x="{_num(x0)},{_num(x1)}" y="{_num(y0)},{_num(y1)}"; widen x=/y= or leave both out '
                            "(the range is then chosen to hold everything)")
    unit = float(a.get("h", H)) / (y1 - y0)
    if a.get("w"):
        unit = min(unit, float(a["w"]) / (x1 - x0))
    unit = min(unit, MAX_W / (x1 - x0))
    color = _colors(node, [n for n, _ in [*vectors, *points]])
    coords = _on(a, "coords")

    def labels(name, p):
        q = apply(mat, p)
        return [(f"{name}=({_num(q[0])},{_num(q[1])})" if coords else name, 1.0)]

    by_dir = {}
    for name, p in vectors:
        by_dir.setdefault(round(math.atan2(p[1], p[0]) % math.pi, 4), color[name])
    line_items = []
    for name, d in lines:
        c = by_dir.get(round(math.atan2(d[1], d[0]) % math.pi, 4), current().muted)
        line_items.append(Item(name, d, c))
    angle = None
    if ang is not None:
        angle = Item(ang[0], (ang[1], 0.0), current().accent, labels=[(ang[0], 1.0)] if ang[0] else [])
    theta = a.get("theta", "θ").strip()
    return Spec(rng=rng, unit=unit, m=np.array(mat if mat is not None else ((1, 0), (0, 1)), float),
                vectors=[Item(n, p, color[n], labels=labels(n, p)) for n, p in vectors],
                points=[Item(n, p, color[n], labels=labels(n, p)) for n, p in points],
                lines=line_items, circle=1.0 if _on(a, "circle") else 0.0, angle=angle,
                proj=1.0 if _on(a, "projections") and angle is not None else 0.0,
                arc=[(theta, 1.0)] if angle is not None and theta.lower() != "none" else [],
                complex=_on(a, "complex"), size=float(a.get("size", 30)))


class PlaneBlock(Block):
    """``<plane vectors="v:1,1" matrix="2,1;1,2" circle="true" angle="z:45" projections="true">``."""

    tag = "plane"

    def __init__(self, node: Node):
        self.spec = spec_of(node)
        pic, self.offsets = draw(self.spec)
        self.view = pic[0]
        super().__init__(*pic.submobjects)
        self.set_content(node, "vectors", "points", "lines", "matrix", "circle", "angle", "projections",
                         "theta", "coords", "complex", "_range", "_colors", "size")


def build(node: Node, world=None) -> PlaneBlock:
    return PlaneBlock(node)


# --- motion -----------------------------------------------------------------------------------
def _between(p, q, t: float) -> tuple[float, float]:
    """Straight from p to q; the same length in a new direction turns along the arc instead (a
    point on the unit circle goes round it, never across the chord)."""
    r0, r1 = math.hypot(*p), math.hypot(*q)
    if r0 > 1e-6 and abs(r0 - r1) < 1e-3 * r0:
        a0, a1 = math.atan2(p[1], p[0]), math.atan2(q[1], q[0])
        da = (a1 - a0 + math.pi) % TAU - math.pi
        if abs(abs(da) - math.pi) > 1e-6:                    # half a turn has no shorter side: go straight
            return r0 * math.cos(a0 + da * t), r0 * math.sin(a0 + da * t)
    return tuple(a + (b - a) * t for a, b in zip(p, q))


def _mix_items(old: list[Item], new: list[Item], t: float) -> list[Item]:
    """Matched by name: a kept item slides to its new coordinates (its label text cross-fades),
    a new one fades in at its place, a gone one fades out."""
    by_new = {squash(i.name): i for i in new}
    out = []
    for i in old:
        j = by_new.pop(squash(i.name), None)
        if j is None:
            out.append(replace(i, alpha=i.alpha * (1 - t)))
            continue
        xy = _between(i.xy, j.xy, t)
        same = [x for x, _ in i.labels] == [x for x, _ in j.labels]
        labs = j.labels if same else [(x, (1 - t)) for x, _ in i.labels] + [(x, t) for x, _ in j.labels]
        out.append(replace(j, xy=xy, labels=labs, alpha=i.alpha + (j.alpha - i.alpha) * t))
    out += [replace(j, alpha=j.alpha * t) for j in by_new.values()]
    return out


def _mix(a: Spec, b: Spec, t: float) -> Spec:
    if a.angle is not None and b.angle is not None:
        angle = _mix_items([a.angle], [replace(b.angle, name=a.angle.name)], t)[0]
        if a.angle.labels != b.angle.labels:
            angle.labels = [(x, 1 - t) for x, _ in a.angle.labels] + [(x, t) for x, _ in b.angle.labels]
    elif a.angle is not None or b.angle is not None:
        one = a.angle or b.angle
        angle = replace(one, alpha=1 - t if a.angle is not None else t)
    else:
        angle = None
    arc = a.arc if a.arc == b.arc else [(x, 1 - t) for x, _ in a.arc] + [(x, t) for x, _ in b.arc]
    return replace(b, m=a.m + (b.m - a.m) * t,
                   vectors=_mix_items(a.vectors, b.vectors, t), points=_mix_items(a.points, b.points, t),
                   lines=_mix_items(a.lines, b.lines, t), circle=a.circle + (b.circle - a.circle) * t,
                   angle=angle, proj=a.proj + (b.proj - a.proj) * t, arc=arc)


def _rot(v: np.ndarray, a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([c * v[0] - s * v[1], s * v[0] + c * v[1], 0.0])


def morph(old: PlaneBlock, new: PlaneBlock, sources=None) -> Animation | None:
    """Same range: the matrix acts continuously (every grid line, arrow and the circle move
    together from the old matrix to the new), arrow tips slide to new coordinates, a point on the
    circle turns along it with its projections. Another range cross-fades (the default)."""
    a, b = old.spec, new.spec
    if a.rng != b.rng or abs(a.unit - b.unit) > 1e-9:
        return None
    grid = grid_sources(a.rng, [a.m + (b.m - a.m) * s for s in np.linspace(0, 1, 9)])
    c0, c1 = old.view.get_center(), new.view.get_center()
    nat_w = (a.rng[1] - a.rng[0]) * a.unit
    k0, k1 = old.view.get_width() / nat_w, new.view.get_width() / nat_w   # the layout's scale, old and new

    def frame(t: float) -> VGroup:
        s = _mix(a, b, t)
        offs = {}
        for key in set(old.offsets) | set(new.offsets):
            p, q = old.offsets.get(key), new.offsets.get(key)
            if p is not None and q is not None and key == ("a",):
                # the point's label turns with the point, then settles where it is placed
                turn = math.radians(b.angle.xy[0] - a.angle.xy[0])
                offs[key] = _rot(p, turn * t) * (1 - t) + _rot(q, -turn * (1 - t)) * t
            else:
                offs[key] = q if p is None else p if q is None else p + (q - p) * t
        pic, _ = draw(s, grid, offs)
        pic.scale(k0 + (k1 - k0) * t, about_point=ORIGIN).shift(c0 + (c1 - c0) * t)
        return pic.fix_in_frame()

    carrier = frame(0.0)

    def update(m, alpha):
        target = frame(smooth(alpha))   # UpdateFromAlphaFunc ignores rate_func in manimgl: time it here
        m.become(target)
        for sm in m.get_family():
            if isinstance(sm, VMobject):
                sm.refresh_unit_normal()

    hide = UpdateFromAlphaFunc(old, lambda m, t: m.set_opacity(0.0), rate_func=linear)
    return AnimationGroup(hide, UpdateFromAlphaFunc(carrier, update, rate_func=linear, remover=True))
