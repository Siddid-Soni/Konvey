"""Marks drawn on a picture in the picture's own coordinates (``on="id"``), after layout.

3Blue1Brown builds most of a scene by adding to one picture at its own coordinates (``c2p``,
``n2p``): dots at computed points, a path through them, an arc between two of them, an angle at
a corner, a shaded region. The mark tags (``<dots>``, ``<path>``, ``<arc>``, ``<angle>``) do the
same here: a picture that has coordinates gives them through ``point(x, y)`` (a plane, a plot,
a grid's ``row,col``), and a mark names its points either as numbers (``"0.5,-1"``) or as
points of a ``<dots>`` in the same beat (``"hits.3"``, ``"hits.2-5"``, ``"hits"``). Marks are
drawn after the picture is fitted, so their lines and words keep their size however large the
picture grows. They take no room in the layout (``konvey.stage.attach``).
"""

from __future__ import annotations

import math
import re

import numpy as np

from .tree import BeatError, Node

_PAIR = re.compile(r"^\s*-?[\d.]+(e-?\d+)?\s*,\s*-?[\d.]+(e-?\d+)?\s*$", re.I)
_ONE = re.compile(r"^\s*-?[\d.]+(e-?\d+)?\s*$", re.I)
_REF = re.compile(r"^\s*([A-Za-z_][\w-]*)(?:\.(\d+)(?:\s*-\s*(\d+))?)?\s*$")
HOSTS = "a <plane>, a <plot>, a <numberline>, a <draw> (its own x/y), a <grid> (row,col) or an <array> (cell)"


def host(node: Node, resolve, where: str):
    """The picture a mark sits on (``on="id"``); it must give its coordinates."""
    ref = node.attrs.get("on", "").strip()
    if not ref:
        raise BeatError(f'{where} needs on="id": the picture it is drawn on ({HOSTS})')
    pic = resolve(ref)
    if not callable(getattr(pic, "point", None)):
        raise BeatError(f'{where} on="{ref}": a <{getattr(pic, "tag", "?")}> has no coordinates; '
                        f"marks go on {HOSTS}")
    return pic


def points(raw: str, resolve, where: str, what: str) -> list[tuple[float, float]]:
    """``"0,0; 1,0.5"``, ``"hits"``, ``"hits.3"``, ``"hits.2-5"`` (1-based, from a ``<dots>``),
    or a mix separated by ``;`` -> data coordinates."""
    out: list[tuple[float, float]] = []
    for part in (p.strip() for p in (raw or "").split(";") if p.strip()):
        if _PAIR.match(part):
            x, y = (float(v) for v in part.split(","))
            out.append((x, y))
            continue
        if _ONE.match(part):   # one number: a position along a line of cells (an array's cell 3)
            out.append((float(part), 0.0))
            continue
        m = _REF.match(part)
        if not m:
            raise BeatError(f'{where} {what}="{raw}": "{part}" is neither x,y nor a <dots> point like hits.3')
        dots = resolve(m.group(1))
        xy = getattr(dots, "xy", None)
        if xy is None:
            raise BeatError(f'{where} {what}: "{m.group(1)}" is not a <dots> of this beat (points are named by '
                            "a <dots id> and a number: hits.3)")
        a = int(m.group(2)) if m.group(2) else 1
        b = int(m.group(3)) if m.group(3) else (a if m.group(2) else len(xy))
        if not (1 <= a <= len(xy) and 1 <= b <= len(xy)):
            raise BeatError(f'{where} {what}: "{part}": #{m.group(1)} has points 1 to {len(xy)}')
        step = 1 if b >= a else -1
        out += [xy[k - 1] for k in range(a, b + step, step)]
    if not out:
        raise BeatError(f'{where} needs {what}= (points as "x,y; x,y" or a <dots> id like hits.2-5)')
    return out


def one(raw: str, resolve, where: str, what: str) -> tuple[float, float]:
    pts = points(raw, resolve, where, what)
    if len(pts) != 1:
        raise BeatError(f'{where} {what}="{raw}" names {len(pts)} points; give one')
    return pts[0]


def screen(pic, pts) -> list[np.ndarray]:
    return [np.asarray(pic.point(x, y), float) for x, y in pts]


def style(node: Node, default: str = "ink") -> tuple[str, float]:
    """(colour, opacity): ``dim="true"`` keeps a mark faint while the line is about something else."""
    from .theme import current

    th = current()
    try:
        color = th.color(node.attrs.get("color"), default) if node.attrs.get("color") else th.color(default)
    except ValueError as e:
        raise BeatError(f"<{node.tag} id={node.id}> {e}") from e
    dim = node.attrs.get("dim", "").strip().lower() in ("true", "1", "yes", "dim")
    return color, (0.3 if dim else 1.0)


