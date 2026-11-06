"""``<plot>`` attributes -> what to draw, and the exact geometry of a function graph (pure
Python + numpy: the checker, the planner checks and the mobject share it).

A plot is fully described by numbers and parsed expressions, so the renderer (not the
model) traces every curve, finds where a curve meets a level, and places ticks:

    fn="sin x: sin(x); T_3: x - x^3/6"   curves, each "label: expression" (label optional)
    x="-2pi,2pi"  y="-2,2"                ranges; numbers or expressions in pi
    points="E: 4,6; A: 2,supply"          a dot at x, y (y may be a curve's label: on it)
    mark="x=pi/2: a; y=4: price"          dashed guide lines across the axes
    gap="supply,demand@y=4: shortage"     the distance between two curves at a level / an x
    shade="demand,supply: 2,4: lost"      the region between two curves (or a curve and a level)
    fn="P_0 | P_2 | P_4: 1 | 1 - x^2/2 | 1 - x^2/2 + x^4/24"
                                          steps: the curve enters as the first and, while the line
                                          is spoken, bends through the rest (terms added one by one)
    slide="0 -> 2"                        while the line is spoken (after any steps) every point,
                                          x mark and @x gap at x=0 rides to x=2
    drop="true"                           a dashed line from each point down to the x axis
    labels with {x}, {y} (a point), {gap} (an @x gap): the live value, as it slides
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction

import numpy as np

from ...expr import _FUNCS, parse_expr
from ...match import squash
from ...tree import BeatError

_IMPLICIT = re.compile(r"(?<=[\d)])\s*(?=x\b|pi\b|\(|(?:" + "|".join(_FUNCS) + r")\()")


def normalize(expr: str) -> str:
    """What models write -> what ``expr`` parses: ``π``, ``2pi``, ``2x``, ``3(x+1)``, ``ln``."""
    s = str(expr).strip().replace("π", "pi").replace("−", "-").replace("·", "*").replace("×", "*")
    s = re.sub(r"\bln\(", "log(", s)
    return _IMPLICIT.sub("*", s)


def fn_of(expr: str):
    """``"x - x^3/6"`` -> vectorised callable; BeatError names what is not allowed."""
    f = parse_expr(normalize(expr), ("x",))

    def g(xs):
        xs = np.asarray(xs, float)
        with np.errstate(all="ignore"):
            ys = np.asarray(f(xs), float)
        return np.broadcast_to(ys, xs.shape).astype(float)
    return g


def number(v) -> float:
    """``"-2pi"``, ``"pi/2"``, ``3`` -> float."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    try:
        val = float(parse_expr(normalize(str(v)), ())())
    except BeatError as e:
        raise BeatError(f"{v!r} is not a number (use 3, 0.5, pi/2 or -2pi)") from e
    if not np.isfinite(val):
        raise BeatError(f"{v!r} is not a finite number")
    return val


def pair(raw, what: str) -> tuple[float, float]:
    parts = raw if isinstance(raw, (list, tuple)) else str(raw).split(",")
    if len(parts) != 2:
        raise BeatError(f'{what}="{raw}": use two values "from,to", e.g. "-3,3" or "-2pi,2pi"')
    lo, hi = (number(p) for p in parts)
    if not hi > lo:
        raise BeatError(f'{what}="{raw}": the second value must be larger than the first')
    return lo, hi


# --- labels -----------------------------------------------------------------------------------
_TEX_FUNCS = {"sin", "cos", "tan", "exp", "log", "ln", "max", "min", "lim", "sinh", "cosh", "tanh"}


def label_form(label: str) -> tuple[str, str]:
    """How a curve or axis label is set: ``("text", words)`` or ``("tex", source)``.

    Models write ids and half-TeX: ``partial_sum`` is the words "partial sum", ``P_11`` is
    P with subscript 11 (not P₁1), ``S_N(x)`` and ``x_new`` keep whole subscripts, and words
    inside math are upright text. ``$…$`` or a backslash is taken as TeX as written."""
    s = str(label).strip()
    if s.startswith("$") or "\\" in s:
        return "tex", s.strip("$")
    s = re.sub(r"(?<=[A-Za-z]{2})_(?=[A-Za-z]{2})", " ", s)   # snake_case words -> words
    if not any(c in s for c in "_^"):
        return "text", s
    s = re.sub(r"([_^])\{?([A-Za-z0-9]+)\}?", r"\1{\2}", s)    # P_11 -> P_{11}
    s = re.sub(r"[A-Za-z]{2,}(?: [A-Za-z]{2,})*",
               lambda m: f"\\{m.group(0)}" if m.group(0) in _TEX_FUNCS else f"\\text{{{m.group(0)}}}", s)
    return "tex", s


