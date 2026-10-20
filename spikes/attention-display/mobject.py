"""``<attention>``: a row of words, the attention pattern under it (queries across the top, keys
down the left, dots sized by weight), arrows from attended words into a focus word, and short
vectors under the words (manimgl).

Every part sits on one canvas reserved for the whole scene (``_room``), so between beats the
words stay put and the mechanism plays out under them: a grid grows out of the words (each key
label flies from its word), raw scores turn into softmax weights column after column, a causal
mask strikes the cells above the diagonal, a focus frame slides to the next word, arrows grow
from the attended words and a value travels along each one into the focus word's vector."""

from __future__ import annotations

import numpy as np

from manimlib import *  # noqa: F401,F403

from ...theme import current
from ...tree import BeatError, Node
from ..base import Block, _label, _swap
from . import (MAX_TOKENS, VIEWS, cell_num, groups_of, masked, room_of, token_index, tokens_of,
               truthy, weight_problems)

ROW = 0.68            # grid row height, per unit of size (size 30 = 1 unit)
MIN_COL = 1.1         # narrowest column: room for a dot and "0.42"
WORD_H = 0.52
VEC_ROW = 0.42        # one vector entry
ARROW_MIN = 0.04      # a weight below this draws no arrow (the eye reads it as "not attending")
DIM = 0.35            # opacity factor of the cells outside the focus
NEG = 3               # palette index of negative scores (dusty rose)
VALUE = 2             # palette index of values travelling along the arrows (clay)
KEY = 0               # palette index of keys (slate blue); queries take the accent


def _ramp(f: float, end: str) -> str:
    """Muted (weak) to ``end`` (strong) in perceived lightness, like the grid's heat ramp."""
    a, b = np.array(color_to_rgb(current().muted)), np.array(color_to_rgb(end))
    t = float(np.clip(f, 0, 1))
    return rgb_to_hex(np.sqrt(a ** 2 + (b ** 2 - a ** 2) * t))


def _word(text: str, size: float, color: str) -> VMobject:
    """A word whose glyphs keep their baseline: typeset after "hg" (an ascender and a descender),
    so every word's box centres on the same line, then the helper glyphs are dropped."""
    if "\\" in text:
        return _label(text, size, color)
    full = _label("hg" + text, size, color)
    if len(full.submobjects) <= 2:
        return _label(text, size, color)
    word = VGroup(*full.submobjects[2:])
    word.shift(full.get_center()[1] * DOWN)
    return word.set_x(0)


def _bracket(h: float, w: float, side: int, color: str, u: float) -> VMobject:
    """One square bracket of a column vector."""
    lip = 0.08 * u * side
    x = side * w / 2
    m = VMobject().set_points_as_corners([[x - lip, h / 2, 0], [x, h / 2, 0], [x, -h / 2, 0], [x - lip, -h / 2, 0]])
    return m.set_stroke(color, 2).set_fill(opacity=0)


def _sym(letter: str, i: int, size: float, color: str) -> VMobject:
    return Tex(rf"\vec{{\mathbf{{{letter}}}}}_{{{i + 1}}}", font_size=size * 1.05).set_fill(color, 1)