def size(node: Node, default: float = 28.0) -> float:
    try:
        return float(node.attrs.get("size", default))
    except ValueError as e:
        raise BeatError(f'<{node.tag} id={node.id}> size="{node.attrs["size"]}": a number') from e


def label(text: str, sz: float, color: str):
    """Short maths (θ, 2θ, x_1, a single letter or number) is typeset; words are plain text."""
    from .displays.base import _label
    from .displays.plane.mobject import label as tex_label

    t = text.strip()
    if "\\" in t or (len(t) <= 6 and " " not in t and not (len(t) > 1 and t.isalpha() and t.isascii())):
        try:
            return tex_label(t, sz * 1.1, color)
        except BeatError:
            pass
    return _label(t, sz, color)


BAR_OPEN = 0.55   # letterbox bar height once open (units); the scene's bars


def half_height(edge: float = 0.5) -> float:
    """How far from the centre words may reach up or down: inside the frame and, with a
    letterbox theme, clear of its bars. 0.5 is manim's edge buffer: a note 0.2 from the top
    edge read as cut off."""
    from manimlib import FRAME_HEIGHT

    from .theme import current

    return FRAME_HEIGHT / 2 - edge - (BAR_OPEN if current().letterbox else 0.0)


def place_label(lab, anchor: np.ndarray, out: np.ndarray, boxes, gap: float = 0.12):
    """Put ``lab`` beside ``anchor``, towards ``out`` first, then turning either way, on the first
    side that covers nothing in ``boxes``; with no clear side, the outward one."""
    from .attach import clear

    u = out / (np.linalg.norm(out) or 1.0)
    cands = []
    for turn in (0, 30, -30, 60, -60, 90, -90, 135, -135, 180):
        a = math.radians(turn)
        cands.append(np.array([u[0] * math.cos(a) - u[1] * math.sin(a),
                               u[0] * math.sin(a) + u[1] * math.cos(a), 0.0]))
    from manimlib import FRAME_HEIGHT, FRAME_WIDTH

    from .attach import _box, _hits

    w, h = lab.get_width(), lab.get_height()
    best = None
    for k, (d, extra) in enumerate((d, e) for e in (0.0, 0.35) for d in cands):   # near ring, then a farther one
        r = gap + extra + 0.5 * (abs(d[0]) * w + abs(d[1]) * h)
        lab.move_to(anchor + d * r)
        x0, y0, x1, y1 = _box(lab)
        out = max(0.0, x1 - FRAME_WIDTH / 2 + 0.5, -FRAME_WIDTH / 2 + 0.5 - x0,
                  y1 - half_height(), -half_height() - y0)
        if out == 0 and clear(lab, boxes):
            return lab
        hits = sum(_hits(_box(lab), o, -0.04) for o in boxes) + 0.01 * k + 20 * out
        if best is None or hits < best[0]:
            best = (hits, anchor + d * r)
    lab.move_to(best[1])
    return lab


def halo(mob, opacity: float = 1.0):
    """A background-coloured outline behind text, so a label stays readable across lines."""
    from .theme import current

    return mob.set_stroke(current().bg, 5, opacity, behind=True)


def clip_polygon(pts: list[np.ndarray], box) -> list[np.ndarray]:
    """Sutherland–Hodgman: the part of a closed polygon inside ``box`` (x0, y0, x1, y1), so a
    region given out to far coordinates ("everything right of this line") ends at the picture's
    edge."""
    x0, y0, x1, y1 = box
    edges = ((0, x0, 1), (0, x1, -1), (1, y0, 1), (1, y1, -1))   # (axis, value, keep side)
    out = list(pts)
    for k, v, side in edges:
        if not out:
            break
        src, out = out, []
        for a, b in zip(src, [*src[1:], src[0]]):
            ina, inb = (a[k] - v) * side >= -1e-9, (b[k] - v) * side >= -1e-9
            if ina:
                out.append(a)
            if ina != inb:
                t = (v - a[k]) / (b[k] - a[k])
                out.append(a + t * (b - a))
    return out