def has_pi(raw) -> bool:
    return bool(re.search(r"pi|π", str(raw)))


# --- the parsed attributes ------------------------------------------------------------------
@dataclass
class Curve:
    label: str
    expr: str
    f: object
    # ``a | b | c``: the stages it bends through during the line, [(label, expr)]; label/expr/f
    # are the stage shown (the first, unless a live hold moved it on)
    steps: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class Spec:
    x: tuple[float, float]
    y: tuple[float, float]
    xpi: bool
    ypi: bool
    curves: list[Curve]
    points: list[tuple[str, float, object]] = field(default_factory=list)   # name, x, y or curve
    marks: list[tuple[str, float, str]] = field(default_factory=list)       # "x"|"y", value, label
    gaps: list[tuple[object, object, str, float, str]] = field(default_factory=list)
    shades: list[tuple[object, object, float, float, str]] = field(default_factory=list)
    slide: tuple[float, float] | None = None
    drop: bool = False

    def curve(self, ref: str) -> Curve | None:
        key = squash(ref)
        return next((c for c in self.curves if key and (squash(c.label) == key
                     or any(squash(lab) == key for lab, _ in c.steps))), None)

    def edge(self, ref: str, what: str):
        """A curve's label -> that Curve; a number -> a level y = number."""
        c = self.curve(ref)
        if c is not None:
            return c
        try:
            return number(ref)
        except BeatError:
            names = [c.label for c in self.curves if c.label]
            raise BeatError(f'{what}: "{ref}" is neither a curve label ({", ".join(names) or "none"}) '
                            f"nor a number") from None


def _items(raw: str) -> list[str]:
    return [p.strip() for p in str(raw or "").split(";") if p.strip()]


def stages(label: str, expr: str) -> list[tuple[str, str]]:
    """``"P_0 | P_2", "1 | 1 - x^2/2"`` -> [("P_0", "1"), ("P_2", "1 - x^2/2")]; one label for
    all stages is fine (``"P: 1 | 1 + x"``)."""
    expr, label = expr.replace("\\|", "|"), label.replace("\\|", "|")   # the docs' table spelling of "|"
    exprs = [e.strip() for e in expr.split("|")]
    labels = [l.strip() for l in label.split("|")]
    if len(labels) == 1:
        labels = labels * len(exprs)
    if len(labels) != len(exprs) or not all(exprs):
        raise BeatError(f'"{label}: {expr}": give one expression per step between "|" (and one label, '
                        "or one per step)")
    return list(zip(labels, exprs))


def curves_of(raw: str) -> list[Curve]:
    out = []
    for part in _items(raw):
        label, sep, expr = part.rpartition(":")
        try:
            steps = stages(label, expr)
            for _, e in steps:
                fn_of(e)
            c = Curve(steps[0][0], steps[0][1], fn_of(steps[0][1]))
            c.steps = steps if len(steps) > 1 else []
            out.append(c)
        except BeatError as e:
            raise BeatError(f'fn "{part}": {e} (write fn="label: expression; label: expression")') from e
    return out


def _slide(raw: str) -> tuple[float, float] | None:
    raw = str(raw or "").strip()
    if not raw:
        return None
    a, arrow, b = raw.replace("→", "->").partition("->")
    a = a.strip().removeprefix("x=").removeprefix("x =").strip()
    if not arrow:
        raise BeatError(f'slide="{raw}": use "from -> to", e.g. slide="0 -> 2" (points at x=0 ride to x=2)')
    return number(a), number(b)


def live_value(v: float) -> str:
    """A readout's number: about four significant figures, never in e-notation."""
    if not np.isfinite(v):
        return "∞"
    if abs(v) < 1e-12:
        return "0"
    mag = int(np.floor(np.log10(abs(v))))
    d = int(min(9, max(0, (4 if mag >= -3 else 2) - 1 - mag)))   # 4 figures, 2 when tiny
    out = f"{v:.{d}f}"
    return _minus(out.rstrip("0").rstrip(".") if "." in out else out)


def fill(text: str, **vals) -> str:
    """``"error {gap}"`` with gap=0.0026 -> ``"error 0.0026"``; unknown names stay as written."""
    return re.sub(r"\{(\w+)\}", lambda m: live_value(vals[m.group(1)]) if m.group(1) in vals else m.group(0), text)


