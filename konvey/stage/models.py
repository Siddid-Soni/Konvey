"""Time-evolving models for ``<sim>`` (pure Python): one model, many views.

A model turns its attributes into a **timeline**, computed once and exactly (or with a fine fixed
step), deterministic for a given seed. Every view of it (the physical picture, a phase plane, a
graph over time, a counter) reads the same ``state(t)``, so they stay in step, as 3b1b's
colliding blocks drive the blocks, the clack counter and the velocity-space point from one state.

A beat says how far model time has got by its end (``t="4"``); the time since the previous beat
plays out during the beat's hold.

Models:

- ``blocks``: a big block slides into a small one in front of a wall; every collision is elastic.
  ``mass`` = big / small (1, 100, 10000 … give 3, 31, 314 … collisions). Channels: ``x1 x2 v1 v2``
  (positions of the left edges, velocities), ``p1 p2`` (√m·v, the velocity-space point that walks
  round a circle), ``clacks`` (collisions so far). Events: ``clack`` (time, where).
- ``spread``: ``people`` wander in a box; the sick pass it to the healthy within ``radius`` with
  probability ``p`` per day and recover after ``sick-days``; ``distancing`` keeps them apart.
  Time is in days. Channels: ``healthy sick recovered`` (counts).
- ``pendulum``: θ'' = −(g/L)·sin θ − μ·θ' from ``angle`` (degrees) with ``damping`` μ. Time is in
  seconds. Channels: ``theta omega``; the phase plane shows its spiral and the vector field.
- ``circles``: a closed curve drawn by ``terms`` arrows tip to tail, each turning at its own whole
  number of turns per loop (a Fourier series, 3b1b's FourierCirclesScene). The curve is the outline
  of ``shape`` (any TeX, e.g. ``\\pi``, or a word) or ``curve="x(u); y(u)"`` for u in [0, 2π]; one
  loop takes ``period`` seconds. Or give the arrows: ``arrows="length, angle, turns; …"`` (angle in
  degrees, whole or not; adding waves, rotating phasors). Channels: ``turns`` (loops so far),
  ``x y`` (where the last tip is: graph ``y`` over time for the wave it makes).
- ``line`` (also ``heat``): a quantity along a line from x = 0 to 1, ``start`` = ``step`` (high
  left half, low right half), ``spike`` or an expression in x. ``equation="heat"``: it evens out
  at ``rate`` (∂T/∂t = rate·∂²T/∂x²; a rod's temperature, a spreading dye). ``equation="wave"``:
  it swings at ``speed`` (∂²u/∂t² = speed²·∂²u/∂x²; a plucked string), ``damping`` optional.
  ``ends="sealed"`` (nothing flows out; heat's default) or ``"fixed"`` (held at 0; wave's
  default). Solved exactly as a series of cosines or sines. Time in seconds. Channels:
  ``left middle right`` (the value there), ``spread`` (highest minus lowest).
- ``walk``: ``walkers`` each take a step ``pace`` times a second: left or right by coin flip
  (``p`` = chance of right), or one of ``step="-1,0,1"`` (equally likely whole-number moves; a
  die: ``"1,2,3,4,5,6"``, the pile is then a running total). The view follows the average move,
  so the pile stays in sight; it spreads like √steps into a bell. Channels: ``steps``,
  ``spread`` (standard deviation), ``far`` (farthest from the average), ``mean``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

from .tree import BeatError

MAX_EVENTS = 20000


@dataclass
class Timeline:
    """What a model does over time: ``state(t)`` for any t in [0, end]."""
    name: str
    end: float
    channels: tuple[str, ...]
    sample: object                          # t -> {channel: value}
    events: dict[str, np.ndarray] = field(default_factory=dict)   # name -> event times
    info: dict = field(default_factory=dict)                      # fixed facts views need

    def state(self, t: float) -> dict:
        return self.sample(min(max(t, 0.0), self.end))


def _num(attrs: dict, key: str, default: float, lo: float, hi: float, where: str) -> float:
    raw = str(attrs.get(key, default)).strip()
    try:
        v = float(raw)
    except ValueError:
        raise BeatError(f'{where} {key}="{raw}": a number') from None
    if not lo <= v <= hi:
        raise BeatError(f'{where} {key}="{raw}": between {lo:g} and {hi:g}')
    return v


# --- blocks -----------------------------------------------------------------------------------------
@lru_cache(maxsize=32)
def _blocks(ratio: float, x1: float, x2: float, v: float, s1: float, s2: float):
    """Exact event list of the two-block system: rows (time, x1, x2, v1, v2, clacks), the state
    just after each collision (row 0: the start)."""
    m1, m2 = 1.0, ratio
    t, p1, p2, u1, u2, n = 0.0, x1, x2, 0.0, -abs(v), 0
    rows, where = [(t, p1, p2, u1, u2, n)], []
    while n < MAX_EVENTS:
        # next block–block contact (gap closes) and next wall contact
        gap, closing = p2 - (p1 + s1), u1 - u2
        dt_bb = gap / closing if closing > 1e-12 else math.inf
        dt_w = -p1 / u1 if u1 < -1e-12 else math.inf
        dt = min(dt_bb, dt_w)
        if not math.isfinite(dt):
            break
        t += dt
        p1, p2 = p1 + u1 * dt, p2 + u2 * dt
        if dt_bb <= dt_w:   # elastic collision between the blocks
            u1, u2 = ((m1 - m2) * u1 + 2 * m2 * u2) / (m1 + m2), ((m2 - m1) * u2 + 2 * m1 * u1) / (m1 + m2)
            where.append(p1 + s1)
        else:               # the small block bounces off the wall
            u1 = -u1
            where.append(0.0)
        n += 1
        rows.append((t, p1, p2, u1, u2, n))
    return np.array(rows), np.array(where)


def blocks_model(attrs: dict, where: str) -> Timeline:
    ratio = _num(attrs, "mass", 100, 1, 1e8, where)
    digits = math.log10(ratio)
    s1 = 1.0
    s2 = min(2.4, 1.0 + 0.32 * digits)          # the big block looks bigger, within reason
    x1, x2 = _num(attrs, "x1", 3, 0.5, 50, where), _num(attrs, "x2", 6, 1, 60, where)
    if x2 < x1 + s1 + 0.1:
        raise BeatError(f'{where} x2="{x2:g}": the big block must start to the right of the small one '
                        f'(x2 > x1 + 1.1)')
    rows, spots = _blocks(ratio, x1, x2, _num(attrs, "v", 1, 0.05, 10, where), s1, s2)
    times = rows[:, 0]
    last = times[-1]
    # the blocks drift apart a while after the last collision, but the clock stops before the big
    # block runs off the end of the floor the view draws
    reach = x2 + s2 + 1.3
    t_off = last + (reach - (rows[-1, 2] + s2)) / max(rows[-1, 4], 1e-6)
    end = max(last + 0.5, min(last + 3.0, t_off))
    m1, m2 = 1.0, ratio

    def sample(t: float) -> dict:
        k = int(np.searchsorted(times, t, side="right") - 1)
        t0, p1, p2, u1, u2, n = rows[k]
        d = t - t0
        return {"x1": p1 + u1 * d, "x2": p2 + u2 * d, "v1": u1, "v2": u2,
                "p1": math.sqrt(m1) * u1, "p2": math.sqrt(m2) * u2, "clacks": int(n)}

    return Timeline("blocks", float(end), ("x1", "x2", "v1", "v2", "p1", "p2", "clacks"), sample,
                    events={"clack": times[1:]},
                    info={"s1": s1, "s2": s2, "m1": m1, "m2": m2, "spots": spots, "x2_0": x2,
                          "radius": math.sqrt(m2) * abs(float(attrs.get("v", 1))),
                          "states": rows[:, 3:5] * np.sqrt([m1, m2]), "total": int(rows[-1, 5])})


# --- spread (agents) -------------------------------------------------------------------------------
@lru_cache(maxsize=16)
def _spread(n: int, radius: float, p: float, sick_days: float, distancing: float, days: float, seed: int):
    """People in a unit box: each walks toward a target that changes every so often, bounces off
    the walls, and (with ``distancing``) is pushed away from the others nearby. A sick person
    passes it to each healthy one within ``radius`` with probability ``p`` per day; the sick recover
    after ``sick_days``. Returns per-step positions, statuses (0 healthy, 1 sick, 2 recovered)
    and the step's time."""
    rng = np.random.default_rng(seed)
    dt = 0.05
    steps = int(days / dt) + 1
    pos = rng.random((n, 2))
    vel = np.zeros((n, 2))
    target = rng.random((n, 2))
    retarget = rng.random(n) * 1.0
    status = np.zeros(n, np.int8)
    sick_since = np.full(n, -1.0)
    status[0], sick_since[0] = 1, 0.0
    P, S = np.empty((steps, n, 2), np.float32), np.empty((steps, n), np.int8)
    for k in range(steps):
        t = k * dt
        P[k], S[k] = pos, status
        # wander: pull toward a target that moves on every ~1 day
        due = t >= retarget
        target[due] = np.clip(pos[due] + rng.normal(0, 0.25, (due.sum(), 2)), 0, 1)
        retarget[due] = t + 0.5 + rng.random(due.sum())
        force = (target - pos) * 6.0
        diff = pos[:, None, :] - pos[None, :, :]
        dist = np.sqrt((diff ** 2).sum(-1)) + np.eye(n)
        if distancing > 0:   # keep apart: a push from everyone close by
            near = dist < 0.12
            force += distancing * 0.002 * (diff * (near / dist ** 3)[..., None]).sum(1)
        vel = 0.85 * vel + force * dt
        speed = np.linalg.norm(vel, axis=1, keepdims=True)
        vel *= np.minimum(1.0, 0.6 / np.maximum(speed, 1e-9))
        pos = pos + vel * dt
        out = (pos < 0) | (pos > 1)
        vel[out] *= -1
        pos = np.clip(pos, 0, 1)
        # passing it on, and getting well
        sick = status == 1
        if sick.any():
            exposed = (dist[:, sick] < radius).sum(1)
            catch = (status == 0) & (rng.random(n) < 1 - (1 - p * dt) ** exposed)
            status[catch], sick_since[catch] = 1, t
            well = sick & (t - sick_since >= sick_days)
            status[well] = 2
        elif k > 0:   # nobody sick any more: the rest of the run looks the same
            P[k:], S[k:] = pos, status
            break
    return P, S, dt