class AttentionBlock(Block):
    tag = "attention"

    def __init__(self, node: Node):
        th = current()
        where = f"<attention id={node.id}>"
        toks = tokens_of(node.attrs.get("tokens", ""))
        if len(toks) < 2:
            raise BeatError(f'{where} needs tokens="a,fluffy,blue,creature" (2 or more words)')
        if len(toks) > MAX_TOKENS:
            raise BeatError(f"{where} has {len(toks)} tokens; at most {MAX_TOKENS} stay readable")
        n = len(toks)
        size = float(node.attrs.get("size", 30))
        u = size / 30
        self.unit, self.n, self.tokens = u, n, toks
        view = node.attrs.get("view", "").strip().lower() or ("grid" if node.attrs.get("weights", "").strip() else "words")
        if view not in VIEWS:
            raise BeatError(f'{where} view="{view}": use one of {", ".join(VIEWS)}')
        mask = node.attrs.get("mask", "").strip().lower() or "none"
        if mask not in ("none", "causal"):
            raise BeatError(f'{where} mask="{mask}": use "causal" or leave it out')
        softmax = truthy(node.attrs.get("softmax", ""))
        numbers = truthy(node.attrs.get("numbers", ""))
        qk = truthy(node.attrs.get("qk", ""))
        weights = groups_of(node.attrs.get("weights", ""))
        if weights:
            problems = weight_problems(toks, weights, softmax, mask)
            if problems:
                raise BeatError(f"{where} " + "; ".join(problems))
        vectors = groups_of(node.attrs.get("vectors", ""))
        if vectors and len(vectors) != n:
            raise BeatError(f"{where} vectors has {len(vectors)} groups for {n} tokens: one group per token "
                            f'("" for a token without one)')
        if any(len(v) > 6 for v in vectors):
            raise BeatError(f"{where} vectors: at most 6 numbers per token")
        focus = token_index(node.attrs.get("focus", ""), toks, f"{where} focus")
        fkey = token_index(node.attrs.get("focus-key", ""), toks, f"{where} focus-key")
        room = room_of(node.attrs.get("_room", ""))
        scale = float(node.attrs.get("_scale", 0) or 0) or max(
            (abs(v) for g in weights for v in map(cell_num, g) if v is not None and np.isfinite(v)), default=1.0)
        self.view, self.mask, self.softmax, self.focus = view, mask, softmax, focus
        grid_on = view in ("grid", "both") and bool(weights)
        arrows_on = view in ("words", "both") and focus is not None and bool(weights) and bool(weights[focus])
        self.grid_on = grid_on

        # --- the words: one column per token, shared by every view ---------------------------
        texts = [_word(t, size, th.ink) for t in toks]
        cw = max(MIN_COL * u, max(t.get_width() for t in texts) + 0.5 * u)
        self.cw = cw
        xs = [j * cw for j in range(n)]
        self.words = VGroup()
        for j, t in enumerate(texts):
            box = RoundedRectangle(t.get_width() + 0.3 * u, WORD_H * u, corner_radius=0.1 * u)
            box.set_fill(th.muted, 0.16).set_stroke(th.muted, 1.5)
            if j == focus:
                box.set_fill(th.accent, 0.2).set_stroke(th.accent, 3)
                t.set_fill(th.accent)
            g = VGroup(box, t)
            g.move_to([xs[j], 0, 0])
            t.set_x(xs[j])
            self.words.add(g)
        top, below = WORD_H * u / 2, -WORD_H * u / 2 - 0.18 * u

        # --- vectors under the words (words view only: the grid takes their place) ----------------
        self.vectors = VGroup()
        vec_bottom = below
        for j in range(n):
            vals = vectors[j] if vectors and view == "words" else []
            if not vals:
                self.vectors.add(VGroup())
                continue
            ents = VGroup(*(_label(v.replace("-", "−"), size * 0.75, th.ink) for v in vals))
            for e, v in zip(ents, vals):
                e.label_text = v
            ew = max(e.get_width() for e in ents)
            if ew > 0.8 * cw:
                for e in ents:
                    e.scale(0.8 * cw / ew)
                ew = 0.8 * cw
            for r, e in enumerate(ents):
                e.move_to([xs[j], below - 0.1 * u - (r + 0.5) * VEC_ROW * u, 0])
            h = len(vals) * VEC_ROW * u + 0.08 * u
            br = VGroup(_bracket(h, ew + 0.22 * u, -1, th.muted, u), _bracket(h, ew + 0.22 * u, 1, th.muted, u))
            br.move_to([xs[j], below - 0.06 * u - h / 2, 0])
            self.vectors.add(VGroup(br, ents))
            vec_bottom = min(vec_bottom, br.get_bottom()[1])
        vec_room = room.get("vec", max((len(v) for v in vectors), default=0) if view == "words" else 0)
        words_floor = below - (vec_room * VEC_ROW * u + 0.2 * u if vec_room else 0)

        # --- queries and keys (qk): under the words, or framing the grid --------------------------
        self.qsyms, self.ksyms, self.legend = VGroup(), VGroup(), VGroup()
        q_y = below - 0.24 * u if grid_on else words_floor - 0.3 * u
        for j in range(n):
            if not qk:
                self.qsyms.add(VGroup())
                self.ksyms.add(VGroup())
                continue
            q, k = _sym("Q", j, size, th.accent), _sym("K", j, size, th.palette[KEY])
            if grid_on:
                q.move_to([xs[j], q_y, 0])
            else:
                q.move_to([xs[j] - 0.27 * u, q_y, 0])
                k.move_to([xs[j] + 0.27 * u, q_y, 0])
            self.qsyms.add(q)
            self.ksyms.add(k)
        k_w = _sym("K", 0, size, th.ink).get_width() if (qk or room.get("qk")) else 0.0
        grid_top = (below - 0.52 * u) if qk else below
        self.grid_top = grid_top

        # --- the grid: keys down the left, a dot per (key, query) -------------------------------
        self.keys, self.lines, self.cells = VGroup(), VGroup(), VGroup()
        self.frame, self.kframe = VGroup(), VGroup()
        ch = ROW * u
        self.ch = ch
        key_texts = [_word(t, size, th.ink) for t in toks]
        key_w = max(t.get_width() for t in key_texts) + 0.3 * u
        left = xs[0] - cw / 2                       # the grid's left edge
        gx0 = left - 0.2 * u - (k_w + 0.18 * u if k_w else 0)   # the key boxes' right edge
        if grid_on:
            for r, t in enumerate(key_texts):
                y = grid_top - (r + 0.5) * ch
                box = RoundedRectangle(key_w, WORD_H * u, corner_radius=0.1 * u)
                box.set_fill(th.palette[KEY], 0.12).set_stroke(th.palette[KEY], 1.5)
                if r == fkey:
                    box.set_fill(th.palette[KEY], 0.3).set_stroke(th.palette[KEY], 3)
                box.move_to([gx0 - key_w / 2, y, 0])
                t.move_to(box).set_y(y)
                self.keys.add(VGroup(box, t))
                if qk:
                    self.ksyms[r].move_to([left - 0.2 * u - k_w / 2, y, 0])
            right, bottom = xs[-1] + cw / 2, grid_top - n * ch
            for r in range(n + 1):
                self.lines.add(Line([left, grid_top - r * ch, 0], [right, grid_top - r * ch, 0]))
            for c in range(n + 1):
                self.lines.add(Line([left + c * cw, grid_top, 0], [left + c * cw, bottom, 0]))
            self.lines.set_stroke(th.muted, 1, 0.55)
            dmax = 0.86 * min(cw, ch)
            for r in range(n):                      # key r: one row
                for c in range(n):                  # query c: one column
                    self.cells.add(self._cell(weights[c][r] if weights[c] else "", r, c, xs[c],
                                              grid_top - (r + 0.5) * ch, dmax, scale, numbers, size, focus, fkey))
            if fkey is not None:
                y = grid_top - (fkey + 0.5) * ch
                self.kframe.add(RoundedRectangle(right - (gx0 - key_w) + 0.16 * u, ch * 0.96, corner_radius=0.1 * u)
                                .set_stroke(th.palette[KEY], 3).set_fill(opacity=0)
                                .move_to([(right + gx0 - key_w) / 2, y, 0]))
        if focus is not None:
            low = (grid_top - n * ch) if grid_on else min(vec_bottom, below + 0.1 * u)
            if qk and not grid_on:
                low = min(low, q_y - 0.28 * u)
            hi = top + 0.1 * u
            self.frame.add(RoundedRectangle(cw - 0.08 * u, hi - low + 0.1 * u, corner_radius=0.14 * u)
                           .set_stroke(th.accent, 3).set_fill(opacity=0)
                           .move_to([xs[focus], (hi + low) / 2 - 0.05 * u, 0]))

        # --- arrows from the attended words into the focus word -------------------------------
        self.arrows = VGroup()
        apex_room = 0.0
        srcs = []
        if arrows_on:
            col = weights[focus]
            for j in range(n):
                v = cell_num(col[j]) if j < len(col) else None
                if j == focus or v is None or not np.isfinite(v) or masked(j, focus, mask):
                    continue
                f = v if softmax else v / scale
                if f >= ARROW_MIN:
                    srcs.append((j, f, col[j]))
        ends = sorted(srcs, key=lambda s: xs[s[0]])
        box_w = self.words[focus][0].get_width() if focus is not None else 0
        spread = min(0.2 * u, (box_w - 0.25 * u) / max(len(ends), 1)) if ends else 0
        end_x = {s[0]: (xs[focus] + (i - (len(ends) - 1) / 2) * spread) for i, s in enumerate(ends)}
        for j in range(n):
            hit = next((s for s in srcs if s[0] == j), None)
            if hit is None:
                self.arrows.add(VGroup())
                continue
            _, f, text = hit
            a = np.array([xs[j], top + 0.06 * u, 0])
            b = np.array([end_x[j], top + 0.06 * u, 0])
            d = abs(b[0] - a[0])
            h = 0.3 * u + 0.16 * d
            theta = 4 * np.arctan(2 * h / d) * (-1 if a[0] < b[0] else 1)
            color = _ramp(0.35 + 0.65 * f, th.accent)
            arrow = Arrow(a, b, buff=0, path_arc=theta, thickness=(2 + 7 * f) * u, fill_color=color)
            path = Line(a, b, path_arc=theta).set_stroke(color, 1, 0)   # the arc, for travelling values
            lab = VGroup()
            if softmax:
                lab = _label(str(text), size * 0.72, color)
                lab.label_text = str(text)
                # beside the arrow's tail, on the side away from the focus word: the arcs of the
                # other words pass high above this spot, so labels never meet an arc or each other
                side = -1 if a[0] < b[0] else 1
                lab.move_to([a[0] + side * (lab.get_width() / 2 + 0.12 * u), top + 0.3 * u, 0]).set_backstroke(th.bg, 5)
            self.arrows.add(VGroup(arrow, lab, path))
            apex_room = max(apex_room, h + 0.4 * u)

        # --- the canvas reserved for the whole scene ------------------------------------------
        n_room = max(n, room.get("rows", n))
        arcs_h = (0.3 * u + 0.16 * (n_room - 1) * cw + 0.4 * u) if room.get("arcs") or arrows_on else 0.0
        floors = [words_floor]
        if qk or room.get("qk"):
            floors.append((words_floor - 0.6 * u) if not grid_on else q_y - 0.25 * u)
        if room.get("grid") or grid_on:
            floors.append(((below - 0.52 * u) if (qk or room.get("qk")) else below) - n_room * ch)
        lefts = [left]
        if room.get("grid") or grid_on:
            lefts.append(gx0 - key_w - 0.1 * u)
        if qk or room.get("qk"):
            lefts.append(left - 0.2 * u - k_w)
        if qk and not grid_on:
            self.legend.add(*self._legend(size, left - 0.2 * u, q_y))
            lefts.append(self.legend.get_left()[0])
        canvas = Rectangle(xs[-1] + cw / 2 - min(lefts), max(top + max(arcs_h, apex_room), top) - min(floors) + 0.1 * u)
        canvas.move_to([(xs[-1] + cw / 2 + min(lefts)) / 2, (max(top + max(arcs_h, apex_room), top) + min(floors)) / 2, 0])
        canvas.set_stroke(opacity=0).set_fill(opacity=0)
        self.canvas = canvas
        self.canvas_w0 = canvas.get_width()
        super().__init__(canvas, self.words, self.vectors, self.qsyms, self.ksyms, self.legend, self.keys,
                         self.lines, self.cells, self.frame, self.kframe, self.arrows)
        self.weights, self.vector_text = weights, vectors
        self.set_content(node, "tokens", "weights", "softmax", "mask", "focus", "focus-key", "view",
                         "numbers", "vectors", "qk", "size", "_room", "_scale")

    def _cell(self, text: str, r: int, c: int, x: float, y: float, dmax: float, scale: float,
              numbers: bool, size: float, focus, fkey) -> VGroup:
        """One (key r, query c) cell: a mask mark, a dot sized by the weight (its area, so 0.5 looks
        half of 1), and the number when ``numbers`` is on. Every part always exists (invisible when
        unused), so a cell morphs into its next look part by part."""
        th = current()
        u = self.unit
        v = cell_num(text)
        hide = masked(r, c, self.mask)
        mark = Square(0.8 * min(self.cw, self.ch)).move_to([x, y, 0])
        mark.set_stroke(th.palette[VALUE], 1.5, 0.4 if hide else 0).set_fill(th.palette[VALUE], 0.07 if hide else 0)
        f = 0.0 if v is None or hide or not np.isfinite(v) else (v if self.softmax else v / scale)
        neg = f < 0
        f = min(1.0, abs(f))
        color = th.palette[NEG] if neg else _ramp(0.25 + 0.75 * f, th.accent)
        show_dot = not numbers and f > 0
        dot = Circle(radius=max(0.5 * dmax * np.sqrt(f), 0.004 * u) if show_dot else 0.004 * u)
        dot.set_stroke(width=0).set_fill(color, (0.55 if neg else 0.92) if show_dot else 0).move_to([x, y, 0])
        num = VMobject()
        if numbers and text.strip():
            shown = ("0" if self.softmax else "−∞") if hide else text.strip()
            ink = th.palette[NEG] if neg else (th.palette[VALUE] if hide and not self.softmax else _ramp(0.3 + 0.7 * f, th.ink))
            num = _label(shown.replace("-", "−"), size * 0.7, ink)
            if num.get_width() > 0.86 * self.cw:
                num.set_width(0.86 * self.cw)
            num.move_to([x, y, 0])
            num.label_text = shown
        cell = VGroup(mark, dot, num)
        lit = (focus is None or c == focus) and (fkey is None or r == fkey)
        if not lit:
            for m in (dot, num):
                for s in m.family_members_with_points():
                    s.set_fill(opacity=float(s.get_fill_opacity()) * DIM)
            mark.set_stroke(opacity=float(mark.get_stroke_opacity()) * DIM)
        return cell

    def _legend(self, size: float, right: float, y: float) -> list[VMobject]:
        th = current()
        q = Tex(r"\vec{\mathbf{Q}} = W_Q\,\vec{\mathbf{E}}", font_size=size * 0.95).set_fill(th.accent, 1)
        k = Tex(r"\vec{\mathbf{K}} = W_K\,\vec{\mathbf{E}}", font_size=size * 0.95).set_fill(th.palette[KEY], 1)
        q.next_to([right, y, 0], LEFT, buff=0).shift(0.26 * self.unit * UP)
        k.next_to([right, y, 0], LEFT, buff=0).shift(0.26 * self.unit * DOWN)
        k.align_to(q, RIGHT)
        return [q, k]

    def scale_now(self) -> float:
        """How much the layout scaled the block since it was built."""
        return self.canvas.get_width() / self.canvas_w0

    def column_box(self, c: int) -> tuple[np.ndarray, np.ndarray]:
        """The drawn (layout-moved) bounds of query c's column of cells."""
        cells = [self.cells[r * self.n + c][0] for r in range(self.n)]
        lo = np.min([m.get_corner(DL) for m in cells], axis=0)
        hi = np.max([m.get_corner(UR) for m in cells], axis=0)
        return lo, hi


