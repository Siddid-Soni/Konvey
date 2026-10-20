"""``<scatter>``: data points on numbered axes, coloured by group, with centroids, links to them,
fitted lines and labels the renderer places clear of each other (manimgl)."""

from __future__ import annotations

import numpy as np

from manimlib import *  # noqa: F401,F403

from ...match import squash
from ...theme import current
from ...tree import BeatError, Node
from ..base import LIT_W, lit_color, Block, _label, _swap, data_list, index_set
from . import OFF, pairs, parse_line

DOT_R = 0.1
CENTROID = 0.3          # the centroid diamond's width
MIN_W, MIN_H = 8.0, 4.5  # the plot's size before the layout fits it to the room
STRETCH = 2.5           # equal units on both axes unless one would have to shrink more than this


def _nice_step(span: float, ticks: int = 5) -> float:
    """A tick step of 1, 2 or 5 times a power of ten, about ``span / ticks`` (never 2.5: whole labels)."""
    raw = span / ticks
    mag = 10 ** np.floor(np.log10(raw))
    return float(min((m * mag for m in (1, 2, 5, 10)), key=lambda s: abs(np.log(s / raw))))


def _axis(vals: list[float]) -> tuple[float, float, float]:
    """(lo, hi, tick step) for data: from 0 when the data is positive and not far from 0, else
    from the tick below (a whole step lower where a point would sit on the axis: ticks start
    there); a quarter step past the top where a point would sit on the edge."""
    lo, hi = min(vals), max(vals)
    if 0 <= lo <= 0.5 * hi:
        lo = 0.0
    step = _nice_step((hi - lo) or 1)
    a, b = np.floor(lo / step) * step, np.ceil(hi / step) * step
    margin = 0.04 * ((hi - lo) or 1)
    a -= step if lo - a < margin and lo != 0 else 0
    b += 0.25 * step if b - hi < margin else 0
    return float(a), float(b), step


def _box(m: Mobject) -> np.ndarray:
    return np.array([*m.get_corner(DL)[:2], *m.get_corner(UR)[:2]])


def _overlap(a: np.ndarray, b: np.ndarray) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(w, 0) * max(h, 0)


DIRS = [UR, UL, DR, DL, UP, DOWN, RIGHT, LEFT]


def _place(label: Mobject, at: np.ndarray, gap: float, taken: list[np.ndarray], frame: np.ndarray) -> None:
    """Put ``label`` beside ``at`` where it covers the least of what is already there (dots,
    markers, lines, labels) and stays inside the plot; then it is taken too."""
    w, h = label.get_width(), label.get_height()
    best, cost = None, np.inf
    # beside the anchor first; a little further out only when every close place is covered
    for k, (far, d) in enumerate((far, d) for far in (0.0, 0.15) for d in DIRS):
        d = d / np.linalg.norm(d)
        c = at + np.array([d[0] * (gap + far + w / 2), d[1] * (gap + far + h / 2), 0])
        b = np.array([c[0] - w / 2, c[1] - h / 2, c[0] + w / 2, c[1] + h / 2])
        out = (max(frame[0] - b[0], 0) + max(b[2] - frame[2], 0) + max(frame[1] - b[1], 0)
               + max(b[3] - frame[3], 0))
        score = sum(_overlap(b, t) for t in taken) + 4 * out * h + 1e-7 * k   # first place wins a tie
        if score < cost:
            best, cost = c, score
    label.move_to(best)
    taken.append(_box(label))


