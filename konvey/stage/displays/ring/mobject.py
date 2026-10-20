"""``<ring>`` (manimgl): a rounded outline drawn around a part once it is placed (``attach``)."""

from __future__ import annotations

import json

from manimlib import *  # noqa: F401,F403

from ...theme import current
from ...tree import BeatError, Node
from ..base import Block, _label


class RingBlock(Block):
    tag = "ring"

    def __init__(self, node: Node):
        super().__init__()
        if not node.attrs.get("of", "").strip():
            raise BeatError(f'<ring id={node.id}> needs of="id" or "id>part"')
        self.add(Dot(radius=0.01).set_opacity(0))
        self.content = json.dumps(["ring", {k: node.attrs.get(k) for k in ("of", "label", "color")}])


def build(node: Node, world=None) -> RingBlock:
    return RingBlock(node)


def attach(node: Node, mob: RingBlock, resolve, obstacles=lambda *skip: []) -> RingBlock:
    th = current()
    target = resolve(node.attrs["of"])
    color = th.color(node.attrs.get("color")) if node.attrs.get("color") else th.lit
    w, h = target.get_width(), target.get_height()
    if max(w, h) <= 1.6 * max(min(w, h), 0.05):
        # about as wide as tall (a point, a node, a cell): a circle around it, as 3b1b circles a dot
        ring = Circle(radius=max(0.5 * (w * w + h * h) ** 0.5 + 0.08, 0.2))
    else:   # a row, a group, a long label: a rounded box
        ring = RoundedRectangle(width=w + 0.3, height=h + 0.3, corner_radius=min(0.16, 0.25 * (min(w, h) + 0.3)))
    ring.move_to(target).set_stroke(color, 4).set_fill(opacity=0)
    mob.set_submobjects([ring])
    out = mob
    if node.attrs.get("label"):
        from ...attach import clear

        lab = _label(node.attrs["label"], float(node.attrs.get("size", 26)), color)
        boxes = obstacles(target)
        for side in (UP, DOWN, RIGHT, LEFT):   # the first side where it covers nothing (a point's own name)
            lab.next_to(ring, side, buff=0.12)
            if clear(lab, boxes):
                break
        else:
            lab.next_to(ring, UP, buff=0.12)
        out.add(lab)
    return out


def enter(node: Node, mob: RingBlock, run_time: float) -> Animation:
    return ShowCreation(mob[0], run_time=run_time * 0.8) if len(mob) == 1 else \
        AnimationGroup(ShowCreation(mob[0]), FadeIn(mob[1]), run_time=run_time * 0.8)
