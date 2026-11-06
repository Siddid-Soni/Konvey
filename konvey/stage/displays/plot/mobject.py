"""``<plot>`` (manimgl): axes through the origin with numbered ticks, curves traced exactly from
their parsed expressions and clipped at the axis box, labels placed where nothing else is.

Between two beats with the same id the plot is re-traced every frame (``morph``): the ranges,
the screen box and every curve's expression are blended, so a term added to a sum grows the
curve, a rescaled axis glides, a marker or a point slides along x, and a new curve draws in."""

from __future__ import annotations

import json

import numpy as np

from manimlib import *  # noqa: F401,F403

from ...theme import current
from ...tree import BeatError, Node
from ..base import Block
from . import spec as S

DIRS = [RIGHT, UR, DR, UP, DOWN, UL, DL, LEFT]


def _label(text: str, size: float, color: str) -> Mobject:
    """Plain words as text; ``T_3``, ``P_11``, ``x^2``, ``\\sin x`` or ``$…$`` typeset (spec.label_form)."""
    s = str(text).strip()
    form, src = S.label_form(s)
    m = None
    if form == "tex":
        try:
            m = Tex(src, font_size=size * 1.25).set_fill(color, 1)
        except Exception as e:  # noqa: BLE001 - LaTeX errors come back to Agent 3 by name
            if s.startswith("$") or "\\" in s:
                raise BeatError(f"label {s!r} is not valid LaTeX: {str(e).strip()[:120]}") from e
            src = s.replace("_", " ").replace("^", "")   # our own conversion failed: plain words
    if m is None:
        m = Text(src, font=current().body_font, font_size=size, fill_color=color)
    m.plot_text = s
    return m


class Frame:
    """Plot coordinates -> points: the axis box's lower-left corner and its two sides."""

    def __init__(self, x, y, ll, ex, ey, unit: float = 1.0):
        self.x, self.y = tuple(x), tuple(y)
        self.ll, self.ex, self.ey, self.unit = np.array(ll, float), np.array(ex, float), np.array(ey, float), unit

    @classmethod
    def of(cls, block: "PlotBlock") -> "Frame":
        v = block.box.get_vertices()   # LL, LR, UR, UL wherever the layout put the block
        return cls(block.spec.x, block.spec.y, v[0], v[1] - v[0], v[3] - v[0],
                   float(np.linalg.norm(v[1] - v[0])) / block.w)

    def lerp(self, other: "Frame", t: float) -> "Frame":
        mix = lambda a, b: (1 - t) * np.asarray(a, float) + t * np.asarray(b, float)  # noqa: E731
        return Frame(mix(self.x, other.x), mix(self.y, other.y), mix(self.ll, other.ll),
                     mix(self.ex, other.ex), mix(self.ey, other.ey), float(mix(self.unit, other.unit)))

    def p(self, x, y) -> np.ndarray:
        """One point, or an (n, 3) array for arrays of x and y."""
        u = (np.asarray(x, float) - self.x[0]) / (self.x[1] - self.x[0])
        v = (np.asarray(y, float) - self.y[0]) / (self.y[1] - self.y[0])
        return self.ll + np.multiply.outer(u, self.ex) + np.multiply.outer(v, self.ey)

    @property
    def size(self) -> tuple[float, float]:   # the box in the plot's own units
        return float(np.linalg.norm(self.ex)) / self.unit, float(np.linalg.norm(self.ey)) / self.unit

    @property
    def origin(self) -> tuple[float, float]:
        """Where the axes cross: at 0 when 0 is in range, else at the range's near end."""
        (x0, x1), (y0, y1) = self.x, self.y
        return min(max(0.0, x0), x1), min(max(0.0, y0), y1)

    def inside(self, x, y, slack: float = 1e-6) -> bool:
        (x0, x1), (y0, y1) = self.x, self.y
        sx, sy = slack * (x1 - x0), slack * (y1 - y0)
        return x0 - sx <= x <= x1 + sx and y0 - sy <= y <= y1 + sy


# --- geometry, shared by the static build and every frame of a morph --------------------------
def _set_path(vm: VMobject, runs: list[np.ndarray], frame: Frame | None = None) -> None:
    """Points of several pieces (plot coordinates with ``frame``, else points already)."""
    vm.clear_points()
    runs = [frame.p(r[:, 0], r[:, 1]) if frame is not None else r for r in runs if len(r) >= 2]
    if not runs:   # keep two points so animations can run on it; nothing is visible
        vm.set_points_as_corners([frame.ll if frame is not None else ORIGIN] * 2)
        vm.set_stroke(opacity=0)
        return
    for r in runs:
        vm.start_new_path(r[0])
        vm.add_points_as_corners(r[1:])
    vm.set_stroke(opacity=1)


def _dashes(a, b, unit: float, dash: float = 0.12, gap: float = 0.09) -> list[np.ndarray]:
    a, b = np.asarray(a, float), np.asarray(b, float)
    n = np.linalg.norm(b - a) / unit
    out, s = [], 0.0
    while s < n:
        e = min(n, s + dash)
        out.append(np.array([a + (b - a) * s / n, a + (b - a) * e / n]))
        s = e + gap
    return out


def _curve(fr: Frame, f, vm: VMobject, upto: float | None = None) -> None:
    w, h = fr.size
    _set_path(vm, S.trace(f, fr.x, fr.y, w, h, upto), fr)


def _axes(fr: Frame, axes: VGroup) -> None:
    ox, oy = fr.origin
    axes[0].put_start_and_end_on(fr.p(fr.x[0], oy), fr.p(fr.x[1], oy))
    axes[1].put_start_and_end_on(fr.p(ox, fr.y[0]), fr.p(ox, fr.y[1]))


