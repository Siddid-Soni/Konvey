"""``<angle>`` (manimgl): the angle at a corner ``at`` between the lines to ``from`` and ``to``
(the smaller side), a small arc of fixed size with its name just outside; a right angle is
drawn as a square corner. Drawn once the picture is fitted (``attach``)."""

from __future__ import annotations

import json
import math

from manimlib import *  # noqa: F401,F403

from ... import marks
from ...tree import BeatError, Node
from ..base import Block

KEYS = ("on", "at", "from", "to", "label", "color", "dim", "size", "radius")
R = 0.5   # arc radius (u): an angle mark keeps its size however large the picture is


class AngleBlock(Block):
    tag = "angle"

    def __init__(self, node: Node):
        super().__init__()
        self.add(Dot(radius=0.01).set_opacity(0))
        self.content = json.dumps(["angle", {k: node.attrs.get(k) for k in KEYS}])


def build(node: Node, world=None) -> AngleBlock:
    return AngleBlock(node)


def attach(node: Node, mob: AngleBlock, resolve, obstacles=lambda *skip: []) -> AngleBlock:
    where = f"<angle id={node.id}>"
    pic = marks.host(node, resolve, where)
    v, a, b = (marks.screen(pic, [marks.one(node.attrs.get(k, ""), resolve, where, k)])[0]
               for k in ("at", "from", "to"))
    if min(np.linalg.norm(a - v), np.linalg.norm(b - v)) < 1e-6:
        raise BeatError(f"{where}: from= and to= must differ from the corner at=")
    t0 = math.atan2(a[1] - v[1], a[0] - v[0])
    t1 = math.atan2(b[1] - v[1], b[0] - v[0])
    sweep = (t1 - t0 + PI) % TAU - PI          # the smaller side, signed
    try:
        r = float(node.attrs.get("radius", R))
    except ValueError:
        r = R
    r = min(r, 0.45 * np.linalg.norm(a - v), 0.45 * np.linalg.norm(b - v)) if r > 0.2 else r
    r = max(r, 0.18)
    color, alpha = marks.style(node, "ink")
    if abs(abs(sweep) - PI / 2) < math.radians(1.5):
        u0 = np.array([math.cos(t0), math.sin(t0), 0.0]) * r * 0.7
        u1 = np.array([math.cos(t1), math.sin(t1), 0.0]) * r * 0.7
        mark = VMobject().set_points_as_corners([v + u0, v + u0 + u1, v + u1])
    else:
        mark = Arc(t0, sweep, radius=r, arc_center=v)
    mark.set_stroke(color, 3, alpha).set_fill(opacity=0)
    parts = [mark]
    if node.attrs.get("label", "").strip():
        mid = t0 + sweep / 2
        u = np.array([math.cos(mid), math.sin(mid), 0.0])
        lab = marks.halo(marks.label(node.attrs["label"], marks.size(node, 30), color).set_fill(opacity=alpha), alpha)
        lab.move_to(v + u * (r + 0.12 + 0.5 * max(lab.get_width(), lab.get_height())))
        if abs(sweep) < math.radians(25):   # a thin angle: its name sits further out, past the lines
            lab.move_to(v + u * (r + 0.25 + 0.6 * max(lab.get_width(), lab.get_height())))
        parts.append(lab)
    mob.set_submobjects(parts)
    return mob


def enter(node: Node, mob: AngleBlock, run_time: float) -> Animation:
    return AnimationGroup(ShowCreation(mob[0]), *(FadeIn(m, shift=0.1 * UP) for m in mob[1:]),
                          run_time=min(run_time * 0.8, 0.9))
