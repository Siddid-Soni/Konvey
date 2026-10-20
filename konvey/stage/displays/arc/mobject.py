"""``<arc>`` (manimgl): the arc of a circle about ``center`` from one point round to another
(counter-clockwise; ``dir="cw"`` the other way), or the filled wedge (``fill``), with its name
outside the middle of the arc; drawn once the picture is fitted (``attach``)."""

from __future__ import annotations

import json
import math

from manimlib import *  # noqa: F401,F403

from ... import marks
from ...tree import BeatError, Node
from ..base import Block

KEYS = ("on", "center", "from", "to", "dir", "fill", "label", "color", "dim", "size", "width")


def current_ink() -> str:
    from ...theme import current

    return current().ink


class ArcBlock(Block):
    tag = "arc"

    def __init__(self, node: Node):
        super().__init__()
        self.add(Dot(radius=0.01).set_opacity(0))
        self.content = json.dumps(["arc", {k: node.attrs.get(k) for k in KEYS}])


def build(node: Node, world=None) -> ArcBlock:
    return ArcBlock(node)


def attach(node: Node, mob: ArcBlock, resolve, obstacles=lambda *skip: []) -> ArcBlock:
    where = f"<arc id={node.id}>"
    pic = marks.host(node, resolve, where)
    c, a, b = (marks.screen(pic, [marks.one(node.attrs.get(k, ""), resolve, where, k)])[0]
               for k in ("center", "from", "to"))
    ra, rb = np.linalg.norm(a - c), np.linalg.norm(b - c)
    if ra < 1e-6:
        raise BeatError(f"{where}: from= is at the centre; an arc needs a radius")
    t0 = math.atan2(a[1] - c[1], a[0] - c[0])
    t1 = math.atan2(b[1] - c[1], b[0] - c[0])
    cw = node.attrs.get("dir", "").strip().lower() in ("cw", "clockwise")
    sweep = (t1 - t0) % TAU
    if cw:
        sweep -= TAU
    if abs(sweep) < 1e-6:
        sweep = TAU if not cw else -TAU
    r = ra if abs(ra - rb) < 0.05 * ra else (ra + rb) / 2
    color, alpha = marks.style(node, "accent")
    try:
        width = float(node.attrs.get("width", 6))
    except ValueError:
        width = 6.0
    arc = Arc(t0, sweep, radius=r, arc_center=c).set_stroke(color, width, alpha).set_fill(opacity=0)
    fill = node.attrs.get("fill", "").strip().lower()
    if fill and fill not in ("false", "no", "none"):
        from ...theme import current

        fc = color if fill in ("true", "yes") else current().color(fill)
        wedge = AnnularSector(angle=sweep, start_angle=t0, inner_radius=0, outer_radius=r, arc_center=c)
        wedge.set_fill(fc, 0.25 * alpha).set_stroke(width=0)
    else:
        wedge = VMobject().set_points_as_corners([c, c]).set_stroke(width=0)
    parts = [wedge, arc]
    if node.attrs.get("label", "").strip():
        mid = t0 + sweep / 2
        u = np.array([math.cos(mid), math.sin(mid), 0.0])
        lab = marks.halo(marks.label(node.attrs["label"], marks.size(node, 30), current_ink()).set_fill(opacity=alpha), alpha)
        marks.place_label(lab, c + u * r, u, obstacles(), gap=0.14)
        parts.append(lab)
    mob.set_submobjects(parts)
    return mob


def enter(node: Node, mob: ArcBlock, run_time: float) -> Animation:
    return AnimationGroup(FadeIn(mob[0]), ShowCreation(mob[1]), *(FadeIn(m) for m in mob[2:]),
                          run_time=min(run_time * 0.8, 1.0))