def _tick_at(fr: Frame, axis: str, v: float) -> np.ndarray:
    ox, oy = fr.origin
    return fr.p(v, oy) if axis == "x" else fr.p(ox, v)


def _tick(fr: Frame, axis: str, v: float, line: Line) -> None:
    c, d = _tick_at(fr, axis, v), (UP if axis == "x" else RIGHT) * 0.06 * fr.unit
    line.put_start_and_end_on(c - d, c + d)
    lo, hi = fr.x if axis == "x" else fr.y
    line.set_stroke(opacity=1 if lo - 1e-9 <= v <= hi + 1e-9 else 0)


def _shade(fr: Frame, a, b, lo: float, hi: float, vm: VMobject, opacity: float) -> None:
    lo, hi = max(lo, fr.x[0]), min(hi, fr.x[1])
    if hi <= lo:
        _set_path(vm, [], fr)
        vm.set_fill(opacity=0)
        return
    xs = np.linspace(lo, hi, 160)
    ya, yb = (np.clip(np.nan_to_num(S.value(e, xs), nan=fr.y[0]), *fr.y) for e in (a, b))
    vm.set_points_as_corners(fr.p(np.r_[xs, xs[::-1], xs[:1]], np.r_[ya, yb[::-1], ya[:1]]))
    vm.set_fill(opacity=opacity).set_stroke(width=0)


def _mark(fr: Frame, axis: str, v: float, vm: VMobject) -> np.ndarray:
    """A dashed line across the box; returns the end its label sits at (top / right)."""
    a, b = (fr.p(v, fr.y[0]), fr.p(v, fr.y[1])) if axis == "x" else (fr.p(fr.x[0], v), fr.p(fr.x[1], v))
    lo, hi = fr.x if axis == "x" else fr.y
    _set_path(vm, _dashes(a, b, fr.unit) if lo <= v <= hi else [])
    return b


def _gap(fr: Frame, a, b, axis: str, v: float, vm: VMobject) -> np.ndarray | None:
    """The distance between two curves along y=v (horizontal) or x=v (vertical), with end
    ticks; returns its middle, or None when a curve does not reach that level."""
    if axis == "y":
        ra, rb = S.roots(a, v, fr.x), S.roots(b, v, fr.x)
        if not ra or not rb or not fr.y[0] <= v <= fr.y[1]:
            _set_path(vm, [])
            return None
        xa, xb = min(((p, q) for p in ra for q in rb), key=lambda pq: abs(pq[0] - pq[1]))
        p, q, d = fr.p(xa, v), fr.p(xb, v), UP * 0.09 * fr.unit
    else:
        ya, yb = (float(np.clip(S.value(e, [v])[0], *fr.y)) for e in (a, b))
        if not fr.x[0] <= v <= fr.x[1] or not np.isfinite(ya + yb):
            _set_path(vm, [])
            return None
        p, q, d = fr.p(v, ya), fr.p(v, yb), RIGHT * 0.09 * fr.unit
    ends = [np.array([p - d, p + d]), np.array([q - d, q + d])]
    # a gap shorter than its end ticks is drawn as the bare segment (no blob)
    _set_path(vm, [np.array([p, q]), *(ends if np.linalg.norm(q - p) > 0.3 * fr.unit else [])])
    return (p + q) / 2


def _point_y(fr: Frame, x: float, yref) -> float:
    return float(S.value(yref, [x])[0])


def _drop(fr: Frame, p: np.ndarray, vm: VMobject) -> None:
    """A dashed line from the point straight down (or up) to the x axis (3b1b's get_v_line)."""
    x = (np.asarray(p - fr.ll) @ fr.ex) / (fr.ex @ fr.ex) * (fr.x[1] - fr.x[0]) + fr.x[0]
    foot = fr.p(x, fr.origin[1])
    _set_path(vm, _dashes(foot, p, fr.unit, dash=0.08, gap=0.07) if np.linalg.norm(p - foot) > 0.05 else [])


def _gap_value(a, b, axis: str, v: float, fr: Frame) -> float:
    if axis == "x":
        return float(abs(S.value(a, [v])[0] - S.value(b, [v])[0]))
    ra, rb = S.roots(a, v, fr.x), S.roots(b, v, fr.x)
    return min((abs(p - q) for p in ra for q in rb), default=float("nan"))


