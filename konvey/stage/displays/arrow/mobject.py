"""``<arrow>`` (manimgl): drawn between two parts once both are placed (``attach``)."""

from __future__ import annotations

import json

from manimlib import *  # noqa: F401,F403

from ...theme import current
from ...tree import BeatError, Node
from ..base import Block, _label


class ArrowBlock(Block):
    tag = "arrow"

    def __init__(self, node: Node):
        super().__init__()
        for key in ("from", "to"):
            if not node.attrs.get(key, "").strip():
                raise BeatError(f'<arrow id={node.id}> needs {key}="id" or "id>part"')
        self.add(Dot(radius=0.01).set_opacity(0))   # placeholder until attach draws it
        self.content = json.dumps(["arrow", {k: node.attrs.get(k) for k in ("from", "to", "label", "color")}])


def build(node: Node, world=None) -> ArrowBlock:
    return ArrowBlock(node)


# straight first; then ever deeper arcs, either side (a semicircle rises half its span)
BENDS = (0.0, *(sign * k for k in (TAU / 6, TAU / 4, TAU / 3, 0.42 * TAU) for sign in (-1, 1)))


def attach(node: Node, mob: ArrowBlock, resolve, obstacles=lambda *skip: []) -> ArrowBlock:
    th = current()
    a, b = resolve(node.attrs["from"]), resolve(node.attrs["to"])
    color = th.color(node.attrs.get("color"), "ink")
    p, q = a.get_center(), b.get_center()
    d = q - p
    if np.linalg.norm(d) < 1e-6:
        raise BeatError(f"<arrow id={node.id}>: from and to are the same place")
    # leave each end at the edge of its shape, plus a gap
    start = _edge(a, d) + 0.12 * normalize(d)
    end = _edge(b, -d) - 0.12 * normalize(d)
    # 3b1b's CurvedArrow: a straight line that would run over other things (the cells between two
    # cells of a row) bends round them instead
    from ...attach import path_hits

    boxes = obstacles(a, b)

    def shaped(bend):
        """(arrow, its centre line) for this bend; a bent one leaves and arrives on the side it
        bulges to (over a row of cells: from the cells' tops)."""
        s0, e0 = start, end
        if bend:
            bulge = Line(start, end, path_arc=bend).point_from_proportion(0.5) - (start + end) / 2
            side = normalize(bulge)
            s0, e0 = _edge(a, side) + 0.08 * side, _edge(b, side) + 0.08 * side
        spine = Line(s0, e0, path_arc=bend)
        return Arrow(s0, e0, buff=0, thickness=4, path_arc=bend).set_fill(color, 1).set_stroke(width=0), spine

    arrow, spine, least = None, None, None
    for bend in BENDS:   # the gentlest bend that crosses nothing, else the one that crosses least
        cand, line = shaped(bend)
        n = path_hits([line.point_from_proportion(t) for t in np.linspace(0.04, 0.96, 48)], boxes)
        if least is None or n < least:
            arrow, spine, least = cand, line, n
        if n == 0:
            break
    mob.set_submobjects([arrow])
    out = mob
    if node.attrs.get("label"):
        lab = _label(node.attrs["label"], float(node.attrs.get("size", 26)), color)
        # on the outside of the arrow: the side its far end leans to (two arrows from one item
        # fanning out keep their labels apart)
        perp = rotate_vector(normalize(d), PI / 2)
        if abs(d[0]) > 0.2 * np.linalg.norm(d) and np.sign(perp[0]) != np.sign(d[0]):
            perp = -perp
        mid = spine.point_from_proportion(0.5)
        chord = (spine.get_start() + spine.get_end()) / 2
        if np.linalg.norm(mid - chord) > 0.05:   # a bent arrow: its label outside the bend
            perp = normalize(mid - chord)
        from ... import marks
        from ...attach import _along

        # outside first, else clear of what is there, its own arrow included; a dark outline keeps
        # it readable where it has to sit near a line
        own = _along(spine, step=0.08, r=0.06)
        marks.halo(lab)
        marks.place_label(lab, mid, perp, obstacles() + own, gap=0.2)
        out.add(lab)
    return out


def _edge(m: Mobject, d: np.ndarray) -> np.ndarray:
    """Where a ray from ``m``'s centre in direction ``d`` leaves its bounding box."""
    c = m.get_center()
    hw, hh = m.get_width() / 2, m.get_height() / 2
    u = normalize(d)
    t = min(hw / abs(u[0]) if abs(u[0]) > 1e-6 else np.inf, hh / abs(u[1]) if abs(u[1]) > 1e-6 else np.inf)
    return c + u * t
