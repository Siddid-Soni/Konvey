"""``<sim>`` (manimgl): the board or montage at the end of the beat, and ``live``: what was added
since the previous beat plays out during the hold.

drop:   pegs in a triangle, one bin under each gap; each ball takes its seeded left/right path,
        hopping peg to peg, and lands on its bin's pile. The first balls fall one at a time, slowly
        (the viewer follows one); the rest pour in, overlapping (the shape emerges).
trials: every case as a card of chips; during the hold the cards appear one after another, the
        ones that count light up, and a tally follows (``<value bind="id.hits">``).

Live numbers (for ``<value bind=…>``): ``id.balls``, ``id.bin0`` … (drop); ``id.shown``,
``id.hits`` (trials)."""

from __future__ import annotations

import json
import math

from manimlib import *  # noqa: F401,F403

from ...sims import drop_runs, drop_spec, trials_spec
from ...theme import current
from ...tree import BeatError, Node
from ..base import LIT_W, Block, _label, lit_color

SLOW = 3          # balls that fall one at a time before the rest pour in
SLOW_S = 1.3      # seconds each slow ball takes


def smoothstep(a: float, b: float, x: float) -> float:
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)
FAST_S = 0.9      # seconds a ball takes once they pour


def build(node: Node, world=None):
    from ...models import MODELS
    from .model import BlocksView, CirclesView, HeatView, SpreadView, PendulumView, WalkView

    rule = node.attrs.get("rule", "").strip()
    if rule in MODELS:
        return {"blocks": BlocksView, "spread": SpreadView, "pendulum": PendulumView,
                "circles": CirclesView, "heat": HeatView, "line": HeatView, "walk": WalkView}[rule](node, world)
    return DropBlock(node, world) if rule == "drop" else TrialsBlock(node, world)


class _Sim(Block):
    tag = "sim"

    def _setup(self, node: Node, world, w: float, h: float):
        self.world = world
        self.key = node.id
        self.start = int(node.attrs.get("_start", 0))
        self.most = int(node.attrs.get("_most", 0))
        # the natural frame: live() maps its own coordinates through wherever layout put this
        self.frame = Rectangle(w, h).set_stroke(width=0).set_fill(opacity=0)
        self.w, self.h = w, h

    def to_screen(self, p) -> np.ndarray:
        k = self.frame.get_width() / self.w
        return self.frame.get_center() + k * np.array([p[0], p[1], 0.0])

    def put(self, name: str, value: float) -> None:
        if self.world is not None:
            self.world.values[f"{self.key}.{name}"] = value