def spread_model(attrs: dict, where: str) -> Timeline:
    n = int(_num(attrs, "people", 100, 2, 400, where))
    radius = _num(attrs, "radius", 0.05, 0.005, 0.5, where)
    p = _num(attrs, "p", 0.4, 0.0, 20, where)
    sick_days = _num(attrs, "sick-days", 5, 0.5, 60, where)
    distancing = _num(attrs, "distancing", 0, 0, 1, where)
    days = _num(attrs, "days", 40, 1, 200, where)
    seed = int(_num(attrs, "seed", 1, 0, 1e9, where))
    P, S, dt = _spread(n, radius, p, sick_days, distancing, days, seed)
    counts = np.stack([(S == k).sum(1) for k in range(3)], 1)

    def sample(t: float) -> dict:
        k = min(int(round(t / dt)), len(P) - 1)
        s, i, r = counts[k]
        return {"healthy": int(s), "sick": int(i), "recovered": int(r), "pos": P[k], "status": S[k]}

    return Timeline("spread", days, ("healthy", "sick", "recovered"), sample,
                    info={"n": n, "radius": radius, "counts": counts, "dt": dt})


# --- pendulum ----------------------------------------------------------------------------------------
@lru_cache(maxsize=16)
def _pendulum(theta0: float, omega0: float, g_l: float, mu: float, seconds: float):
    dt = 0.005
    steps = int(seconds / dt) + 1

    def f(th, om):
        return om, -g_l * math.sin(th) - mu * om

    out = np.empty((steps, 2))
    th, om = theta0, omega0
    for k in range(steps):   # RK4
        out[k] = th, om
        k1 = f(th, om)
        k2 = f(th + dt / 2 * k1[0], om + dt / 2 * k1[1])
        k3 = f(th + dt / 2 * k2[0], om + dt / 2 * k2[1])
        k4 = f(th + dt * k3[0], om + dt * k3[1])
        th += dt / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
        om += dt / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
    return out, dt


