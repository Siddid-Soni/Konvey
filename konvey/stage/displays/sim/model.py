"""Views of a time-evolving model (``konvey.stage.models``), manimgl.

Each view draws the model at the time the previous beat reached (``_t0``); during the hold its
``play`` runs the clock to ``_t1``, moving everything to ``state(t)``. Every view of one model
computes the same timeline, so the blocks, a phase plane and a counter keep in step.

Live numbers for ``<value bind=…>``: ``simId.<channel>`` (``b.clacks``, ``b.v1`` …)."""

from __future__ import annotations

import json
import math

from manimlib import *  # noqa: F401,F403

from ...models import timeline
from ...theme import current
from ...tree import BeatError, Node
from ..base import Block, _label


class ModelView(Block):
    tag = "sim"

    def _setup(self, node: Node, attrs: dict, world, w: float, h: float):
        self.world = world
        self.key = node.attrs.get("sim", node.id).strip().lstrip("#")
        self.tl = timeline(attrs["rule"].strip(), attrs, f"<{node.tag} id={node.id}>")
        self.t0 = float(node.attrs.get("_t0", 0))
        self.t1 = float(node.attrs.get("_t1", self.t0))
        self.frame = Rectangle(w, h).set_stroke(width=0).set_fill(opacity=0)
        self.w, self.h = w, h

    def to_screen(self, p) -> np.ndarray:
        k = self.frame.get_width() / self.w
        return self.frame.get_center() + k * np.array([p[0], p[1], 0.0])

    def scale_k(self) -> float:
        return self.frame.get_width() / self.w

    def publish(self, t: float) -> None:
        if self.world is None:
            return
        for k, v in self.tl.state(t).items():
            if isinstance(v, (int, float)):
                self.world.values[f"{self.key}.{k}"] = v

    def show(self, t: float, prev: float | None = None) -> None:   # overridden
        pass

    def play(self, hold: float) -> Animation | None:
        if self.t1 <= self.t0 + 1e-9:
            return None
        last = [self.t0]

        def update(_m, a):
            t = self.t0 + (self.t1 - self.t0) * a
            self.show(t, last[0])
            self.publish(t)
            last[0] = t

        return UpdateFromAlphaFunc(Mobject(), update, run_time=hold, rate_func=linear)


# --- the blocks themselves -----------------------------------------------------------------------
FLASH_S = 0.35   # a clack's ring burst lasts this long (model time is real time at speed 1)


class BlocksView(ModelView):
    def __init__(self, node: Node, world=None):
        super().__init__()
        th = current()
        w, h = float(node.attrs.get("w", 10)), float(node.attrs.get("h", 3.6))
        self._setup(node, node.attrs, world, w, h)
        info = self.tl.info
        reach = info["x2_0"] + info["s2"] + 1.5          # model metres shown right of the wall
        self.k = k = (w - 0.7) / reach
        self.x_wall = -w / 2 + 0.45
        self.floor_y = -h / 2 + 0.3
        top = h / 2 - 0.1
        floor = Line([self.x_wall, self.floor_y, 0], [w / 2, self.floor_y, 0]).set_stroke(th.ink, 2)
        wall = Line([self.x_wall, self.floor_y, 0], [self.x_wall, top, 0]).set_stroke(th.ink, 2)
        hatch = VGroup(*(Line([self.x_wall, y, 0], [self.x_wall - 0.18, y - 0.18, 0])
                         for y in np.arange(self.floor_y + 0.2, top, 0.3))).set_stroke(th.muted, 1.5)
        hatch.add(*(Line([x, self.floor_y, 0], [x - 0.18, self.floor_y - 0.18, 0])
                    for x in np.arange(self.x_wall + 0.2, w / 2, 0.3)))
        hatch.set_stroke(th.muted, 1.5)
        self.blocks = VGroup()
        for s, m, col in ((info["s1"], info["m1"], th.palette[0]), (info["s2"], info["m2"], th.palette[1])):
            sq = Square(s * k).set_fill(col, 0.9).set_stroke(th.ink, 2)
            lab = _label(f"{m:,.0f} kg", 26, th.ink)
            self.blocks.add(VGroup(sq, lab))
        self.flashes = VGroup(*(VGroup(*(Circle(radius=0.1).set_stroke(th.lit, 3, 0) for _ in range(3)))
                                for _ in range(8)))
        self.flash_at: list[tuple[float, np.ndarray] | None] = [None] * len(self.flashes)
        self._place_blocks(self.t0, local=True)
        super().__init__(self.frame, hatch, floor, wall, self.blocks, self.flashes)
        self.content = json.dumps(["sim", {k_: node.attrs.get(k_) for k_ in ("rule", "mass", "x1", "x2", "v", "t")}])

    def _block_local(self, i: int, x_model: float) -> np.ndarray:
        s = self.tl.info["s1" if i == 0 else "s2"] * self.k
        return np.array([self.x_wall + x_model * self.k + s / 2, self.floor_y + s / 2])

    def _place_blocks(self, t: float, local: bool = False) -> None:
        st = self.tl.state(t)
        for i, key in enumerate(("x1", "x2")):
            c = self._block_local(i, st[key])
            p = np.array([*c, 0.0]) if local else self.to_screen(c)
            sq, lab = self.blocks[i]
            sq.move_to(p)
            lab.next_to(sq, UP, buff=0.12 * (1 if local else self.scale_k()))
            # past the end of its floor a block fades out (it has left the picture), rather than
            # sliding over whatever is drawn beside the view
            s = self.tl.info["s1" if i == 0 else "s2"] * self.k
            over = (c[0] + s / 2) - self.w / 2
            seen = float(np.clip(1 - over / s, 0, 1))
            sq.set_fill(opacity=0.9 * seen).set_stroke(opacity=seen)
            lab.set_opacity(seen)

    def part(self, name: str):
        n = name.strip()
        return {"small": self.blocks[0], "big": self.blocks[1], "wall": None}.get(n)

    def show(self, t: float, prev: float | None = None) -> None:
        self._place_blocks(t)
        times = self.tl.events["clack"]
        spots = self.tl.info["spots"]
        if prev is not None and len(times):
            lo, hi = np.searchsorted(times, prev, side="right"), np.searchsorted(times, t, side="right")
            for e in range(lo, hi):   # a ring burst where each collision happened
                slot = e % len(self.flashes)
                y = self.floor_y + self.tl.info["s1"] * self.k / 2
                self.flash_at[slot] = (float(times[e]), self.to_screen([self.x_wall + spots[e] * self.k, y]))
        k = self.scale_k()
        for slot, ring in enumerate(self.flashes):
            got = self.flash_at[slot]
            if got is None:
                continue
            age = (t - got[0]) / FLASH_S
            for j, c in enumerate(ring):
                f = min(max(age - 0.15 * j, 0.0), 1.0)
                c.set_width(max(2 * k * (0.1 + 0.5 * f), 1e-3)).move_to(got[1])
                c.set_stroke(opacity=(1 - f) if 0 < f < 1 else 0)
            if age > 1.4:
                self.flash_at[slot] = None