# --- drop ------------------------------------------------------------------------------------------
def _ball_size(dx: float, room: float, tallest: int) -> tuple[float, int]:
    """(radius, balls abreast) for the biggest ball, at most 0.32 of a bin's width, with which a pile
    of ``tallest`` fits a bin ``dx`` wide and ``room`` tall."""
    r = min(0.32 * dx, 0.16)
    while r > 0.004:
        across = max(1, int((dx * 0.92) // (2 * r)))
        if math.ceil(max(tallest, 1) / across) * 2 * r <= room:
            return r, across
        r *= 0.94
    return 0.004, max(1, int((dx * 0.92) // 0.008))


class DropBlock(_Sim):
    def __init__(self, node: Node, world=None):
        super().__init__()
        th = current()
        where = f"<sim id={node.id}>"
        spec = self.spec = drop_spec(node.attrs, where)
        w, h = float(node.attrs.get("w", 7)), float(node.attrs.get("h", 6))
        self._setup(node, world, w, h)
        R = spec.rows
        self.dx = dx = w / (R + 2)
        top = h / 2 - 0.35
        peg_h = 0.5 * h
        self.dy = dy = peg_h / R
        self.peg_y = [top - (k + 0.5) * dy for k in range(R)]
        self.bin_top, self.bin_bottom = top - peg_h - 0.15, -h / 2 + 0.05
        peg_r = min(0.07, 0.12 * dx)
        pegs = VGroup(*(Dot([(j - k / 2) * dx, self.peg_y[k], 0], radius=peg_r).set_fill(th.muted, 1)
                        for k in range(R) for j in range(k + 1)))
        xs = [(b - R / 2) * dx for b in range(R + 1)]
        walls = VGroup(*(Line([x - dx / 2, self.bin_top, 0], [x - dx / 2, self.bin_bottom, 0])
                         for x in [*xs, xs[-1] + dx])).set_stroke(th.muted, 1.5)
        floor = Line([xs[0] - dx / 2, self.bin_bottom, 0], [xs[-1] + dx / 2, self.bin_bottom, 0]).set_stroke(th.muted, 2)
        self.bin_x = xs
        # one ball size for the whole scene: the tallest pile the scene reaches must fit its bin
        runs_most = drop_runs(R, max(self.most, spec.balls), spec.seed, spec.p)
        tallest = max([0] * (R + 1) + [sum(1 for r in runs_most if r.bin == b) for b in range(R + 1)])
        room = self.bin_top - self.bin_bottom
        # the biggest ball for which the tallest pile fits its bin, piled several abreast
        r, self.across = _ball_size(dx, room, tallest)
        self.r = r
        self.peg_r = peg_r
        color = th.color(node.attrs.get("color"), "c1")
        self.runs = runs = runs_most[:spec.balls]
        height = [0] * (R + 1)
        self.slot = []   # where each ball rests: filling its bin row by row, from the bottom
        a = self.across
        for run in runs:
            row, col = divmod(height[run.bin], a)
            x = xs[run.bin] + (col - (a - 1) / 2) * 2 * r
            self.slot.append(np.array([x, self.bin_bottom + r + 2 * r * row]))
            height[run.bin] += 1
        self.balls = VGroup(*(Dot([*p, 0], radius=r).set_fill(color, 1).set_stroke(width=0) for p in self.slot))
        for i, ball in enumerate(self.balls):   # what has not fallen yet is hidden until live() drops it
            if i >= self.start:
                ball.set_opacity(0)
        self.bin_boxes = VGroup(*(Rectangle(dx, room).move_to([x, (self.bin_top + self.bin_bottom) / 2, 0])
                                  .set_stroke(width=0).set_fill(opacity=0) for x in xs))
        self.counts = [sum(1 for r_ in runs if r_.bin == b) for b in range(R + 1)]
        super().__init__(self.frame, pegs, walls, floor, self.bin_boxes, self.balls)
        self.content = json.dumps(["sim", {k: node.attrs.get(k) for k in ("rule", "rows", "balls", "seed", "p", "color")}])

    def part(self, name: str):
        n = name.strip().removeprefix("bin").strip()
        return self.bin_boxes[int(n)] if n.isdigit() and int(n) < len(self.bin_boxes) else None

    def path_point(self, i: int, f: float) -> np.ndarray:
        """Ball i at fraction f of its fall (in the board's own coordinates)."""
        run, R, dx, dy, r = self.runs[i], self.spec.rows, self.dx, self.dy, self.r
        ways = [np.array([0.0, self.peg_y[0] + dy])]
        x = 0.0
        for k in range(R):
            ways.append(np.array([x, self.peg_y[k] + self.peg_r + r]))
            x += dx / 2 if run.moves[k] else -dx / 2
        ways.append(np.array([x, self.bin_top]))
        ways.append(self.slot[i])
        legs = len(ways) - 1
        t = min(max(f, 0.0), 1.0) * legs
        k = min(int(t), legs - 1)
        g = t - k
        a, b = ways[k], ways[k + 1]
        if 1 <= k <= R:          # a bounce off a peg: a little hop on the way to the next one
            return np.array([a[0] + (b[0] - a[0]) * g, a[1] + (b[1] - a[1]) * g * g + 0.35 * dy * math.sin(math.pi * g)])
        return a + (b - a) * (g * g if k == legs - 1 else g)

    def schedule(self, hold: float) -> list[tuple[float, float]]:
        """(start, duration) in seconds for each ball dropped this beat."""
        new = list(range(self.start, len(self.runs)))
        if not new:
            return []
        slow = new[:SLOW]
        rest = new[SLOW:]
        need = len(slow) * SLOW_S + (FAST_S * 2 if rest else 0)
        k = min(1.0, hold / max(need, 1e-6))   # a short hold plays the same story faster
        each = SLOW_S * k
        if not rest:   # only the followed balls: they share the whole line (unhurried, ≤ 2.5 s each)
            each = min(2.5, max(each, 0.9 * hold / len(slow)))
        out, t = [], 0.0
        for _ in slow:
            out.append((t, each))
            t += each
        if rest:
            span = max(hold - t - FAST_S * k, 1e-3)
            for j in range(len(rest)):
                out.append((t + span * j / max(len(rest), 1), FAST_S * k))
        return out


def _live_drop(mob: DropBlock, start: int, hold: float) -> Animation | None:
    new = list(range(start, len(mob.runs)))
    if not new:
        return None
    mob.start = start
    times = mob.schedule(hold)
    th = current()
    movers = VGroup(*(mob.balls[i].copy().set_opacity(0) for i in new))
    movers.set_z_index(2)
    landed = [False] * len(new)
    slow = SLOW if len(new) > SLOW else len(new)
    big = max(1.0, min(0.3 * mob.dx, 0.14) / mob.r)   # how much bigger a followed ball is drawn
    base_w = movers[0].get_width() if len(movers) else 0.0
    counts = [sum(1 for r in mob.runs[:mob.start] if r.bin == b) for b in range(len(mob.bin_x))]

    def update(m, a):
        t = a * hold
        for j, i in enumerate(new):
            s, d = times[j]
            dot = movers[j]
            if t < s:
                continue
            if t >= s + d or a >= 1:
                if not landed[j]:
                    landed[j] = True
                    dot.set_opacity(0)
                    mob.balls[i].set_opacity(1)
                    counts[mob.runs[i].bin] += 1
                    mob.put(f"bin{mob.runs[i].bin}", counts[mob.runs[i].bin])
                continue
            dot.set_opacity(1)
            f = (t - s) / d
            if j < slow:   # a ball the eye follows is drawn big, and settles to pile size as it lands
                grow = 1 + (big - 1) * (1 - smoothstep(0.82, 1.0, f))
                dot.set_width(base_w * grow)
            dot.move_to(mob.to_screen(mob.path_point(i, f)))
        mob.put("balls", mob.start + sum(landed))

    return UpdateFromAlphaFunc(movers, update, run_time=hold, rate_func=linear, remover=True)


# --- trials ----------------------------------------------------------------------------------------
class TrialsBlock(_Sim):
    def __init__(self, node: Node, world=None):
        super().__init__()
        th = current()
        where = f"<sim id={node.id}>"
        spec = self.spec = trials_spec(node.attrs, where)
        n = len(spec.cases)
        size = float(node.attrs.get("size", 26))
        tokens = sorted({t for c in spec.cases for t in c})
        palette = th.palette
        tone = {t: palette[k % len(palette)] for k, t in enumerate(tokens)}
        lc = lit_color(node)
        chip = 0.42 * size / 26
        cards = VGroup()
        for i, case in enumerate(spec.cases):
            chips = VGroup()
            for tok in case:
                box = RoundedRectangle(width=max(chip, 0.25 + 0.16 * len(tok)), height=chip, corner_radius=0.07)
                box.set_fill(tone[tok], 0.85).set_stroke(width=0)
                lab = _label(tok, size * 0.7, th.bg).move_to(box)
                chips.add(VGroup(box, lab))
            chips.arrange(RIGHT, buff=0.06)
            frame = RoundedRectangle(width=chips.get_width() + 0.3, height=chips.get_height() + 0.26, corner_radius=0.12)
            frame.set_fill(th.panel_fill, 0.6).set_stroke(th.muted, 1.5).move_to(chips)
            cards.add(VGroup(frame, chips))
        cols = max(1, math.ceil(math.sqrt(n * 1.8)))
        cards.arrange_in_grid(n_cols=cols, h_buff=0.22, v_buff=0.22)
        w, h = cards.get_width() + 0.2, cards.get_height() + 0.2
        self._setup(node, world, w, h)
        self.frame.move_to(cards)
        self.cards, self.lc = cards, lc
        self.shown = min(spec.shown, n)
        for i, card in enumerate(cards):
            if i in spec.hits and i < self.shown:
                card[0].set_stroke(lc, LIT_W)
        self.looks = [card.copy() for card in cards]   # each card as it looks once it has come in
        for i, card in enumerate(cards):
            if i >= self.start or i >= self.shown:
                card.set_opacity(0)
        super().__init__(self.frame, cards)
        self.content = json.dumps(["sim", {k: node.attrs.get(k) for k in ("rule", "cases", "hits", "shown")}])

    def part(self, name: str):
        n = name.strip()
        if n == "hits":
            return VGroup(*(self.cards[i] for i in sorted(self.spec.hits) if i < self.shown)) or None
        return self.cards[int(n)] if n.isdigit() and int(n) < len(self.cards) else None


def _live_trials(mob: TrialsBlock, start: int, hold: float) -> Animation | None:
    new = list(range(start, mob.shown))
    if not new:
        return None
    mob.start = start
    step = hold / (len(new) + 1)
    shown = [False] * len(new)
    full = {i: mob.looks[i].copy().move_to(mob.cards[i]).scale(mob.cards[i].get_width() / mob.looks[i].get_width())
            for i in new}   # its final look (a hit's outline lit), where the layout put the card

    def update(m, a):
        t = a * hold
        hits = sum(1 for i in mob.spec.hits if i < mob.start)
        for j, i in enumerate(new):
            at = step * (j + 0.5)
            f = min(1.0, max(0.0, (t - at) / min(0.25, step)))
            if f > 0:
                card = mob.cards[i]
                card.become(full[i].copy().scale(1.25 - 0.25 * f).set_opacity(f) if f < 1 else full[i])
                if f >= 1:
                    shown[j] = True
            if shown[j] and i in mob.spec.hits:
                hits += 1
        mob.put("shown", mob.start + sum(shown))
        mob.put("hits", hits)

    return UpdateFromAlphaFunc(Mobject(), update, run_time=hold, rate_func=linear)


def live(node: Node, mob, hold: float) -> Animation | None:
    """What plays during the hold: the part of the simulation this beat adds. Where it starts
    comes from this beat (``_start``): when nothing changed, the block on screen is the previous
    beat's, which already played its part."""
    from .model import ModelView

    if isinstance(mob, ModelView):   # the clock runs from where the last beat left it to this beat's t
        mob.t0, mob.t1 = float(node.attrs.get("_t0", 0)), float(node.attrs.get("_t1", 0))
        return mob.play(hold)
    start = int(node.attrs.get("_start", 0))
    return _live_drop(mob, start, hold) if isinstance(mob, DropBlock) else _live_trials(mob, start, hold)


def morph(old, new, sources=None) -> Animation:
    """The state the previous beat ended in is the state this beat starts in, so the transition
    only carries the board to where this beat's layout put it; the new part plays in the hold.
    (A Transform into the new block would invent copies of old balls to match the new count and
    fly them, fading, toward slots that are still empty.)"""
    target = old.copy()
    target.scale(new.frame.get_width() / max(old.frame.get_width(), 1e-6))
    target.shift(new.frame.get_center() - target.frame.get_center())
    return Transform(old, target)