# --- label placement --------------------------------------------------------------------------
class _Space:
    """What is already on the picture: points of curves and lines, and boxes of labels."""

    def __init__(self, bounds):
        self.pts = np.zeros((0, 2))
        self.weak = np.zeros((0, 2))
        self.boxes: list[tuple[float, float, float, float]] = []
        self.bounds = bounds   # (x0, y0, x1, y1) a label may use

    def add_points(self, mob: Mobject, weak: bool = False, step: float = 0.04) -> None:
        for path in (m.get_points() for m in mob.get_family() if m.has_points()):
            if len(path) < 2:
                continue
            seg = np.linalg.norm(np.diff(path[:, :2], axis=0), axis=1)
            s = np.r_[0, np.cumsum(seg)]
            if s[-1] <= 0:
                continue
            at = np.linspace(0, s[-1], int(s[-1] / step) + 2)
            pts = np.c_[np.interp(at, s, path[:, 0]), np.interp(at, s, path[:, 1])]
            if weak:
                self.weak = np.r_[self.weak, pts]
            else:
                self.pts = np.r_[self.pts, pts]

    def add_box(self, mob: Mobject) -> None:
        (x0, y0, _), (x1, y1, _) = mob.get_corner(DL), mob.get_corner(UR)
        self.boxes.append((x0, y0, x1, y1))

    def cost(self, c, w: float, h: float) -> float:
        x0, y0, x1, y1 = c[0] - w / 2 - 0.05, c[1] - h / 2 - 0.05, c[0] + w / 2 + 0.05, c[1] + h / 2 + 0.05
        pad = 0.08   # labels keep this much clear of each other
        hit = lambda p: int(((p[:, 0] > x0) & (p[:, 0] < x1) & (p[:, 1] > y0) & (p[:, 1] < y1)).sum())  # noqa: E731
        over = sum(max(0, min(x1 + pad, b[2]) - max(x0 - pad, b[0])) * max(0, min(y1 + pad, b[3]) - max(y0 - pad, b[1]))
                   for b in self.boxes)
        bx0, by0, bx1, by1 = self.bounds
        out = max(0, bx0 - x0) + max(0, x1 - bx1) + max(0, by0 - y0) + max(0, y1 - by1)
        return 0.08 * hit(self.pts) + 0.03 * hit(self.weak) + 40 * over / (w * h) + 20 * out

    def place(self, mob: Mobject, options: list[tuple[np.ndarray, np.ndarray, float]], gap: float = 0.1):
        """options: (anchor, direction, preference cost). The label goes to the cheapest."""
        w, h = mob.get_width(), mob.get_height()
        best = None
        for anchor, d, pref in options:
            c = np.asarray(anchor, float) + d * gap + np.array([d[0] * w / 2, d[1] * h / 2, 0])
            k = pref + self.cost(c, w, h)
            if best is None or k < best[0]:
                best = (k, c)
        mob.move_to(best[1])
        self.add_box(mob)


def _along(vm: VMobject, fracs) -> list[np.ndarray]:
    """Points at fractions of a curve's drawn length (pieces in order)."""
    pts = vm.get_points()
    if len(pts) < 2 or vm.get_stroke_opacity() == 0:
        return []
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.r_[0, np.cumsum(seg)]
    return [np.array([np.interp(f * s[-1], s, pts[:, k]) for k in range(3)]) for f in fracs]