# --- a phase / velocity plane ------------------------------------------------------------------------
DEFAULT_AXES = {"blocks": ("p1", "p2"), "pendulum": ("theta", "omega")}


def _field(f, reach: float, unit: float, color: str, n: int = 11) -> VGroup:
    """Little arrows of the model's flow on a grid (3b1b's phase-space vector field): direction
    true, length capped so they never cross."""
    out = VGroup()
    step = 2 * reach / (n - 1)
    for i in range(n):
        for j in range(n):
            x, y = -reach + i * step, -reach + j * step
            dx, dy = f(x, y)
            mag = math.hypot(dx, dy)
            if mag < 1e-9:
                continue
            length = 0.42 * step * min(1.0, 0.3 + mag / 4)
            a = np.array([x * unit, y * unit, 0])
            b = a + np.array([dx / mag, dy / mag, 0]) * length * unit
            out.add(Arrow(a, b, buff=0, thickness=1.5, max_tip_length_to_length_ratio=0.35)
                    .set_fill(color, 0.45).set_stroke(width=0))
    return out


class PhaseView(ModelView):
    tag = "simview"

    def __init__(self, node: Node, world=None):
        super().__init__()
        th = current()
        attrs = json.loads(node.attrs["_model"])
        w = h = float(node.attrs.get("w", 4.4))
        self._setup(node, attrs, world, w, h)
        info = self.tl.info
        first, second = DEFAULT_AXES.get(self.tl.name, self.tl.channels[:2])
        self.cx, self.cy = node.attrs.get("x", first), node.attrs.get("y", second)
        R = info.get("radius") or max(info.get("extent", (1.0, 1.0)))
        self.unit = (w / 2 - 0.45) / (1.15 * R)
        half = 1.15 * R * self.unit
        axes = VGroup(Line([-half, 0, 0], [half, 0, 0]), Line([0, -half, 0], [0, half, 0])).set_stroke(th.muted, 1.5)
        parts = [self.frame, axes]
        if info.get("radius"):
            parts.append(Circle(radius=R * self.unit).set_stroke(th.muted, 2, 0.8))
        if info.get("field") and node.attrs.get("field", "on") != "off":
            parts.append(_field(info["field"], R * 1.1, self.unit, th.muted))
        names = {"p1": r"\sqrt{m_1}\,v_1", "p2": r"\sqrt{m_2}\,v_2", "theta": r"\theta", "omega": r"\dot\theta"}
        xl = Tex(names.get(self.cx, self.cx), font_size=26).set_fill(th.muted).next_to([half, 0, 0], DOWN, buff=0.1)
        yl = Tex(names.get(self.cy, self.cy), font_size=26).set_fill(th.muted).next_to([0, half, 0], RIGHT, buff=0.1)
        parts += [xl, yl]
        # the path so far: every state the model passes (event moments included, so no corner is
        # cut), and the point where it is now
        times = np.unique(np.concatenate([np.linspace(0, self.tl.end, 400), self.tl.events.get("clack", [])]))
        self.path_t = times
        self.path_p = np.array([[self.tl.state(tt)[self.cx], self.tl.state(tt)[self.cy]] for tt in times]) * self.unit
        # many chords (314 clacks) would fill the circle solid at one width: thinner as they multiply
        corners = max(len(self.tl.events.get("clack", [])), 1)
        self.trace = VMobject().set_stroke(th.lit, float(np.clip(2.5 * (12 / corners) ** 0.5, 0.6, 2.5)))
        self.dot = Dot(radius=0.08).set_fill(th.accent, 1)
        parts += [self.trace, self.dot]
        self._draw(self.t0, local=True)
        super().__init__(*parts)
        self.content = json.dumps(["simview", node.attrs.get("_model"), node.attrs.get("show"), self.t0, self.t1])

    def _draw(self, t: float, local: bool = False) -> None:
        n = int(np.searchsorted(self.path_t, t, side="right"))
        st = self.tl.state(t)
        here = np.array([st[self.cx], st[self.cy]]) * self.unit
        pts = [*self.path_p[:n], here]
        conv = (lambda p: np.array([*p, 0.0])) if local else self.to_screen
        screen = [conv(p) for p in pts]
        if len(screen) >= 2:
            self.trace.set_points_as_corners(screen)
        else:
            self.trace.set_points_as_corners([screen[0], screen[0]])
        self.dot.move_to(screen[-1])

    def show(self, t: float, prev: float | None = None) -> None:
        self._draw(t)


