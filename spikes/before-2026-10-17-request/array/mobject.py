"""``<array>``: a row of cells with index labels and named pointers (manimgl)."""

from __future__ import annotations

from manimlib import *  # noqa: F401,F403

from ...tree import BeatError, Node
from ...theme import current
from ..base import CELL, LIT_W, lit_color, cell_width, data_list, index_set, _num, _label, Block, HOP


class ArrayBlock(Block):
    tag = "array"

    def __init__(self, node: Node):
        th = current()
        values = data_list(node, "values", required=False)   # empty: an empty slot (an empty stack)
        n = len(values)
        size = float(node.attrs.get("size", 30))
        cell_h = CELL * min(1.0, size / 30)   # size= shrinks the cells too, not just the digits
        cell_w = cell_width(values, size, cell_h)   # long values widen every cell alike
        hot = index_set(node.attrs.get("highlight", ""), n, "highlight")
        lc = lit_color(node)
        dim = index_set(node.attrs.get("dim", ""), n, "dim")
        self.cells = VGroup()
        for i, v in enumerate(values):
            box = Rectangle(cell_w, cell_h).set_fill(th.panel_fill, 0.6)
            box.set_stroke(*((lc, LIT_W) if i in hot else (th.muted, 1.5)))
            txt = _label(v, size, th.ink)
            if txt.get_width() > cell_w * 0.85:
                txt.set_width(cell_w * 0.85)
            cell = VGroup(box, txt.move_to(box))
            if i in dim:
                cell.set_opacity(0.25)
            self.cells.add(cell)
        self.empty = VGroup()
        if not n:
            self.empty.add(DashedVMobject(Square(cell_h), num_dashes=16).set_stroke(th.muted, 1.5, 0.6))
        self.cells.arrange(RIGHT, buff=0.08)
        self.values = [str(v).strip() for v in values]   # motion.py matches cells by value
        self.pointer_names: list[str] = []
        self.pointer_at: list[int] = []      # cell index each pointer marks
        parts = [self.cells, self.empty]
        start = node.attrs.get("index", "0")
        self.index = VGroup()
        if start != "none":
            for i, cell in enumerate(self.cells):
                self.index.add(_label(int(_num(start)) + i, 0.65 * size, th.muted).next_to(cell, DOWN, buff=0.12))
            parts.append(self.index)
        self.pointers = VGroup()
        stacked: dict[int, int] = {}
        for k, item in enumerate(p for p in node.attrs.get("pointers", "").split(",") if p.strip()):
            name, _, at = item.partition(":")
            i = next(iter(index_set(at, n, f"pointer {name.strip()}"))) if at.strip() else None
            if i is None:
                raise BeatError(f'<array id={node.id}> pointer "{item}": use name:index, e.g. "i:0"')
            color = th.palette[(k + 1) % len(th.palette)]
            level = stacked.get(i, 0)
            stacked[i] = level + 1
            top = self.cells[i].get_top() + (0.12 + 0.42 * level) * UP
            arrow = Arrow(top + 0.42 * UP, top, buff=0, stroke_width=3, fill_color=color,
                          stroke_color=color, max_tip_length_to_length_ratio=0.45)
            label = _label(name.strip(), 0.7 * size, color).next_to(arrow, UP, buff=0.05)
            # A stacked pointer's label sits beside its arrow so names never overlap.
            if level:
                label.next_to(arrow, RIGHT, buff=0.06)
            self.pointers.add(VGroup(arrow, label))
            self.pointer_names.append(name.strip())
            self.pointer_at.append(i)
        parts.append(self.pointers)
        super().__init__(*parts)
        self.set_content(node, "values", "index")


def _array(old: ArrayBlock, new: ArrayBlock) -> Animation:
    anims = []
    pairs = _match_by_value(old.values, new.values)
    used_old = set(pairs.values())
    hops = _hoppers(pairs)
    for j, cell in enumerate(new.cells):
        i = pairs.get(j)
        if i is not None:
            arc = 0.0 if j not in hops else (HOP if j < i else -HOP)   # over the top of the row
            anims.append(Transform(old.cells[i], cell, path_arc=arc))
        elif j < len(old.cells) and j not in used_old:
            used_old.add(j)
            anims.append(FadeTransform(old.cells[j], cell))
        else:
            anims.append(FadeIn(cell, shift=0.2 * DOWN))
    anims += [FadeOut(c) for i, c in enumerate(old.cells) if i not in used_old]
    anims.append(Transform(old.index, new.index) if len(old.index) == len(new.index)
                 else FadeTransform(old.index, new.index))
    old_ptr = dict(zip(old.pointer_names, old.pointers))
    for name, ptr in zip(new.pointer_names, new.pointers):
        anims.append(Transform(old_ptr.pop(name), ptr) if name in old_ptr else FadeIn(ptr, shift=0.2 * DOWN))
    anims += [FadeOut(p, shift=0.2 * UP) for p in old_ptr.values()]
    return AnimationGroup(*anims)


def _match_by_value(old: list[str], new: list[str]) -> dict[int, int]:
    """new index -> old index for equal values. Equal values keep their order when both rows
    hold the same number of them (so duplicates never leapfrog each other); otherwise the
    nearest positions pair first."""
    out: dict[int, int] = {}
    for v in dict.fromkeys(new):
        js = [j for j, x in enumerate(new) if x == v]
        is_ = [i for i, x in enumerate(old) if x == v]
        if len(js) == len(is_):
            out.update(zip(js, is_))
            continue
        taken = set()
        for _, j, i in sorted((abs(i - j), j, i) for j in js for i in is_):
            if j not in out and i not in taken:
                out[j] = i
                taken.add(i)
    return out


def _hoppers(pairs: dict[int, int]) -> set[int]:
    """New indices of items that jump over the row: of two items whose paths cross, the one
    moving farther (on a tie, the one moving left). The others slide straight, so a shift
    looks like a shift and an insertion like one item leaping into its gap."""
    moves = [(j, i) for j, i in pairs.items() if i != j]
    hop = set()
    for j, i in moves:
        for j2, i2 in pairs.items():
            if j2 == j or (i - i2) * (j - j2) >= 0:
                continue   # same order before and after: no crossing
            d, d2 = abs(i - j), abs(i2 - j2)
            if d > d2 or (d == d2 and j < i):
                hop.add(j)
    return hop


def build(node: Node, world=None) -> ArrayBlock:
    return ArrayBlock(node)


def morph(old: ArrayBlock, new: ArrayBlock, sources=None) -> Animation:
    return _array(old, new)


def sources(new: ArrayBlock, old) -> list:
    """Cells being looked at: under a pointer, or an item that just hopped to a new place
    (read from the old cell while it is still moving there)."""
    pairs = _match_by_value(old.values, new.values) if isinstance(old, ArrayBlock) else {}
    looked = set(new.pointer_at) | _hoppers(pairs)
    return [(new.values[j], old.cells[pairs[j]][1] if j in pairs else new.cells[j][1]) for j in sorted(looked)]