# --- motion ------------------------------------------------------------------------------------
def _at(anim: Animation, lo: float, hi: float) -> Animation:
    anim.rate_func = squish_rate_func(smooth, max(0.0, lo), min(1.0, hi))
    return anim


def _part(a: VGroup, b: VGroup, lo: float, hi: float, enter=None) -> Animation:
    """Old part into new: both drawn -> Transform; only new -> enters (``enter`` or a fade);
    only old -> fades out early."""
    has_a, has_b = bool(a.family_members_with_points()), bool(b.family_members_with_points())
    if has_a and has_b:
        if len(a.submobjects) == len(b.submobjects) or not a.submobjects:
            return _at(Transform(a, b), lo, hi)
        return _at(FadeTransform(a, b), lo, hi)
    if has_b:
        return _at(enter(b) if enter else FadeIn(b), lo, hi)
    if has_a:
        return _at(FadeOut(a), 0.0, min(hi, 0.3))
    return Animation(Mobject())


def _sweep(new: AttentionBlock, lo: float, hi: float) -> Animation:
    """A frame with "softmax" under it visits the columns one by one (while each column's dots
    resize to their normalised weights). A carrier of fixed structure, removed afterwards."""
    th = current()
    k = new.scale_now()
    rect = Rectangle(1, 1).set_stroke(th.accent, 4).set_fill(opacity=0)
    lab = _label("softmax", 22 * new.unit * k, th.accent).set_backstroke(th.bg, 5)
    carrier = VGroup(rect, lab)
    carrier.fix_in_frame()        # overlay space (a fresh mobject is not)
    boxes = [new.column_box(c) for c in range(new.n)]
    n = new.n

    def update(m, alpha):
        r, lb = m
        t = (alpha - lo) / ((hi - lo) or 1)
        if t <= 0 or t >= 1:
            m.set_opacity(0)
            return
        pos = t * n
        c = min(n - 1, int(pos))
        frac = pos - c
        # glide into the column during the first quarter of its turn, then rest there
        prev = boxes[max(c - 1, 0)]
        g = smooth(min(1.0, frac / 0.25)) if c > 0 else 1.0
        a_lo, a_hi = (prev[0] + (boxes[c][0] - prev[0]) * g), (prev[1] + (boxes[c][1] - prev[1]) * g)
        pad = 0.05 * new.unit * k
        r.set_width(a_hi[0] - a_lo[0] + 2 * pad, stretch=True).set_height(a_hi[1] - a_lo[1] + 2 * pad, stretch=True)
        r.move_to((a_lo + a_hi) / 2)
        lb.next_to(r, DOWN, buff=0.1 * new.unit * k)
        seen = min(1.0, 10 * t, 10 * (1 - t))
        r.set_stroke(opacity=seen)
        lb.set_fill(opacity=seen)
        lb.set_backstroke(th.bg, 5)
    return UpdateFromAlphaFunc(carrier, update, rate_func=linear, remover=True)