def parse(attrs: dict) -> Spec:
    curves = curves_of(attrs.get("fn", ""))
    if not curves:
        raise BeatError('<plot> needs fn="label: expression", e.g. fn="sin x: sin(x); T_1: x"')
    x = pair(attrs.get("x", ""), "x")
    y = pair(attrs["y"], "y") if attrs.get("y", "").strip() else auto_y(curves, x)
    spec = Spec(x, y, has_pi(attrs.get("x")), has_pi(attrs.get("y")), curves)
    spec.slide = _slide(attrs.get("slide"))
    spec.drop = str(attrs.get("drop", "")).strip().lower() in ("true", "1", "yes")
    for part in _items(attrs.get("points", "")):
        name, _, at = part.rpartition(":")
        xs, sep, ys = at.partition(",")
        if not sep:
            raise BeatError(f'points "{part}": use "name: x,y" (y may be a curve label: "A: 2,supply")')
        yref = spec.curve(ys) or _on_curve(spec, number(xs), number(ys))
        spec.points.append((name.strip(), number(xs), yref))
    for part in _items(attrs.get("mark", "")):
        where, _, label = part.partition(":")
        axis, eq, v = where.partition("=")
        if not eq or axis.strip() not in ("x", "y"):
            raise BeatError(f'mark "{part}": use "x=VALUE: label" (a vertical line) or "y=VALUE: label"')
        spec.marks.append((axis.strip(), number(v), label.strip()))
    for part in _items(attrs.get("gap", "")):
        what, _, label = part.partition(":")
        refs, at, where = what.partition("@")
        axis, eq, v = where.partition("=")
        ab = [r.strip() for r in refs.split(",")]
        if not at or not eq or axis.strip() not in ("x", "y") or len(ab) != 2:
            raise BeatError(f'gap "{part}": use "curveA,curveB@y=VALUE: label" (horizontal distance '
                            f'at that level) or "curveA,curveB@x=VALUE: label"')
        a, b = (spec.edge(r, f'gap "{part}"') for r in ab)
        spec.gaps.append((a, b, axis.strip(), number(v), label.strip()))
    for part in _items(attrs.get("shade", "")):
        refs, _, rest = part.partition(":")
        span, _, label = rest.partition(":")
        ab = [r.strip() for r in refs.split(",")]
        if len(ab) != 2:
            raise BeatError(f'shade "{part}": use "curveA,curveB: from,to: label" (B may be a level, '
                            f'e.g. "demand,4: 0,2")')
        a, b = (spec.edge(r, f'shade "{part}"') for r in ab)
        lo, hi = pair(span, "shade") if span.strip() else spec.x
        spec.shades.append((a, b, lo, hi, label.strip()))
    return spec


def stage_attrs(attrs: dict, step: int, slide: tuple[float, float] | None) -> dict:
    """The plot's attributes at one stage: every stepped curve at its ``step``-th expression
    (the last when it has fewer), and with ``slide`` what sat at x=from moved to x=to."""
    out = {k: v for k, v in attrs.items() if k != "slide"}
    parts, alias = [], {}
    for part in _items(attrs.get("fn", "")):
        label, _, expr = part.rpartition(":")
        st = stages(label, expr)
        lab, e = st[min(step, len(st) - 1)]
        parts.append(f"{lab}: {e}" if lab else e)
        alias.update({squash(l): lab for l, _ in st if l})
    out["fn"] = "; ".join(parts)

    def name(ref: str) -> str:   # a curve named by any of its step labels: its label at this stage
        return alias.get(squash(ref), ref.strip())

    if alias:
        pts = []
        for part in _items(attrs.get("points", "")):
            nm, _, xy = part.rpartition(":")
            xs, _, ys = xy.partition(",")
            pts.append(f"{nm}: {xs.strip()},{name(ys)}")
        out["points"] = "; ".join(pts)
        for key, sep in (("gap", "@"), ("shade", ":")):
            items = []
            for part in _items(attrs.get(key, "")):
                refs, s_, rest = part.partition(sep)
                items.append(",".join(name(r) for r in refs.split(",")) + s_ + rest)
            out[key] = "; ".join(items)
    attrs = out
    if slide is not None:
        a, b = slide
        at = lambda v: abs(number(v) - a) <= 1e-9 * max(1.0, abs(a))  # noqa: E731
        pts = []
        for part in _items(attrs.get("points", "")):
            nm, _, xy = part.rpartition(":")
            xs, _, ys = xy.partition(",")
            pts.append(f"{nm}: {b!r},{ys.strip()}" if at(xs) else part)
        out["points"] = "; ".join(pts)
        marks = []
        for part in _items(attrs.get("mark", "")):
            where, sep, label = part.partition(":")
            axis, _, v = where.partition("=")
            marks.append(f"x={b!r}{sep}{label}" if axis.strip() == "x" and at(v) else part)
        out["mark"] = "; ".join(marks)
        gaps = []
        for part in _items(attrs.get("gap", "")):
            what, sep, label = part.partition(":")
            refs, _, where = what.partition("@")
            axis, _, v = where.partition("=")
            gaps.append(f"{refs}@x={b!r}{sep}{label}" if axis.strip() == "x" and at(v) else part)
        out["gap"] = "; ".join(gaps)
    return {k: v for k, v in out.items() if v != ""}


