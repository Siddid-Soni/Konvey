"""``<array>``: a row of cells with index labels and named pointers; ``linked`` cells each point
to the next (a linked list), ``chains`` hang a short linked list below a cell (a bucket) (manimgl)."""

from __future__ import annotations

from manimlib import *  # noqa: F401,F403

from ...tree import BeatError, Node
from ...theme import current
from ..base import CELL, LIT_W, lit_color, cell_width, data_list, index_set, _num, _label, Block, HOP, tidy_number

LINK = 0.5    # the gap an arrow between two linked boxes spans


def _flag(node: Node, key: str) -> bool:
    return node.attrs.get(key, "").strip().lower() in ("true", "yes", "1")


def parse_chains(node: Node, n: int) -> dict[int, list[str]]:
    """``chains="3:cat>fox;5:dog"`` -> {3: ["cat", "fox"], 5: ["dog"]}: the list below each cell."""
    out: dict[int, list[str]] = {}
    for part in (p.strip() for p in node.attrs.get("chains", "").split(";") if p.strip()):
        at, _, items = part.partition(":")
        try:
            i = int(at.strip())
        except ValueError:
            raise BeatError(f'<array id={node.id}> chains "{part}": use cell:item>item, e.g. "3:cat>fox"') from None
        if not 0 <= i < n:
            raise BeatError(f'<array id={node.id}> chains "{part}": cell {i} is outside 0..{n - 1}')
        out[i] = [x.strip() for x in items.split(">") if x.strip()]
    return out


def _link(a: np.ndarray, b: np.ndarray, color: str) -> Arrow:
    return Arrow(a, b, buff=0, stroke_width=2.5, fill_color=color, stroke_color=color,
                 max_tip_length_to_length_ratio=0.35)


WRAP = 16    # cells in a row before a plain array wraps (more do not fit across the stage)


