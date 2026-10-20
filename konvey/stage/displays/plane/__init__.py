"""``<plane vectors="v:1,1" matrix="2,1;1,2">``: a coordinate plane with arrows, points, lines
through the origin and a point on the unit circle, optionally seen through a 2x2 matrix; the
plan's ``plane`` kind. Pure Python: parsing, the scene-wide range, the plan checks."""

from __future__ import annotations

import json
import math
import re

from ...match import as_num, squash
from ...tree import BeatError
from .. import Display

ASPECT = 1.3        # an automatic range fills a box about this many times wider than tall
MAX_NAME = 12


# --- parsing (shared by the mobject and the checks) -----------------------------------------
def _pair(raw: str, what: str) -> tuple[float, float]:
    try:
        x, y = (float(v) for v in raw.split(","))
    except ValueError as e:
        raise BeatError(f'{what} "{raw}": use two numbers like "1,-2"') from e
    if not all(math.isfinite(v) for v in (x, y)):
        raise BeatError(f'{what} "{raw}": use finite numbers')
    return x, y


def named_pairs(raw: str, what: str, need_name: bool = True) -> list[tuple[str, tuple[float, float]]]:
    """``"v:1,1; w:1,-1"`` -> [("v", (1, 1)), ("w", (1, -1))]; names unique. Unnamed entries
    (``"1,1; 1,-1"``, for lines) get "" when ``need_name`` is False."""
    out, seen = [], set()
    for part in (p.strip() for p in (raw or "").split(";") if p.strip()):
        name, sep, xy = part.rpartition(":")
        name = name.strip()
        if not sep or not name:
            if need_name:
                raise BeatError(f'{what} "{part}": use name:x,y like "v:1,2"')
            name, xy = "", part
        if name and squash(name) in seen:
            raise BeatError(f'{what}: the name "{name}" is used twice')
        seen.add(squash(name))
        out.append((name, _pair(xy, what)))
    return out