class ScatterBlock(Block):
    """Points ``x,y; x,y`` on axes with numbered ticks. ``groups`` colours each point by its
    group, ``centroids`` are diamonds labelled μ1, μ2, …, ``links`` joins each point to its
    group's centroid, ``lines`` draws y = a·x + b (or x = c) across the plot. The parts are kept
    per point and per centroid, so a later beat with the same id moves them in place."""

    tag = "scatter"

    def __init__(self, node: Node):
        th = current()
        where = f"<scatter id={node.id}>"
        try:
            pts = pairs(node.attrs.get("points", ""))
            cents = pairs(node.attrs.get("centroids", ""))
            lines = [parse_line(s) for s in node.attrs.get("lines", "").split(";") if s.strip()]
        except ValueError as e:
            raise BeatError(f"{where}: {e}") from e
        if not pts:
            raise BeatError(f'{where} needs points="x,y; x,y; …"')
        n = len(pts)
        groups = [str(g) for g in data_list(node, "groups", required=False)]
        if groups:
            if len(groups) != n or not all(g.isdigit() for g in groups):
                raise BeatError(f'{where} groups="{node.attrs["groups"]}": one group number (0, 1, …) '
                                f"per point; there are {n} points")
            groups = [int(g) for g in groups]
            if cents and max(groups) >= len(cents):
                raise BeatError(f"{where}: group {max(groups)} has no centroid (centroids are "
                                f"numbered 0..{len(cents) - 1})")
        links = squash(node.attrs.get("links", "off")) not in OFF
        if links and not (groups and cents):
            raise BeatError(f'{where} links: needs groups= and centroids= (a link joins a point to its centroid)')
        hot = index_set(node.attrs.get("highlight", ""), n, "highlight")
        lc = lit_color(node)
        names = data_list(node, "labels", required=False)
        if names and len(names) != n:
            raise BeatError(f"{where}: {len(names)} labels for {n} points (leave one blank to skip it)")
        size = float(node.attrs.get("size", 28))
        # w/h are a floor, not a size: the layout only ever shrinks a steady block, so a small
        # w/h would leave the plot small on an empty page. It shrinks from here to fit.
        w, h = max(float(node.attrs.get("w", 0)), MIN_W), max(float(node.attrs.get("h", 0)), MIN_H)

        # Ranges: from x=/y= or from the data. Equal units on both axes (distances read true)
        # when that needs little stretching: the box then narrows on one side to fit.
        xs, ys = [p[0] for p in pts + cents], [p[1] for p in pts + cents]
        given = {k: [float(v) for v in data_list(node, k, required=False)[:2]] for k in ("x", "y")}
        for k, vals in (("x", xs), ("y", ys)):
            r = given[k]
            if r and (len(r) != 2 or r[0] >= r[1]):
                raise BeatError(f'{where} {k}="{node.attrs[k]}": give the range as "low,high"')
            if r and (min(vals) < r[0] or max(vals) > r[1]):
                raise BeatError(f'{where} {k}="{node.attrs[k]}": the data spans {min(vals):g}..{max(vals):g}; '
                                f"widen {k}= or leave it out")
        xr = given["x"] or _axis(xs)
        yr = given["y"] or _axis(ys)
        ux, uy = w / (xr[1] - xr[0]), h / (yr[1] - yr[0])
        if max(ux, uy) / min(ux, uy) <= STRETCH:
            u = min(ux, uy)
            w, h = u * (xr[1] - xr[0]), u * (yr[1] - yr[0])
        x0, y0 = xr[0], yr[0]
        xstep, ystep = (r[2] if len(r) == 3 else _nice_step(r[1] - r[0]) for r in (xr, yr))
        xr, yr = xr[:2], yr[:2]
        axes = Axes((0, xr[1] - x0, xstep), (0, yr[1] - y0, ystep), width=w, height=h,
                    axis_config={"stroke_color": th.muted, "stroke_width": 1.5, "include_tip": False})
        self.axes, self.x0, self.y0, self.xr, self.yr = axes, x0, y0, xr, yr
        tick = 0.7 * size
        ticks, self.tick_text = VGroup(), []
        for v in np.arange(x0, xr[1] + 1e-9, xstep):   # where the axis draws its ticks
            ticks.add(_label(f"{v:g}", tick, th.muted).next_to(self.c2p(v, y0), DOWN, buff=0.12))
            self.tick_text.append(f"x{v:g}")
        for v in np.arange(y0, yr[1] + 1e-9, ystep):
            ticks.add(_label(f"{v:g}", tick, th.muted).next_to(self.c2p(x0, v), LEFT, buff=0.12))
            self.tick_text.append(f"y{v:g}")
        axis_names = VGroup()
        if node.attrs.get("xlabel"):
            axis_names.add(_label(node.attrs["xlabel"], 0.85 * size, th.muted)
                           .next_to(ticks, DOWN, buff=0.1).align_to(axes, RIGHT))
        if node.attrs.get("ylabel"):
            axis_names.add(_label(node.attrs["ylabel"], 0.85 * size, th.muted)
                           .next_to(axes, UP, buff=0.15).align_to(axes, LEFT))
        self.frame = VGroup(axes, ticks, axis_names)

        palette = list(th.palette)
        color = (lambda i: palette[groups[i] % len(palette)]) if groups else (lambda i: th.color(node.attrs.get("color"), "ink"))
        at = [self.c2p(x, y) for x, y in pts]
        cat = [self.c2p(x, y) for x, y in cents]

        self.lines, self.line_specs = VGroup(), lines
        for spec in lines:
            self.lines.add(self.line_mob(spec).set_stroke(th.accent, 4))
        self.links = VGroup()
        for i in range(n):
            if links and np.linalg.norm(cat[groups[i]] - at[i]) > 1e-6:   # a point on its centroid has no link
                self.links.add(Line(at[i], cat[groups[i]]).set_stroke(color(i), 2, opacity=0.45))
            else:
                self.links.add(VMobject())
        self.points = VGroup()
        for i in range(n):
            dot = Dot(at[i], radius=DOT_R, fill_color=color(i))
            dot.set_stroke(th.bg, 2)   # reads on top of its centroid's diamond of the same colour
            # an unlit point keeps an invisible ring, so lighting it later grows the ring in place
            ring = Circle(radius=DOT_R).move_to(at[i]).set_stroke(lc, LIT_W, opacity=1 if i in hot else 0)
            self.points.add(VGroup(dot, ring))
        self.centroids = VGroup()
        for k, c in enumerate(cat):
            col = palette[k % len(palette)] if groups or len(cents) > 1 else th.accent
            mark = Square(side_length=CENTROID / np.sqrt(2)).rotate(PI / 4).move_to(c)
            # see-through, drawn over the points: every centre looks the same, and a point lying
            # on its centre still shows through it
            mark.set_fill(col, 0.35).set_stroke(th.ink, 2.5)
            name = Tex(rf"\mu_{{{k + 1}}}", font_size=size * 1.15).set_fill(col, 1)
            self.centroids.add(VGroup(mark, name))

        # Labels go where they cover the least: every dot, marker and line is in the way.
        plot = np.array([*self.c2p(x0, y0)[:2], *self.c2p(*[r[1] for r in (xr, yr)])[:2]])
        taken = [np.array([p[0] - DOT_R, p[1] - DOT_R, p[0] + DOT_R, p[1] + DOT_R]) for p in at]
        taken += [_box(c[0]) for c in self.centroids]
        for m in [*self.lines, *self.links]:
            if m.has_points():   # straight lines: sampled between their ends
                for t in np.linspace(0, 1, 12):
                    q = m.get_start() + t * (m.get_end() - m.get_start())
                    taken.append(np.array([q[0] - 0.04, q[1] - 0.04, q[0] + 0.04, q[1] + 0.04]))
        for k, c in enumerate(cat):
            _place(self.centroids[k][1], c, CENTROID / 2 + 0.06, taken, plot)
            self.centroids[k][1].set_backstroke(th.bg, 5)
        self.names, self.name_text = VGroup(), [str(s).strip() for s in names] or [""] * n
        for i, s in enumerate(self.name_text):
            lab = _label(s, 0.75 * size, th.ink if i in hot else th.muted) if s else VMobject()
            if s:
                _place(lab, at[i], DOT_R + 0.05, taken, plot)
                lab.set_backstroke(th.bg, 4)
            self.names.add(lab)
        self.groups = groups or [None] * n
        # centroids over the points (see-through, so a point on its centre still shows)
        super().__init__(self.frame, self.lines, self.links, self.points, self.centroids, self.names)
        self.set_content(node, "points", "groups", "centroids", "lines", "links", "highlight", "labels",
                         "x", "y", "xlabel", "ylabel", "color")

    def c2p(self, x: float, y: float) -> np.ndarray:
        """Data -> scene point, live: it follows the block wherever the layout moved it.
        (manimgl's Axes always span the origin, so the axes are built 0..span and shifted.)"""
        return self.axes.c2p(x - self.x0, y - self.y0)

    def line_mob(self, spec: tuple[str, float, float]) -> VMobject:
        """The part of a line inside the plot (empty when it misses the plot)."""
        kind, a, b = spec
        (x0, x1), (y0, y1) = self.xr, self.yr
        if kind == "x":
            ends = [(a, y0), (a, y1)] if x0 <= a <= x1 else []
        elif abs(a) < 1e-12:
            ends = [(x0, b), (x1, b)] if y0 <= b <= y1 else []
        else:
            xa, xb = sorted(((y0 - b) / a, (y1 - b) / a))
            lo, hi = max(x0, xa), min(x1, xb)
            ends = [(lo, a * lo + b), (hi, a * hi + b)] if lo < hi - 1e-9 else []
        if not ends:
            return VMobject()
        return Line(self.c2p(*ends[0]), self.c2p(*ends[1]))