# --- the block ----------------------------------------------------------------------------------
class PlotBlock(Block):
    tag = "plot"

    def __init__(self, node: Node):
        th = current()
        try:
            self.spec = sp = S.parse(node.attrs)
        except BeatError as e:
            raise BeatError(f"<plot id={node.id}> {e}") from e
        self.w, self.h = float(node.attrs.get("w", 7)), float(node.attrs.get("h", 4))
        size = float(node.attrs.get("size", 30))
        fr = Frame(sp.x, sp.y, ORIGIN, self.w * RIGHT, self.h * UP)
        self.box = Polygon(ORIGIN, self.w * RIGHT, self.w * RIGHT + self.h * UP, self.h * UP)
        self.box.set_stroke(width=0).set_fill(opacity=0)
        names = [c.strip() for c in node.attrs.get("color", "").split(",") if c.strip()]
        colors = [th.color(c) for c in names] or list(th.palette)
        self.colors = [colors[i % len(colors)] for i in range(len(sp.curves))]
        muted = th.muted

        self.axes = VGroup(Line(LEFT, RIGHT), Line(DOWN, UP)).set_stroke(muted, 2.2)
        _axes(fr, self.axes)
        ox, oy = fr.origin
        self.ticks = []          # (axis, value, tick line, label or None)
        tick_size = 0.9 * size   # landmarks read at a glance (3b1b's −π, π, 2π are body size)
        corner = False   # the x axis wrote the value where the axes meet: the y axis does not repeat it
        for axis, (lo, hi), length, pi in (("x", sp.x, self.w, sp.xpi), ("y", sp.y, self.h, sp.ypi)):
            other = oy if axis == "x" else ox
            other_lo, other_hi = sp.y if axis == "x" else sp.x
            crossing = ox if axis == "x" else oy
            for v, text in S.ticks(lo, hi, length, pi):
                at_cross = abs(v - crossing) < 1e-9 and other_lo < other < other_hi and lo < v < hi
                if at_cross:   # the origin, where both axes meet: no tick, no "0"
                    continue
                if abs(v - crossing) < 1e-9:   # the point where the axes meet: labelled once, on x
                    if axis == "y" and corner:
                        continue
                    corner = corner or axis == "x"
                line = Line(LEFT, RIGHT).set_stroke(muted, 2.2)
                _tick(fr, axis, v, line)
                lab = _label(text, tick_size, muted)
                c = _tick_at(fr, axis, v)
                lab.move_to(c + (DOWN * (0.12 + lab.get_height() / 2) if axis == "x"
                                 else LEFT * (0.1 + lab.get_width() / 2)))
                lab.set_backstroke(th.bg, 5)
                self.ticks.append((axis, v, line, lab))
        self.tick_lines = VGroup(*(t[2] for t in self.ticks))
        self.tick_labels = VGroup(*(t[3] for t in self.ticks))

        self.lines = VGroup()
        for c, color in zip(sp.curves, self.colors):
            vm = VMobject().set_stroke(color, 4)
            _curve(fr, c.f, vm)
            self.lines.add(vm)
        self.shades = VGroup()
        for a, b, lo, hi, _ in sp.shades:
            base = a if isinstance(a, S.Curve) else b
            color = self.colors[sp.curves.index(base)] if isinstance(base, S.Curve) else th.accent
            vm = VMobject().set_fill(color, 0.28).set_stroke(width=0)
            _shade(fr, a, b, lo, hi, vm, 0.28)
            self.shades.add(vm)
        self.marks = VGroup()
        for axis, v, _ in sp.marks:
            vm = VMobject().set_stroke(th.accent, 2.5)
            _mark(fr, axis, v, vm)
            self.marks.add(vm)
        self.gaps = VGroup()
        gap_mid = []
        for a, b, axis, v, _ in sp.gaps:
            vm = VMobject().set_stroke(th.accent, 5)
            gap_mid.append(_gap(fr, a, b, axis, v, vm))
            self.gaps.add(vm)
        self.dots = VGroup()
        for _, x, yref in sp.points:
            y = _point_y(fr, x, yref)
            dot = Dot(fr.p(x, y) if np.isfinite(y) else ORIGIN, radius=0.075, fill_color=th.accent)
            dot.set_backstroke(th.bg, 3)
            if not (np.isfinite(y) and fr.inside(x, y)):
                raise BeatError(f'<plot id={node.id}> point at x={x:g}, y={y:g} is outside x/y; '
                                f"widen the range or drop it")
            self.dots.add(dot)
        self.drops = VGroup()
        if sp.drop:
            for dot in self.dots:
                vm = VMobject().set_stroke(muted, 2)
                _drop(fr, dot.get_center(), vm)
                self.drops.add(vm)

        # Labels: axis names, then marks, gaps, points and curves, each where it covers least.
        space = _Space((-1.2, -0.7, self.w + 3.0, self.h + 0.7))
        for m in (*self.lines, *self.marks, *self.gaps, *self.dots, *self.drops):
            space.add_points(m)
        space.add_points(self.axes, weak=True)
        for lab in self.tick_labels:
            space.add_box(lab)
        lab_size = 0.9 * size
        self.names = VGroup()
        self.name_labels = {}
        for key, end, opts in (("xlabel", fr.p(sp.x[1], oy), (RIGHT, DR, UR)),
                               ("ylabel", fr.p(ox, sp.y[1]), (UP, UR, RIGHT))):
            if node.attrs.get(key):
                lab = _label(node.attrs[key], lab_size, muted)
                space.place(lab, [(end, d, 0.2 * i) for i, d in enumerate(opts)], gap=0.14)
                self.names.add(lab)
                self.name_labels[key] = lab
        self.mark_labels = []
        for (axis, v, text), vm in zip(sp.marks, self.marks):
            lab = None
            if text:
                lab = _label(S.fill(text, x=v), lab_size, th.accent)
                top, bottom = (fr.p(v, sp.y[1]), fr.p(v, sp.y[0])) if axis == "x" else (fr.p(sp.x[1], v), fr.p(sp.x[0], v))
                opts = ([(top, UP, 0), (top, UR, 0.3), (top, UL, 0.3), (bottom, DOWN, 1.5)] if axis == "x"
                        else [(top, RIGHT, 0), (top, UL, 0.4), (top, DL, 0.4), (bottom, UR, 0.6)])
                space.place(lab, opts)
                lab.plot_anchor = ((v, sp.y[1]) if axis == "x" else (sp.x[1], v))
                lab.set_backstroke(th.bg, 5)
            self.mark_labels.append(lab)
        self.gap_labels = []
        for (a, b, axis, v, text), mid in zip(sp.gaps, gap_mid):
            lab = None
            if text and mid is not None:
                lab = _label(S.fill(text, gap=_gap_value(a, b, axis, v, fr), x=v), lab_size, th.accent)
                dirs = (DOWN, UP) if axis == "y" else (RIGHT, LEFT)
                space.place(lab, [(mid, d, 0.3 * i) for i, d in enumerate(dirs)], gap=0.16)
                lab.set_backstroke(th.bg, 5)
            self.gap_labels.append(lab)
        self.point_labels = []
        for (name, x, yref), dot in zip(sp.points, self.dots):
            lab = None
            if name:
                lab = _label(S.fill(name, x=x, y=_point_y(fr, x, yref)), lab_size, th.ink)
                space.place(lab, [(dot.get_center(), d, 0.12 * i) for i, d in enumerate([UR, UL, DR, DL, UP, DOWN, RIGHT, LEFT])])
                lab.set_backstroke(th.bg, 5)
            self.point_labels.append(lab)
        self.curve_labels = []
        fracs = [1.0, 0.94, 0.88, 0.8, 0.72, 0.62, 0.5, 0.38, 0.26, 0.14]
        for c, vm, color in zip(sp.curves, self.lines, self.colors):
            lab = None
            if c.label:
                lab = _label(c.label, lab_size, color)
                opts = []
                for f, p in zip(fracs, _along(vm, fracs)):
                    for k, d in enumerate(DIRS):
                        if d is RIGHT and f < 1.0:
                            continue
                        opts.append((p, d, 1.5 * (1 - f) + 0.08 * k))
                if opts:
                    space.place(lab, opts, gap=0.12)
                else:   # nothing of it is in view: name it beside the box
                    lab.next_to(self.box, RIGHT, buff=0.2)
                lab.set_backstroke(th.bg, 5)
            self.curve_labels.append(lab)
        self.shade_labels = []
        for (a, b, lo, hi, text), vm in zip(sp.shades, self.shades):
            lab = None
            if text:
                lab = _label(text, 0.8 * size, th.ink).move_to(vm.get_center() if vm.has_points() else ORIGIN)
                lab.set_backstroke(th.bg, 4)
            self.shade_labels.append(lab)

        labels = [m for m in (*self.mark_labels, *self.gap_labels, *self.point_labels,
                              *self.curve_labels, *self.shade_labels) if m is not None]
        self.labels = VGroup(*labels)
        # tick labels over the curves: a curve crossing the axis at pi must not hide "π"
        super().__init__(self.box, self.shades, self.axes, self.tick_lines, self.marks, self.drops, self.lines,
                         self.tick_labels, self.gaps, self.dots, self.names, self.labels)
        self.set_content(node, "fn", "x", "y", "points", "mark", "gap", "shade", "color",
                         "xlabel", "ylabel", "slide", "drop")