def pendulum_model(attrs: dict, where: str) -> Timeline:
    theta0 = math.radians(_num(attrs, "angle", 60, -179, 179, where))
    omega0 = _num(attrs, "spin", 0, -20, 20, where)
    g_l = _num(attrs, "g", 9.8, 0.1, 100, where) / _num(attrs, "length", 2, 0.1, 20, where)
    mu = _num(attrs, "damping", 0.3, 0, 5, where)
    seconds = _num(attrs, "seconds", 20, 1, 120, where)
    path, dt = _pendulum(theta0, omega0, g_l, mu, seconds)

    def sample(t: float) -> dict:
        k = t / dt
        i = min(int(k), len(path) - 2)
        f = k - i
        th, om = path[i] + (path[i + 1] - path[i]) * f
        return {"theta": float(th), "omega": float(om)}

    def field(th, om):
        return om, -g_l * math.sin(th) - mu * om

    return Timeline("pendulum", seconds, ("theta", "omega"), sample,
                    info={"field": field, "extent": (float(np.abs(path[:, 0]).max()), float(np.abs(path[:, 1]).max()))})


# --- circles (a Fourier series drawing a curve) -------------------------------------------------------
SAMPLES = 2048


@lru_cache(maxsize=16)
def _outline(shape: str) -> np.ndarray:
    """SAMPLES points evenly spaced along the outline of a TeX shape (all its pieces, in order),
    centred, largest radius 1. Needs manimgl (and LaTeX for maths)."""
    from manimlib import Tex, VMobject

    mob = Tex(shape)
    paths = []
    for sub in mob.family_members_with_points():
        for piece in sub.get_subpaths():
            if len(piece) >= 3:
                paths.append(piece)
    if not paths:
        raise BeatError(f'shape="{shape}" has no outline to draw')
    one = VMobject()
    for piece in paths:   # the pieces joined in order: the circles draw one closed curve
        one.append_points(piece) if one.has_points() else one.set_points(piece)
    pts = np.array([one.point_from_proportion(a)[:2] for a in np.linspace(0, 1, SAMPLES, endpoint=False)])
    return pts


