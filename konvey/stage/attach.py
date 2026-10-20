"""Things placed against a part of another display, after the page is laid out.

A part is written ``id`` (a whole display) or ``id>group`` (a display's own part: a collection's
group, ``people>left-handed>plays chess``); a display that has parts gives them through its
``part(name)`` method. Two kinds of leaves are attached instead of laid out:

- any leaf with ``of="part"`` (a ``number``, ``text`` or ``tex``): it sits beside that part,
  ``side="top|bottom|left|right"`` (top), and moves with it from beat to beat;
- an annotation display (``<arrow from to>``, ``<ring of>``, ``<brace of>``) whose
  ``attach(node, mob, resolve, obstacles)`` hook draws it between or around the parts, clear of
  ``obstacles(*skip)``: the visible pieces already drawn, less ``skip`` (its own parts).

Attached leaves take no room in the layout (``layout`` writes them out of the flow).
"""

from __future__ import annotations

import re

import numpy as np

from . import displays
from .tree import BeatError, Node

DL_, UR_ = (-1.0, -1.0, 0.0), (1.0, 1.0, 0.0)

SIDES = ("top", "bottom", "left", "right")


def attached(node: Node) -> bool:
    return "of" in node.attrs or displays.hook(node.tag, "attach") is not None


def resolve(ref: str, mobs: dict, where: str):
    """The mobject for ``id`` or ``id>part`` among the beat's built leaves."""
    head, _, rest = re.sub(r">+", ">", ref.strip().lstrip("#")).partition(">")   # "a>>b" is "a>b"
    head = head.strip()
    if head not in mobs:
        raise BeatError(f'{where}: "{ref}" names no element of this beat (ids: {", ".join(sorted(mobs))})')
    mob = mobs[head]
    if not rest.strip():
        return mob
    from .parts import find

    found = find(mob, rest)
    if found is None:
        raise BeatError(f'{where}: "{ref}": #{head} (a <{getattr(mob, "tag", "?")}>) has no part '
                        f'"{rest.strip()}"; see konvey/stage/parts.py for how each display names its parts')
    return found


def _box(m):
    (x0, y0, _), (x1, y1, _) = m.get_corner(DL_), m.get_corner(UR_)
    return x0, y0, x1, y1


def _hits(a, b, pad: float = 0.05) -> bool:
    return a[0] < b[2] - pad and b[0] < a[2] - pad and a[1] < b[3] - pad and b[1] < a[3] - pad


def place(nodes: dict[str, Node], mobs: dict, strict: bool = True) -> None:
    """Attach every attached leaf of one beat, in place in ``mobs`` (after the others are fitted).
    A leaf without ``side`` takes the first of top, bottom, right, left where it covers nothing
    already drawn (annotations included, so a note never sits under an arrow)."""
    from manimlib import DOWN, LEFT, RIGHT, UP

    dirs = dict(zip(SIDES, (UP, DOWN, LEFT, RIGHT)))
    def rank(i):   # marks first, then words beside parts, then what points at either (notes, arrows)
        n = nodes[i]
        if displays.hook(n.tag, "attach") is None:
            return 1
        return 2 if n.tag in ("note", "arrow") else 0
    order = sorted((i for i in nodes if i in mobs and attached(nodes[i])), key=rank)
    taken = [_box(m) for i, m in mobs.items() if not attached(nodes[i]) and len(m.get_all_points())]
    drawn = [m for i, m in mobs.items() if not attached(nodes[i])]
    for i in order:
        n = nodes[i]
        where = f"<{n.tag} id={i}>"
        hook = displays.hook(n.tag, "attach")
        if hook is not None:
            try:
                mobs[i] = hook(n, mobs[i], lambda ref: resolve(ref, mobs, where),
                               lambda *skip: pieces(drawn, skip))
            except BeatError:
                if strict:   # the check names it; a render leaves that one mark out
                    raise
                mobs[i].set_submobjects([])
                continue
            taken.append(_box(mobs[i]))
            drawn.append(mobs[i])
            continue
        side = n.attrs.get("side", "").strip()
        if side.startswith("inside"):
            target = resolve(n.attrs["of"], mobs, where)
            _inside(mobs[i], target, side, pieces(drawn), where)
            taken.append(_box(mobs[i]))
            drawn.append(mobs[i])
            continue
        if side and side not in dirs:
            raise BeatError(f'{where} side="{side}": use one of {", ".join(SIDES)}, or inside '
                            f'({", ".join(INSIDE)})')
        target = resolve(n.attrs["of"], mobs, where)
        for s in ([side] if side else ["top", "bottom", "right", "left"]):
            mobs[i].next_to(target, dirs[s], buff=0.25)
            if side or not any(_hits(_box(mobs[i]), t) for t in taken):
                break
        else:
            mobs[i].next_to(target, UP, buff=0.25)
        taken.append(_box(mobs[i]))
        drawn.append(mobs[i])


