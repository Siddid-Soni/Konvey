"""``<brace>`` (manimgl): a brace along one side of a part once it is placed (``attach``)."""

from __future__ import annotations

import json

from manimlib import *  # noqa: F401,F403

from ...theme import current
from ...tree import BeatError, Node
from ..base import Block, _label

SIDES = {"bottom": DOWN, "top": UP, "left": LEFT, "right": RIGHT}


class BraceBlock(Block):
    tag = "brace"

    def __init__(self, node: Node):
        super().__init__()
        if not node.attrs.get("of", "").strip() and not node.attrs.get("on", "").strip():
            raise BeatError(f'<brace id={node.id}> needs of="id" or "id>part" (a thing on screen), or on="id" '
                            'from="x,y" to="x,y" (a stretch of a picture: a side of a triangle)')
        side = node.attrs.get("side", "bottom").strip()
        if side not in SIDES:
            raise BeatError(f'<brace id={node.id}> side="{side}": use one of {", ".join(SIDES)}')
        self.add(Dot(radius=0.01).set_opacity(0))
        self.content = json.dumps(["brace", {k: node.attrs.get(k) for k in
                                             ("of", "on", "from", "to", "flip", "label", "side", "color", "dim")}])


def build(node: Node, world=None) -> BraceBlock:
    return BraceBlock(node)


def _between(node: Node, mob: BraceBlock, resolve, obstacles) -> BraceBlock:
    """A brace along the stretch from one point of a picture to another (a side of a triangle, a
    run of a number line), on the side away from the picture's middle (``flip`` for the other)."""
    from ... import marks

    th = current()
    where = f"<brace id={node.id}>"
    pic = marks.host(node, resolve, where)
    a, b = marks.screen(pic, [marks.one(node.attrs.get(k, ""), resolve, where, k) for k in ("from", "to")])
    if np.linalg.norm(b - a) < 0.15:
        raise BeatError(f"{where}: from= and to= are the same point; a brace spans a stretch")
    from ...attach import _box, _hits, clear

    t = (b - a) / np.linalg.norm(b - a)
    d = np.array([-t[1], t[0], 0.0])
    away = (a + b) / 2 - pic.get_center()
    if np.dot(d, away) < 0:
        d = -d
    color = th.color(node.attrs.get("color")) if node.attrs.get("color") else th.ink
    boxes = obstacles()

    def placed(side):
        """The brace on that side, stepped out past what sits right there (a number line's
        numbers), at most 0.6 u; and how much it still covers."""
        br = Brace(Line(a, b), side, buff=0.1).set_fill(color)
        for _ in range(8):
            if clear(br, boxes):
                break
            br.shift(0.08 * side)
        return br, sum(_hits(_box(p), o, -0.02) for p in br.family_members_with_points() for o in boxes)

    sides = [d, -d]   # the side that covers the least; away from the picture's middle on a tie
    if node.attrs.get("flip", "").strip().lower() in ("true", "1", "yes"):
        sides = [-d]
    (brace, _), d = min(((placed(s), s) for s in sides), key=lambda x: x[0][1])
    mob.set_submobjects([brace])
    if node.attrs.get("label"):
        lab = marks.halo(marks.label(node.attrs["label"], marks.size(node, 30), color))
        lab.move_to(brace.get_tip() + d * (0.12 + 0.5 * (abs(d[0]) * lab.get_width() + abs(d[1]) * lab.get_height())))
        mob.add(lab)
    return mob


def attach(node: Node, mob: BraceBlock, resolve, obstacles=lambda *skip: []) -> BraceBlock:
    out = _attach(node, mob, resolve, obstacles)
    if node.attrs.get("dim", "").strip().lower() in ("true", "1", "yes"):
        out.set_opacity(0.3)   # the line has moved past it: it stays, faint
    return out


def _attach(node: Node, mob: BraceBlock, resolve, obstacles) -> BraceBlock:
    th = current()
    if node.attrs.get("on", "").strip():
        return _between(node, mob, resolve, obstacles)
    target = resolve(node.attrs["of"])
    if max(target.get_width(), target.get_height()) < 0.15:
        raise BeatError(f'<brace id={node.id} of="{node.attrs["of"]}">: that part is a point, so a '
                        'brace has nothing to span; brace a run of cells, a group, a bar or a whole '
                        'display, or mark a point with <ring> or <arrow>')
    d = SIDES[node.attrs.get("side", "bottom").strip()]
    color = th.color(node.attrs.get("color")) if node.attrs.get("color") else th.lit
    brace = Brace(target, d, buff=0.12).set_fill(color)
    # out past whatever else sits on that side (an array's index numbers under its cells)
    from ...attach import clear

    boxes = obstacles(target)
    for _ in range(30):
        if clear(brace, boxes):
            break
        brace.shift(0.08 * d)
    mob.set_submobjects([brace])
    if node.attrs.get("label"):
        mob.add(_label(node.attrs["label"], float(node.attrs.get("size", 28)), color)
                .next_to(brace, d, buff=0.1))
    return mob


def enter(node: Node, mob: BraceBlock, run_time: float) -> Animation:
    grow = GrowFromCenter(mob[0], run_time=run_time * 0.7)
    return grow if len(mob) == 1 else AnimationGroup(grow, FadeIn(mob[1], shift=0.1 * DOWN), lag_ratio=0.4,
                                                     run_time=run_time * 0.8)