def _even(pts: np.ndarray) -> np.ndarray:
    """Resample a closed polyline at SAMPLES points evenly spaced by length."""
    closed = np.vstack([pts, pts[:1]])
    seg = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    want = np.linspace(0, s[-1], SAMPLES, endpoint=False)
    return np.c_[np.interp(want, s, closed[:, 0]), np.interp(want, s, closed[:, 1])]


def circles_model(attrs: dict, where: str) -> Timeline:
    from .expr import parse_expr

    terms = int(_num(attrs, "terms", 20, 1, 400, where))
    period = _num(attrs, "period", 10, 1, 120, where)
    # a drawn shape repeats each loop; free arrows keep making new patterns, so the clock runs on
    loops = _num(attrs, "loops", 50 if attrs.get("arrows") else 3, 1, 200, where)
    pts = None
    if attrs.get("arrows"):   # the arrows themselves: length, starting angle (degrees), turns a loop
        try:
            rows = [[float(v) for v in a_.split(",")] for a_ in str(attrs["arrows"]).split(";") if a_.strip()]
        except ValueError:
            rows = []
        if not rows or any(len(r) != 3 for r in rows) or len(rows) > 400:
            raise BeatError(f'{where} arrows="{attrs["arrows"]}": "length, angle, turns" per arrow, e.g. '
                            '"1, 0, 1; 0.5, 90, -2" (angle in degrees, turns per loop)')
        rows = np.array(rows)
        freqs = rows[:, 2]
        coefs = rows[:, 0] * np.exp(1j * np.radians(rows[:, 1]))
        order = np.argsort(np.abs(freqs) + (freqs < 0) * 0.5, kind="stable")   # slowest first
        freqs, coefs = freqs[order], coefs[order]
        coefs = coefs / max(float(np.abs(coefs).sum()), 1e-9)   # the chain's full reach is 1
    else:
        if attrs.get("curve"):
            parts = [p.strip() for p in str(attrs["curve"]).split(";")]
            if len(parts) != 2:
                raise BeatError(f'{where} curve="{attrs["curve"]}": "x(u); y(u)", u from 0 to 2pi')
            fx, fy = (parse_expr(p, ("u",)) for p in parts)
            u = np.linspace(0, 2 * math.pi, 4 * SAMPLES, endpoint=False)
            raw = np.c_[np.broadcast_to(fx(u), u.shape), np.broadcast_to(fy(u), u.shape)]
        else:
            raw = _outline(str(attrs.get("shape", r"\pi")).strip())
        pts = _even(raw)
        lo, hi = pts.min(0), pts.max(0)
        pts = (pts - (lo + hi) / 2) / (max(hi - lo) / 2 or 1.0)   # centred on its box, filling [-1, 1]
        z = pts[:, 0] + 1j * pts[:, 1]
        c = np.fft.fft(z) / len(z)                              # c[k]: the arrow turning k times a loop
        freqs = sorted(range(-(terms // 2), terms - terms // 2), key=lambda f: (abs(f), -f))   # 0, 1, -1, 2 …
        coefs = np.array([c[f % len(z)] for f in freqs])
        freqs = np.array(freqs, float)
    s = np.linspace(0, 1, 1200, endpoint=False)
    drawn = (coefs[None, :] * np.exp(2j * math.pi * np.outer(s, freqs))).sum(1)   # what the tips trace

    def sample(t: float) -> dict:
        tip = complex((coefs * np.exp(2j * math.pi * freqs * t / period)).sum())
        return {"turns": t / period, "x": tip.real, "y": tip.imag}

    return Timeline("circles", loops * period, ("turns", "x", "y"), sample,
                    info={"freqs": freqs, "coefs": coefs, "period": period, "drawn": np.c_[drawn.real, drawn.imag],
                          "target": pts if pts is not None else np.zeros((0, 2))})


# --- heat along a rod ------------------------------------------------------------------------------------
MODES = 160


@lru_cache(maxsize=16)
def _heat_start(start: str):
    from .expr import parse_expr

    x = (np.arange(4000) + 0.5) / 4000
    if start == "step":
        return x, np.where(x < 0.5, 1.0, 0.0)
    if start == "spike":
        return x, np.exp(-((x - 0.5) / 0.05) ** 2)
    f = parse_expr(start, ("x",))
    return x, np.broadcast_to(np.asarray(f(x), float), x.shape).copy()


def line_model(attrs: dict, where: str) -> Timeline:
    start = str(attrs.get("start", "step")).strip()
    try:
        x, f0 = _heat_start(start)
    except BeatError:
        raise
    except Exception:
        raise BeatError(f'{where} start="{start}": "step", "spike" or an expression in x (0 to 1)') from None
    equation = str(attrs.get("equation", "heat")).strip()
    if equation not in ("heat", "wave"):
        raise BeatError(f'{where} equation="{equation}": "heat" (evens out) or "wave" (swings)')
    ends = str(attrs.get("ends", "sealed" if equation == "heat" else "fixed")).strip()
    if ends not in ("sealed", "fixed"):
        raise BeatError(f'{where} ends="{ends}": "sealed" (nothing flows out) or "fixed" (held at 0)')
    rate = _num(attrs, "rate", 0.02, 1e-5, 10, where)
    speed = _num(attrs, "speed", 0.5, 0.01, 20, where)
    damping = _num(attrs, "damping", 0, 0, 10, where)
    seconds = _num(attrs, "seconds", 30, 1, 600, where)
    if ends == "sealed":   # no flow through the ends: cosines (the n = 0 term is the average)
        n = np.arange(MODES)
        wave = lambda k, z: np.cos(np.pi * np.outer(k, z))  # noqa: E731
    else:                  # ends held at 0: sines
        n = np.arange(1, MODES + 1)
        wave = lambda k, z: np.sin(np.pi * np.outer(k, z))  # noqa: E731
    a = wave(n, x) @ f0 / len(x) * 2
    if ends == "sealed":
        a[0] /= 2
    if equation == "wave":   # nothing smooths a swinging line: soften the series' overshoot at
        a = a * np.sinc(n / (MODES + 1))   # sharp corners (Lanczos factors)
    xs = np.linspace(0, 1, 241)
    shown = wave(n, xs)                                    # modes × 241
    k2 = (np.pi * n) ** 2

    def weights(t: float) -> np.ndarray:
        if equation == "heat":
            return a * np.exp(-rate * k2 * t)
        return a * np.cos(speed * np.pi * n * t) * math.exp(-damping * t)

    def profile(t: float) -> np.ndarray:
        if t <= 0 and equation == "heat":
            return np.interp(xs, x, f0) if ends == "sealed" else np.interp(xs, x, f0) * ((xs > 0) & (xs < 1))
        return weights(t) @ shown

    def change(t: float) -> np.ndarray:
        """How fast each point is moving up or down: rate·∂²T/∂x² (heat), or the acceleration
        speed²·∂²u/∂x² (wave)."""
        if equation == "heat":
            return -(weights(max(t, 1e-3)) * k2 * rate) @ shown
        return -(weights(t) * k2 * speed ** 2) @ shown

    def sample(t: float) -> dict:
        T = profile(t)
        return {"left": float(T[0]), "middle": float(T[len(T) // 2]), "right": float(T[-1]),
                "spread": float(T.max() - T.min()), "profile": T}

    top = float(np.abs(f0).max())
    span = (float(f0.min()), float(f0.max())) if equation == "heat" else (-top, top)
    return Timeline("line", seconds, ("left", "middle", "right", "spread"), sample,
                    info={"xs": xs, "range": span, "change": change, "equation": equation, "ends": ends})


heat_model = line_model


# --- random walkers ---------------------------------------------------------------------------------------
@lru_cache(maxsize=16)
def _walk(n: int, steps: int, moves: tuple, p: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    if moves == (-1, 1):   # a coin, maybe biased: right with chance p
        step = np.where(rng.random((steps, n)) < p, 1, -1)
    else:                  # equally likely moves
        step = np.array(moves)[rng.integers(0, len(moves), (steps, n))]
    return np.vstack([np.zeros((1, n), np.int32), np.cumsum(step, 0, dtype=np.int32)])


def walk_model(attrs: dict, where: str) -> Timeline:
    n = int(_num(attrs, "walkers", 400, 1, 5000, where))
    pace = _num(attrs, "pace", 4, 0.2, 60, where)
    seconds = _num(attrs, "seconds", 30, 1, 300, where)
    p = _num(attrs, "p", 0.5, 0, 1, where)
    seed = int(_num(attrs, "seed", 2, 0, 1e9, where))
    raw = str(attrs.get("step", "-1,1")).strip()
    try:
        moves = tuple(int(v) for v in raw.split(","))
    except ValueError:
        raise BeatError(f'{where} step="{raw}": whole-number moves, equally likely ("-1,1" a coin, '
                        '"-1,0,1", "1,2,3,4,5,6" a die)') from None
    if not 1 <= len(moves) <= 20:
        raise BeatError(f'{where} step="{raw}": 1 to 20 moves')
    steps = int(seconds * pace) + 1
    X = _walk(n, steps, moves, p, seed)
    mean = (2 * p - 1) if moves == (-1, 1) else float(np.mean(moves))
    var = 4 * p * (1 - p) if moves == (-1, 1) else float(np.var(moves))

    def sample(t: float) -> dict:
        k = t * pace
        i = min(int(k), steps - 1)
        f = min(k - i, 1.0)
        f = f * f * (3 - 2 * f)                       # each hop eases from one spot to the next
        pos = X[i] + (X[min(i + 1, steps)] - X[i]) * f
        here = X[i]
        return {"steps": i, "spread": float(here.std()), "far": int(np.abs(here - mean * i).max()),
                "mean": float(here.mean()), "pos": pos, "at": here, "drift": mean * (i + f), "drift_at": mean * i}

    return Timeline("walk", seconds, ("steps", "spread", "far", "mean"), sample,
                    info={"n": n, "pace": pace, "steps": steps, "mean": mean, "var": var,
                          "reach": float(np.percentile(np.abs(X[-1] - mean * steps), 99.5)) + 2})


MODELS = {"blocks": blocks_model, "spread": spread_model, "pendulum": pendulum_model,
          "circles": circles_model, "line": line_model, "heat": line_model,
          "walk": walk_model}


def timeline(rule: str, attrs: dict, where: str) -> Timeline:
    if rule not in MODELS:
        raise BeatError(f'{where} rule="{rule}": the models are {", ".join(MODELS)}')
    return MODELS[rule](attrs, where)
