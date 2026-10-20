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
        if not node.attrs.get("of", "").strip():
            raise BeatError(f'<brace id={node.id}> needs of="id" or "id>part"')
        side = node.attrs.get("side", "bottom").strip()
        if side not in SIDES:
            raise BeatError(f'<brace id={node.id}> side="{side}": use one of {", ".join(SIDES)}')
        self.add(Dot(radius=0.01).set_opacity(0))
        self.content = json.dumps(["brace", {k: node.attrs.get(k) for k in ("of", "label", "side", "color")}])


def build(node: Node, world=None) -> BraceBlock:
    return BraceBlock(node)


def attach(node: Node, mob: BraceBlock, resolve, obstacles=lambda *skip: []) -> BraceBlock:
    th = current()
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