def clip_to(p: np.ndarray, q: np.ndarray, box) -> tuple[np.ndarray, np.ndarray]:
    """The line through p and q, extended both ways to the edges of ``box`` (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = box
    d = q - p
    ts = []
    for k, (lo, hi) in enumerate(((x0, x1), (y0, y1))):
        if abs(d[k]) > 1e-9:
            ts += [(lo - p[k]) / d[k], (hi - p[k]) / d[k]]
    inside = [t for t in ts if all(lo - 1e-6 <= (p + t * d)[k] <= hi + 1e-6
                                  for k, (lo, hi) in enumerate(((x0, x1), (y0, y1))))]
    if len(inside) < 2:
        return p, q
    return p + min(inside) * d, p + max(inside) * d


# --- the plan: a mark is planned as an object whose data are the tag's attributes ---------------
def _fmt(v) -> str:
    v = float(v)
    return f"{v:.0f}" if v.is_integer() else f"{v:g}"


def as_attr(v) -> str:
    """Planned data -> the attribute text the tag takes: ``[[0, 0], [1, 2]]`` -> ``"0,0; 1,2"``,
    ``[1, 2]`` -> ``"1,2"``, ``true`` -> ``"true"``."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return _fmt(v)
    if isinstance(v, dict):
        return "; ".join(f"{k}: {as_attr(x)}" for k, x in v.items())
    if isinstance(v, (list, tuple)):
        if v and all(isinstance(p, (list, tuple)) for p in v):
            return "; ".join(",".join(_fmt(c) for c in p) for p in v)
        if all(isinstance(c, (int, float)) for c in v):
            return ",".join(_fmt(c) for c in v)
        sep = "|" if any("," in str(c) for c in v) else ","   # a name with a comma in it: 12,367 books
        return sep.join(str(c) for c in v)
    return str(v)


def _same(a: str, b: str) -> bool:
    """Equal as written, or as the same numbers (``0.50,1`` = ``0.5, 1``)."""
    sq = lambda s: re.sub(r">+", ">", re.sub(r"\s+", "", str(s)))  # noqa: E731  ("a>>b" is "a>b")
    if sq(a) == sq(b):
        return True
    na, nb = re.findall(r"-?\d+\.?\d*(?:e-?\d+)?", a), re.findall(r"-?\d+\.?\d*(?:e-?\d+)?", b)
    if na and len(na) == len(nb) and re.sub(r"-?\d+\.?\d*(?:e-?\d+)?", "#", sq(a)) == re.sub(r"-?\d+\.?\d*(?:e-?\d+)?", "#", sq(b)):
        return all(abs(float(x) - float(y)) <= 1e-6 * max(1.0, abs(float(x))) for x, y in zip(na, nb))
    return _same_points(a, b)


def _same_points(a: str, b: str) -> bool:
    """The same points with coordinates written as expressions (``pi/3,0.5`` = ``1.0472,0.5``), to
    the 4 decimals a plan writes them with."""
    from .displays.plot.spec import number

    def coords(s: str) -> list[float] | None:
        try:
            return [number(c) for p in str(s).split(";") if p.strip() for c in p.split(",")]
        except BeatError:
            return None
    ca, cb = coords(a), coords(b)
    return bool(ca) and ca is not None and cb is not None and len(ca) == len(cb) and \
        all(abs(x - y) <= 5e-5 * max(1.0, abs(x)) for x, y in zip(ca, cb))


def plan_hooks(tag: str, keys: tuple[str, ...], needs_one_of: tuple[tuple[str, ...], ...]):
    """(check_object, check_drawn) for a mark planned as an object of its own: ``data`` holds the
    tag's attributes (points as ``[[x, y], …]`` or ``"x,y; x,y"``, or ``"hits.2"`` for a planned
    ``dots``); the beat must have ``<tag id=…>`` with each planned attribute as planned."""

    def check_object(d: dict) -> list[str]:
        problems = []
        for group in needs_one_of:
            if not any(d.get(k) not in (None, "", []) for k in group):
                problems.append(f"kind '{tag}' needs data['{group[0]}']" if len(group) == 1 else
                                f"kind '{tag}' needs one of data[{', '.join(repr(k) for k in group)}]")
        bad = [k for k in d if k not in keys]
        if bad:
            problems.append(f"kind '{tag}' data has {bad}; it takes {', '.join(keys)}")
        return problems

    def check_drawn(where: str, obj, leaves) -> list[str]:
        want = {k: as_attr(v) for k, v in obj.data.items() if k in keys and v not in (None, "", [])}
        tags = [n for n in leaves if n.tag == tag and n.id == obj.id]
        attrs = " ".join(f'{k}="{v}"' for k, v in want.items())
        if not tags:
            return [f'{where}: needs <{tag} id="{obj.id}" {attrs}> (the planned {tag})']
        # the leaves are the whole scene's; a mark that changes from beat to beat is drawn as
        # planned when one of its beats has every planned attribute
        offs = [[k for k, v in want.items() if not _same(n.attrs.get(k, ""), v)] for n in tags]
        off = min(offs, key=len)
        if off:
            pairs = ", ".join(f'{k}="{want[k]}"' for k in off)
            return [f'{where}: <{tag} id="{obj.id}"> must have {pairs} as planned']
        return []

    return check_object, check_drawn