def _on_curve(spec: Spec, x: float, y: float):
    """A point written as numbers that sits on a curve ("0.1,0.5" on PPV) is that curve's point,
    so it slides along the curve between beats instead of cutting across."""
    tol = 0.01 * (spec.y[1] - spec.y[0])
    for c in spec.curves:
        with np.errstate(all="ignore"):
            v = float(value(c, [x])[0])
        if np.isfinite(v) and abs(v - y) <= tol:
            return c
    return y


def auto_y(curves: list[Curve], x: tuple[float, float]) -> tuple[float, float]:
    xs = np.linspace(*x, 400)
    ys = np.concatenate([fn_of(e)(xs) for c in curves for _, e in (c.steps or [(c.label, c.expr)])])
    ys = ys[np.isfinite(ys)]
    if not len(ys):
        raise BeatError("no curve has a value in the x range; check fn= and x=")
    lo, hi = float(np.percentile(ys, 2)), float(np.percentile(ys, 98))
    lo, hi = min(lo, 0.0), max(hi, 0.0)
    pad = 0.1 * ((hi - lo) or 1.0)
    return lo - pad, hi + pad


def value(ref, xs) -> np.ndarray:
    """A curve or a level at xs."""
    xs = np.asarray(xs, float)
    return ref.f(xs) if isinstance(ref, Curve) else np.full(xs.shape, float(ref))


# --- ticks ----------------------------------------------------------------------------------
def _minus(s: str) -> str:
    return s.replace("-", "−")


def ticks(lo: float, hi: float, length: float, pi: bool) -> list[tuple[float, str]]:
    """Tick values and their labels: one about every 1.6 units of axis (3b1b numbers few ticks:
    whole numbers, not a ruler), at 1/2/5 steps, or at pi/4, pi/2, pi, 2pi ... when the range
    was given in pi."""
    span = hi - lo
    most = max(3.0, min(9.0, length / 1.6))
    if pi:   # π, 2π read as landmarks; at every π/2 the axis turns into a ruler (3b1b numbers π only)
        most = min(most, 6.0)
    unit = np.pi if pi else 1.0
    if pi:
        steps = [np.pi / 4, np.pi / 2, np.pi, 2 * np.pi, 4 * np.pi, 8 * np.pi]
    else:
        mag = 10.0 ** np.floor(np.log10(span / most))
        steps = [m * mag for m in (1, 2, 5, 10, 20)]
    step = next((s for s in steps if span / s <= most), steps[-1])
    if not pi and step < 1 and span >= 3:   # whole numbers when there are enough of them
        step = 1.0
    k0, k1 = int(np.ceil(lo / step - 1e-9)), int(np.floor(hi / step + 1e-9))
    out = []
    for k in range(k0, k1 + 1):
        v = k * step
        if pi:
            q = Fraction(v / unit).limit_denominator(8)
            n, d = q.numerator, q.denominator
            body = "0" if n == 0 else ("" if abs(n) == 1 else str(abs(n))) + "π" + (f"/{d}" if d > 1 else "")
            text = ("−" if n < 0 else "") + body
        else:
            dec = max(0, -int(np.floor(np.log10(step) + 1e-9)))
            text = _minus(f"{v:.{dec}f}") if abs(v) > 1e-12 else "0"
        out.append((0.0 if abs(v) < 1e-12 else float(v), text))
    return out


# --- tracing ---------------------------------------------------------------------------------
MAX_POINTS = 6000


