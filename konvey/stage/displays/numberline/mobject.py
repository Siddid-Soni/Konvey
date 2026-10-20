"""``<numberline>`` (manimgl): ticks, numbers and sliding markers along one line (3b1b's
``NumberLine`` with a ``Triangle`` pointer and a ``DecimalNumber`` riding on a ``ValueTracker``)."""

from __future__ import annotations

import json
import math

from manimlib import *  # noqa: F401,F403

from ... import marks
from ...match import squash
from ...theme import current
from ...tree import BeatError, Node
from ..base import Block

W = 10.0     # natural length (u); the layout stretches it into the room it is given
TICK = 0.12  # half height of a numbered tick (u); small ticks are half that


def _range(node: Node) -> tuple[float, float]:
    raw = node.attrs.get("x", "").strip()
    try:
        a, b = (float(eval_num(v)) for v in raw.split(","))
    except (ValueError, TypeError) as e:
        raise BeatError(f'<numberline id={node.id}> needs x="low,high" like "0,3"') from e
    if b <= a:
        raise BeatError(f'<numberline id={node.id}> x="{raw}": the high end must be larger')
    return a, b


def eval_num(v: str) -> float:
    v = v.strip().replace("π", "pi")
    if v.endswith("pi"):
        k = v[:-2].strip() or "1"
        return float(-1 if k == "-" else k) * math.pi
    return float(v)


def _step(a: float, b: float) -> float:
    span = b - a
    for s in (0.1, 0.2, 0.25, 0.5, 1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000):
        if span / s <= 10 + 1e-9:
            return s
    return 10 ** math.ceil(math.log10(span / 10))


def _markers(node: Node) -> list[tuple[str, float]]:
    out = []
    for part in (p.strip() for p in node.attrs.get("markers", "").split(";") if p.strip()):
        name, sep, val = part.rpartition(":")
        if not sep:
            raise BeatError(f'<numberline id={node.id}> markers="{node.attrs["markers"]}": use name:value, '
                            'like "x: 1.5; x^2: 2.25"')
        try:
            out.append((name.strip(), eval_num(val)))
        except ValueError as e:
            raise BeatError(f'<numberline id={node.id}> marker "{part}": the value must be a number') from e
    return out


def _fmt(v: float) -> str:
    return f"{v:.0f}" if abs(v - round(v)) < 1e-9 else f"{v:g}"


class NumberLineBlock(Block):
    tag = "numberline"

    def __init__(self, node: Node):
        super().__init__()
        th = current()
        self.x0, self.x1 = _range(node)
        try:
            self.w = float(node.attrs.get("w", W)) - (0.6 if node.attrs.get("_fill") else 0.0)   # room for end numbers
            step = float(node.attrs["step"]) if node.attrs.get("step") else _step(self.x0, self.x1)
        except ValueError as e:
            raise BeatError(f"<numberline id={node.id}> w= and step= are numbers") from e
        size = marks.size(node, 34)
        self.line = Line(ORIGIN, self.w * RIGHT).set_stroke(th.palette[0], 2.5)
        ticks, nums = VMobject(), VGroup()
        small = step / (5 if abs(step / 10 ** math.floor(math.log10(step)) - 1) < 1e-9
                        or abs(step / 10 ** math.floor(math.log10(step)) - 5) < 1e-9 else 4)
        k0, k1 = math.ceil(self.x0 / small - 1e-9), math.floor(self.x1 / small + 1e-9)
        for k in range(k0, k1 + 1):
            v = k * small
            big = abs(v / step - round(v / step)) < 1e-6
            p = self._at(v)
            h = TICK if big else TICK * 0.5
            ticks.start_new_path(p + DOWN * h)
            ticks.add_line_to(p + UP * h)
            if big and node.attrs.get("numbers", "").strip().lower() not in ("none", "false", "off"):
                nums.add(Tex(_fmt(v), font_size=size).set_fill(th.muted, 1).next_to(p, DOWN, buff=0.18))
        ticks.set_stroke(th.palette[0], 2)
        self.markers = VGroup()
        self.marker_names: list[str] = []
        colors = [c.strip() for c in node.attrs.get("colors", "").split(",") if c.strip()]
        for i, (name, v) in enumerate(_markers(node)):
            if not self.x0 - 1e-9 <= v <= self.x1 + 1e-9:
                raise BeatError(f'<numberline id={node.id}> marker {name}={_fmt(v)} is outside x="{_fmt(self.x0)},'
                                f'{_fmt(self.x1)}"; widen x=')
            color = th.color(colors[i]) if i < len(colors) else (th.accent if i == 0 else th.palette[(i + 1) % 5])
            p = self._at(v)
            tri = Triangle().set_fill(color, 1).set_stroke(width=0).rotate(PI).set_height(0.24)
            tri.next_to(p, UP, buff=0.04)
            g = VGroup(tri)
            if name:
                g.add(marks.halo(marks.label(name, size * 1.25, color)).next_to(tri, UP, buff=0.1))
            self.markers.add(g)
            self.marker_names.append(name)
        self.add(self.line, ticks, nums, self.markers)
        self.view = self.line
        self.set_content(node, "x", "w", "step", "markers", "colors", "numbers", "size")

    def _at(self, v: float) -> np.ndarray:
        return RIGHT * self.w * (v - self.x0) / (self.x1 - self.x0)

    def point(self, x: float, y: float = 0.0) -> np.ndarray:
        a, b = self.line.get_start(), self.line.get_end()
        u = (b - a) / (self.x1 - self.x0)
        return a + (x - self.x0) * u + UP * y * np.linalg.norm(u)

    def bounds(self) -> tuple[float, float, float, float]:
        a, b = self.line.get_start(), self.line.get_end()
        return a[0], a[1] - 1, b[0], b[1] + 1

    def part(self, name: str):
        """A marker by its name (``x``), or ``x=1.5`` (that spot on the line)."""
        n = name.strip()
        if n.startswith("x="):
            try:
                return Dot(self.point(eval_num(n[2:]), 0), radius=0.02).set_opacity(0)
            except ValueError:
                return None
        for g, m in zip(self.markers, self.marker_names):
            if squash(m) == squash(n):
                return g
        return None


def build(node: Node, world=None) -> NumberLineBlock:
    return NumberLineBlock(node)
