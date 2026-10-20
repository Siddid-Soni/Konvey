"""``<relation>``: one or two lists of items and the weight of every pair between them (manimgl).

The column items sit in a row across the top. Under them, ``view="grid"`` draws the pattern: the
row items down the left and a dot per (row, column) sized by its weight. ``view="links"`` draws
the items instead: with one list, arrows arc from the related items into the ``focus`` item; with
two lists, the row items sit in a second line under the columns and a line joins each pair, as
thick as its weight.

Every part sits on one canvas reserved for the whole scene (``_room``), so between beats the
items stay put and the story plays out under them: a grid grows out of the items (each row label
flies from its item), raw weights are normalised column by column (or row by row) under a
sweeping frame, a mask strikes the cells of later items, a focus frame slides to the next item,
and arrows or lines grow from the related items. The focus column's weights are ``sources``: a
``<vector>`` or label beside the picture that takes one of them takes it from here."""

from __future__ import annotations

import numpy as np

from manimlib import *  # noqa: F401,F403

from ...theme import current
from ...tree import BeatError, Node
from ..base import Block, _label, _swap
from . import (VIEWS, cell_num, groups_of, item_index, items_of, list_problems, mask_of, masked, norm_of,
               room_of, truthy, two_lists, view_of, weight_problems)

ROW = 0.68            # grid row height, per unit of size (size 30 = 1 unit)
MIN_COL = 1.1         # narrowest column: room for a dot and "0.42"
WORD_H = 0.52
LINK_GAP = 2.6        # two lists in the links view: the rows' line sits this far under the columns
LINK_MIN = 0.04       # a weight below this draws no arrow or line (the eye reads it as "unrelated")
DIM = 0.35            # opacity factor of the cells outside the focus
NEG = 3               # palette index of negative weights (dusty rose)
VALUE = 2             # palette index of values travelling along the links (clay)
ROWC = 0              # palette index of row items (slate blue); columns take the accent


def _ramp(f: float, end: str) -> str:
    """Muted (weak) to ``end`` (strong) in perceived lightness, like the grid's heat ramp."""
    a, b = np.array(color_to_rgb(current().muted)), np.array(color_to_rgb(end))
    t = float(np.clip(f, 0, 1))
    return rgb_to_hex(np.sqrt(a ** 2 + (b ** 2 - a ** 2) * t))


def _word(text: str, size: float, color: str) -> VMobject:
    """An item whose glyphs keep their baseline: typeset after "hg" (an ascender and a descender),
    so every item's box centres on the same line, then the helper glyphs are dropped."""
    if "\\" in text:
        return _label(text, size, color)
    full = _label("hg" + text, size, color)
    if len(full.submobjects) <= 2:
        return _label(text, size, color)
    word = VGroup(*full.submobjects[2:])
    word.shift(full.get_center()[1] * DOWN)
    return word.set_x(0)


def _box(t: VMobject, u: float, color: str, fill: float, lit: bool, w: float | None = None) -> VGroup:
    box = RoundedRectangle(w or t.get_width() + 0.3 * u, WORD_H * u, corner_radius=0.1 * u)
    box.set_fill(color, fill).set_stroke(color, 1.5)
    if lit:
        box.set_fill(color, 0.3 if fill < 0.2 else fill + 0.1).set_stroke(color, 3)
    return VGroup(box, t)