# --- a town of people ------------------------------------------------------------------------------
class SpreadView(ModelView):
    def __init__(self, node: Node, world=None):
        super().__init__()
        th = current()
        w = h = float(node.attrs.get("w", 5.2))
        self._setup(node, node.attrs, world, w, h)
        self.colors = [th.palette[0], th.palette[2], th.muted]
        box = Square(w - 0.1).set_stroke(th.ink, 2).set_fill(opacity=0)
        n = self.tl.info["n"]
        self.pad = 0.25
        r_dot = max(0.035, min(0.09, 0.75 / math.sqrt(n)))   # 150 people: about 0.06
        self.people = VGroup(*(Dot(radius=r_dot) for _ in range(n)))
        span = w - 2 * self.pad
        self.rings = VGroup(*(Circle(radius=self.tl.info["radius"] * span).set_stroke(th.palette[2], 1.2, 0)
                              for _ in range(n)))
        self.span = span
        self.last = None
        self._draw(self.t0, local=True)
        super().__init__(self.frame, box, self.rings, self.people)
        self.content = json.dumps(["sim", {k: node.attrs.get(k) for k in node.attrs if not k.startswith("_")}])

    def _draw(self, t: float, local: bool = False) -> None:
        st = self.tl.state(t)
        pos, status = st["pos"], st["status"]
        conv = (lambda q: np.array([*q, 0.0])) if local else self.to_screen
        for k, (dot, ring) in enumerate(zip(self.people, self.rings)):
            q = conv([-self.w / 2 + self.pad + pos[k, 0] * self.span, -self.h / 2 + self.pad + pos[k, 1] * self.span])
            dot.move_to(q)
            ring.move_to(q)
            if self.last is None or self.last[k] != status[k]:
                dot.set_fill(self.colors[status[k]], 1).set_stroke(width=0)
                ring.set_stroke(opacity=0.45 if status[k] == 1 else 0)
        self.last = status.copy()

    def part(self, name: str):
        key = {"healthy": 0, "sick": 1, "recovered": 2}.get(name.strip())
        if key is None or self.last is None:
            return None
        return VGroup(*(d for d, s_ in zip(self.people, self.last) if s_ == key)) or None

    def show(self, t: float, prev: float | None = None) -> None:
        self._draw(t)


# --- counts over time ----------------------------------------------------------------------------------
class GraphView(ModelView):
    """Stacked bands of a model's counts over time (3b1b's SIR graph): sick at the bottom, then
    healthy, then recovered, growing as the clock runs."""
    tag = "simview"
    ORDER = ("sick", "healthy", "recovered")

    def __init__(self, node: Node, world=None):
        super().__init__()
        th = current()
        attrs = json.loads(node.attrs["_model"])
        w, h = float(node.attrs.get("w", 6)), float(node.attrs.get("h", 3.6))
        self._setup(node, attrs, world, w, h)
        self.x0, self.y0 = -w / 2 + 0.5, -h / 2 + 0.45
        self.gw, self.gh = w - 0.8, h - 0.75
        axes = VGroup(Line([self.x0, self.y0, 0], [self.x0 + self.gw, self.y0, 0]),
                      Line([self.x0, self.y0, 0], [self.x0, self.y0 + self.gh, 0])).set_stroke(th.muted, 1.5)
        days = _label("days", 22, th.muted).next_to([self.x0 + self.gw, self.y0, 0], DOWN, buff=0.12, aligned_edge=RIGHT)
        cols = {"sick": th.palette[2], "healthy": th.palette[0], "recovered": th.muted}
        self.bands = VGroup(*(VMobject().set_fill(cols[k], 0.85).set_stroke(width=0) for k in self.ORDER))
        legend = VGroup(*(_label(k, 22, cols[k]) for k in self.ORDER)).arrange(RIGHT, buff=0.35)
        legend.next_to([0, self.y0 + self.gh, 0], UP, buff=0.12)
        counts = self.tl.info["counts"]
        self.steps = np.arange(len(counts)) * self.tl.info["dt"]
        self.stack = np.cumsum(counts[:, [1, 0, 2]], axis=1) / self.tl.info["n"]
        self._draw(self.t0, local=True)
        super().__init__(self.frame, self.bands, axes, days, legend)
        self.content = json.dumps(["simview", node.attrs.get("_model"), "graph", self.t0, self.t1])

    def _draw(self, t: float, local: bool = False) -> None:
        conv = (lambda q: np.array([*q, 0.0])) if local else self.to_screen
        n = max(2, int(np.searchsorted(self.steps, t, side="right")))
        idx = np.unique(np.linspace(0, n - 1, min(n, 240)).astype(int))
        xs = self.x0 + self.steps[idx] / self.tl.end * self.gw
        lower = np.zeros(len(idx))
        for b, band in enumerate(self.bands):
            upper = self.stack[idx, b]
            pts = [conv([x, self.y0 + y * self.gh]) for x, y in zip(xs, upper)] + \
                  [conv([x, self.y0 + y * self.gh]) for x, y in zip(xs[::-1], lower[::-1])]
            band.set_points_as_corners([*pts, pts[0]])
            lower = upper

    def show(self, t: float, prev: float | None = None) -> None:
        self._draw(t)