def _point(self, x: float, y: float) -> np.ndarray:
    """Where the plot's (x, y) is on the page now (after the layout has fitted it)."""
    return Frame.of(self).p(x, y)


def _bounds(self) -> tuple[float, float, float, float]:
    (a, b, _), (c, d, _) = self.box.get_corner(DL), self.box.get_corner(UR)
    return a, b, c, d


PlotBlock.point, PlotBlock.bounds = _point, _bounds


def build(node: Node, world=None) -> PlotBlock:
    return PlotBlock(node)


def enter(node: Node, mob: PlotBlock, run_time: float) -> Animation:
    """Axes first, then each curve drawn left to right, then what sits on the curves."""
    name = node.attrs.get("enter")
    if name and name != "create":
        from ...animations import ENTERS
        fn = ENTERS.get(name)
        return (fn(mob, run_time) if fn else None) or FadeIn(mob, shift=0.25 * UP, run_time=run_time)
    frame = Group(mob.axes, mob.tick_lines, mob.tick_labels, mob.names)
    rest = Group(mob.shades, mob.marks, mob.drops, mob.gaps, mob.dots, mob.labels)
    draw = max(0.8, run_time - 0.9)
    return AnimationGroup(FadeIn(frame, run_time=0.5),
                          ShowCreation(mob.lines, lag_ratio=0.15, run_time=draw),
                          FadeIn(rest, run_time=0.5), lag_ratio=0.45)


# --- motion -------------------------------------------------------------------------------------
def _pairs(old: list, new: list, key) -> list[tuple[int | None, int | None]]:
    """Match items by key (a curve's label, a point's name), then the rest in order."""
    out, used = [], set()
    rest_old = []
    for i, o in enumerate(old):
        k = key(o)
        j = next((j for j, n in enumerate(new) if j not in used and k and key(n) == k), None)
        if j is None:
            rest_old.append(i)
        else:
            used.add(j)
            out.append((i, j))
    rest_new = [j for j in range(len(new)) if j not in used]
    for i, j in zip(rest_old, rest_new):
        out.append((i, j))
    out += [(i, None) for i in rest_old[len(rest_new):]]
    out += [(None, j) for j in rest_new[len(rest_old):]]
    return out


class _Label:
    """One label across the morph: the same words glide (riding on an anchor if given);
    changed words cross-fade on the way; a label only in one beat fades."""

    def __init__(self, o, n, anchor_o=None, anchor_n=None):
        self.o = o.copy() if o is not None else None
        self.n = n.copy() if n is not None else None
        self.same = o is not None and n is not None and getattr(o, "plot_text", None) == getattr(n, "plot_text", None)
        self.co = o.get_center() if o is not None else None
        self.cn = n.get_center() if n is not None else None
        self.ho = o.get_height() if o is not None else None
        self.hn = n.get_height() if n is not None else None
        self.ofs_o = self.co - anchor_o if o is not None and anchor_o is not None else None
        self.ofs_n = self.cn - anchor_n if n is not None and anchor_n is not None else None
        self.ofs = (self.ofs_o if self.ofs_o is not None else self.ofs_n,
                    self.ofs_n if self.ofs_n is not None else self.ofs_o)

    def mobs(self) -> list[Mobject]:
        return [m for m in (self.o if not self.same else None, self.n) if m is not None]

    def update(self, t: float, anchor=None) -> None:
        if self.o is None and self.n is None:   # unlabelled in both beats (a curve, a shade)
            return
        co = self.co if self.co is not None else self.cn
        cn = self.cn if self.cn is not None else self.co
        if anchor is not None and self.ofs[0] is not None:
            c = anchor + (1 - t) * self.ofs[0] + t * self.ofs[1]
        else:
            c = (1 - t) * co + t * cn
        if self.same:
            self.n.set_height((1 - t) * self.ho + t * self.hn).move_to(c)
            return
        if self.o is not None:
            self.o.move_to(c).set_opacity(float(np.clip(1 - 2 * t, 0, 1)) if self.n is not None else 1 - t)
        if self.n is not None:
            self.n.move_to(c).set_opacity(float(np.clip(2 * t - 1, 0, 1)))


def _edge_fn(e):
    return (lambda xs: S.value(e, xs))


def _blend(fo, fn, t):
    return S.Curve("", "", lambda xs: (1 - t) * fo(xs) + t * fn(xs))


def morph(old: Mobject, new: Mobject, sources=None) -> Animation | None:
    if not isinstance(old, PlotBlock) or not isinstance(new, PlotBlock):
        return None
    return _Morph(old, new).animation()


