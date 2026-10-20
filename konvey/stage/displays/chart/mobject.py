"""``<chart>``: line / area chart from a zero baseline (manimgl)."""

from __future__ import annotations

import numpy as np

from manimlib import *  # noqa: F401,F403

from ...tree import BeatError, Node
from ...theme import current
from ..base import data_list, _num, _label, Block


def parse_series(node: Node) -> list[tuple[str, list[float]]]:
    out = []
    for part in (p for p in node.attrs.get("series", "").split(";") if p.strip()):
        name, sep, vals = part.partition(":")
        if not sep:
            raise BeatError(f'<chart id={node.id}> series "{part[:30]}": use "Name:1,2,3;Other:4,5,6"')
        out.append((name.strip(), [_num(v) for v in vals.split(",") if v.strip()]))
    if not out:
        raise BeatError(f"<chart id={node.id}> needs series=")
    lens = {len(v) for _, v in out}
    if len(lens) != 1 or min(lens) < 2:
        raise BeatError(f"<chart id={node.id}>: every series needs the same number (>= 2) of values")
    return out


def _nice_step(span: float, ticks: int = 5) -> float:
    raw = span / ticks
    mag = 10 ** np.floor(np.log10(raw))
    return float(min((m * mag for m in (1, 2, 2.5, 5, 10)), key=lambda s: abs(s - raw)))


class ChartBlock(Block):
    tag = "chart"

    def __init__(self, node: Node):
        th = current()
        series = parse_series(node)
        n = len(series[0][1])
        xs_raw = [_num(v) for v in data_list(node, "x", required=False)] or [0, n - 1]
        xs = np.array(xs_raw if len(xs_raw) == n else np.linspace(xs_raw[0], xs_raw[1], n))
        fill = node.attrs.get("fill", "none")
        if fill not in ("none", "area", "stack"):
            raise BeatError(f'<chart id={node.id}> fill="{fill}": use none, area or stack')
        ys = np.array([v for _, v in series], float)
        tops = np.cumsum(ys, axis=0) if fill == "stack" else ys
        if node.attrs.get("y"):
            y0, y1 = (_num(v) for v in data_list(node, "y")[:2])
            slack = 0.05 * (y1 - y0)
            for (name, _), top in zip(series, tops):
                if top.min() < y0 - slack or top.max() > y1 + slack:
                    raise BeatError(
                        f'<chart id={node.id}> series "{name}" spans {top.min():g}..{top.max():g}, outside '
                        f'y="{y0:g},{y1:g}": widen y= or drop that series (x positions belong in x=)')
        else:
            y0, y1 = min(0.0, float(tops.min())), max(0.0, float(tops.max()))
            y1 += 0.08 * (y1 - y0 or 1)
        colors = [th.color(c) for c in data_list(node, "colors", required=False)] or list(th.palette)
        w, h = float(node.attrs.get("w", 7)), float(node.attrs.get("h", 3.8))
        x_step, y_step = _nice_step(xs[-1] - xs[0]), _nice_step(y1 - y0)
        # manimgl's Axes always spans the origin, so a range like 81..89 is built as 0..8
        # and shifted: c2p takes the real coordinates.
        x0 = float(xs[0])
        axes = Axes((0, xs[-1] - x0, x_step), (0, y1 - y0, y_step), width=w, height=h,
                    axis_config={"stroke_color": th.muted, "stroke_width": 1.5, "include_tip": False})
        self.axes = axes
        self.c2p = c2p = lambda x, y: axes.c2p(x - x0, y - y0)
        tick = 0.65 * float(node.attrs.get("size", 30))
        labels = VGroup()
        for v in np.arange(x0, xs[-1] + 1e-9, x_step):           # where the axis draws its ticks
            labels.add(_label(f"{v:g}", tick, th.muted).next_to(c2p(v, y0), DOWN, buff=0.12))
        for v in np.arange(y0, y1 + 1e-9, y_step):
            labels.add(_label(f"{v:g}", tick, th.muted).next_to(c2p(xs[0], v), LEFT, buff=0.12))
        parts = [axes, labels]
        if y0 < 0 < y1:
            parts.append(DashedLine(c2p(xs[0], 0), c2p(xs[-1], 0)).set_stroke(th.muted, 1))
        self.lines, self.areas, ends = VGroup(), VGroup(), []
        self.series_names = [name for name, _ in series]   # parts by name (konvey.stage.parts)
        below = np.zeros(n)
        for k, ((name, _), top) in enumerate(zip(series, tops)):
            color = colors[k % len(colors)]
            pts = [c2p(x, y) for x, y in zip(xs, top)]
            line = VMobject().set_points_as_corners(pts).set_stroke(color, 4)
            self.lines.add(line)
            if fill != "none":
                base = below if fill == "stack" else np.zeros(n)
                low = [c2p(x, max(y0, y)) for x, y in zip(xs[::-1], base[::-1])]
                self.areas.add(Polygon(*pts, *low).set_fill(color, 0.35 if fill == "stack" else 0.18)
                               .set_stroke(width=0))
            below = top
            ends.append([_label(name, 0.8 * float(node.attrs.get("size", 30)), color), pts[-1]])
        # Legend at the line ends, pushed apart so names never overlap.
        ends.sort(key=lambda e: e[1][1])
        gap, last = 0.34, -np.inf
        legend = VGroup()
        for lab, p in ends:
            y = max(p[1], last + gap)
            lab.move_to([p[0] + 0.15 + lab.get_width() / 2, y, 0])
            last = y
            legend.add(lab)
        self.marks = VGroup()
        for m in (s.strip() for s in node.attrs.get("mark", "").split(";") if s.strip()):
            key, _, arg = m.partition(":")
            if key == "x":
                xv = _num(arg)
                self.marks.add(DashedLine(c2p(xv, y0), c2p(xv, y1)).set_stroke(th.accent, 2))
                continue
            names = [s for s, _ in series]
            if key not in names or arg not in ("max", "min"):
                raise BeatError(f'<chart id={node.id}> mark="{m}": use "x:VALUE" or "NAME:max|min" '
                                f"with NAME one of {names}")
            k = names.index(key)
            j = int(np.argmax(tops[k]) if arg == "max" else np.argmin(tops[k]))
            p = c2p(xs[j], tops[k][j])
            dot = Dot(p, radius=0.07, fill_color=th.accent)
            guide = DashedLine(c2p(xs[j], y0), p).set_stroke(th.accent, 1.5)
            val = series[k][1][j]
            txt = _label(f"{val:g}", tick * 1.3, th.accent).next_to(p, UP + LEFT, buff=0.08)
            self.marks.add(VGroup(guide, dot, txt))
        for m in [*legend, *(g[-1] for g in self.marks if isinstance(g, VGroup))]:
            m.set_backstroke(th.bg, 6)   # stays readable where it crosses a line
        parts += [self.areas, self.lines, legend, self.marks]
        for key in ("xlabel", "ylabel"):
            if node.attrs.get(key):
                lab = _label(node.attrs[key], tick * 1.2, th.muted)
                if key == "xlabel":
                    lab.next_to(labels, DOWN, buff=0.1).align_to(axes, RIGHT)
                else:
                    lab.next_to(axes, UP, buff=0.15).align_to(axes, LEFT)
                parts.append(lab)
        super().__init__(*parts)
        self.set_content(node, "series", "x", "y", "fill")


def build(node: Node, world=None) -> ChartBlock:
    return ChartBlock(node)
