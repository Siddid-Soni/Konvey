"""``<dots>`` (manimgl): points of a picture at its own coordinates, each with an optional name or
number, placed once the picture is fitted (``attach``)."""

from __future__ import annotations

import json

from manimlib import *  # noqa: F401,F403

from ... import marks
from ...tree import BeatError, Node
from ..base import Block

R = 0.06    # dot radius (u)


def _xy(node: Node) -> list[tuple[float, float]]:
    where = f"<dots id={node.id}>"
    pts = []
    for part in (p.strip() for p in node.attrs.get("at", "").split(";") if p.strip()):
        try:
            x, y = (float(v) for v in part.split(","))
        except ValueError as e:
            raise BeatError(f'{where} at="{node.attrs["at"]}": "{part}" is not x,y') from e
        pts.append((x, y))
    if not pts:
        raise BeatError(f'{where} needs at="x,y; x,y" (in the coordinates of the picture it is on)')
    return pts


def _names(node: Node, n: int) -> list[str]:
    if node.attrs.get("numbered", "").strip().lower() in ("true", "1", "yes"):
        return [str(k + 1) for k in range(n)]
    raw = node.attrs.get("labels", "")
    if not raw.strip():
        return [""] * n
    names = [s.strip() for s in raw.split("|" if "|" in raw else ",")]   # "|" when a name has a comma
    if n == 1:
        return [raw.strip()]   # one point: its whole name, commas and all
    if len(names) != n:
        raise BeatError(f'<dots id={node.id}> labels="{raw}" has {len(names)} names for {n} points '
                        "(leave one blank to skip it: \"A,,C\")")
    return names


class DotsBlock(Block):
    tag = "dots"

    def __init__(self, node: Node):
        super().__init__()
        self.xy = _xy(node)
        self.names = _names(node, len(self.xy))
        self.add(Dot(radius=0.01).set_opacity(0))
        self.content = json.dumps(["dots", {k: node.attrs.get(k) for k in
                                            ("on", "at", "labels", "numbered", "color", "dim", "size")}])


def _part(self, name: str):
    """A point by its name (``12,367 books``) or its number (``3``, from 1)."""
    from ...match import squash

    n = name.strip()
    for k, label in enumerate(self.names):
        if label and squash(label) == squash(n):
            return self[k]
    if n.isdigit() and 1 <= int(n) <= len(self.submobjects):
        return self[int(n) - 1]
    return None


DotsBlock.part = _part


def build(node: Node, world=None) -> DotsBlock:
    return DotsBlock(node)


def attach(node: Node, mob: DotsBlock, resolve, obstacles=lambda *skip: []) -> DotsBlock:
    where = f"<dots id={node.id}>"
    pic = marks.host(node, resolve, where)
    color, alpha = marks.style(node, "accent")
    sz = marks.size(node, 28)
    at = marks.screen(pic, mob.xy)
    centre = np.mean([*at], axis=0) if len(at) > 2 else pic.get_center()
    row = None   # points in a row (on a number line, along a side): names go off the row, all one side
    if len(at) > 2:
        pts = np.array(at)[:, :2] - centre[:2]
        _, sv, vt = np.linalg.svd(pts, full_matrices=False)
        if sv[1] < 0.05 * max(sv[0], 1e-9):
            row = np.array([-vt[0][1], vt[0][0], 0.0])
            if np.dot(row, centre - pic.get_center()) < 0 or (abs(np.dot(row, centre - pic.get_center())) < 0.05 and row[1] < 0):
                row = -row
    boxes = obstacles()
    groups = []
    for p in at:
        boxes.append((p[0] - R, p[1] - R, p[0] + R, p[1] + R))
    from ...attach import _box, _hits

    own = []   # this mark's names: two points close together never share a spot for theirs
    for p, name in zip(at, mob.names):
        g = VGroup(Dot(p, radius=R).set_fill(color, alpha).set_stroke(width=0))
        if name:
            lab = marks.halo(marks.label(name, sz, color).set_fill(opacity=alpha), alpha)
            out = row if row is not None else (p - centre if np.linalg.norm(p - centre) > 1e-6 else UP)
            for d in (out, -out, np.array([-out[1], out[0], 0.0]), np.array([out[1], -out[0], 0.0])):
                marks.place_label(lab, p, d, boxes + own * 3, gap=0.1)   # a sibling's name weighs most
                if not any(_hits(_box(lab), o, 0.0) for o in own):
                    break
            own.append(_box(lab))
            boxes.append(tuple(np.r_[lab.get_corner(DL)[:2], lab.get_corner(UR)[:2]]))
            g.add(lab)
        groups.append(g)
    mob.set_submobjects(groups)
    return mob


def enter(node: Node, mob: DotsBlock, run_time: float) -> Animation:
    return LaggedStart(*(FadeIn(g, scale=0.3) for g in mob), lag_ratio=0.3,
                       run_time=min(run_time * 0.8, 0.4 + 0.15 * len(mob)))


def morph(old: DotsBlock, new: DotsBlock, sources=None) -> Animation:
    """Point by point: a kept point slides, a new one pops in, a gone one fades."""
    anims = []
    for k in range(max(len(old), len(new))):
        if k < len(old) and k < len(new):
            anims.append(FadeTransform(old[k], new[k]) if len(old[k]) != len(new[k]) else Transform(old[k], new[k]))
        elif k < len(new):
            anims.append(FadeIn(new[k], scale=0.3))
        else:
            anims.append(FadeOut(old[k]))
    return AnimationGroup(*anims)