class _Morph:
    def __init__(self, old: PlotBlock, new: PlotBlock):
        self.old, self.new = old, new
        self.fo, self.fn = Frame.of(old), Frame.of(new)
        so, sn = old.spec, new.spec
        group = []
        self.axes = new.axes.copy()
        group.append(self.axes)

        # ticks: the union of both beats' ticks, each fading where only one beat has it
        self.ticks = []
        key = lambda t: (t[0], round(t[1], 9))  # noqa: E731
        old_t, new_t = {key(t): t for t in old.ticks}, {key(t): t for t in new.ticks}
        for k in sorted(set(old_t) | set(new_t)):
            src = new_t.get(k) or old_t[k]
            line = src[2].copy()
            lab = _Label(old_t[k][3] if k in old_t else None, new_t[k][3] if k in new_t else None,
                         _tick_at(self.fo, k[0], k[1]) if k in old_t else None,
                         _tick_at(self.fn, k[0], k[1]) if k in new_t else None)
            self.ticks.append((k, line, lab, k in old_t, k in new_t))
            group += [line, *lab.mobs()]

        self.curves = []
        for i, j in _pairs(so.curves, sn.curves, lambda c: S.squash(c.label)):
            vm = (new.lines[j] if j is not None else old.lines[i]).copy()
            lab = _Label(old.curve_labels[i] if i is not None else None,
                         new.curve_labels[j] if j is not None else None)
            self.curves.append((i, j, vm, lab))
            group += [vm, *lab.mobs()]

        self.shades = []
        for k in range(max(len(so.shades), len(sn.shades))):
            i = k if k < len(so.shades) else None
            j = k if k < len(sn.shades) else None
            vm = (new.shades[j] if j is not None else old.shades[i]).copy()
            lab = _Label(old.shade_labels[i] if i is not None else None,
                         new.shade_labels[j] if j is not None else None)
            self.shades.append((i, j, vm, lab))
            group = [vm, *lab.mobs()] + group   # under the axes and curves

        self.marks = []
        for i, j in _pairs(so.marks, sn.marks, lambda m: m[0]):
            vm = (new.marks[j] if j is not None else old.marks[i]).copy()
            ao = self.fo.p(*old.mark_labels[i].plot_anchor) if i is not None and old.mark_labels[i] is not None else None
            an = self.fn.p(*new.mark_labels[j].plot_anchor) if j is not None and new.mark_labels[j] is not None else None
            lab = _Label(old.mark_labels[i] if i is not None else None,
                         new.mark_labels[j] if j is not None else None, ao, an)
            self.marks.append((i, j, vm, lab))
            group += [vm, *lab.mobs()]

        self.gaps = []
        for k in range(max(len(so.gaps), len(sn.gaps))):
            i = k if k < len(so.gaps) else None
            j = k if k < len(sn.gaps) else None
            vm = (new.gaps[j] if j is not None else old.gaps[i]).copy()
            lo = old.gap_labels[i] if i is not None else None
            ln = new.gap_labels[j] if j is not None else None
            # the label rides on the gap's middle, measured where each beat's plot is now
            mo = _gap(self.fo, *so.gaps[i][:4], VMobject()) if i is not None else None
            mn = _gap(self.fn, *sn.gaps[j][:4], VMobject()) if j is not None else None
            lab = _Label(lo, ln, mo, mn)
            self.gaps.append((i, j, vm, lab))
            group += [vm, *lab.mobs()]

        self.points = []
        for i, j in _pairs(so.points, sn.points, lambda p: S.squash(p[0])):
            dot = (new.dots[j] if j is not None else old.dots[i]).copy()
            lab = _Label(old.point_labels[i] if i is not None else None,
                         new.point_labels[j] if j is not None else None,
                         old.dots[i].get_center() if i is not None else None,
                         new.dots[j].get_center() if j is not None else None)
            drop = None
            if so.drop or sn.drop:
                drop = VMobject().set_stroke(current().muted, 2)
                drop.fix_in_frame()   # like the plot's own parts, drawn in the overlay
                group.append(drop)
            self.points.append((i, j, dot, lab, drop))
            group += [dot, *lab.mobs()]

        self.names = [(_Label(old.name_labels.get(k), new.name_labels.get(k)))
                      for k in ("xlabel", "ylabel") if k in old.name_labels or k in new.name_labels]
        for lab in self.names:
            group += lab.mobs()
        self.group = Group(*group)
        self.hidden = False

    def animation(self) -> Animation:
        return UpdateFromAlphaFunc(self.group, self.update, remover=True)

    def update(self, _m, alpha: float) -> None:
        if not self.hidden:   # the old plot steps aside for the moving copy on the first frame
            self.old.set_opacity(0)
            self.hidden = True
        t = smooth(alpha)
        fade_in, fade_out = squish_rate_func(smooth, 0.4, 1.0)(alpha), squish_rate_func(smooth, 0.0, 0.5)(alpha)
        so, sn, old, new = self.old.spec, self.new.spec, self.old, self.new
        fr = self.fo.lerp(self.fn, t)
        _axes(fr, self.axes)
        for (axis, v), line, lab, in_o, in_n in self.ticks:
            _tick(fr, axis, v, line)
            lo, hi = fr.x if axis == "x" else fr.y
            show = 1.0 if lo - 1e-9 <= v <= hi + 1e-9 else 0.0
            op = show * (1.0 if in_o and in_n else (1 - fade_out) if in_o else fade_in)
            line.set_stroke(opacity=op)
            lab.update(t, _tick_at(fr, axis, v))
            for m in lab.mobs():
                m.set_opacity(op)

        def curve_fn(spec, k):
            return spec.curves[k].f

        live = {}
        for i, j, vm, lab in self.curves:
            if i is not None and j is not None:
                f = _blend(curve_fn(so, i), curve_fn(sn, j), t).f
                _curve(fr, f, vm)
                vm.set_stroke(interpolate_color(old.colors[i], new.colors[j], t))
                live[("o", i)] = live[("n", j)] = f
            elif j is not None:
                _curve(fr, curve_fn(sn, j), vm, upto=fr.x[0] + fade_in * (fr.x[1] - fr.x[0]))
                live[("n", j)] = curve_fn(sn, j)
            else:
                _curve(fr, curve_fn(so, i), vm)
                if vm.get_stroke_opacity() > 0:
                    vm.set_stroke(opacity=1 - fade_out)
            lab.update(t)

        def edge(spec, e, side):
            """What a gap/shade/point stands on now: a curve morphing with its pair, or a level."""
            if isinstance(e, S.Curve):
                return live.get((side, spec.curves.index(e)), e.f)
            return _edge_fn(e)

        def mixed(ei, ej):
            return _blend(ei, ej, t)

        for i, j, vm, lab in self.shades:
            a = so.shades[i] if i is not None else sn.shades[j]
            b = sn.shades[j] if j is not None else a
            fa = mixed(edge(so, a[0], "o") if i is not None else edge(sn, b[0], "n"), edge(sn, b[0], "n") if j is not None else edge(so, a[0], "o")).f
            fb = mixed(edge(so, a[1], "o") if i is not None else edge(sn, b[1], "n"), edge(sn, b[1], "n") if j is not None else edge(so, a[1], "o")).f
            lo, hi = (1 - t) * a[2] + t * b[2], (1 - t) * a[3] + t * b[3]
            op = 0.28 * (1.0 if i is not None and j is not None else fade_in if j is not None else 1 - fade_out)
            _shade(fr, S.Curve("", "", fa), S.Curve("", "", fb), lo, hi, vm, op)
            lab.update(t)
            for m in lab.mobs():
                if i is None or j is None:
                    m.set_opacity(fade_in if j is not None else 1 - fade_out)

        for i, j, vm, lab in self.marks:
            a = so.marks[i] if i is not None else sn.marks[j]
            b = sn.marks[j] if j is not None else a
            v = (1 - t) * a[1] + t * b[1]
            end = _mark(fr, b[0], v, vm)
            if i is None or j is None:
                vm.set_stroke(opacity=fade_in if j is not None else 1 - fade_out)
            lab.update(t, end)

        for i, j, vm, lab in self.gaps:
            a = so.gaps[i] if i is not None else sn.gaps[j]
            b = sn.gaps[j] if j is not None else a
            sa, sb = (so if i is not None else sn), (sn if j is not None else so)
            fa = mixed(edge(sa, a[0], "o" if i is not None else "n"), edge(sb, b[0], "n" if j is not None else "o")).f
            fb = mixed(edge(sa, a[1], "o" if i is not None else "n"), edge(sb, b[1], "n" if j is not None else "o")).f
            mid = _gap(fr, S.Curve("", "", fa), S.Curve("", "", fb), b[2], (1 - t) * a[3] + t * b[3], vm)
            if i is None or j is None:
                vm.set_stroke(opacity=(fade_in if j is not None else 1 - fade_out) * (mid is not None))
            lab.update(t, mid)

        for i, j, dot, lab, drop in self.points:
            a = so.points[i] if i is not None else sn.points[j]
            b = sn.points[j] if j is not None else a
            x = (1 - t) * a[1] + t * b[1]
            ya = float(edge(so if i is not None else sn, a[2], "o" if i is not None else "n")(np.array([x]))[0]) \
                if isinstance(a[2], S.Curve) else a[2]
            yb = float(edge(sn if j is not None else so, b[2], "n" if j is not None else "o")(np.array([x]))[0]) \
                if isinstance(b[2], S.Curve) else b[2]
            y = (1 - t) * ya + t * yb
            if np.isfinite(y):
                dot.move_to(fr.p(x, y))
            op = 1.0 if i is not None and j is not None else fade_in if j is not None else 1 - fade_out
            dot.set_opacity(op if np.isfinite(y) and fr.inside(x, y, 0.01) else 0)
            lab.update(t, dot.get_center())
            if i is None or j is None:
                for m in lab.mobs():
                    m.set_opacity(op)
            if drop is not None:
                _drop(fr, dot.get_center(), drop)
                both = so.drop and sn.drop
                drop.set_stroke(opacity=float((op if both else fade_in if sn.drop else 1 - fade_out)
                                              * bool(np.isfinite(y) and fr.inside(x, y, 0.01))))
        self.t = t

        for lab in self.names:
            lab.update(t)