# --- a pendulum ------------------------------------------------------------------------------------------
class PendulumView(ModelView):
    def __init__(self, node: Node, world=None):
        super().__init__()
        th = current()
        w, h = float(node.attrs.get("w", 4.6)), float(node.attrs.get("h", 4.6))
        self._setup(node, node.attrs, world, w, h)
        self.pivot = np.array([0.0, h / 2 - 0.4])
        self.L = h - 1.3
        ceiling = Line([-1, self.pivot[1], 0], [1, self.pivot[1], 0]).set_stroke(th.ink, 2)
        hatch = VGroup(*(Line([x, self.pivot[1], 0], [x + 0.15, self.pivot[1] + 0.15, 0])
                         for x in np.arange(-0.95, 1, 0.2))).set_stroke(th.muted, 1.5)
        rest = DashedLine([*self.pivot, 0], [self.pivot[0], self.pivot[1] - self.L, 0]).set_stroke(th.muted, 1, 0.6)
        self.rod = Line([*self.pivot, 0], [*self.pivot, 0]).set_stroke(th.ink, 3)
        self.bob = Circle(radius=0.22).set_fill(th.palette[0], 1).set_stroke(th.ink, 2)
        self._draw(self.t0, local=True)
        super().__init__(self.frame, rest, hatch, ceiling, self.rod, self.bob)
        self.content = json.dumps(["sim", {k: node.attrs.get(k) for k in node.attrs if not k.startswith("_")}])

    def _draw(self, t: float, local: bool = False) -> None:
        a = self.tl.state(t)["theta"]
        tip = self.pivot + self.L * np.array([math.sin(a), -math.cos(a)])
        conv = (lambda q: np.array([*q, 0.0])) if local else self.to_screen
        self.rod.put_start_and_end_on(conv(self.pivot), conv(tip))
        self.bob.move_to(conv(tip))

    def part(self, name: str):
        return {"bob": self.bob, "rod": self.rod}.get(name.strip())

    def show(self, t: float, prev: float | None = None) -> None:
        self._draw(t)


def _local_or_screen(view: ModelView, local: bool):
    return (lambda q: np.array([q[0], q[1], 0.0])) if local else view.to_screen


