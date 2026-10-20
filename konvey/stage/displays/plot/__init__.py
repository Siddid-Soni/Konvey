"""``<plot fn="sin x: sin(x); T_1: x" x="-2pi,2pi" y="-2,2">``: exact function graphs on real
axes; the plan's ``plot`` kind. The renderer evaluates every expression itself (see
``spec.py``), so a model never traces a curve by hand."""

from __future__ import annotations

import numpy as np

from ...match import squash
from ...tree import BeatError
from .. import Display
from . import spec as S


def _planned_fns(d: dict) -> list[tuple[str, str]]:
    fns = d.get("fns")
    if isinstance(fns, dict):
        return [(str(k), str(v)) for k, v in fns.items()]
    if isinstance(fns, list):
        return [("", str(v)) for v in fns]
    if isinstance(fns, str):
        return [("", fns)]
    return []


def _check_object(d: dict) -> list[str]:
    if "fns" not in d or "x" not in d:
        return []
    fns = _planned_fns(d)
    if not fns:
        return ['plot data["fns"] must be {"label": "expression"}, e.g. {"sin x": "sin(x)", "T_1": "x"}']
    problems = []
    try:
        x = S.pair(d["x"], "plot x")
        y = S.pair(d["y"], "plot y") if d.get("y") is not None else None
    except BeatError as e:
        return [str(e)]
    for label, expr in fns:
        if any(c in label for c in ":;"):
            problems.append(f'plot fns label {label!r}: no ":" or ";" in a label')
        try:
            steps = [S.fn_of(e) for _, e in S.stages(label, expr)]   # "a | b | c": played in turn
        except BeatError as e:
            problems.append(f"plot fns {label or expr!r}: {e}")
            continue
        for f in steps:
            ys = f(np.linspace(*x, 400))
            ys = ys[np.isfinite(ys)]
            if not len(ys) or (y and not ((ys >= y[0]) & (ys <= y[1])).any()):
                problems.append(f"plot fns {label or expr!r} = {expr!r} has no value inside the plot's "
                                f"x/y range, so nothing would show")
                break
    if d.get("slide") is not None:
        sl = d["slide"]
        try:
            a, b = (S.number(v) for v in sl) if isinstance(sl, (list, tuple)) and len(sl) == 2 else (None, None)
        except BeatError:
            a = b = None
        if a is None or not (x[0] <= a <= x[1] and x[0] <= b <= x[1]):
            problems.append(f'plot slide {sl!r}: use [from, to], both inside x (the points at x=from ride to x=to)')
    labels = {squash(l) for k, e in fns for l, _ in S.stages(k, e) if l} if not problems else {squash(k) for k, _ in fns}
    for name, at in (d.get("points") or {}).items() if isinstance(d.get("points"), dict) else []:
        ok = isinstance(at, (list, tuple)) and len(at) == 2
        if ok:
            try:
                S.number(at[0])
                if squash(at[1]) not in labels:
                    S.number(at[1])
            except BeatError:
                ok = False
        if not ok:
            problems.append(f'plot points {name!r}: use [x, y] (y a number or a fns label), got {at!r}')
    return problems


def _drawn(leaves) -> list[tuple[S.Curve, tuple, set]]:
    out = []
    for n in leaves:
        if n.tag != "plot":
            continue
        try:
            curves = S.curves_of(n.attrs.get("fn", ""))
            x = S.pair(n.attrs.get("x", ""), "x")
        except BeatError:
            continue
        names = {squash(p.rpartition(":")[0]) for p in n.attrs.get("points", "").split(";") if p.strip()}
        out += [(c, x, names) for c in curves]
    return out


def _check_drawn(where: str, obj, leaves) -> list[str]:
    fns = _planned_fns(obj.data)
    try:
        x = S.pair(obj.data.get("x"), "x")
        planned = [(label, expr, S.fn_of(S.stages(label, expr)[0][1])) for label, expr in fns]
    except BeatError:
        return []
    drawn = _drawn(leaves)
    for label, expr, f in planned:
        hits = [(c, dx, names) for c, dx, names in drawn if S.same_fn(c.f, f, x)]
        tag = f"{label}: {expr}" if label else expr
        if not hits:
            return [f'{where}: needs <plot fn="{tag}; …"> drawing the planned function {expr!r} '
                    f"(the renderer draws it exactly; never trace it by hand)"]
        if not any(np.allclose(dx, x, rtol=1e-6, atol=1e-6) for _, dx, _ in hits):
            return [f'{where}: <plot> with {expr!r} must use the planned x range '
                    f'x="{",".join(str(v) for v in obj.data["x"])}"']
    if obj.data.get("slide") is not None and not any(n.attrs.get("slide", "").strip() for n in leaves if n.tag == "plot"):
        a, b = obj.data["slide"] if isinstance(obj.data["slide"], (list, tuple)) and len(obj.data["slide"]) == 2 else ("from", "to")
        return [f'{where}: <plot slide="{a} -> {b}"> (the planned slide: the points at x={a} ride to x={b})']
    for k in NAMES:
        want = obj.data.get(k)
        if want and not any(squash(n.attrs.get(k, "")) == squash(want) for n in leaves if n.tag == "plot"):
            return [f'{where}: <plot {k}="{want}"> (the planned axis name)']
    points = obj.data.get("points") if isinstance(obj.data.get("points"), dict) else {}
    names = set().union(*(n for _, _, n in drawn)) if drawn else set()
    missing = [k for k in points if squash(k) not in names]
    if missing:
        return [f'{where}: <plot points="name: x,y; …"> must mark the planned points {missing}']
    return []


NAMES = ("xlabel", "ylabel")


def _plots(beat) -> list:
    return [n for n in beat.leaves().values() if n.tag == "plot" and n.id]


def carry_axis_names(beats: list, strict: bool = True) -> None:
    """A plot keeps the axis names it was first given: a later beat (or the next scene, after
    ``_adopt``) that leaves them out or renames them draws the first ones, so "price" never
    turns into "quantity" on the same curves."""
    names: dict[str, dict[str, str]] = {}
    for b in beats:
        for n in _plots(b):
            first = names.setdefault(n.id, {})
            for k in NAMES:
                if k in first:
                    n.attrs[k] = first[k]
                elif n.attrs.get(k, "").strip():
                    first[k] = n.attrs[k]


def _same_plot(a, b) -> bool:
    try:
        ca, cb = S.curves_of(a.attrs.get("fn", "")), S.curves_of(b.attrs.get("fn", ""))
        x = S.pair(b.attrs.get("x", ""), "x")
    except BeatError:
        return False
    return any(S.same_fn(p.f, q.f, x) for p in ca for q in cb)


def _adopt(prev, first) -> None:
    """One plot each side of a scene cut drawing a curve in common: the same plot (it morphs
    across the cut and keeps its axis names)."""
    olds, news = _plots(prev), _plots(first)
    if len(olds) == 1 and len(news) == 1 and olds[0].id != news[0].id and _same_plot(olds[0], news[0]):
        olds[0].attrs["id"] = news[0].id


DISPLAY = Display(tag="plot", order=55, steady=True, grow=True, enter="create", prepare=carry_axis_names,
                  adopt=_adopt, kind="plot", needs=("fns", "x"), check_object=_check_object, check_drawn=_check_drawn)