def build(node: Node, world=None) -> ScatterBlock:
    try:
        return ScatterBlock(node)
    except BeatError:
        raise
    except Exception as e:  # noqa: BLE001 - a manimgl failure must still tell Agent 3 what to change
        raise BeatError(f"<scatter id={node.id}> could not be drawn ({type(e).__name__}: {e}); check that "
                        f"points, centroids and lines are plain numbers inside x=/y=") from e


def enter(node: Node, mob: ScatterBlock, run_time: float) -> Animation:
    """Axes first, then the points pop in one after another, then centroids, links and lines."""
    t = max(run_time, 1.0)
    # one after another, but all begun at once (lag_ratio=1): with Succession the points stood
    # fully drawn until their turn, then vanished and grew back
    return AnimationGroup(
        ShowCreation(mob.frame, run_time=0.35 * t),
        AnimationGroup(LaggedStart(*(GrowFromCenter(p) for p in mob.points), lag_ratio=0.12),
                       FadeIn(mob.names), run_time=0.35 * t),
        AnimationGroup(*(GrowFromCenter(c) for c in mob.centroids), *(ShowCreation(m) for m in mob.links),
                       *(ShowCreation(m) for m in mob.lines), run_time=0.3 * t), lag_ratio=1.0)


class _Pulse(Transform):
    """A point that changed group: it swells while it takes its new colour, so the eye finds it."""

    def begin(self) -> None:
        super().begin()
        self.mobject.unlock_data()   # its points do not move, and locked points would not reset each frame

    def interpolate_mobject(self, alpha: float) -> None:
        super().interpolate_mobject(alpha)
        self.mobject.scale(1 + 0.6 * np.sin(PI * alpha), about_point=self.mobject[0].get_center())