def trace(f, x: tuple[float, float], y: tuple[float, float], w: float, h: float,
          upto: float | None = None) -> list[np.ndarray]:
    """The visible pieces of y = f(x) as (n, 2) arrays in plot coordinates: sampled finely
    (more points where it is steep), cut at a real jump (a square wave's step, tan's pole: no
    vertical smear), and clipped exactly at the top and bottom of the axis box. ``upto``
    traces only x0..upto (a curve being drawn in)."""
    x0, x1 = x
    y0, y1 = y
    if upto is not None:
        x1 = min(x1, upto)
        if x1 <= x0:
            return []
    sy = h / (y1 - y0)
    xs = np.linspace(x0, x1, int(max(240, 90 * w * (x1 - x0) / (x[1] - x0))))
    ys = f(xs)

    def screen(v):   # y in axis units, clamped just outside the box (far outside counts as "out")
        return np.clip((v - y0) * sy, -0.1 * h, 1.1 * h)

    tol = 0.02
    for _ in range(18):
        c = screen(ys)
        d = np.abs(np.diff(c))
        nan = np.isnan(c)
        bad = (d > tol) | (nan[:-1] ^ nan[1:])
        bad &= np.diff(xs) > (x1 - x0) * 1e-12
        if not bad.any() or len(xs) > MAX_POINTS:
            break
        at = np.nonzero(bad)[0]
        xm = (xs[at] + xs[at + 1]) / 2
        xs, ys = np.insert(xs, at + 1, xm), np.insert(ys, at + 1, f(xm))
    c = screen(ys)
    # a step still this tall between neighbours that close is a jump, not a steep curve
    jump = np.abs(np.diff(c)) > 0.12
    pieces, start = [], 0
    for i in [*np.nonzero(jump)[0], len(xs) - 1]:
        pieces.append((xs[start:i + 1], ys[start:i + 1]))
        start = i + 1
    out = []
    for px, py in pieces:
        ok = np.isfinite(py)
        idx = np.nonzero(ok)[0]
        if not len(idx):
            continue
        # runs of finite values
        cuts = np.nonzero(np.diff(idx) > 1)[0]
        for run in np.split(idx, cuts + 1):
            out += _clip(px[run], py[run], y0, y1)
    return [r for r in out if len(r) >= 2]


def _clip(xs: np.ndarray, ys: np.ndarray, y0: float, y1: float) -> list[np.ndarray]:
    """Cut a polyline where it leaves y0..y1 (linear between samples, which are dense there)."""
    out, cur = [], []
    inside = (ys >= y0) & (ys <= y1)
    for i in range(len(xs)):
        if i > 0:
            xa, ya, xb, yb = xs[i - 1], ys[i - 1], xs[i], ys[i]
            hits = [(xa + (yl - ya) / (yb - ya) * (xb - xa), yl)
                    for yl in sorted((y0, y1), key=lambda yl: abs(yl - ya)) if (ya - yl) * (yb - yl) < 0]
            if inside[i - 1] and not inside[i]:          # leaves the box
                out.append(np.array(cur + hits[:1]))
                cur = []
            elif inside[i] and not inside[i - 1]:        # comes back in
                cur = hits[-1:]
            elif not inside[i] and len(hits) == 2:       # jumps right across it
                out.append(np.array(hits))
        if inside[i]:
            cur.append((xs[i], ys[i]))
    out.append(np.array(cur))
    return [r for r in out if len(r) >= 2]


def roots(ref, level: float, x: tuple[float, float]) -> list[float]:
    """Where a curve (or level) equals ``level`` inside x, by sign change, then halving the bracket."""
    xs = np.linspace(*x, 2001)
    d = value(ref, xs) - level
    out = []
    for i in np.nonzero((np.sign(d[:-1]) * np.sign(d[1:]) <= 0) & np.isfinite(d[:-1]) & np.isfinite(d[1:]))[0]:
        a, b = xs[i], xs[i + 1]
        fa = d[i]
        for _ in range(60):
            m = (a + b) / 2
            fm = value(ref, [m])[0] - level
            if np.sign(fm) == np.sign(fa) and fm != 0:
                a, fa = m, fm
            else:
                b = m
        r = (a + b) / 2
        if not out or abs(r - out[-1]) > 1e-9 * (x[1] - x[0]):
            out.append(r)
    return out


def same_fn(f, g, x: tuple[float, float]) -> bool:
    """Two parsed expressions draw the same curve over x (``x-x^3/6`` == ``x - x**3/6``)."""
    xs = np.linspace(*x, 41)
    a, b = f(xs), g(xs)
    na, nb = ~np.isfinite(a), ~np.isfinite(b)
    if (na != nb).any():
        return False
    ok = ~na
    return bool(np.all(np.abs(a[ok] - b[ok]) <= 1e-6 * np.maximum(1.0, np.abs(a[ok]))))
