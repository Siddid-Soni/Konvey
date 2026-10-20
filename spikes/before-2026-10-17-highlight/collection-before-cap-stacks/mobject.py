"""``<collection>`` (manimgl): members sorted into groups, laid out by the renderer.

Looks (``look=``):
- ``units``: one packed block, groups as bands (filled column by column), legend beside it;
- ``bins``: one pile per top-level group, side by side, filled from the bottom, named underneath;
- ``row``: every member in one line in order (wrapping only when it must), legend beside it.

Units (``shape=``): ``dot``, ``square``, ``ball``, ``chip`` (a rounded tag showing a listed
member's text; the default for listed members). ``mark`` rings a group or member, ``dim`` fades
it, ``strike`` crosses it out.

Between beats every member keeps its identity: a listed member by its text, wherever it moved;
counted units by group path (``from="a > b"`` names where a group's units come from; a group that
was split or merged takes them from every old group on its path). Members nobody takes fade out,
members with no source fade in, and the rest fly to their new place, shape and look."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

from manimlib import *  # noqa: F401,F403

from ...match import squash
from ...theme import current
from ...tree import BeatError, Node
from ..base import Block, _label

LOOKS = ("units", "bins", "row")
SHAPES = ("dot", "square", "ball", "chip")
MAX_UNITS = 2000
LEGEND_SHARE = 0.3    # of the width, for units and row
INDENT = 0.32
QUICK = squish_rate_func(smooth, 0, 0.25)
LATE = squish_rate_func(smooth, 0.6, 1)


@dataclass
class Member:
    text: str            # "" for a counted unit
    color: str
    mark: bool
    dim: bool
    strike: bool


@dataclass
class Group:
    label: str
    color: str
    mark: bool
    path: tuple[str, ...]
    source: tuple[str, ...]
    kids: list["Group"] = field(default_factory=list)
    members: list[Member] = field(default_factory=list)   # this group's own units, in order

    @property
    def count(self) -> int:
        return len(self.members) + sum(k.count for k in self.kids)

    def units(self):
        """(group, member) for every unit under this group, in drawing order."""
        for m in self.members:
            yield self, m
        for k in self.kids:
            yield from k.units()

    def walk(self, depth: int = 0):
        yield self, depth
        for k in self.kids:
            yield from k.walk(depth + 1)


def _flags(n: Node, inherited: tuple[bool, bool, bool]) -> tuple[bool, bool, bool]:
    return tuple(i or key in n.attrs for i, key in zip(inherited, ("mark", "dim", "strike")))


def _group(n: Node, parent: Group | None, where: str) -> Group:
    th = current()
    label = n.text
    color = th.color(n.attrs["color"]) if n.attrs.get("color") else parent.color if parent else th.muted
    mark, dim, strike = _flags(n, (parent.mark, False, False) if parent else (False, False, False))
    path = (*(parent.path if parent else ()), squash(label))
    src = tuple(squash(p) for p in n.attrs["from"].split(">") if p.strip()) if n.attrs.get("from") else path
    g = Group(label, color, mark, path, src)
    lists = [c for c in n.children if c.tag == "li"]
    if "count" in n.attrs:
        try:
            count = int(n.attrs["count"])
        except ValueError:
            raise BeatError(f'{where}: <li count="{n.attrs["count"]}">{label}</li>: count is a whole number') from None
        if count < 0:
            raise BeatError(f"{where}: <li>{label}</li>: count must be 0 or more")
        if lists:
            g.kids = [_child(c, g, where) for c in lists]
            if any(not k.label for k in g.kids):
                raise BeatError(f'{where}: <li count="{count}">{label}</li> splits into named groups only '
                                f'(<li count="N">name</li>), not listed members')
            if g.count != count:
                parts = " + ".join(str(k.count) for k in g.kids)
                raise BeatError(f"{where}: <li>{label}</li> has count {count} but its lists add up to "
                                f"{parts} = {g.count}")
        else:
            g.members = [Member("", color, mark, dim, strike) for _ in range(count)]
    else:
        for c in lists:
            if c.children or "count" in c.attrs:
                g.kids.append(_group(c, g, where))
            else:
                g.members.append(_member(c, g))
    return g


def _member(n: Node, g: Group) -> Member:
    th = current()
    mark, dim, strike = _flags(n, (g.mark, False, False))
    color = th.color(n.attrs["color"]) if n.attrs.get("color") else g.color
    return Member(n.text, color, mark, dim, strike)


def _child(n: Node, parent: Group, where: str) -> Group:
    if not n.children and "count" not in n.attrs:
        return Group("", parent.color, parent.mark, parent.path, parent.source, members=[_member(n, parent)])
    return _group(n, parent, where)


def _top(node: Node, where: str) -> list[Group]:
    """Top-level groups; listed members written straight inside the collection share one unnamed group."""
    th = current()
    root = Group("", th.muted, False, (), ())
    out = []
    for c in (c for c in node.children if c.tag == "li"):
        if c.children or "count" in c.attrs:
            out.append(_group(c, None, where))
        else:
            if not out or out[-1] is not root:
                out.append(root)
            root.members.append(_member(c, root))
    return out


# --- unit shapes -------------------------------------------------------------------------------
class Unit(VGroup):
    """One member: its body (and text), a ring for ``mark``, a line for ``strike``."""

    def __init__(self, g: Group, m: Member, shape: str, cw: float, ch: float, size: float):
        th = current()
        c = min(cw, ch)
        if shape == "chip":
            body = RoundedRectangle(width=cw * 0.9, height=ch * 0.82, corner_radius=0.18 * ch)
            body.set_fill(m.color, 0.28).set_stroke(m.color, 2)
        elif shape == "square":
            body = Square(0.68 * c).set_fill(m.color, 1).set_stroke(width=0)
        elif shape == "ball":
            body = VGroup(Circle(radius=0.4 * c).set_fill(m.color, 1).set_stroke(width=0),
                          Circle(radius=0.12 * c).set_fill(WHITE, 0.35).set_stroke(width=0)
                          .shift(np.array([-0.13 * c, 0.13 * c, 0])))
        else:
            body = Circle(radius=0.3 * c).set_fill(m.color, 1).set_stroke(width=0)
        ring_w = max(1.0, 9 * c)
        if shape == "chip":
            ring = RoundedRectangle(width=cw * 0.98, height=ch * 0.96, corner_radius=0.22 * ch)
        else:
            ring = Circle(radius=0.47 * c)
        ring.set_stroke(th.accent, ring_w, opacity=1 if m.mark else 0).set_fill(opacity=0)
        cross = Line(np.array([-0.4 * cw, -0.3 * ch, 0]), np.array([0.4 * cw, 0.3 * ch, 0]))
        cross.set_stroke(th.ink, max(1.5, 6 * c), opacity=1 if m.strike else 0)
        parts = [body]
        self.text = None
        if m.text:
            self.text = _label(m.text, size, th.ink)
            self.text.scale(min(1.0, cw * 0.78 / max(self.text.get_width(), 1e-6),
                                ch * 0.6 / max(self.text.get_height(), 1e-6)))
            parts.append(self.text)
        super().__init__(*parts, ring, cross)
        self.body, self.ring, self.cross = body, ring, cross
        if m.dim or m.strike:
            body.set_opacity(0.3 if m.strike else 0.22)
            if self.text is not None:
                self.text.set_opacity(0.4)


# --- layout ------------------------------------------------------------------------------------
def _fit(n: int, w: float, h: float, aspect: float, cap: float, one_line: bool = False):
    """Rows, columns and cell height putting n cells of width/height ``aspect`` into w x h."""
    best = None
    for rows in range(1, n + 1):
        cols = math.ceil(n / rows)
        ch = min(h / rows, w / (cols * aspect), cap)
        if best is None or ch > best[2] + 1e-9:
            best = (rows, cols, ch)
        if one_line and ch >= min(cap, h) * 0.5:
            return rows, cols, ch   # a row stays one line while its members are still big enough
        if rows * ch > h * 2:
            break
    return best


class CollectionBlock(Block):
    tag = "collection"

    def __init__(self, node: Node):
        super().__init__()
        th = current()
        where = f"<collection id={node.id}>"
        look = node.attrs.get("look", "units").strip()
        if look not in LOOKS:
            raise BeatError(f'{where} look="{look}": use one of {", ".join(LOOKS)}')
        self.groups = _top(node, where)
        pairs = [u for g in self.groups for u in g.units()]
        n = len(pairs)
        if not 0 < n <= MAX_UNITS:
            raise BeatError(f"{where}: {n} members; draw 1 to {MAX_UNITS} (scale the population down)")
        listed = any(m.text for _, m in pairs)
        shape = node.attrs.get("shape", "chip" if listed else "dot").strip()
        if shape not in SHAPES:
            raise BeatError(f'{where} shape="{shape}": use one of {", ".join(SHAPES)}')
        w, h = float(node.attrs.get("w", 12)), float(node.attrs.get("h", 5))
        size = float(node.attrs.get("size", 26))
        aspect, cap = 1.0, 0.9
        if shape == "chip":
            probe = [_label(m.text or "00", size, th.ink) for _, m in pairs]
            tw = max(t.get_width() for t in probe) + 0.36
            th_ = max(t.get_height() for t in probe) + 0.3
            aspect, cap = tw / th_, th_ * 2.4
        self.look, self.shape = look, shape
        named = [g for g in self.groups if g.label or g.kids]
        legend = self._legend(size) if look != "bins" and named else VGroup()
        area_w = w * (1 - LEGEND_SHARE) if len(legend) else w
        self.units: list[tuple[Group, Member, Unit]] = []
        deco = VGroup()
        counts = [g.count for g in self.groups]
        apart = (look == "units" and len(self.groups) > 1 and all(g.kids for g in self.groups)
                 and min(counts) >= 0.1 * max(counts))
        if look == "bins":
            deco = self._bins(w, h, aspect, cap, size)
        elif apart:
            # Populations of comparable size, each split the same way (patients per treatment by
            # outcome): one block per population, side by side, so their mixes can be compared.
            deco = VGroup(*self._blocks(area_w, h, aspect, cap, size), legend)
            if len(legend):
                right = max(u.get_right()[0] for _, _, u in self.units) + 0.4
                legend.shift([right - legend.get_left()[0], -legend.get_center()[1], 0])
        else:
            rows, cols, ch = _fit(n, area_w, h, aspect, cap, one_line=look == "row")
            cw = ch * aspect
            x0 = -w / 2 + (area_w - cols * cw) / 2
            y0 = rows * ch / 2
            by_column = look == "units" and shape != "chip"
            for k, (g, m) in enumerate(pairs):
                col, row = divmod(k, rows) if by_column else (k % cols, k // cols)
                u = Unit(g, m, shape, cw, ch, size).move_to([x0 + (col + 0.5) * cw, y0 - (row + 0.5) * ch, 0])
                self.units.append((g, m, u))
            if len(legend):
                left = x0 + cols * cw + 0.4
                room = w / 2 - left
                if legend.get_width() > room:
                    legend.scale(room / legend.get_width())
                if legend.get_height() > h:
                    legend.scale(h / legend.get_height())
                legend.shift([left - legend.get_left()[0], -legend.get_center()[1], 0])
                deco = legend
        self.deco = deco
        body = VGroup(VGroup(*(u for _, _, u in self.units)), deco)
        body.shift(-body.get_center())   # members and their names centred together in the box
        frame = Rectangle(w, h).set_stroke(width=0).set_fill(opacity=0)   # keeps the natural size
        self.add(frame, body)
        self.content = json.dumps(["collection", look, shape, _tree(self.groups)])

    def _legend(self, size: float) -> VGroup:
        th = current()
        legend, depths = VGroup(), []
        for top in self.groups:
            for g, depth in top.walk():
                if not g.label:
                    continue
                sw = Dot(radius=0.09).set_fill(g.color, 1)
                if g.mark:
                    sw = VGroup(sw, Circle(radius=0.14).set_stroke(th.accent, 2.5))
                text = _label(f"{g.label}  {g.count:,}", size * (1 if depth == 0 else 0.88),
                              th.ink if not g.kids else th.muted)
                legend.add(VGroup(sw, text).arrange(RIGHT, buff=0.14))
                depths.append(depth)
        legend.arrange(DOWN, aligned_edge=LEFT, buff=0.16)
        for row, depth in zip(legend, depths):
            row.shift(RIGHT * depth * INDENT)   # nested lists indent, like the HTML they come from
        return legend

    def _blocks(self, w: float, h: float, aspect: float, cap: float, size: float) -> list[Mobject]:
        """One block per top-level group, all the same height and unit size (so a block's area is
        its count), filled column by column into bands; its name and count underneath."""
        th = current()
        nb, gap = len(self.groups), 0.6
        label_h = size / 48 + 0.25
        hb = h - label_h
        bw = (w - gap * (nb - 1)) / nb
        ch = min(_fit(g.count, bw, hb, aspect, cap)[2] for g in self.groups)
        cw = ch * aspect
        rows = max(1, min(int(hb / ch + 1e-9), max(g.count for g in self.groups)))
        cols = [math.ceil(g.count / rows) for g in self.groups]
        total = sum(c * cw for c in cols) + gap * (nb - 1)
        x0, top = -total / 2, -h / 2 + label_h + rows * ch
        names = []
        for g, nc in zip(self.groups, cols):
            for j, (gg, m) in enumerate(g.units()):
                col, row = divmod(j, rows)
                u = Unit(gg, m, self.shape, cw, ch, size)
                u.move_to([x0 + (col + 0.5) * cw, top - (row + 0.5) * ch, 0])
                self.units.append((gg, m, u))
            lab = _label(f"{g.label}  {g.count:,}", size, g.color)
            if lab.get_width() > nc * cw + gap * 0.9:
                lab.scale((nc * cw + gap * 0.9) / lab.get_width())
            names.append(lab.move_to([x0 + nc * cw / 2, -h / 2 + label_h - 0.1 - lab.get_height() / 2, 0]))
            x0 += nc * cw + gap
        return names

    def _bins(self, w: float, h: float, aspect: float, cap: float, size: float) -> VGroup:
        """One pile per top-level group, filled from the bottom, its name and count underneath."""
        th = current()
        nb = len(self.groups)
        gap = 0.5
        label_h = size / 48 + 0.25
        hb = h - label_h
        most = max(g.count for g in self.groups) or 1
        best = None
        for k in range(1, most + 1):
            ch = min(hb / math.ceil(most / k), (w - gap * (nb - 1)) / (nb * k * aspect), cap)
            if best is None or ch > best[1] + 1e-9:
                best = (k, ch)
        k, ch = best
        cw = ch * aspect
        bin_w = k * cw
        total = nb * bin_w + gap * (nb - 1)
        deco = VGroup()
        floor = -h / 2 + label_h
        for b, g in enumerate(self.groups):
            x0 = -total / 2 + b * (bin_w + gap)
            for j, (gg, m) in enumerate(g.units()):
                row, col = divmod(j, k)
                u = Unit(gg, m, self.shape, cw, ch, size)
                u.move_to([x0 + (col + 0.5) * cw, floor + (row + 0.5) * ch, 0])
                self.units.append((gg, m, u))
            base = Line([x0 - 0.08, floor - 0.04, 0], [x0 + bin_w + 0.08, floor - 0.04, 0])
            deco.add(base.set_stroke(th.muted, 2))
            name = f"{g.label}  {g.count:,}" if g.label else f"{g.count:,}"
            lab = _label(name, size, g.color if g.label else th.muted)
            if lab.get_width() > bin_w + gap * 0.9:
                lab.scale((bin_w + gap * 0.9) / lab.get_width())
            deco.add(lab.move_to([x0 + bin_w / 2, floor - 0.08 - lab.get_height() / 2 - 0.08, 0]))
        return deco


def _tree(groups: list[Group]) -> list:
    return [[g.label, g.color, g.mark, list(g.source), [(m.text, m.color, m.mark, m.dim, m.strike) for m in g.members],
             _tree(g.kids)] for g in groups]


def build(node: Node, world=None) -> CollectionBlock:
    return CollectionBlock(node)


# --- motion ------------------------------------------------------------------------------------
def _fits(old: tuple[str, ...], new: tuple[str, ...]) -> bool:
    """One path continues the other: 'sick' split into 'sick > positive', or merged back."""
    k = min(len(old), len(new))
    return old[:k] == new[:k]


def _pairs(old: CollectionBlock, new: CollectionBlock) -> tuple[list[tuple[int | None, int]], list[int]]:
    """(old index or None, new index) for every new member, and the old members nobody took."""
    taken: set[int] = set()
    out: list[tuple[int | None, int]] = []
    by_text: dict[str, list[int]] = {}
    for i, (_, m, _) in enumerate(old.units):
        if m.text:
            by_text.setdefault(squash(m.text), []).append(i)
    pools: dict[tuple, list[int]] = {}
    for j, (g, m, _) in enumerate(new.units):
        i = None
        if m.text:
            cands = [x for x in by_text.get(squash(m.text), []) if x not in taken]
            i = cands[0] if cands else None
        else:
            if g.source not in pools:
                pools[g.source] = [x for x, (og, om, _) in enumerate(old.units)
                                   if not om.text and _fits(og.path, g.source)]
            pool = pools[g.source]
            while pool and pool[0] in taken:
                pool.pop(0)
            i = pool.pop(0) if pool else None
        if i is not None:
            taken.add(i)
        out.append((i, j))
    return out, [i for i in range(len(old.units)) if i not in taken]


def morph(old: CollectionBlock, new: CollectionBlock, sources=None) -> Animation:
    pairs, gone = _pairs(old, new)
    anims = []
    for i, j in pairs:
        u = new.units[j][2]
        if i is None:
            anims.append(FadeIn(u, scale=3, rate_func=LATE))   # grows from small
        else:
            anims.append(Transform(old.units[i][2], u))
    if gone:
        anims.append(FadeOut(VGroup(*(old.units[i][2] for i in gone)), scale=0.3, rate_func=QUICK))
    # names go first and the new ones arrive once the members have moved (like captions)
    anims += [FadeOut(old.deco, rate_func=QUICK), FadeIn(new.deco, shift=0.08 * UP, rate_func=LATE)]
    return AnimationGroup(*anims)


def enter(node: Node, mob: CollectionBlock, run_time: float) -> Animation:
    """Members appear in a quick wave, then their names."""
    units = [u for _, _, u in mob.units]
    return AnimationGroup(
        LaggedStart(*(FadeIn(u, scale=2.5) for u in units), lag_ratio=0.6 / max(len(units), 1),
                    run_time=run_time),
        FadeIn(mob.deco, shift=0.1 * LEFT, run_time=run_time))