# --- circles drawing a curve -----------------------------------------------------------------------------
class CirclesView(ModelView):
    """3b1b's FourierCirclesScene: arrows tip to tail, each with its circle, the slowest first; the
    last tip draws the curve, whose old part fades as the pen comes round again."""
    FADE = 0.25   # 3b1b's fade_rate: how fast the drawn curve fades behind the pen

    def __init__(self, node: Node, world=None):
        super().__init__()
        th = current()
        w = h = float(node.attrs.get("w", 5.6))
        self._setup(node, node.attrs, world, w, h)
        info = self.tl.info
        self.unit = w / 2 - 0.15
        self.freqs, self.coefs = info["freqs"], info["coefs"]
        # the constant term (frequency 0) only moves the start: it is the centre, not an arrow
        self.k_arrows = [k for k, f in enumerate(self.freqs) if f != 0]
        cols = color_gradient([th.palette[0], th.palette[3], th.palette[0]], max(len(self.k_arrows), 2))
        big = max(abs(self.coefs[k]) for k in self.k_arrows) if self.k_arrows else 1.0
        self.arrows = VGroup(*(Arrow(ORIGIN, RIGHT, buff=0, thickness=2.4, max_tip_length_to_length_ratio=0.3)
                               .set_fill(th.ink, 0.85).set_stroke(width=0) for _ in self.k_arrows))
        self.circles = VGroup(*(Circle(radius=1, n_components=24).set_stroke(c, 1.2, 0.35 + 0.4 * float(abs(self.coefs[k]) / big) ** 0.5)
                                for c, k in zip(cols, self.k_arrows)))
        self.unit_circle = Circle(radius=1, n_components=24).get_points().copy()
        drawn = info["drawn"] * self.unit
        self.drawn = drawn
        self.closed = bool(np.allclose(self.freqs, np.round(self.freqs)))   # whole turns: one loop repeats
        self.path = VMobject().set_stroke(th.accent, 3)
        self.width = 3.0
        self.ghost = VMobject().set_stroke(th.muted, 1.5, 0)
        if node.attrs.get("ghost", "off").strip() in ("on", "true", "yes") and len(info["target"]):
            ring = np.c_[info["target"] * self.unit, np.zeros(len(info["target"]))]
            self.ghost.set_points_as_corners([*ring, ring[0]])
            self.ghost.set_stroke(opacity=0.45)
        self.ghost_pts = self.ghost.get_points().copy()
        self._draw(self.t0, local=True)
        super().__init__(self.frame, self.ghost, self.circles, self.arrows, self.path)
        self.content = json.dumps(["sim", {k: node.attrs.get(k) for k in node.attrs if not k.startswith("_")}])

    def _draw(self, t: float, local: bool = False) -> None:
        conv = _local_or_screen(self, local)
        k = 1.0 if local else self.scale_k()
        turns = self.tl.state(t)["turns"]
        phase = np.exp(2j * math.pi * self.freqs * turns) * self.coefs
        at = complex(self.coefs[list(self.freqs).index(0)]) if 0 in list(self.freqs) else 0j
        for arrow, circle, i in zip(self.arrows, self.circles, self.k_arrows):
            a = conv([at.real * self.unit, at.imag * self.unit])
            nxt = at + phase[i]
            b = conv([nxt.real * self.unit, nxt.imag * self.unit])
            r = abs(self.coefs[i]) * self.unit * k
            if r > 1e-4 and np.linalg.norm(b - a) > 1e-4:
                arrow.put_start_and_end_on(a, b)
                arrow.set_fill(opacity=0.85)
            else:
                arrow.set_fill(opacity=0)
            circle.set_points(self.unit_circle * max(r, 1e-4) + a)
            at = nxt
        if not local and len(self.ghost_pts):
            self.ghost.set_points(np.array([conv(p[:2] / 1.0) for p in self.ghost_pts]))
        # the pen's curve: in the first loop what it has drawn so far; later the whole loop, its old
        # part fading (opacity ((s - turns) mod 1) ** FADE, as 3b1b's path fader)
        n = len(self.drawn)
        s = np.arange(n) / n
        if not self.closed:   # arrows at fractional rates never close a loop: the last loop's worth
            # of the trace, sampled on a fixed grid in time so its points stay put as it grows
            g = np.arange(math.floor(max(turns - 1, 0) * n) + 1, math.floor(turns * n) + 1) / n
            g = np.concatenate([[max(turns - 1, 0)], g, [turns]])
            tip = (self.coefs[None, :] * np.exp(2j * math.pi * np.outer(g, self.freqs))).sum(1) * self.unit
            pts = np.c_[tip.real, tip.imag]
            s, turns_ = g % 1.0, turns
            screen = np.array([conv(p) for p in pts])
            self.path.set_points_as_corners(screen if len(screen) > 1 else [screen[0], screen[0]])
            fade = np.clip(1 - (turns_ - g), 0, 1) ** self.FADE
            npts = self.path.get_num_points()
            f = np.interp(np.linspace(0, 1, npts), np.linspace(0, 1, len(fade)), fade)
            self.path.set_stroke(width=self.width * k * f, opacity=f)
            return
        if turns < 1:
            m = max(int(turns * n), 1)
            pts = [*self.drawn[:m], [at.real * self.unit, at.imag * self.unit]]
            s = np.concatenate([s[:m], [turns]])
        else:
            m = n
            pts = [*self.drawn, self.drawn[0]]
            s = np.concatenate([s, [1.0]])
        screen = np.array([conv(p) for p in pts])
        self.path.set_points_as_corners(screen)
        fade = ((s - turns) % 1.0) ** self.FADE if turns >= 1 else (1 - (turns - s)) ** self.FADE
        fade = np.clip(fade, 0, 1)
        npts = self.path.get_num_points()
        f = np.interp(np.linspace(0, 1, npts), np.linspace(0, 1, len(fade)), fade)
        self.path.set_stroke(width=self.width * k * f, opacity=f)

    def part(self, name: str):
        n = name.strip()
        if n == "curve":
            return self.path
        if n.isdigit() and 1 <= int(n) <= len(self.arrows):   # the k-th arrow, slowest first
            return VGroup(self.arrows[int(n) - 1], self.circles[int(n) - 1])
        return None

    def show(self, t: float, prev: float | None = None) -> None:
        self._draw(t)