def _slide_line(old_line: Mobject, old: ScatterBlock, new: ScatterBlock, style: Mobject,
                a: tuple, b: tuple) -> Animation:
    """A fitted line turns and slides to its new slope through every line between (not a
    straight-line morph of its two ends, which would shrink it on the way). Each in-between
    line is drawn on both the old and the new axes and blended, so it stays on the axes while
    they rescale."""

    def upd(m, t):
        s = smooth(t)
        spec = (a[0], a[1] + (b[1] - a[1]) * s, a[2] + (b[2] - a[2]) * s)
        p, q = old.line_mob(spec), new.line_mob(spec)
        if p.has_points() and q.has_points():
            q.set_points(p.get_points() * (1 - s) + q.get_points() * s)
        m.become((q if q.has_points() else p).match_style(style))

    return UpdateFromAlphaFunc(old_line, upd)


def morph(old: ScatterBlock, new: ScatterBlock, sources=None) -> Animation:
    """Same id, new state: centroids glide, points that changed group pulse into their new
    colour, links follow their centroid (or let go and re-attach to the new one), lines turn
    to their new slope, new points pop in and dropped ones fade."""
    (ax0, ticks0, names0), (ax1, ticks1, names1) = old.frame, new.frame
    anims = [Transform(ax0, ax1), Transform(names0, names1) if len(names0) == len(names1)
             else FadeTransform(names0, names1)]
    if old.tick_text == new.tick_text:
        anims.append(Transform(ticks0, ticks1))
    else:   # rescaled axes: the old numbers go, the new ones come once the axes have stretched
        anims += [FadeOut(ticks0, rate_func=squish_rate_func(smooth, 0, 0.4)),
                  FadeIn(ticks1, rate_func=squish_rate_func(smooth, 0.6, 1))]
    n_old, n_new = len(old.points), len(new.points)
    for i in range(max(n_old, n_new)):
        if i >= n_new:
            anims += [FadeOut(old.points[i], scale=0.3), FadeOut(old.links[i]), FadeOut(old.names[i])]
            continue
        if i >= n_old:
            anims += [GrowFromCenter(new.points[i]), ShowCreation(new.links[i]), FadeIn(new.names[i])]
            continue
        moved = old.groups[i] != new.groups[i]
        switched = moved and None not in (old.groups[i], new.groups[i])   # not its first colour
        anims.append(_Pulse(old.points[i], new.points[i]) if switched
                     else Transform(old.points[i], new.points[i]))
        had, has = old.links[i].has_points(), new.links[i].has_points()
        if had and has and not moved:
            anims.append(Transform(old.links[i], new.links[i]))     # rides along with its centroid
        else:
            if had:
                anims.append(FadeOut(old.links[i]))
            if has:
                anims.append(GrowFromPoint(new.links[i], new.points[i].get_center(),
                                           rate_func=squish_rate_func(smooth, 0.35, 1.0)))
        same = old.name_text[i] == new.name_text[i]
        anims.append(Transform(old.names[i], new.names[i]) if same else _swap(old.names[i], new.names[i]))
    for k in range(max(len(old.centroids), len(new.centroids))):
        if k >= len(new.centroids):
            anims.append(FadeOut(old.centroids[k], scale=0.3))
        elif k >= len(old.centroids):
            anims.append(GrowFromCenter(new.centroids[k]))
        else:
            anims.append(Transform(old.centroids[k], new.centroids[k]))   # glides to its new place
    for j in range(max(len(old.lines), len(new.lines))):
        if j >= len(new.lines):
            anims.append(FadeOut(old.lines[j]))
        elif j >= len(old.lines):
            anims.append(ShowCreation(new.lines[j]))
        elif old.line_specs[j][0] == new.line_specs[j][0] and old.lines[j].has_points():
            anims.append(_slide_line(old.lines[j], old, new, new.lines[j], old.line_specs[j], new.line_specs[j]))
        else:
            anims.append(Transform(old.lines[j], new.lines[j]))
    return AnimationGroup(*anims)
