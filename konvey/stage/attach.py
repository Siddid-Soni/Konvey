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

from . import displays
from .tree import BeatError, Node

DL_, UR_ = (-1.0, -1.0, 0.0), (1.0, 1.0, 0.0)

SIDES = ("top", "bottom", "left", "right")


def attached(node: Node) -> bool:
    return "of" in node.attrs or displays.hook(node.tag, "attach") is not None


def resolve(ref: str, mobs: dict, where: str):
    """The mobject for ``id`` or ``id>part`` among the beat's built leaves."""
    head, _, rest = ref.strip().lstrip("#").partition(">")
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


def place(nodes: dict[str, Node], mobs: dict) -> None:
    """Attach every attached leaf of one beat, in place in ``mobs`` (after the others are fitted).
    A leaf without ``side`` takes the first of top, bottom, right, left where it covers nothing
    already drawn (annotations included, so a note never sits under an arrow)."""
    from manimlib import DOWN, LEFT, RIGHT, UP

    dirs = dict(zip(SIDES, (UP, DOWN, LEFT, RIGHT)))
    order = sorted((i for i in nodes if i in mobs and attached(nodes[i])),
                   key=lambda i: displays.hook(nodes[i].tag, "attach") is None)   # drawn ones first
    taken = [_box(m) for i, m in mobs.items() if not attached(nodes[i]) and len(m.get_all_points())]
    drawn = [m for i, m in mobs.items() if not attached(nodes[i])]
    for i in order:
        n = nodes[i]
        where = f"<{n.tag} id={i}>"
        hook = displays.hook(n.tag, "attach")
        if hook is not None:
            mobs[i] = hook(n, mobs[i], lambda ref: resolve(ref, mobs, where),
                           lambda *skip: pieces(drawn, skip))
            taken.append(_box(mobs[i]))
            drawn.append(mobs[i])
            continue
        side = n.attrs.get("side", "").strip()
        if side and side not in dirs:
            raise BeatError(f'{where} side="{side}": use one of {", ".join(SIDES)}')
        target = resolve(n.attrs["of"], mobs, where)
        for s in ([side] if side else ["top", "bottom", "right", "left"]):
            mobs[i].next_to(target, dirs[s], buff=0.18)
            if side or not any(_hits(_box(mobs[i]), t) for t in taken):
                break
        else:
            mobs[i].next_to(target, UP, buff=0.18)
        taken.append(_box(mobs[i]))


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
            seen = any(k in a.dtype.names and len(a[k]) and float(a[k][:, 3].max()) > 0.05
                       for k in ("fill_rgba", "stroke_rgba"))
            if seen:
                out.append(_box(sm))
    return out


def clear(m, boxes, pad: float = 0.04) -> bool:
    b = _box(m)
    return not any(_hits(b, o, -pad) for o in boxes)


def path_hits(points, boxes, shrink: float = 0.06) -> int:
    """How many boxes a path (sampled points) runs through (each shrunk a little: touching is fine)."""
    return sum(any(x0 + shrink < x < x1 - shrink and y0 + shrink < y < y1 - shrink for x, y, *_ in points)
               for x0, y0, x1, y1 in boxes)