def _value_packet(path: VMobject, color: str, r: float, lo: float, hi: float) -> Animation:
    """A value dot runs along an arrow's arc between lo and hi, lighting the arc behind it."""
    th = current()
    trail = VMobject().set_points_as_corners([path.get_start(), path.get_start()]).set_stroke(color, 5, 0)
    dot = Dot(radius=r).set_fill(color, 1).set_stroke(th.bg, 2).move_to(path.get_start())
    carrier = VGroup(trail, dot)
    carrier.fix_in_frame()
    samples = [path.point_from_proportion(s) for s in np.linspace(0, 1, 40)]

    def update(m, alpha):
        tr, d = m
        t = float(np.clip((alpha - lo) / ((hi - lo) or 1), 0, 1))
        seen = 0.0 if t <= 0 or t >= 1 else min(1.0, 8 * t, 8 * (1 - t))
        k = max(2, int(round(smooth(t) * 39)) + 1)
        pts = samples[:k]
        tr.set_points_as_corners(pts).set_stroke(color, 5, 0.8 * seen)
        d.move_to(pts[-1]).set_opacity(seen)
    return UpdateFromAlphaFunc(carrier, update, rate_func=linear, remover=True)


def _flash(m: Mobject, lo: float, hi: float) -> Animation:
    """The updated vector's brackets light up once its new numbers are in."""
    ring = SurroundingRectangle(m, buff=0.06).set_stroke(current().accent, 5, 0).set_fill(opacity=0)
    ring.fix_in_frame()

    def glow(r, a):
        t = float(np.clip((a - lo) / ((hi - lo) or 1), 0, 1))
        r.set_stroke(opacity=float(np.sin(PI * t)))
    return UpdateFromAlphaFunc(ring, glow, rate_func=linear, remover=True)