def _per_row(node: Node, n: int) -> int:
    """How many cells a row holds: ``wrap="8"``, else WRAP for a long plain array (rows of equal
    length); a linked list or an array with chains below stays one row."""
    raw = node.attrs.get("wrap", "").strip()
    if raw:
        try:
            k = int(raw)
        except ValueError:
            raise BeatError(f'<array id={node.id}> wrap="{raw}": the number of cells in a row, e.g. "8"') from None
        return max(1, k)
    if n <= WRAP or _flag(node, "linked") or node.attrs.get("chains", "").strip():
        return max(n, 1)
    rows = -(-n // WRAP)
    return -(-n // rows)


class ArrayBlock(Block):
    tag = "array"

    def __init__(self, node: Node):
        th = current()
        values = data_list(node, "values", required=False)   # empty: an empty slot (an empty stack)
        shown = [tidy_number(v) for v in values]   # 0.0013888889 is drawn 0.001389
        n = len(values)
        size = float(node.attrs.get("size", 30))
        cell_h = CELL * min(1.0, size / 30)   # size= shrinks the cells too, not just the digits
        cell_w = cell_width(shown, size, cell_h)   # long values widen every cell alike
        hot = index_set(node.attrs.get("highlight", ""), n, "highlight")
        lc = lit_color(node)
        dim = index_set(node.attrs.get("dim", ""), n, "dim")
        self.cells = VGroup()
        for i, v in enumerate(values):
            box = Rectangle(cell_w, cell_h).set_fill(th.panel_fill, 0.6)
            box.set_stroke(*((lc, LIT_W) if i in hot else (th.muted, 1.5)))
            txt = _label(shown[i], size, th.ink)
            if txt.get_width() > cell_w * 0.85:
                txt.set_width(cell_w * 0.85)
            cell = VGroup(box, txt.move_to(box))
            if i in dim:
                cell.set_opacity(0.25)
            self.cells.add(cell)
        self.empty = VGroup()
        if not n:
            self.empty.add(DashedVMobject(Square(cell_h), num_dashes=16).set_stroke(th.muted, 1.5, 0.6))
        linked = _flag(node, "linked")
        self.cells.arrange(RIGHT, buff=LINK if linked else 0.08)
        per_row = _per_row(node, n)
        if per_row < n:   # a long row (a 32-bit filter) wraps into rows, indices still counted along
            gap = (0.65 * size / 30) * 0.5 + 0.3 + (0.9 if node.attrs.get("pointers", "").strip() else 0.0)
            self.cells.arrange_in_grid(n_cols=per_row, h_buff=0.08, v_buff=gap, fill_rows_first=True)
        self.values = [str(v).strip() for v in values]   # motion.py matches cells by value
        # linked: each cell points to the next, the last to nothing (a linked list)
        self.links = VGroup(*(_link(a.get_right(), b.get_left(), th.muted)
                              for a, b in zip(self.cells, self.cells[1:]))) if linked else VGroup()
        if linked and n:
            end = _label("\u2205", 0.8 * size, th.muted).next_to(self.cells[-1], RIGHT, buff=LINK)
            self.links.add(_link(self.cells[-1].get_right(), end.get_left() + 0.06 * LEFT, th.muted), end)
        # chains: a short linked list hanging below a cell, top to bottom
        chains = parse_chains(node, n)
        lit_items = set()
        for part in (p.strip() for p in node.attrs.get("chain-highlight", "").split(",") if p.strip()):
            at, _, k = part.partition(":")
            try:
                lit_items.add((int(at), int(k)))
            except ValueError:
                raise BeatError(f'<array id={node.id}> chain-highlight "{part}": use cell:position, '
                                'e.g. "3:1" (the second item below cell 3)') from None
        self.chain_keys: list[tuple[int, str, int]] = []   # (cell, item, its order among equal items)
        self.chain_items, self.chain_links = VGroup(), VGroup()
        self.link_keys: list[tuple[int, int]] = []
        for i, items in sorted(chains.items()):
            above = self.cells[i]
            for k, v in enumerate(items):
                box = Rectangle(cell_w, cell_h).set_fill(th.panel_fill, 0.6)
                box.set_stroke(*((lc, LIT_W) if (i, k) in lit_items else (th.ink, 1.5)))
                txt = _label(v, size, th.ink)
                if txt.get_width() > cell_w * 0.85:
                    txt.set_width(cell_w * 0.85)
                item = VGroup(box, txt.move_to(box)).next_to(above, DOWN, buff=LINK)
                self.chain_links.add(_link(above.get_bottom(), item.get_top(), th.muted))
                self.link_keys.append((i, k))
                self.chain_items.add(item)
                self.chain_keys.append((i, v, sum(1 for c, x, _ in self.chain_keys if c == i and x == v)))
                above = item
        self.pointer_names: list[str] = []
        self.pointer_at: list[int] = []      # cell index each pointer marks
        parts = [self.cells, self.empty, self.links, self.chain_links, self.chain_items]
        start = node.attrs.get("index", "0")
        self.index = VGroup()
        # with chains hanging below, the index labels go above the cells
        side = UP if chains else DOWN
        if start != "none":
            for i, cell in enumerate(self.cells):
                self.index.add(_label(int(_num(start)) + i, 0.65 * size, th.muted).next_to(cell, side, buff=0.12))
            parts.append(self.index)
        lift = self.index.get_height() + 0.12 if chains and len(self.index) else 0.0
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
            top = self.cells[i].get_top() + (0.12 + lift + 0.42 * level) * UP
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
        self.set_content(node, "values", "index", "linked", "chains", "wrap")


def _point(self, i: float, _y: float = 0.0) -> np.ndarray:
    """The centre of cell i (counted from 0, whatever the index labels say) on the page now, so a
    mark can point at a cell (a note "at" cells 1, 8 and 14: one arrow each). The second number,
    if given, is ignored: an array has one row of indices even when it wraps."""
    n = len(self.cells)
    if not n or not -0.5 <= i <= n - 0.5:
        raise BeatError(f"cell {i:g} is not in this array (cells 0-{n - 1}); a mark on an array names a cell by "
                        'its position from 0: at="3; 7"')
    k = int(np.clip(round(i), 0, n - 1))
    return self.cells[k].get_center()


def _bounds(self) -> tuple[float, float, float, float]:
    (a, b, _), (c, d, _) = self.cells.get_corner(DL), self.cells.get_corner(UR)
    return a, b, c, d


ArrayBlock.point, ArrayBlock.bounds = _point, _bounds


def _array(old: ArrayBlock, new: ArrayBlock) -> Animation:
    anims = []
    pairs = _in_place(old.values, new.values) or _match_by_value(old.values, new.values)
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
    if len(old.links) or len(new.links):
        anims.append(Transform(old.links, new.links) if len(old.links) == len(new.links)
                     else FadeTransform(old.links, new.links))
    anims += _chains(old, new)
    return AnimationGroup(*anims)


def _chains(old: ArrayBlock, new: ArrayBlock) -> list[Animation]:
    """Items below the cells keep their identity by cell and value: one already there moves
    (down, when an item is put in front of it), a new one drops in, a gone one fades; the
    arrow into each place in a chain reshapes, or grows/fades with its item."""
    anims = []
    at = {key: i for i, key in enumerate(old.chain_keys)}
    for j, key in enumerate(new.chain_keys):
        i = at.pop(key, None)
        anims.append(Transform(old.chain_items[i], new.chain_items[j]) if i is not None
                     else FadeIn(new.chain_items[j], shift=0.25 * DOWN))
    anims += [FadeOut(old.chain_items[i]) for i in at.values()]
    links = {key: i for i, key in enumerate(old.link_keys)}
    for j, key in enumerate(new.link_keys):
        i = links.pop(key, None)
        anims.append(Transform(old.chain_links[i], new.chain_links[j]) if i is not None
                     else GrowArrow(new.chain_links[j]))
    anims += [FadeOut(old.chain_links[i]) for i in links.values()]
    return anims


def _in_place(old: list[str], new: list[str]) -> dict[int, int] | None:
    """Each cell to itself when the row keeps its length and only a few cells change value (bits set,
    a count going up): those cells change where they are. Matched by value instead, a 0 would fly
    off to wherever another 0 sits. A reordering (a sort, an insert) changes most places: None."""
    if len(old) != len(new) or not old:
        return None
    changed = sum(a != b for a, b in zip(old, new))
    return {j: j for j in range(len(new))} if changed <= max(1, len(new) // 3) else None


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
    pairs = (_in_place(old.values, new.values) or _match_by_value(old.values, new.values)) if isinstance(old, ArrayBlock) else {}
    looked = set(new.pointer_at) | _hoppers(pairs)
    return [(new.values[j], old.cells[pairs[j]][1] if j in pairs else new.cells[j][1]) for j in sorted(looked)]