class RelationBlock(Block):
    tag = "relation"

    def __init__(self, node: Node):
        th = current()
        a = node.attrs
        where = f"<relation id={node.id}>"
        cols = items_of(a.get("cols", ""))
        if not cols:
            raise BeatError(f'{where} needs cols="a,fluffy,blue,creature" (the items across the top)')
        two = two_lists(a)
        rows = items_of(a.get("rows", "")) if two else cols
        view = view_of(a)
        mask, norm = mask_of(a.get("mask")), norm_of(a.get("normalize"))
        problems = list_problems(cols, rows if two else cols, mask, view)
        if norm not in ("none", "columns", "rows"):
            problems.append(f'normalize="{a.get("normalize")}": use "columns" or "rows"')
        if problems:
            raise BeatError(f"{where} " + "; ".join(problems))
        n, m = len(cols), len(rows)
        size = float(a.get("size", 30))
        u = size / 30
        self.unit, self.n, self.m, self.cols, self.rows, self.two = u, n, m, cols, rows, two
        numbers = truthy(a.get("numbers", ""))
        weights = groups_of(a.get("weights", ""))
        if weights:
            problems = weight_problems(cols, rows, weights, norm, mask)
            if problems:
                raise BeatError(f"{where} " + "; ".join(problems))
        focus = item_index(a.get("focus", ""), cols, f"{where} focus")
        frow = item_index(a.get("focus-row", ""), rows, f"{where} focus-row")
        room = room_of(a.get("_room", ""))
        scale = float(a.get("_scale", 0) or 0) or max(
            (abs(v) for g in weights for v in map(cell_num, g) if v is not None and np.isfinite(v)), default=1.0)
        self.view, self.mask, self.norm, self.focus = view, mask, norm, focus
        self.op = a.get("op", "").strip() or "normalize"
        grid_on = view in ("grid", "both") and bool(weights)
        links2_on = two and view == "links"
        arrows_on = not two and view in ("links", "both") and focus is not None and bool(weights) \
            and bool(weights[focus])
        self.grid_on, self.links2_on = grid_on, links2_on

        # --- the column items: one column each, shared by every view -----------------------------
        texts = [_word(t, size, th.ink) for t in cols]
        cw = max(MIN_COL * u, max(t.get_width() for t in texts) + 0.5 * u)
        self.cw = cw
        xs = [j * cw for j in range(n)]
        self.xs = xs
        self.words = VGroup()
        for j, t in enumerate(texts):
            g = _box(t, u, th.accent if j == focus else th.muted, 0.2 if j == focus else 0.16, j == focus)
            if j == focus:
                t.set_fill(th.accent)
            g.move_to([xs[j], 0, 0])
            t.set_x(xs[j])
            self.words.add(g)
        top, below = WORD_H * u / 2, -WORD_H * u / 2 - 0.18 * u

        grid_top = below
        self.grid_top = grid_top

        # --- the grid: rows down the left, a dot per (row, column) --------------------------------
        self.keys, self.lines, self.cells = VGroup(), VGroup(), VGroup()
        self.frame, self.kframe = VGroup(), VGroup()
        ch = ROW * u
        self.ch = ch
        key_texts = [_word(t, size, th.ink) for t in rows]
        key_w = max(t.get_width() for t in key_texts) + 0.3 * u
        left = xs[0] - cw / 2                       # the grid's left edge
        right = xs[-1] + cw / 2
        gx0 = left - 0.2 * u                       # the row labels' right edge
        if grid_on:
            for r, t in enumerate(key_texts):
                y = grid_top - (r + 0.5) * ch
                g = _box(t, u, th.palette[ROWC], 0.12, r == frow, key_w)
                g[0].move_to([gx0 - key_w / 2, y, 0])
                t.move_to(g[0]).set_y(y)
                self.keys.add(g)
            bottom = grid_top - m * ch
            for r in range(m + 1):
                self.lines.add(Line([left, grid_top - r * ch, 0], [right, grid_top - r * ch, 0]))
            for c in range(n + 1):
                self.lines.add(Line([left + c * cw, grid_top, 0], [left + c * cw, bottom, 0]))
            self.lines.set_stroke(th.muted, 1, 0.55)
            dmax = 0.86 * min(cw, ch)
            for r in range(m):
                for c in range(n):
                    self.cells.add(self._cell(weights[c][r] if weights[c] else "", r, c, xs[c],
                                              grid_top - (r + 0.5) * ch, dmax, scale, numbers, size, focus, frow))
            if frow is not None:
                y = grid_top - (frow + 0.5) * ch
                self.kframe.add(RoundedRectangle(right - (gx0 - key_w) + 0.16 * u, ch * 0.96, corner_radius=0.1 * u)
                                .set_stroke(th.palette[ROWC], 3).set_fill(opacity=0)
                                .move_to([(right + gx0 - key_w) / 2, y, 0]))

        # --- two lists, links view: the rows' line under the columns ------------------------------
        rw = max(MIN_COL * u, max(t.get_width() for t in key_texts) + 0.5 * u)
        cx = (xs[0] + xs[-1]) / 2
        xr = [cx + (r - (m - 1) / 2) * rw for r in range(m)]
        row_y = -LINK_GAP * u
        self.rowwords = VGroup()
        for r in range(m):
            if not links2_on:
                self.rowwords.add(VGroup())
                continue
            t = _word(rows[r], size, th.ink)
            g = _box(t, u, th.palette[ROWC], 0.12, r == frow)
            g.move_to([xr[r], row_y, 0])
            t.set_x(xr[r])
            self.rowwords.add(g)

        # --- links: arcs into the focus (one list) or lines between the lists (two) ---------------
        self.arrows = VGroup()       # one list: per row item, its arc into the focus column
        self.links = VGroup()        # two lists: per (row, column), the line joining them
        apex_room = 0.0
        if arrows_on:
            col = weights[focus]
            srcs = []
            for j in range(n):
                v = cell_num(col[j]) if j < len(col) else None
                if j == focus or v is None or not np.isfinite(v) or masked(j, focus, mask):
                    continue
                f = v if norm != "none" else v / scale
                if f >= LINK_MIN:
                    srcs.append((j, f, col[j]))
            ends = sorted(srcs, key=lambda s: xs[s[0]])
            box_w = self.words[focus][0].get_width()
            spread = min(0.2 * u, (box_w - 0.25 * u) / max(len(ends), 1)) if ends else 0
            end_x = {s[0]: (xs[focus] + (i - (len(ends) - 1) / 2) * spread) for i, s in enumerate(ends)}
        for j in range(m if not two else 0):
            hit = next((s for s in srcs if s[0] == j), None) if arrows_on else None
            if hit is None:
                self.arrows.add(VGroup())
                continue
            _, f, text = hit
            p = np.array([xs[j], top + 0.06 * u, 0])
            q = np.array([end_x[j], top + 0.06 * u, 0])
            d = abs(q[0] - p[0])
            h = 0.3 * u + 0.16 * d
            theta = 4 * np.arctan(2 * h / d) * (-1 if p[0] < q[0] else 1)
            color = _ramp(0.35 + 0.65 * f, th.accent)
            arrow = Arrow(p, q, buff=0, path_arc=theta, thickness=(2 + 7 * f) * u, fill_color=color)
            path = Line(p, q, path_arc=theta).set_stroke(color, 1, 0)   # the arc, for travelling values
            lab = VGroup()
            if norm != "none":
                lab = _label(str(text), size * 0.72, color)
                lab.label_text = str(text)
                # beside the arrow's tail, on the side away from the focus: the arcs of the other
                # items pass high above this spot, so labels never meet an arc or each other
                side = -1 if p[0] < q[0] else 1
                lab.move_to([p[0] + side * (lab.get_width() / 2 + 0.12 * u), top + 0.3 * u, 0]).set_backstroke(th.bg, 5)
            self.arrows.add(VGroup(arrow, lab, path))
            apex_room = max(apex_room, h + 0.4 * u)
        for r in range(m if two else 0):
            for c in range(n):
                v = cell_num(weights[c][r]) if links2_on and weights and weights[c] else None
                f = 0.0 if v is None or not np.isfinite(v) else (v if norm != "none" else v / scale)
                if not links2_on or f < LINK_MIN or (focus is not None and c != focus):
                    self.links.add(VGroup())
                    continue
                f = min(1.0, f)
                p = np.array([xr[r], row_y + WORD_H * u / 2 + 0.04 * u, 0])
                q = np.array([xs[c], -WORD_H * u / 2 - 0.04 * u, 0])
                lit = frow is None or r == frow
                color = _ramp(0.35 + 0.65 * f, th.accent)
                line = Line(p, q).set_stroke(color, (1.5 + 8 * f) * u, 0.9 if lit else 0.9 * DIM)
                path = Line(p, q).set_stroke(color, 1, 0)
                lab = VGroup()
                if norm != "none" and focus is not None:
                    lab = _label(weights[c][r], size * 0.72, color)
                    lab.label_text = weights[c][r]
                    lab.move_to(p + 0.28 * (q - p)).shift(0.28 * u * (LEFT if q[0] > p[0] else RIGHT))
                    lab.set_backstroke(th.bg, 5)
                self.links.add(VGroup(line, lab, path))

        if focus is not None:
            low = (grid_top - m * ch) if grid_on else below + 0.1 * u
            hi = top + 0.1 * u
            self.frame.add(RoundedRectangle(cw - 0.08 * u, hi - low + 0.1 * u, corner_radius=0.14 * u)
                           .set_stroke(th.accent, 3).set_fill(opacity=0)
                           .move_to([xs[focus], (hi + low) / 2 - 0.05 * u, 0]))

        # --- the canvas reserved for the whole scene ------------------------------------------
        m_room = max(m, room.get("rows", m))
        arcs_h = (0.3 * u + 0.16 * room["arcs"] * cw + 0.4 * u) if room.get("arcs") else 0.0
        tops = [top, top + arcs_h, top + apex_room]
        floors = [below]
        if room.get("grid") or grid_on:
            floors.append(grid_top - m_room * ch)
        lefts, rights = [left], [right]
        if room.get("grid") or grid_on:
            lefts.append(gx0 - key_w - 0.1 * u)
        if room.get("links2") or links2_on:
            floors.append(row_y - WORD_H * u / 2 - 0.1 * u)
            lefts.append(xr[0] - rw / 2)
            rights.append(xr[-1] + rw / 2)
        hi, lo, l, rgt = max(tops), min(floors), min(lefts), max(rights)
        canvas = Rectangle(rgt - l, hi - lo + 0.1 * u)
        canvas.move_to([(rgt + l) / 2, (hi + lo) / 2, 0])
        canvas.set_stroke(opacity=0).set_fill(opacity=0)
        self.canvas = canvas
        self.canvas_w0 = canvas.get_width()
        super().__init__(canvas, self.words, self.keys, self.lines, self.cells, self.frame, self.kframe,
                         self.rowwords, self.links, self.arrows)
        self.weights, self.numbers = weights, numbers
        self.set_content(node, "cols", "rows", "weights", "normalize", "op", "mask", "focus", "focus-row",
                         "view", "numbers", "size", "_room", "_scale")

    def _cell(self, text: str, r: int, c: int, x: float, y: float, dmax: float, scale: float,
              numbers: bool, size: float, focus, frow) -> VGroup:
        """One (row r, column c) cell: a mask mark, a dot sized by the weight (its area, so 0.5 looks
        half of 1), and the number when ``numbers`` is on. Every part always exists (invisible when
        unused), so a cell morphs into its next look part by part."""
        th = current()
        u = self.unit
        v = cell_num(text)
        normed = self.norm != "none"
        hide = masked(r, c, self.mask)
        mark = Square(0.8 * min(self.cw, self.ch)).move_to([x, y, 0])
        mark.set_stroke(th.palette[VALUE], 1.5, 0.4 if hide else 0).set_fill(th.palette[VALUE], 0.07 if hide else 0)
        f = 0.0 if v is None or hide or not np.isfinite(v) else (v if normed else v / scale)
        neg = f < 0
        f = min(1.0, abs(f))
        color = th.palette[NEG] if neg else _ramp(0.25 + 0.75 * f, th.accent)
        show_dot = not numbers and f > 0
        dot = Circle(radius=max(0.5 * dmax * np.sqrt(f), 0.004 * u) if show_dot else 0.004 * u)
        dot.set_stroke(width=0).set_fill(color, (0.55 if neg else 0.92) if show_dot else 0).move_to([x, y, 0])
        num = VMobject()
        if numbers and text.strip():
            shown = ("0" if normed else "−∞") if hide else text.strip()
            ink = th.palette[NEG] if neg else (th.palette[VALUE] if hide and not normed else _ramp(0.3 + 0.7 * f, th.ink))
            num = _label(shown.replace("-", "−"), size * 0.7, ink)
            if num.get_width() > 0.86 * self.cw:
                num.set_width(0.86 * self.cw)
            num.move_to([x, y, 0])
            num.label_text = shown
        cell = VGroup(mark, dot, num)
        lit = (focus is None or c == focus) and (frow is None or r == frow)
        if not lit:
            for p in (dot, num):
                for s in p.family_members_with_points():
                    s.set_fill(opacity=float(s.get_fill_opacity()) * DIM)
            mark.set_stroke(opacity=float(mark.get_stroke_opacity()) * DIM)
        return cell

    def scale_now(self) -> float:
        """How much the layout scaled the block since it was built."""
        return self.canvas.get_width() / self.canvas_w0

    def cell(self, r: int, c: int) -> VGroup:
        return self.cells[r * self.n + c]

    def line_box(self, k: int, by_row: bool) -> tuple[np.ndarray, np.ndarray]:
        """The drawn (layout-moved) bounds of column k's cells, or row k's with ``by_row``."""
        cells = [self.cell(k, c)[0] for c in range(self.n)] if by_row else [self.cell(r, k)[0] for r in range(self.m)]
        lo = np.min([p.get_corner(DL) for p in cells], axis=0)
        hi = np.max([p.get_corner(UR) for p in cells], axis=0)
        return lo, hi