INSIDE = ("inside-top-left", "inside-top-right", "inside-bottom-left", "inside-bottom-right")


def _inside(mob, target, side: str, boxes, where: str) -> None:
    """Inside the picture's own box, in a corner where it covers none of the picture's lines,
    marks or words: where 3b1b writes the equation of the curve he is drawing. ``inside`` takes
    the first clear corner (top-left first); ``inside-top-right`` etc. ask for one."""
    import numpy as np

    corners = {"inside-top-left": (-1, 1), "inside-top-right": (1, 1),
               "inside-bottom-left": (-1, -1), "inside-bottom-right": (1, -1)}
    if side != "inside" and side not in corners:
        raise BeatError(f'{where} side="{side}": inside, or one of {", ".join(INSIDE)}')
    x0, y0, x1, y1 = _box(target)
    w, h = mob.get_width(), mob.get_height()
    pad = 0.2
    order = [side] if side != "inside" else list(corners)
    best, best_hits = None, None
    for name in order:
        dx, dy = corners[name]
        cx = (x0 + pad + w / 2) if dx < 0 else (x1 - pad - w / 2)
        cy = (y1 - pad - h / 2) if dy > 0 else (y0 + pad + h / 2)
        mob.move_to(np.array([cx, cy, 0.0]))
        b = _box(mob)
        hits = sum(_hits(b, o, -0.04) for o in boxes)
        if best_hits is None or hits < best_hits:
            best, best_hits = (cx, cy), hits
        if hits == 0:
            return
    mob.move_to(np.array([best[0], best[1], 0.0]))


def pieces(mobs, skip=()) -> list[tuple[float, float, float, float]]:
    """Boxes of the visible pieces drawn on the page (each glyph, cell, dot, line), leaving out
    ``skip`` and everything inside them: what a mark placed on a part must not cover."""
    gone = {id(x) for m in skip for x in m.get_family()}
    out = []
    for m in mobs:
        for sm in m.get_family():
            if id(sm) in gone or not sm.has_points() or sm.submobjects:
                continue
            a = sm.data
            fill = float(a["fill_rgba"][:, 3].max()) if "fill_rgba" in a.dtype.names and len(a["fill_rgba"]) else 0.0
            stroke = 0.0
            if "stroke_rgba" in a.dtype.names and len(a["stroke_rgba"]):
                width = a["stroke_width"] if "stroke_width" in a.dtype.names else None
                if width is None or float(width.max()) > 0:
                    stroke = float(a["stroke_rgba"][:, 3].max())
            if max(fill, stroke) <= 0.05:
                continue
            box = _box(sm)
            if box[2] - box[0] > BIG or box[3] - box[1] > BIG:
                if fill < 0.4 and stroke < 0.6:
                    continue            # a faint grid line or shaded region: words sit on it (with a halo)
                if fill < 0.4:          # a long line or curve: what it covers is the line itself
                    out += _along(sm)
                    continue
            out.append(box)
    return out


BIG = 0.8   # a piece wider and taller than this (u) is a curve or an area, not a word


def _along(sm, step: float = 0.1, r: float = 0.04) -> list[tuple[float, float, float, float]]:
    """Small boxes along a stroked curve (a circle, a long diagonal): its bounding box would
    cover everything inside it."""
    pts = sm.get_points()
    if not len(pts):
        return []
    keep = [pts[0]]
    for a, b in zip(pts[:-1], pts[1:]):   # evenly along each stretch: a straight line has few points
        n = int(np.linalg.norm(b - a) / step)
        keep += [a + (b - a) * (k / (n + 1)) for k in range(1, n + 2)]
    return [(p[0] - r, p[1] - r, p[0] + r, p[1] + r) for p in keep]


def clear(m, boxes, pad: float = 0.04) -> bool:
    b = _box(m)
    return not any(_hits(b, o, -pad) for o in boxes)


def path_hits(points, boxes, shrink: float = 0.06) -> int:
    """How many boxes a path (sampled points) runs through (each shrunk a little: touching is fine)."""
    return sum(any(x0 + shrink < x < x1 - shrink and y0 + shrink < y < y1 - shrink for x, y, *_ in points)
               for x0, y0, x1, y1 in boxes)