# --- heat along a rod --------------------------------------------------------------------------------------
class HeatView(ModelView):
    """3b1b's heat-equation scenes: the temperature graph over the rod, the rod below it coloured
    by temperature, and arrows on the graph showing how fast each point is warming or cooling
    (the curvature ∂²T/∂x²), so bumps flatten where they bend most."""

    def __init__(self, node: Node, world=None):
        super().__init__()
        th = current()
        w, h = float(node.attrs.get("w", 8)), float(node.attrs.get("h", 4.6))
        self._setup(node, node.attrs, world, w, h)
        self.cold, self.hot = th.palette[0], th.palette[2]
        lo, hi = self.tl.info["range"]
        pad = 0.08 * max(hi - lo, 1e-6)
        self.lo, self.hi = lo - pad, hi + pad
        # "rod": coloured by value under the graph (a temperature); "string": the line itself,
        # pinned or free at its ends, swinging about its rest line
        self.look = node.attrs.get("look", "rod" if self.tl.info["equation"] == "heat" else "string").strip()
        if self.look not in ("rod", "string"):
            raise BeatError(f'<sim id={node.id}> look="{self.look}": "rod" or "string"')
        rod = self.look == "rod"
        self.x0, self.x1 = -w / 2 + 0.55, w / 2 - 0.15
        self.rod_y, self.rod_h = -h / 2 + 0.25, 0.32
        self.y0, self.y1 = (self.rod_y + self.rod_h + 0.45 if rod else -h / 2 + 0.2), h / 2 - 0.15
        if rod:
            axes = VGroup(Line([self.x0, self.y0, 0], [self.x1, self.y0, 0]),
                          Line([self.x0, self.y0, 0], [self.x0, self.y1, 0])).set_stroke(th.muted, 1.5)
            temp = _label(node.attrs.get("label", "T"), 26, th.muted).next_to([self.x0, self.y1, 0], LEFT, buff=0.15)
        else:
            y_rest = float(self._y(0.0))
            axes = DashedLine([self.x0, y_rest, 0], [self.x1, y_rest, 0]).set_stroke(th.muted, 1.5, 0.6)
            temp = VGroup()
            if self.tl.info["ends"] == "fixed":   # where it is held
                temp = VGroup(*(VGroup(Line([x, y_rest - 0.35, 0], [x, y_rest + 0.35, 0]).set_stroke(th.ink, 3),
                                       Dot([x, y_rest, 0], radius=0.07).set_fill(th.ink, 1))
                                for x in (self.x0, self.x1)))
        n_piece = 120
        self.xs = self.tl.info["xs"]
        self.pieces = VGroup(*(Rectangle((self.x1 - self.x0) / n_piece, self.rod_h).set_stroke(width=0)
                               .move_to([self.x0 + (i + 0.5) * (self.x1 - self.x0) / n_piece, self.rod_y + self.rod_h / 2, 0])
                               for i in range(n_piece)))
        self.piece_x = (np.arange(n_piece) + 0.5) / n_piece
        rim = Rectangle(self.x1 - self.x0, self.rod_h).set_stroke(th.ink, 1.5).set_fill(opacity=0)
        rim.move_to([(self.x0 + self.x1) / 2, self.rod_y + self.rod_h / 2, 0])
        self.graph = VMobject().set_stroke(th.ink, 4)
        self.arrow_x = np.linspace(0.04, 0.96, 13)
        self.arrows = VGroup(*(Arrow(ORIGIN, UP, buff=0, thickness=3, max_tip_length_to_length_ratio=0.4)
                               .set_fill(th.accent, 0.9).set_stroke(width=0) for _ in self.arrow_x))
        # arrows: one length scale for the whole scene, from the biggest change early on
        # (over the stretch the scene shows: a sharp start changes so fast at first that scaling
        # to that moment leaves every later arrow too small to see; early arrows are capped)
        tmax = min(float(node.attrs.get("_tmax", 2.0)) or 2.0, self.tl.end)
        curv = [np.abs(np.interp(self.arrow_x, self.xs, self.tl.info["change"](tt))).max()
                for tt in (0.1 * tmax, 0.2 * tmax, 0.35 * tmax)]
        self.arrow_k = 0.35 * (self.y1 - self.y0) / max(max(curv), 1e-9)
        self._draw(self.t0, local=True)
        if not rod:
            self.pieces, rim = VGroup(), VGroup()
            self.graph.set_stroke(th.ink, 4)
        super().__init__(self.frame, axes, temp, self.pieces, rim, self.graph, self.arrows)
        self.content = json.dumps(["sim", {k: node.attrs.get(k) for k in node.attrs if not k.startswith("_")}])

    def _y(self, T):
        return self.y0 + (np.asarray(T) - self.lo) / (self.hi - self.lo) * (self.y1 - self.y0)

    def _color(self, T: float) -> str:
        lo, hi = self.tl.info["range"]
        f = float(np.clip((T - lo) / max(hi - lo, 1e-9), 0, 1))
        return rgb_to_hex(interpolate(hex_to_rgb(self.cold), hex_to_rgb(self.hot), f))

    def _draw(self, t: float, local: bool = False) -> None:
        conv = _local_or_screen(self, local)
        k = 1.0 if local else self.scale_k()
        T = self.tl.state(t)["profile"]
        X = self.x0 + self.xs * (self.x1 - self.x0)
        pts = np.array([conv(p) for p in zip(X, self._y(T))])
        self.graph.set_points_as_corners(pts)
        if self.look == "rod":
            self.graph.set_stroke([self._color(v) for v in T[::8]], width=4 * k)
        else:
            self.graph.set_stroke(width=4 * k)
        for piece, x in zip(self.pieces, self.piece_x):
            piece.set_fill(self._color(float(np.interp(x, self.xs, T))), 1)
        rate = np.interp(self.arrow_x, self.xs, self.tl.info["change"](t))
        for arrow, x, r in zip(self.arrows, self.arrow_x, rate):
            y = float(self._y(np.interp(x, self.xs, T)))
            dy = float(np.clip(r * self.arrow_k, -0.9, 0.9))
            if abs(dy) < 0.12 or (t <= 0 and self.tl.info["equation"] == "heat"):
                arrow.set_fill(opacity=0)
                continue
            px = self.x0 + x * (self.x1 - self.x0)
            arrow.put_start_and_end_on(conv([px, y]), conv([px, y + dy]))
            arrow.set_fill(opacity=0.9)

    def part(self, name: str):
        return {"rod": self.pieces, "curve": self.graph, "arrows": self.arrows}.get(name.strip())

    def show(self, t: float, prev: float | None = None) -> None:
        self._draw(t)