# --- motion ------------------------------------------------------------------------------------
def _at(anim: Animation, lo: float, hi: float) -> Animation:
    anim.rate_func = squish_rate_func(smooth, max(0.0, lo), min(1.0, hi))
    return anim


def _drawn(m: Mobject) -> bool:
    return bool(m.family_members_with_points())


def _part(a: VGroup, b: VGroup, lo: float, hi: float, enter=None) -> Animation:
    """Old part into new: both drawn -> Transform; only new -> enters (``enter`` or a fade);
    only old -> fades out early."""
    has_a, has_b = _drawn(a), _drawn(b)
    if has_a and has_b:
        if len(a.submobjects) == len(b.submobjects) or not a.submobjects:
            return _at(Transform(a, b), lo, hi)
        return _at(FadeTransform(a, b), lo, hi)
    if has_b:
        return _at(enter(b) if enter else FadeIn(b), lo, hi)
    if has_a:
        return _at(FadeOut(a), 0.0, min(hi, 0.3))
    return Animation(Mobject())


def _sweep(new: RelationBlock, lo: float, hi: float) -> Animation:
    """A frame with the ``op`` name under it visits the columns (or rows) one by one while each
    one's dots resize to their normalised weights. A carrier of fixed structure, removed after."""
    th = current()
    k = new.scale_now()
    by_row = new.norm == "rows"
    rect = Rectangle(1, 1).set_stroke(th.accent, 4).set_fill(opacity=0)
    lab = _label(new.op, 22 * new.unit * k, th.accent).set_backstroke(th.bg, 5)
    carrier = VGroup(rect, lab)
    carrier.fix_in_frame()        # overlay space (a fresh mobject is not)
    count = new.m if by_row else new.n
    boxes = [new.line_box(i, by_row) for i in range(count)]

    def update(mob, alpha):
        r, lb = mob
        t = (alpha - lo) / ((hi - lo) or 1)
        if t <= 0 or t >= 1:
            mob.set_opacity(0)
            return
        pos = t * count
        c = min(count - 1, int(pos))
        frac = pos - c
        # glide into the line during the first quarter of its turn, then rest there
        prev = boxes[max(c - 1, 0)]
        g = smooth(min(1.0, frac / 0.25)) if c > 0 else 1.0
        a_lo, a_hi = (prev[0] + (boxes[c][0] - prev[0]) * g), (prev[1] + (boxes[c][1] - prev[1]) * g)
        pad = 0.05 * new.unit * k
        r.set_width(a_hi[0] - a_lo[0] + 2 * pad, stretch=True).set_height(a_hi[1] - a_lo[1] + 2 * pad, stretch=True)
        r.move_to((a_lo + a_hi) / 2)
        if by_row:
            lb.next_to(r, RIGHT, buff=0.12 * new.unit * k)
        else:
            lb.next_to(r, DOWN, buff=0.1 * new.unit * k)
        seen = min(1.0, 10 * t, 10 * (1 - t))
        r.set_stroke(opacity=seen)
        lb.set_fill(opacity=seen)
        lb.set_backstroke(th.bg, 5)
    return UpdateFromAlphaFunc(carrier, update, rate_func=linear, remover=True)