# --- while the line is spoken: steps, then a slide ------------------------------------------------
STATE = ("spec", "colors", "ticks", "tick_lines", "tick_labels", "lines", "shades", "marks", "drops",
         "gaps", "dots", "names", "name_labels", "mark_labels", "gap_labels", "point_labels",
         "curve_labels", "shade_labels", "labels", "box", "axes", "w", "h")


_stage = S.stage_attrs   # the plot's attributes at one stage (spec.stage_attrs)


def _keep_offsets(start: PlotBlock, end: PlotBlock) -> None:
    """A slide carries each point's and gap's words with it, where they sat at the start: two
    readouts placed on their own at each end would cross on the way (3b1b's readouts ride along)."""
    fs, fe = Frame.of(start), Frame.of(end)
    for (a, b) in ((start.dots, end.dots),):
        for d0, d1, l0, l1 in zip(a, b, start.point_labels, end.point_labels):
            if l0 is not None and l1 is not None:
                l1.move_to(d1.get_center() + (l0.get_center() - d0.get_center()))
    for g0, g1, l0, l1 in zip(start.spec.gaps, end.spec.gaps, start.gap_labels, end.gap_labels):
        m0, m1 = _gap(fs, *g0[:4], VMobject()), _gap(fe, *g1[:4], VMobject())
        if l0 is not None and l1 is not None and m0 is not None and m1 is not None:
            l1.move_to(m1 + (l0.get_center() - m0))


def _aligned(block: PlotBlock, like: PlotBlock) -> PlotBlock:
    """``block`` moved and scaled so its axis box sits exactly on ``like``'s (as laid out and framed)."""
    k = like.box.get_width() / max(block.box.get_width(), 1e-9)
    block.scale(k, about_point=block.box.get_corner(DL))
    block.shift(like.box.get_corner(DL) - block.box.get_corner(DL))
    block.fix_in_frame()
    return block


def schedule(steps: int, slide: bool, hold: float):
    """When each step bends (about a second, then a rest on it) and when the slide runs, as
    ([(t0, t1)] per step, (t0, t1) or None), in seconds into the hold. A formula that follows the
    plot (``<tex follow>``) changes on the same beats."""
    slide_t = (max(1.5, 0.5 * hold) if steps else 0.9 * hold) if slide else 0.0
    step_t = max(0.0, hold - slide_t) / max(steps, 1)
    times, t = [], 0.0
    for _ in range(steps):
        times.append((t, t + max(0.35, min(1.2, 0.6 * step_t))))
        t += step_t
    return times, ((t, min(hold, t + max(1.0, 0.9 * slide_t))) if slide else None)


