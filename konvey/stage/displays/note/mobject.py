"""``<note>`` (manimgl): a short note placed in the nearest open space around a point of a picture
(``on`` + ``at``) or a thing on screen (``to="id>part"``), with a thin straight arrow from the note
to it, stopping just short of both (3b1b: ``Arrow(word, target, buff=0.1)``)."""

from __future__ import annotations

import json

from manimlib import *  # noqa: F401,F403

from ... import marks
from ...tree import BeatError, Node
from ..base import Block

KEYS = ("on", "at", "to", "text", "color", "size", "side", "dim")
DIRS = {"up-left": UL, "up-right": UR, "left": LEFT, "right": RIGHT, "up": UP, "down": DOWN,
        "down-left": DL, "down-right": DR}
REACH = (0.6, 1.0, 1.4, 1.9, 2.5)   # how far from the point the note may sit (u), nearest first
EDGE = 0.5                     # kept clear of the frame's edge (u): manim's DEFAULT_MOBJECT_TO_EDGE_BUFFER


class NoteBlock(Block):
    tag = "note"

    def __init__(self, node: Node):
        super().__init__()
        if not node.attrs.get("text", "").strip():
            raise BeatError(f'<note id={node.id}> needs text="…" (the words of the note)')
        if not (node.attrs.get("to", "").strip() or (node.attrs.get("on", "").strip() and node.attrs.get("at"))):
            raise BeatError(f'<note id={node.id}> needs on="pic" at="x,y" (a point of a picture) or to="id" '
                            '(a thing on screen)')
        side = node.attrs.get("side", "").strip()
        if side and side not in DIRS:
            raise BeatError(f'<note id={node.id}> side="{side}": one of {", ".join(DIRS)}, or leave it out')
        self.add(Dot(radius=0.01).set_opacity(0))
        self.content = json.dumps(["note", {k: node.attrs.get(k) for k in KEYS}])


def build(node: Node, world=None) -> NoteBlock:
    return NoteBlock(node)


def _targets(node: Node, resolve, where: str) -> list[tuple[np.ndarray, Mobject | None]]:
    """[(the point an arrow ends at, the thing pointed at or None)]: one note may point at several
    (``at="3,0; 7,0; 11,0"``, ``to="eq>a; eq>b"``), one arrow each (3b1b's "Already Gaussian primes")."""
    if node.attrs.get("to", "").strip():
        things = [resolve(r.strip()) for r in node.attrs["to"].split(";") if r.strip()]
        return [(t.get_center(), t) for t in things]
    pic = marks.host(node, resolve, where)
    pts = marks.points(node.attrs["at"], resolve, where, "at")
    if callable(getattr(pic, "cell_count", None)):   # a grid: "row,col", and the arrow must end on a cell
        rows, cols = pic.cell_count()
        for r, c in pts:
            if not (-0.5 <= r <= rows - 0.5 and -0.5 <= c <= cols - 0.5):
                hint = f' (to point at row {c:g}, write "{c:g},{r:g}")' if 0 <= c < rows and 0 <= r < cols else ""
                raise BeatError(f'{where} at="{node.attrs["at"]}": a grid\'s points are "row,col", and '
                                f"{node.attrs.get('on')} has rows 0-{rows - 1} and columns 0-{cols - 1}, so "
                                f'"{r:g},{c:g}" is off the table{hint}')
    return [(p, None) for p in marks.screen(pic, pts)]


def _aims(node: Node, resolve, where: str) -> list[tuple[float, float]]:
    """The ``at`` points in the picture's own coordinates (the frame audit checks they touch ink)."""
    if node.attrs.get("to", "").strip():
        return []
    return marks.points(node.attrs["at"], resolve, where, "at")


def _edge_toward(m: Mobject, toward: np.ndarray) -> np.ndarray:
    """Where the line from m's centre towards ``toward`` leaves m's bounding box."""
    c = m.get_center()
    d = toward - c
    hw, hh = m.get_width() / 2, m.get_height() / 2
    k = min(hw / abs(d[0]) if abs(d[0]) > 1e-9 else np.inf, hh / abs(d[1]) if abs(d[1]) > 1e-9 else np.inf)
    return c + d * min(k, 1.0)