def _fly(a: Mobject, b: Mobject, lo: float, hi: float) -> Animation:
    """A copy of ``a`` moves and turns into ``b`` (a word becoming its key label); removed after,
    the new block then shows ``b`` there."""
    src = a.copy()
    src.fix_in_frame()
    return _at(Transform(src, b.copy().fix_in_frame(), remover=True), lo, hi)


def _attention(old: AttentionBlock, new: AttentionBlock) -> Animation:
    """Same words. What changed plays as a mechanism, in this order: what leaves fades (0-25%);
    a new grid grows out of the words (key labels fly from the words, lines draw, dots grow row
    by row); a new causal mask strikes the cells above the diagonal one by one; raw scores turn
    into softmax weights column by column under a sweeping frame; any other change of weights
    resizes the dots together. The focus frame slides; new arrows grow from the attended words,
    then a value runs along each arrow and the focus word's vector changes when they arrive."""
    n = new.n
    anims: list[Animation] = []
    anims += [_at(Transform(a, b), 0.0, 0.4) for a, b in zip(old.words, new.words)]
    anims.append(_at(Transform(old.canvas, new.canvas), 0.0, 0.4))
    anims.append(_part(old.legend, new.legend, 0.1, 0.5))
    for j in range(n):
        anims.append(_part(old.qsyms[j], new.qsyms[j], 0.15 + 0.03 * j, 0.45 + 0.03 * j,
                           enter=lambda m, w=new.words[j]: FadeIn(m, shift=0.25 * DOWN)))
        anims.append(_part(old.ksyms[j], new.ksyms[j], 0.15 + 0.04 * j, 0.45 + 0.04 * j,
                           enter=lambda m, w=new.words[j]: FadeIn(m, shift=0.25 * DOWN)))

    # the grid
    grow = new.grid_on and not old.grid_on
    if grow:
        for j in range(n):            # each key label leaves its word in turn and settles at its row
            lo = 0.1 + 0.36 * j / n
            anims.append(_fly(old.words[j], new.keys[j], lo, lo + 0.36 / n + 0.1))
        anims.append(_at(ShowCreation(new.lines, lag_ratio=0.05), 0.4, 0.68))
        for k, cell in enumerate(new.cells):
            r = k // n
            anims.append(_at(GrowFromCenter(cell), 0.55 + 0.25 * r / n, 0.78 + 0.2 * r / n))
    elif old.grid_on and not new.grid_on:
        anims += [_at(FadeOut(m), 0.0, 0.3) for m in (old.keys, old.lines, old.cells)]
    elif new.grid_on:
        anims += [_at(Transform(a, b), 0.0, 0.5) for a, b in zip(old.keys, new.keys)]
        anims.append(_at(Transform(old.lines, new.lines), 0.0, 0.5))
        add_mask = new.mask == "causal" and old.mask != "causal"
        to_softmax = new.softmax and not old.softmax
        m_end = 0.4 if to_softmax else 0.9
        s_lo = m_end if add_mask else 0.05
        order = [k for k in range(n * n) if masked(k // n, k % n, new.mask)]
        for k, (a, b) in enumerate(zip(old.cells, new.cells)):
            r, c = divmod(k, n)
            if add_mask and k in order:
                i = order.index(k)
                lo = 0.05 + (m_end - 0.15) * i / max(len(order), 1)
                win = (lo, lo + 0.12)
            elif to_softmax:
                lo = s_lo + (0.98 - s_lo) * (c + 0.2) / n
                win = (lo, s_lo + (0.98 - s_lo) * (c + 1) / n)
            else:
                win = (0.1, 0.9)
            anims += [_at(Transform(a[0], b[0]), *win), _at(Transform(a[1], b[1]), *win)]
            anims.append(_at(Transform(a[2], b[2]) if _txt(a[2]) == _txt(b[2]) else _swap(a[2], b[2]), *win))
        if to_softmax:
            anims.append(_sweep(new, s_lo, 0.99))
    anims.append(_part(old.frame, new.frame, 0.0, 0.45, enter=lambda m: ShowCreation(m)))
    anims.append(_part(old.kframe, new.kframe, 0.0, 0.45, enter=lambda m: ShowCreation(m)))

    # arrows and the values they carry
    same_target = old.focus == new.focus
    grown = 0.0
    for j in range(n):
        a, b = old.arrows[j], new.arrows[j]
        has_a, has_b = bool(a.family_members_with_points()), bool(b.family_members_with_points())
        if has_a and has_b and same_target:
            anims.append(_at(Transform(a[0], b[0]), 0.0, 0.4))
            anims.append(_at(Transform(a[2], b[2]), 0.0, 0.4))
            anims.append(_at(_swap(a[1], b[1]) if _txt(a[1]) != _txt(b[1]) else Transform(a[1], b[1]), 0.0, 0.4))
            continue
        if has_a:
            anims.append(_at(FadeOut(a), 0.0, 0.25))
        if has_b:
            d = abs(b[0].get_start()[0] - b[0].get_end()[0]) / (new.cw * new.scale_now() * max(n - 1, 1))
            lo = 0.15 + 0.15 * d
            anims.append(_at(GrowArrow(b[0]), lo, lo + 0.3))
            anims.append(_at(FadeIn(b[1]), lo + 0.2, lo + 0.35))
            grown = max(grown, lo + 0.3)
    f = new.focus
    sources = [j for j in range(n) if new.arrows[j].family_members_with_points()]
    for j in range(n):
        a, b = old.vectors[j], new.vectors[j]
        has_a, has_b = bool(a.family_members_with_points()), bool(b.family_members_with_points())
        if has_a and has_b:
            changed = [k for k, (x, y) in enumerate(zip(a[1], b[1])) if _txt(x) != _txt(y)]
            if len(a[1]) != len(b[1]):
                anims.append(_at(FadeTransform(a, b), 0.1, 0.6))
                continue
            if j == f and sources and changed:
                # the attended words' values travel along the arrows, then the vector changes
                t0 = grown + 0.02 if grown else 0.1
                t1 = min(0.82, t0 + 0.38)
                k = new.scale_now()
                th = current()
                anims += [_value_packet(new.arrows[s][2], th.palette[VALUE], 0.09 * new.unit * k, t0, t1)
                          for s in sources]
                win = (t1 - 0.02, min(1.0, t1 + 0.16))
                anims.append(_flash(b, win[0], min(1.0, win[1] + 0.06)))
            else:
                win = (0.1, 0.55)
            anims.append(_at(Transform(a[0], b[0]), *win))
            anims += [_at(Transform(x, y) if _txt(x) == _txt(y) else _swap(x, y), *win) for x, y in zip(a[1], b[1])]
        elif has_b:
            anims.append(_at(FadeIn(b, shift=0.3 * DOWN), 0.15 + 0.03 * j, 0.5 + 0.03 * j))
        elif has_a:
            # the vector folds back into its word (the grid takes the room)
            anims.append(_at(FadeOut(a, shift=0.3 * UP), 0.0, 0.2))
    return AnimationGroup(*anims)


def _txt(m: Mobject) -> str:
    """The text a label shows (kept on it when built; a Text keeps no string)."""
    return getattr(m, "label_text", "")


def build(node: Node, world=None) -> AttentionBlock:
    return AttentionBlock(node)


def morph(old: AttentionBlock, new: AttentionBlock, sources=None) -> Animation | None:
    if old.tokens != new.tokens:
        return AnimationGroup(FadeOut(old, rate_func=squish_rate_func(smooth, 0, 0.4)),
                              FadeIn(new, rate_func=squish_rate_func(smooth, 0.4, 1)))
    return _attention(old, new)