# --- random walkers --------------------------------------------------------------------------------------------
class WalkView(ModelView):
    """The walkers as dots in lanes, hopping left and right, and under them the pile of where they
    stand now, a bar per spot, with the bell that √steps predicts (``bell="on"``)."""

    def __init__(self, node: Node, world=None):
        super().__init__()
        th = current()
        w, h = float(node.attrs.get("w", 9)), float(node.attrs.get("h", 5))
        self._setup(node, node.attrs, world, w, h)
        info = self.tl.info
        n = info["n"]
        # ± spots shown: where the furthest walkers are by the last moment the scene shows
        tmax = min(float(node.attrs.get("_tmax", self.tl.end)), self.tl.end)
        last = self.tl.state(tmax)
        span = max(6, int(math.ceil(np.percentile(np.abs(last["at"] - last["drift_at"]), 98) + 2)))
        # bar heights: the last pile the scene shows fills four fifths of the room; earlier, taller
        # piles stand at full height
        end_at = np.clip(np.floor(last["at"] - last["drift_at"] + 0.5), -span, span).astype(int) + span
        self.peak = max(int(np.bincount(end_at).max()) * 1.25, 1)
        self.span = span
        self.dx = (w - 0.4) / (2 * span + 1)
        self.lane_top, self.lane_bot = h / 2 - 0.1, h * 0.06
        rng = np.random.default_rng(5)
        self.lanes = self.lane_bot + rng.random(n) * (self.lane_top - self.lane_bot)
        r = max(0.02, min(0.07, 0.9 / math.sqrt(n)))
        self.dots = VGroup(*(Dot(radius=r).set_fill(th.palette[0], 0.9).set_stroke(width=0) for _ in range(n)))
        self.base_y = -h / 2 + 0.35
        self.bar_h = self.lane_bot - 0.25 - self.base_y
        floor = Line([-w / 2 + 0.2, self.base_y, 0], [w / 2 - 0.2, self.base_y, 0]).set_stroke(th.muted, 1.5)
        mid = DashedLine([0, self.base_y, 0], [0, self.lane_top, 0]).set_stroke(th.muted, 1, 0.5)
        self.bars = VGroup(*(Rectangle(self.dx * 0.86, 0.01).set_fill(th.palette[0], 0.8).set_stroke(width=0)
                             for _ in range(2 * span + 1)))
        self.bell = VMobject().set_stroke(th.accent, 3, 0)
        self.bell_on = node.attrs.get("bell", "off").strip() in ("on", "true", "yes")
        self._draw(self.t0, local=True)
        super().__init__(self.frame, mid, floor, self.bars, self.bell, self.dots)
        self.content = json.dumps(["sim", {k: node.attrs.get(k) for k in node.attrs if not k.startswith("_")}])

    def _draw(self, t: float, local: bool = False) -> None:
        conv = _local_or_screen(self, local)
        k = 1.0 if local else self.scale_k()
        st = self.tl.state(t)
        pos = np.clip(st["pos"] - st["drift"], -self.span - 0.5, self.span + 0.5)   # following the average
        for dot, x, y in zip(self.dots, pos, self.lanes):
            dot.move_to(conv([x * self.dx, y]))
        n = self.tl.info["n"]
        # the same spot for the same offset (round-half-to-even would alternate spots: a comb)
        at = np.clip(np.floor(st["at"] - st["drift_at"] + 0.5), -self.span, self.span)
        counts = np.bincount((at + self.span).astype(int), minlength=2 * self.span + 1)
        # one height scale for the beat: the tallest pile the walkers make two steps in (odd or even:
        # after an even number of steps they all stand on even spots)
        for i, (bar, c) in enumerate(zip(self.bars, counts)):
            hgt = max(min(c / self.peak, 1.0) * self.bar_h, 1e-3)
            x = (i - self.span) * self.dx
            bar.set_points(Rectangle(self.dx * 0.86 * k, hgt * k).get_points())
            bar.move_to(conv([x, self.base_y + hgt / 2]))
            bar.set_fill(opacity=0.8 if c else 0)
        steps = st["steps"]
        if self.bell_on and steps >= 2:
            sd = math.sqrt(self.tl.info["var"] * steps)
            xs = np.linspace(-self.span, self.span, 200)
            moves = sorted(set(np.diff(np.unique(np.round(st["at"])))))   # spots apart (a coin: 2)
            gap = float(moves[0]) if moves else 1.0
            ys = n * gap / (sd * math.sqrt(2 * math.pi)) * np.exp(-(xs / sd) ** 2 / 2)
            self.bell.set_points_smoothly([conv([x * self.dx, self.base_y + y / self.peak * self.bar_h]) for x, y in zip(xs, ys)])
            self.bell.set_stroke(width=3 * k, opacity=0.9)
        else:
            self.bell.set_stroke(opacity=0)

    def part(self, name: str):
        return {"walkers": self.dots, "pile": self.bars, "bell": self.bell}.get(name.strip())

    def show(self, t: float, prev: float | None = None) -> None:
        self._draw(t)


# --- any numbers over time ---------------------------------------------------------------------------------
def _nice_ticks(lo: float, hi: float, n: int = 4) -> list[float]:
    span = hi - lo
    if span <= 0:
        return [lo]
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), default=10 * mag)
    first = math.ceil(lo / step) * step
    return [round(first + k * step, 10) for k in range(int((hi - first) / step + 1e-9) + 1)]