def _stop_at_name(q: np.ndarray, frm: np.ndarray, boxes, reach: float = 0.8) -> np.ndarray:
    """The arrow to a point stops at the point's own name when it has to cross it (a dot's number
    sits right above the dot): 3b1b's arrows end at the label, never through it."""
    d = frm - q
    n = np.linalg.norm(d)
    if n < 1e-6:
        return q
    u = d / n
    last = None
    for s in np.linspace(0.0, min(reach, n * 0.6), 24):
        p = q + u * s
        if any(x0 < p[0] < x1 and y0 < p[1] < y1 for x0, y0, x1, y1 in boxes):
            last = p
        elif last is not None:
            return p
    return q


def attach(node: Node, mob: NoteBlock, resolve, obstacles=lambda *skip: []) -> NoteBlock:
    from ...attach import _box, _hits, path_hits

    where = f"<note id={node.id}>"
    targets = _targets(node, resolve, where)
    p = np.mean([q for q, _ in targets], axis=0)
    things = [t for _, t in targets if t is not None]
    thing = things[0] if len(targets) == 1 and things else None
    color, alpha = marks.style(node, "accent")
    lab = marks.halo(marks.label(node.attrs["text"], marks.size(node, 32), color).set_fill(opacity=alpha), alpha)
    boxes = obstacles(*things)
    w, h = lab.get_width(), lab.get_height()
    half_w, half_h = FRAME_WIDTH / 2 - EDGE, marks.half_height(EDGE)
    reach0 = 0.0 if thing is None else 0.5 * max(thing.get_width(), thing.get_height())
    side = node.attrs.get("side", "").strip()
    order = [DIRS[side]] if side else [UL, UR, LEFT, RIGHT, DL, DR, UP, DOWN]
    best = None
    for rank, d in enumerate(order):
        u = d / np.linalg.norm(d)
        for step, r in enumerate(REACH):
            c = p + u * (reach0 + r + 0.5 * (abs(u[0]) * w + abs(u[1]) * h))
            lab.move_to(c)
            b = _box(lab)
            out = max(0.0, b[2] - half_w, -half_w - b[0], b[3] - half_h, -half_h - b[1])
            hits = sum(_hits(b, o, -0.25) for o in boxes)   # a clear gap round other words (MED_SMALL_BUFF)
            crossings = 0
            for q, _ in targets:
                start = _edge_toward(lab, q)
                near = 0.75 / max(np.linalg.norm(q - start), 1e-6)   # the target's own name may be crossed
                crossings += path_hits([start + (q - start) * s for s in np.linspace(0.15, max(0.15, 1 - near), 12)], boxes)
            score = 10 * hits + 2.5 * crossings + 20 * out + 0.6 * step + 0.15 * rank
            if best is None or score < best[0]:
                best = (score, c)
            if score < 0.6 * (step + 1) + 0.15 * rank + 1e-9 and hits == 0 and crossings == 0 and out == 0:
                break
        if best is not None and best[0] < 1.0:
            break
    lab.move_to(best[1])
    arrows = VGroup()
    for q, t in targets:
        end = _edge_toward(t, best[1]) if t is not None else _stop_at_name(q, best[1], boxes)
        start = _edge_toward(lab, end)
        v = end - start
        n = np.linalg.norm(v)
        u = v / n if n > 1e-6 else DOWN
        arrows.add(Arrow(start + u * 0.1, end - u * 0.1, buff=0, thickness=2.5,
                         max_tip_length_to_length_ratio=0.3).set_fill(color, alpha).set_stroke(width=0))
    mob.set_submobjects([lab, arrows])
    mob.aims = _aims(node, resolve, where)
    return mob


def enter(node: Node, mob: NoteBlock, run_time: float) -> Animation:
    return AnimationGroup(FadeIn(mob[0], shift=0.15 * UP), LaggedStart(*(GrowArrow(a) for a in mob[1]), lag_ratio=0.15),
                          lag_ratio=0.3,
                          run_time=min(run_time * 0.8, 1.0))