def _fly(a: Mobject, b: Mobject, lo: float, hi: float) -> Animation:
    """A copy of ``a`` moves and turns into ``b`` (an item becoming its row label); removed after,
    the new block then shows ``b`` there."""
    src = a.copy()
    src.fix_in_frame()
    return _at(Transform(src, b.copy().fix_in_frame(), remover=True), lo, hi)


def _grid(old: RelationBlock, new: RelationBlock) -> list[Animation]:
    n, m = new.n, new.m
    anims: list[Animation] = []
    if new.grid_on and not old.grid_on:
        # each row label leaves its item (a column item, or the second line's) and settles at its row
        srcs = old.rowwords if old.two else old.words
        for r in range(m):
            lo = 0.1 + 0.36 * r / m
            if r < len(srcs) and _drawn(srcs[r]):
                anims.append(_fly(srcs[r], new.keys[r], lo, lo + 0.36 / m + 0.1))
                if old.two:       # the second line's item itself leaves with its copy
                    anims.append(_at(FadeOut(srcs[r]), lo, lo + 0.04))
            else:
                anims.append(_at(FadeIn(new.keys[r], shift=0.2 * RIGHT), lo, lo + 0.36 / m + 0.1))
        anims.append(_at(ShowCreation(new.lines, lag_ratio=0.05), 0.4, 0.68))
        for k, cell in enumerate(new.cells):
            r = k // n
            anims.append(_at(GrowFromCenter(cell), 0.55 + 0.25 * r / m, 0.78 + 0.2 * r / m))
        return anims
    if old.grid_on and not new.grid_on:
        if new.links2_on:     # the row labels drop back into their own line
            for r in range(m):
                lo = 0.05 + 0.3 * r / m
                anims.append(_fly(old.keys[r], new.rowwords[r], lo, lo + 0.3))
                anims.append(_at(FadeOut(old.keys[r]), lo, lo + 0.04))
            anims += [_at(FadeOut(p), 0.0, 0.3) for p in (old.lines, old.cells)]
        else:
            anims += [_at(FadeOut(p), 0.0, 0.3) for p in (old.keys, old.lines, old.cells)]
        return anims
    if not new.grid_on:
        return anims
    anims += [_at(Transform(a, b), 0.0, 0.5) for a, b in zip(old.keys, new.keys)]
    anims.append(_at(Transform(old.lines, new.lines), 0.0, 0.5))
    add_mask = new.mask == "later" and old.mask != "later"
    to_norm = new.norm != "none" and old.norm != new.norm
    count = m if new.norm == "rows" else n
    m_end = 0.4 if to_norm else 0.9
    s_lo = m_end if add_mask else 0.05
    order = [k for k in range(n * m) if masked(k // n, k % n, new.mask)]
    for k, (a, b) in enumerate(zip(old.cells, new.cells)):
        r, c = divmod(k, n)
        line = r if new.norm == "rows" else c
        if add_mask and k in order:
            i = order.index(k)
            lo = 0.05 + (m_end - 0.15) * i / max(len(order), 1)
            win = (lo, lo + 0.12)
        elif to_norm:
            lo = s_lo + (0.98 - s_lo) * (line + 0.2) / count
            win = (lo, s_lo + (0.98 - s_lo) * (line + 1) / count)
        else:
            win = (0.1, 0.9)
        anims += [_at(Transform(a[0], b[0]), *win), _at(Transform(a[1], b[1]), *win)]
        anims.append(_at(Transform(a[2], b[2]) if _txt(a[2]) == _txt(b[2]) else _swap(a[2], b[2]), *win))
    if to_norm:
        anims.append(_sweep(new, s_lo, 0.99))
    return anims


def _links(old: RelationBlock, new: RelationBlock) -> list[Animation]:
    """Arcs (one list) or lines (two lists): kept ones reshape, new ones grow from their source
    item."""
    anims: list[Animation] = []
    same_target = old.focus == new.focus
    pairs = list(zip(old.arrows, new.arrows)) + list(zip(old.links, new.links))
    for i, (a, b) in enumerate(pairs):
        has_a, has_b = _drawn(a), _drawn(b)
        if has_a and has_b and (same_target or new.two):
            anims.append(_at(Transform(a[0], b[0]), 0.0, 0.4))
            anims.append(_at(Transform(a[2], b[2]), 0.0, 0.4))
            anims.append(_at(_swap(a[1], b[1]) if _txt(a[1]) != _txt(b[1]) else Transform(a[1], b[1]), 0.0, 0.4))
            continue
        if has_a:
            anims.append(_at(FadeOut(a), 0.0, 0.25))
        if has_b:
            if new.two:
                lo = 0.2 + 0.25 * (i // new.n) / max(new.m, 1)
                anims.append(_at(ShowCreation(b[0]), lo, lo + 0.3))
            else:
                d = abs(b[0].get_start()[0] - b[0].get_end()[0]) / (new.cw * new.scale_now() * max(new.n - 1, 1))
                lo = 0.15 + 0.15 * d
                anims.append(_at(GrowArrow(b[0]), lo, lo + 0.3))
            anims.append(_at(FadeIn(b[1]), lo + 0.2, lo + 0.35))
    return anims


def _relation(old: RelationBlock, new: RelationBlock) -> Animation:
    """Same items. What changed plays as a mechanism, in this order: what leaves fades (0-25%);
    a new grid grows out of the items (row labels fly from their items, lines draw, dots grow row
    by row); a new mask strikes the cells of later items one by one; raw weights turn into
    normalised ones line by line under a sweeping frame; any other change of weights resizes the
    dots together. The focus frame slides; new arrows or lines grow from the related items."""
    anims: list[Animation] = []
    anims += [_at(Transform(a, b), 0.0, 0.4) for a, b in zip(old.words, new.words)]
    anims.append(_at(Transform(old.canvas, new.canvas), 0.0, 0.4))
    anims += _grid(old, new)
    if not ((old.links2_on and new.grid_on) or (old.grid_on and new.links2_on)):   # else _grid flies them
        anims += [_part(a, b, 0.05, 0.45, enter=lambda p: FadeIn(p, shift=0.3 * DOWN))
                  for a, b in zip(old.rowwords, new.rowwords)]
    anims.append(_part(old.frame, new.frame, 0.0, 0.45, enter=lambda p: ShowCreation(p)))
    anims.append(_part(old.kframe, new.kframe, 0.0, 0.45, enter=lambda p: ShowCreation(p)))

    anims += _links(old, new)
    return AnimationGroup(*anims)


def _txt(m: Mobject) -> str:
    """The text a label shows (kept on it when built; a Text keeps no string)."""
    return getattr(m, "label_text", "")


def sources(new: RelationBlock, old) -> list:
    """The focus column's weights are the ones being read: a number elsewhere (a vector entry, a
    label) that changes to one of them takes it from its cell, arc or line."""
    f = new.focus
    if f is None or not new.weights or not new.weights[f]:
        return []
    # read from the block on screen when it draws the same thing (the new one is not drawn yet)
    same = isinstance(old, RelationBlock) and (old.cols, old.rows, old.focus, old.grid_on, old.numbers,
                                               old.weights) == (new.cols, new.rows, f, new.grid_on, new.numbers,
                                                                new.weights)
    new = old if same else new
    out = []
    for r, v in enumerate(new.weights[f]):
        if not v.strip():
            continue
        if new.grid_on and new.numbers:
            out.append((v, new.cell(r, f)[2]))
        elif new.two and _drawn(new.links[r * new.n + f]) and _drawn(new.links[r * new.n + f][1]):
            out.append((v, new.links[r * new.n + f][1]))
        elif not new.two and r < len(new.arrows) and _drawn(new.arrows[r]) and _drawn(new.arrows[r][1]):
            out.append((v, new.arrows[r][1]))
    return out


def build(node: Node, world=None) -> RelationBlock:
    return RelationBlock(node)


def morph(old: RelationBlock, new: RelationBlock, sources=None) -> Animation | None:
    if old.cols != new.cols or old.rows != new.rows:
        return AnimationGroup(FadeOut(old, rate_func=squish_rate_func(smooth, 0, 0.4)),
                              FadeIn(new, rate_func=squish_rate_func(smooth, 0.4, 1)))
    return _relation(old, new)