def steps_of(attrs: dict) -> tuple[int, bool]:
    """(number of steps after the first, whether it slides) of a plot's attributes."""
    sp = S.parse(attrs)
    return max([len(c.steps) for c in sp.curves if c.steps] or [1]) - 1, sp.slide is not None


class _Live:
    """The stages one after another: each step bends the curve in about a second, then the
    picture rests on it; the slide runs smoothly through what is left of the line. Labels with
    {x}, {y} or {gap} show the live value while they slide."""

    def __init__(self, node: Node, mob: PlotBlock, hold: float):
        sp = mob.spec
        n = max([len(c.steps) for c in sp.curves if c.steps] or [1])
        stages = [_stage(node.attrs, k, None) for k in range(1, n)]
        if sp.slide is not None:
            stages.append(_stage(node.attrs, n - 1, sp.slide))
        blocks = [mob] + [_aligned(PlotBlock(Node("plot", a)), mob) for a in stages]
        if sp.slide is not None:
            _keep_offsets(blocks[-2], blocks[-1])
        self.mob, self.final = mob, blocks[-1]
        self.morphs = [_Morph(a, b) for a, b in zip(blocks, blocks[1:])]
        times, slide_seg = schedule(n - 1, sp.slide is not None, hold)
        self.segs = [(t0, t1, self.morphs[k], False) for k, (t0, t1) in enumerate(times)]
        if slide_seg is not None:
            self.segs.append((*slide_seg, self.morphs[-1], True))
        self.hold = hold
        self.holder = Group()
        self.cache: dict[str, Mobject] = {}
        self.scale: dict[int, tuple[float, str]] = {}
        self.shown: list[Mobject] = []
        self.size = 0.9 * float(node.attrs.get("size", 30))   # the plot's label size
        self.started = False

    def animation(self) -> Animation:
        return UpdateFromAlphaFunc(self.holder, self.update, run_time=self.hold, rate_func=linear, remover=True)

    def _readouts(self, m: "_Morph") -> None:
        """Labels written with {x}, {y}, {gap}: the number as it is right now."""
        so, sn, t = m.old.spec, m.new.spec, m.t
        for i, j, dot, lab, _ in m.points:
            if i is None or j is None or "{" not in so.points[i][0] or lab.n is None:
                continue
            x = (1 - t) * so.points[i][1] + t * sn.points[j][1]
            y = float(S.value(sn.points[j][2], [x])[0])
            self._swap(lab, S.fill(sn.points[j][0], x=x, y=y))
        for k, (i, j, vm, lab) in enumerate(m.gaps):
            if i is None or j is None or "{" not in so.gaps[i][4] or lab.n is None:
                continue
            a, b, axis, v1, text = sn.gaps[j]
            v = (1 - t) * so.gaps[i][3] + t * v1
            self._swap(lab, S.fill(text, gap=_gap_value(a, b, axis, v, m.fn), x=v))
        for i, j, vm, lab in m.marks:
            if i is None or j is None or "{" not in so.marks[i][2] or lab.n is None:
                continue
            v = (1 - t) * so.marks[i][1] + t * sn.marks[j][1]
            self._swap(lab, S.fill(sn.marks[j][2], x=v))

    def _swap(self, lab: "_Label", text: str) -> None:
        """Show ``text`` in the label's place (the label itself is hidden), at the size the label
        was drawn after any layout scaling; each distinct readout is typeset once."""
        if id(lab) not in self.scale:   # how much the layout scaled this plot's labels
            ref = _label(lab.n.plot_text, self.size, "#ffffff")
            self.scale[id(lab)] = (lab.hn / max(ref.get_height(), 1e-6), lab.n.get_fill_color())
        k, color = self.scale[id(lab)]
        if text not in self.cache:
            m = _label(text, self.size, color).scale(k)
            m.set_backstroke(current().bg, 5)
            m.fix_in_frame()
            self.cache[text] = m
        for m in lab.mobs():
            m.set_opacity(0)
        self.shown.append(self.cache[text].copy().move_to(lab.n.get_center()))

    def update(self, _m, alpha: float) -> None:
        if not self.started:   # the moving copies stand in for the plot during the line
            self.started = True
            self.mob.set_submobjects([])
        t = alpha * self.hold
        k = max((n for n, seg in enumerate(self.segs) if seg[0] <= t + 1e-9), default=0)
        t0, t1, morph, slide = self.segs[k]
        a = float(np.clip((t - t0) / max(t1 - t0, 1e-6), 0, 1))
        morph.update(None, a)
        self.shown = []
        if slide:
            self._readouts(morph)
        self.holder.set_submobjects([morph.group, *self.shown])
        if alpha >= 1 - 1e-9:   # the plot is now the last stage, for the beats after this one
            for key in STATE:
                setattr(self.mob, key, getattr(self.final, key))
            self.mob.set_submobjects(self.final.submobjects)
            self.holder.set_submobjects([])


def live(node: Node, mob, hold: float) -> Animation | None:
    """Steps (``fn="P: a | b | c"``) and a slide (``slide="0 -> 2"``) play while the line is
    spoken; a plot kept from the beat before (nothing changed) already played them."""
    if not isinstance(mob, PlotBlock) or getattr(mob, "played", False):
        return None
    if not any(c.steps for c in mob.spec.curves) and mob.spec.slide is None:
        return None
    mob.played = True
    return _Live(node, mob, hold).animation()