class LinesView(ModelView):
    """A graph of chosen channels against model time (3b1b's live graphs beside a simulation):
    each a line growing as the clock runs, a dot at its head, its name at its end. ``ref`` adds
    a dashed curve in t, drawn whole from the start, to compare against."""
    tag = "simview"
    SAMPLES = 400

    def __init__(self, node: Node, world=None):
        from ...expr import parse_expr

        super().__init__()
        th = current()
        attrs = json.loads(node.attrs["_model"])
        w, h = float(node.attrs.get("w", 6)), float(node.attrs.get("h", 3.6))
        self._setup(node, attrs, world, w, h)
        names = [c.strip() for c in node.attrs.get("y", "").split(",") if c.strip()]
        bad = [c for c in names if c not in self.tl.channels]
        if bad:
            raise BeatError(f'<simview id={node.id} y="{node.attrs["y"]}">: {", ".join(bad)} is not a number '
                            f'this model gives; it gives {", ".join(self.tl.channels)}')
        if len(names) > 4:
            raise BeatError(f'<simview id={node.id}>: at most 4 numbers on one graph')
        self.names = names
        self.tmax = min(float(node.attrs.get("_tmax", self.tl.end)) or self.tl.end, self.tl.end)
        self.ts = np.linspace(0, self.tmax, self.SAMPLES)
        self.vals = np.array([[float(self.tl.state(t)[c]) for c in names] for t in self.ts])
        ref = None
        if node.attrs.get("ref", "").strip():
            f = parse_expr(node.attrs["ref"].strip(), ("t",))
            ref = np.broadcast_to(np.asarray(f(self.ts), float), self.ts.shape)
        lo = min(float(self.vals.min()), float(ref.min()) if ref is not None else math.inf, 0.0)
        hi = max(float(self.vals.max()), float(ref.max()) if ref is not None else -math.inf)
        if hi - lo < 1e-9:
            hi = lo + 1
        self.lo, self.hi = lo, hi + 0.06 * (hi - lo)
        right = max((_label(c, 22, th.ink).get_width() for c in names), default=0) + 0.25
        self.x0, self.y0 = -w / 2 + 0.75, -h / 2 + 0.55
        self.gw, self.gh = w - 0.85 - right, h - 0.75
        ink, muted = th.ink, th.muted
        axes = VGroup(Line([self.x0, self.y0, 0], [self.x0 + self.gw, self.y0, 0]),
                      Line([self.x0, self.y0, 0], [self.x0, self.y0 + self.gh, 0])).set_stroke(muted, 1.5)
        ticks = VGroup()
        for v in _nice_ticks(self.lo, self.hi):
            y = self._y(v)
            ticks.add(Line([self.x0 - 0.08, y, 0], [self.x0, y, 0]).set_stroke(muted, 1.5))
            ticks.add(_label(f"{v:g}", 18, muted).next_to([self.x0 - 0.08, y, 0], LEFT, buff=0.08))
        for v in _nice_ticks(0, self.tmax)[1:]:
            x = self._x(v)
            ticks.add(Line([x, self.y0, 0], [x, self.y0 - 0.08, 0]).set_stroke(muted, 1.5))
            ticks.add(_label(f"{v:g}", 18, muted).next_to([x, self.y0 - 0.08, 0], DOWN, buff=0.06))
        unit = node.attrs.get("time", "time").strip()
        tlab = _label(unit, 20, muted).next_to([self.x0 + self.gw, self.y0, 0], UP, buff=0.1, aligned_edge=RIGHT)
        cols = [th.palette[k % len(th.palette)] for k in range(len(names))] if len(names) > 1 else [th.accent]
        self.lines = VGroup(*(VMobject().set_stroke(c, 3) for c in cols))
        self.heads = VGroup(*(Dot(radius=0.06).set_fill(c, 1).set_stroke(width=0) for c in cols))
        self.tags = VGroup(*(_label(c, 22, col) for c, col in zip(names, cols)))
        self.ref = VMobject()
        if ref is not None:
            pts = [[self._x(t), self._y(v), 0] for t, v in zip(self.ts, ref)]
            self.ref = DashedVMobject(VMobject().set_points_smoothly(pts), num_dashes=40).set_stroke(ink, 2, 0.55)
        self._draw(self.t0, local=True)
        super().__init__(self.frame, axes, ticks, tlab, self.ref, self.lines, self.heads, self.tags)
        self.content = json.dumps(["simview", node.attrs.get("_model"), "lines", node.attrs.get("y"),
                                   node.attrs.get("ref"), self.t0, self.t1])

    def _x(self, t):
        return self.x0 + t / max(self.tmax, 1e-9) * self.gw

    def _y(self, v):
        return self.y0 + (v - self.lo) / (self.hi - self.lo) * self.gh

    def _draw(self, t: float, local: bool = False) -> None:
        conv = _local_or_screen(self, local)
        k = 1.0 if local else self.scale_k()
        t = min(t, self.tmax)
        n = int(np.searchsorted(self.ts, t, side="right"))
        here = [float(self.tl.state(t)[c]) for c in self.names]
        for j, (line, head, tag) in enumerate(zip(self.lines, self.heads, self.tags)):
            pts = [conv([self._x(tt), self._y(v)]) for tt, v in zip(self.ts[:n], self.vals[:n, j])]
            pts.append(conv([self._x(t), self._y(here[j])]))
            if len(pts) < 2:
                pts = [pts[0], pts[0]]
            line.set_points_as_corners(pts)
            head.move_to(pts[-1])
            tag.next_to(pts[-1], RIGHT, buff=0.1 * k)

    def show(self, t: float, prev: float | None = None) -> None:
        self._draw(t)

    def part(self, name: str):
        n = name.strip()
        if n in self.names:
            j = self.names.index(n)
            return VGroup(self.lines[j], self.heads[j])
        return {"ref": self.ref}.get(n)