def parse_matrix(raw: str) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """``"2,1;1,2"`` (row by row) or ``"[[2,1],[1,2]]"`` -> ((2, 1), (1, 2)); empty -> None."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        rows = json.loads(raw) if raw.startswith("[") else [r.split(",") for r in raw.split(";")]
        m = tuple(tuple(float(v) for v in r) for r in rows)
    except (ValueError, TypeError) as e:
        raise BeatError(f'matrix="{raw}": use two rows of two numbers, like "2,1;1,2"') from e
    if len(m) != 2 or any(len(r) != 2 for r in m) or not all(math.isfinite(v) for r in m for v in r):
        raise BeatError(f'matrix="{raw}": use two rows of two numbers, like "2,1;1,2"')
    return m


def parse_angle(raw: str) -> tuple[str, float] | None:
    """``"z:45"`` or ``"45"`` (degrees, counter-clockwise from +x) -> (name, 45.0); empty -> None."""
    raw = (raw or "").strip()
    if not raw:
        return None
    name, _, deg = raw.rpartition(":")
    try:
        d = float(deg.replace("°", ""))
    except ValueError as e:
        raise BeatError(f'angle="{raw}": use name:degrees like "z:45" (degrees, counter-clockwise from +x)') from e
    return name.strip(), d


def apply(m, p: tuple[float, float]) -> tuple[float, float]:
    if m is None:
        return p
    return m[0][0] * p[0] + m[0][1] * p[1], m[1][0] * p[0] + m[1][1] * p[1]


def _on(attrs: dict, key: str) -> bool:
    return attrs.get(key, "").strip().lower() in ("true", "1", "yes", key)


def content_points(attrs: dict) -> list[tuple[float, float]]:
    """Every point the beat draws (vectors before and after its matrix, points, the circle)."""
    m = parse_matrix(attrs.get("matrix", ""))
    pts = [(0.0, 0.0)]
    for key in ("vectors", "points"):
        for _, p in named_pairs(attrs.get(key, ""), f"{key}="):
            pts += [p, apply(m, p)]
    ang = parse_angle(attrs.get("angle", ""))
    if _on(attrs, "circle") or ang is not None:
        pts += [apply(m, (math.cos(a), math.sin(a))) for a in (k * math.pi / 16 for k in range(32))]
    return pts


def nice_range(pts: list[tuple[float, float]], aspect: float = ASPECT) -> tuple[float, float, float, float, float]:
    """A symmetric range around the origin that holds every point with a margin, a grid step
    (0.5 / 1 / 2 / 5 ...), and a width-to-height ratio near ``aspect`` -> (x0, x1, y0, y1, step)."""
    rx = max(abs(p[0]) for p in pts) * 1.15 + 0.2
    ry = max(abs(p[1]) for p in pts) * 1.15 + 0.2
    ry = max(ry, rx / aspect, 1.0)
    step = grid_step(ry)
    ry = math.ceil(ry / step - 1e-9) * step
    rx = max(math.ceil(rx / step - 1e-9), math.ceil(ry * aspect / step - 1e-9)) * step
    return -rx, rx, -ry, ry, step


def grid_step(half_height: float) -> float:
    """Grid lines (and numbered ticks) every 1, 2, 5, 10 ...: at most five above the axis; every
    0.5 when the plane is about the unit circle (half a height of 1.6 or less)."""
    if half_height <= 1.6:
        return 0.5
    return next((s for s in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000) if half_height <= 5 * s + 1e-9),
                10 ** math.ceil(math.log10(half_height / 5)))


def range_of(nodes: list) -> tuple[float, float, float, float, float]:
    """The range of one plane over the given beats' nodes: the first one's x=/y= when it gives
    both, else one that holds what every beat draws."""
    first = nodes[0].attrs
    if first.get("x") and first.get("y"):
        x0, x1 = _pair(first["x"], "x=")
        y0, y1 = _pair(first["y"], "y=")
        if x1 <= x0 or y1 <= y0:
            raise BeatError(f'<plane id={nodes[0].id}> x="{first["x"]}" y="{first["y"]}": use "low,high"')
        return x0, x1, y0, y1, grid_step(max(abs(y0), abs(y1), (x1 - x0) / 2 / ASPECT))
    pts = []
    for n in nodes:
        try:
            pts += content_points(n.attrs)
        except BeatError:
            pass                          # the beat itself reports it when it is built
    return nice_range(pts)


def _carry_range(beats: list, strict: bool = True) -> None:
    """One plane keeps one range and one colour per name for the whole scene, so a matrix applied
    in a later beat moves the grid instead of zooming it: the range holds what every beat draws
    (or the first beat's x=/y=), written into each beat as ``_range``; colours go to ``_colors``
    in order of first appearance."""
    by_id: dict[str, list] = {}
    for b in beats:
        for n in b.leaves().values():
            if n.tag == "plane" and n.id:
                by_id.setdefault(n.id, []).append(n)
    for nodes in by_id.values():
        rng = range_of(nodes)
        names: list[str] = []
        for n in nodes:
            for key in ("vectors", "points"):
                try:
                    names += [k for k, _ in named_pairs(n.attrs.get(key, ""), key) if k not in names]
                except BeatError:
                    pass
        for n in nodes:
            n.attrs["_range"] = ",".join(f"{v:g}" for v in rng)
            n.attrs["_colors"] = ",".join(names)


# --- plan checks ----------------------------------------------------------------------------
def _num_pair(v) -> bool:
    return isinstance(v, (list, tuple)) and len(v) == 2 and all(as_num(x) is not None and math.isfinite(float(x))
                                                                for x in v)


_ID_LIKE = re.compile(r"^[A-Za-z]+\d+[A-Za-z]+\w*$|^[A-Za-z]+\d{2,}$|^[A-Za-z]{3,}$")


def _id_like(name: str) -> bool:
    """``p11``, ``p1m1``, ``sum``: an identifier, not a label (``v``, ``e1``, ``Av``, ``e_1`` are fine)."""
    return bool(_ID_LIKE.match(name.strip()))


def _check_object(d: dict) -> list[str]:
    keys = ("vectors", "points", "matrix", "lines", "angle", "circle")
    if not any(k in d for k in keys):
        return ["kind 'plane' needs at least one of data['vectors'] {name: [x, y]}, 'points', 'lines', "
                "'matrix' [[a, b], [c, d]] or 'angle' (degrees)"]
    problems, seen = [], set()
    for key in ("vectors", "points"):
        if key not in d:
            continue
        v = d[key]
        if not isinstance(v, dict) or not v:
            problems.append(f"plane data['{key}'] must be {{name: [x, y]}}, e.g. {{'v': [1, 0], 'w': [1, -1]}}")
            continue
        for name, xy in v.items():
            if not str(name).strip() or len(str(name)) > MAX_NAME or any(c in str(name) for c in ":;,"):
                problems.append(f"plane {key} name {name!r}: a short label without : ; or , (like 'v' or 'Av')")
            elif _id_like(str(name)):
                problems.append(f"plane {key} name {name!r} is drawn on screen as the arrow's label: name it like "
                                "maths, v, w, e_1, Av, u+v, \\lambda v (not a program id like p11 or sum)")
            elif squash(name) in seen:
                problems.append(f"plane name {name!r} is used twice (vectors and points share names)")
            seen.add(squash(name))
            if not _num_pair(xy):
                problems.append(f"plane {key}[{name!r}] = {xy!r}: must be two numbers [x, y]")
    if "matrix" in d:
        m = d["matrix"]
        if not (isinstance(m, list) and len(m) == 2 and all(_num_pair(r) for r in m)):
            problems.append(f"plane data['matrix'] = {m!r}: must be two rows of two numbers, [[2, 1], [1, 2]]")
    if "lines" in d:
        ls = d["lines"]
        if not isinstance(ls, list) or not all(_num_pair(x) and any(float(c) for c in x) for x in ls):
            problems.append(f"plane data['lines'] = {ls!r}: a list of non-zero directions [[1, 1], [1, -1]]")
    if "angle" in d and (as_num(d["angle"]) is None or not math.isfinite(float(d["angle"]))):
        problems.append(f"plane data['angle'] = {d['angle']!r}: one number, degrees counter-clockwise from +x")
    return problems


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-6 * max(1.0, abs(a))


def _fmt(v) -> str:
    v = float(v)
    return f"{int(v)}" if v.is_integer() else f"{v:g}"


def _check_drawn(where: str, obj, leaves) -> list[str]:
    """The beat's ``<plane>`` draws the planned vectors, points, matrix and angle verbatim."""
    d = obj.data
    planes = [n for n in leaves if n.tag == "plane"]
    want = []
    for key in ("vectors", "points"):
        if isinstance(d.get(key), dict):
            want.append(f'{key}="' + ";".join(f"{k}:{_fmt(x)},{_fmt(y)}" for k, (x, y) in d[key].items()) + '"')
    m = d.get("matrix")
    if isinstance(m, list):
        want.append('matrix="' + ";".join(",".join(_fmt(v) for v in r) for r in m) + '"')
    if as_num(d.get("angle")) is not None:
        want.append(f'angle="…:{_fmt(d["angle"])}"')

    def ok(n) -> bool:
        try:
            for key in ("vectors", "points"):
                if isinstance(d.get(key), dict):
                    got = {squash(k): p for k, p in named_pairs(n.attrs.get(key, ""), key)}
                    for name, xy in d[key].items():
                        p = got.get(squash(name))
                        if p is None or not (_close(float(xy[0]), p[0]) and _close(float(xy[1]), p[1])):
                            return False
            if isinstance(m, list):
                got_m = parse_matrix(n.attrs.get("matrix", ""))
                if got_m is None or not all(_close(float(m[i][j]), got_m[i][j]) for i in (0, 1) for j in (0, 1)):
                    return False
            if as_num(d.get("angle")) is not None:
                a = parse_angle(n.attrs.get("angle", ""))
                if a is None or not _close(float(d["angle"]), a[1]):
                    return False
        except BeatError:
            return False
        return True

    if want and not any(ok(n) for n in planes):
        return [f'{where}: needs <plane id="{obj.id}" {" ".join(want)}> (the planned values; the vectors are '
                "written before the matrix acts, the renderer draws where the matrix sends them)"]
    return []


DISPLAY = Display(tag="plane", order=85, steady=True, shrink=0.75, grow=True, prepare=_carry_range,
                  kind="plane", check_object=_check_object, check_drawn=_check_drawn)
