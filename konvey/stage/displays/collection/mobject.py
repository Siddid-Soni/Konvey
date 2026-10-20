"""``<collection>`` (manimgl): members sorted into groups, laid out by the renderer.

Looks (``look=``):
- ``units``: one packed block, groups as bands (filled column by column), legend beside it;
- ``bins``: one pile per top-level group, side by side, filled from the bottom, named underneath;
- ``row``: every member in one line in order (wrapping only when it must), legend beside it;
- ``stacks``: one post per group, its members piled bottom-up in the order listed (plates in
  piles, coins in columns, a pushed-and-popped stack), its name underneath; a member that
  changes post lifts off, moves across and drops.

Units (``shape=``): ``dot``, ``square``, ``ball``, ``chip`` (a rounded tag showing a listed
member's text; the default for listed members), ``slab`` (a flat bar as wide as the member's
``size=``, or its text when that is a number; the default for ``stacks``), or ``icon="name"``
(a line icon from ``konvey.stage.icons``: a sock, a person, a coin; on the collection, a group or
one member). ``mark`` lights the outline of a group's or member's units, ``dim`` fades
it, ``strike`` crosses it out.

Between beats every member keeps its identity: a listed member by its text, wherever it moved;
counted units by group path (``from="a > b"`` names where a group's units come from; a group that
was split or merged takes them from every old group on its path). ``from="#other > b"`` takes
them from another collection on screen: the members that collection loses fly across into this
one (a sock leaves the drawer and drops into its bin). Members nobody takes fade out,
members with no source fade in, and the rest fly to their new place, shape and look."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

from manimlib import *  # noqa: F401,F403

from ... import icons
from ...match import squash
from ...theme import current
from ...tree import BeatError, Node
from ..base import LIT_W, Block, _label, lit_color

LOOKS = ("units", "bins", "row", "stacks")
SHAPES = ("dot", "square", "ball", "chip", "slab", "icon")
PILES = ("bins", "stacks")   # named underneath each pile: no legend
MAX_UNITS = 2000
LEGEND_SHARE = 0.3    # of the width, for units and row
LEGEND_MAX = 44       # px: legend text beside big members
CAP = 1.5             # largest cell (units) for a dot, square or ball: a small crowd fills its box
ICON_CAP = 2.4        # an icon stays a crisp drawing when large: a few socks may fill a full shot
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
    size: float = 0.0    # a slab's width, relative to the widest member
    icon: str = ""       # drawn as this line icon (konvey.stage.icons) when set


@dataclass
class Group:
    label: str
    color: str
    mark: bool
    path: tuple[str, ...]
    source: tuple[str, ...]
    kids: list["Group"] = field(default_factory=list)
    icon: str = ""
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
    g = Group(label, color, mark, path, src, icon=_icon(n, where) or (parent.icon if parent else ""))
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
            g.members = [Member("", color, mark, dim, strike, icon=g.icon) for _ in range(count)]
    else:
        for c in lists:
            if c.children or "count" in c.attrs:
                g.kids.append(_group(c, g, where))
            else:
                g.members.append(_member(c, g, where))
    return g


def _icon(n: Node, where: str) -> str:
    name = n.attrs.get("icon", "").strip()
    if name and not icons.exists(name):
        near = icons.suggest(name)
        raise BeatError(f'{where}: icon="{name}" is not in the icon set'
                        + (f"; close: {', '.join(near)}" if near else "; use a shape= instead"))
    return icons.resolve(name) if name else ""


def _member(n: Node, g: Group, where: str = "") -> Member:
    th = current()
    mark, dim, strike = _flags(n, (g.mark, False, False))
    color = th.color(n.attrs["color"]) if n.attrs.get("color") else g.color
    try:
        size = float(n.attrs.get("size") or n.text)
    except ValueError:
        size = 0.0
    return Member(n.text, color, mark, dim, strike, max(size, 0.0), icon=_icon(n, where) or g.icon)


def _child(n: Node, parent: Group, where: str) -> Group:
    if not n.children and "count" not in n.attrs:
        return Group("", parent.color, parent.mark, parent.path, parent.source, icon=parent.icon,
                     members=[_member(n, parent, where)])
    return _group(n, parent, where)


def _top(node: Node, where: str) -> list[Group]:
    """Top-level groups; listed members written straight inside the collection share one unnamed group."""
    th = current()
    root = Group("", th.muted, False, (), (), icon=_icon(node, where))
    out = []
    for c in (c for c in node.children if c.tag == "li"):
        if c.children or "count" in c.attrs:
            out.append(_group(c, root if root.icon else None, where))
        else:
            if not out or out[-1] is not root:
                out.append(root)
            root.members.append(_member(c, root, where))
    return out


# --- unit shapes -------------------------------------------------------------------------------
class Unit(VGroup):
    """One member: its body (and text), a ring for ``mark``, a line for ``strike``."""

    def __init__(self, g: Group, m: Member, shape: str, cw: float, ch: float, size: float, lit: str = ""):
        th = current()
        c = min(cw, ch)
        if m.icon:
            # a dark thing keeps a light edge, a light one a dark edge: both read on the background
            edge = th.ink if th.needs_edge(m.color) or m.color == th.dark else th.dark
            body = icons.icon(m.icon, 0.86 * c, m.color, edge).move_to(ORIGIN)
        elif shape == "chip":
            body = RoundedRectangle(width=cw * 0.9, height=ch * 0.82, corner_radius=0.18 * ch)
            body.set_fill(m.color, 0.28).set_stroke(m.color, 2)
        elif shape == "slab":   # cw is this member's own width (stacks)
            body = RoundedRectangle(width=cw, height=ch * 0.8, corner_radius=0.3 * ch)
            body.set_fill(m.color, 1).set_stroke(th.bg, 2)
        elif shape == "square":
            body = Square(0.68 * c).set_fill(m.color, 1).set_stroke(width=0)
        elif shape == "ball":
            body = VGroup(Circle(radius=0.4 * c).set_fill(m.color, 1).set_stroke(width=0),
                          Circle(radius=0.12 * c).set_fill(WHITE, 0.35).set_stroke(width=0)
                          .shift(np.array([-0.13 * c, 0.13 * c, 0])))
        else:
            body = Circle(radius=0.3 * c).set_fill(m.color, 1).set_stroke(width=0)
        if not m.icon and shape in ("dot", "square", "ball") and th.needs_edge(m.color):
            (body[0] if isinstance(body, VGroup) else body).set_stroke(th.ink, max(1.0, 3 * c))
        # mark: the member's own outline lit in the accent, thin (3b1b), not a frame around it
        ring = (body if m.icon else body[0] if isinstance(body, VGroup) else body).copy()
        ring.set_fill(opacity=0).set_stroke(lit or th.lit, min(LIT_W, max(1.5, 6 * c)), opacity=1 if m.mark else 0)
        cross = Line(np.array([-0.4 * cw, -0.3 * ch, 0]), np.array([0.4 * cw, 0.3 * ch, 0]))
        cross.set_stroke(th.ink, max(1.5, 6 * c), opacity=1 if m.strike else 0)
        parts = [body]
        self.text = None
        if m.text:
            self.text = _label(m.text, size, th.ink)
            self.text.scale(min(1.0, cw * 0.78 / max(self.text.get_width(), 1e-6),
                                ch * 0.6 / max(self.text.get_height(), 1e-6)))
            if shape == "slab":
                self.text.set_color(th.bg)
            parts.append(self.text)
        super().__init__(*parts, ring, cross)
        # above the posts while animating: the scene batches neighbouring mobjects into one render
        # group, which loses their order; z_index splits the batch and draws members after
        self.set_z_index(1)
        self.body, self.ring, self.cross = body, ring, cross
        if m.dim or m.strike:
            if m.icon:   # fill and edge fade together; open strokes keep no fill
                for part in body:
                    part.set_stroke(opacity=0.3 if m.strike else 0.22)
                    part.set_fill(opacity=min(part.get_fill_opacity(), 0.3 if m.strike else 0.22))
            else:
                body.set_opacity(0.3 if m.strike else 0.22)
            if self.text is not None:
                self.text.set_opacity(0.4)


# --- layout ------------------------------------------------------------------------------------
def _name_color(color: str) -> str:
    """A group's name is written in its colour, unless that colour is too dark to read (a group of
    dark things): then in ink."""
    th = current()
    return th.ink if th.needs_edge(color) else color


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
        self.lc = lit_color(node)
        look = node.attrs.get("look", "units").strip()
        if look not in LOOKS:
            raise BeatError(f'{where} look="{look}": use one of {", ".join(LOOKS)}')
        self.groups = _top(node, where)
        pairs = [u for g in self.groups for u in g.units()]
        n = len(pairs)
        if n > MAX_UNITS:   # empty is fine: the bins, or the row things will be put in, before they arrive
            raise BeatError(f"{where}: {n} members; draw 1 to {MAX_UNITS} (scale the population down)")
        listed = any(m.text for _, m in pairs)
        iconic = any(m.icon for _, m in pairs) or any(g.icon for g in self.groups)
        shape = node.attrs.get("shape", "icon" if iconic else "slab" if look == "stacks" else "chip" if listed
                               else "dot").strip()
        if shape not in SHAPES:
            raise BeatError(f'{where} shape="{shape}": use one of {", ".join(SHAPES)}')
        if shape == "icon" and not iconic:
            raise BeatError(f'{where} shape="icon" needs icon="name" (on the collection, a group or a member)')
        w, h = float(node.attrs.get("w", 12)), float(node.attrs.get("h", 5))
        size = float(node.attrs.get("size", 26))
        aspect, cap = 1.0, ICON_CAP if shape == "icon" else CAP
        if shape == "chip" and pairs:
            probe = [_label(m.text or "00", size, th.ink) for _, m in pairs]
            tw = max(t.get_width() for t in probe) + 0.36
            th_ = max(t.get_height() for t in probe) + 0.3
            aspect, cap = tw / th_, th_ * 2.4
        self.look, self.shape = look, shape
        named = [g for g in self.groups if g.label or g.kids] if node.attrs.get("legend") != "none" else []
        legend = self._legend(size) if look not in PILES and named else VGroup()
        # Room for a legend in every beat of the scene if any beat has one (prepare: _legend), so
        # the block keeps its rows when a split names its groups.
        room = look not in PILES and bool(named or node.attrs.get("_legend") == "1")
        area_w = w * (1 - LEGEND_SHARE) if room else w
        self.units: list[tuple[Group, Member, Unit]] = []
        deco = VGroup()
        counts = [g.count for g in self.groups]
        apart = (look == "units" and len(self.groups) > 1 and all(g.kids for g in self.groups)
                 and min(counts) >= 0.1 * max(counts))
        self.back = VGroup()   # drawn behind the members (posts), and kept still between beats
        self.piles: dict[str, VGroup] = {}   # bins/stacks: a pile's base and name, by group name
        self.names: tuple | None = None   # stacks: the posts' names, kept still while they stay
        if look == "stacks":
            deco = self._stacks(w, h, size)
        elif look == "bins":
            deco = self._bins(w, h, aspect, cap, size)
        elif apart:
            # Populations of comparable size, each split the same way (patients per treatment by
            # outcome): one block per population, side by side, so their mixes can be compared.
            deco = VGroup(*self._blocks(area_w, h, aspect, cap, size), legend)
            if len(legend):
                right = max(u.get_right()[0] for _, _, u in self.units) + 0.4
                legend.shift([right - legend.get_left()[0], -legend.get_center()[1], 0])
        else:
            rows, cols, ch = _fit(max(n, 1), area_w, h, aspect, cap, one_line=look == "row")
            cw = ch * aspect
            if len(legend) and shape != "chip":   # names read at the size of what they name
                legend = self._legend(max(size, min(LEGEND_MAX, ch * 28)))
            x0 = -w / 2 + (area_w - cols * cw) / 2
            y0 = rows * ch / 2
            by_column = look == "units" and shape != "chip"
            for k, (g, m) in enumerate(pairs):
                col, row = divmod(k, rows) if by_column else (k % cols, k // cols)
                u = Unit(g, m, shape, cw, ch, size, self.lc).move_to([x0 + (col + 0.5) * cw, y0 - (row + 0.5) * ch, 0])
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
        body = VGroup(self.back, VGroup(*(u for _, _, u in self.units)), deco)
        body.shift(-body.get_center())   # members and their names centred together in the box
        frame = Rectangle(w, h).set_stroke(width=0).set_fill(opacity=0)   # keeps the natural size
        self.add(frame, body)
        self.content = json.dumps(["collection", look, shape, self.lc, _tree(self.groups)])
        self.node_id = node.id

    def _legend(self, size: float) -> VGroup:
        th = current()
        legend, depths = VGroup(), []
        for top in self.groups:
            for g, depth in top.walk():
                if not g.label:
                    continue
                sw = Dot(radius=0.09).set_fill(g.color, 1)
                if g.mark:
                    sw.set_stroke(self.lc, 2.5)
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
                u = Unit(gg, m, self.shape, cw, ch, size, self.lc)
                u.move_to([x0 + (col + 0.5) * cw, top - (row + 0.5) * ch, 0])
                self.units.append((gg, m, u))
            lab = _label(f"{g.label}  {g.count:,}", size, _name_color(g.color))
            if lab.get_width() > nc * cw + gap * 0.9:
                lab.scale((nc * cw + gap * 0.9) / lab.get_width())
            names.append(lab.move_to([x0 + nc * cw / 2, -h / 2 + label_h - 0.1 - lab.get_height() / 2, 0]))
            x0 += nc * cw + gap
        return names

    def _stacks(self, w: float, h: float, size: float) -> VGroup:
        """One post per group, members piled bottom-up in list order. A member's height comes
        from how many members there are in all (not on the tallest pile), so members keep their
        thickness while they move; its width from its size, relative to the largest."""
        th = current()
        nb = len(self.groups)
        gap = 0.4
        label_h = size / 48 + 0.3
        total = sum(g.count for g in self.groups) or 1
        col_w = (w - gap * (nb - 1)) / nb
        ch = min((h - label_h - 0.5) / total, col_w * 0.28)
        floor = -h / 2 + label_h
        top = max(floor + total * ch + 0.35, h / 2 - 0.05)   # posts run the box's height
        sizes = [m.size for g in self.groups for _, m in g.units() if m.size > 0]
        biggest = max(sizes, default=0) or 1
        # slabs without a colour of their own take one per size, so each is told apart as it moves
        rank = {v: k for k, v in enumerate(sorted(set(sizes)))}
        for g in self.groups:
            for _, m in g.units():
                if self.shape == "slab" and m.size in rank and m.color == g.color == th.muted:
                    m.color = th.color(f"c{rank[m.size] % 5 + 1}")
        deco = VGroup()
        self.rod_top = top
        self.names = tuple(g.label for g in self.groups)
        for b, g in enumerate(self.groups):
            x = -w / 2 + b * (col_w + gap) + col_w / 2
            for j, (gg, m) in enumerate(g.units()):
                frac = m.size / biggest if m.size > 0 else 1.0
                dw = col_w * (0.3 + 0.62 * frac) if self.shape == "slab" else ch
                u = Unit(gg, m, self.shape, dw, ch, size, self.lc).move_to([x, floor + (j + 0.5) * ch, 0])
                self.units.append((gg, m, u))
            # filled, not stroked: manimgl draws a group's strokes after all its fills, so a stroked
            # post would cross the members; as a fill it stays behind them, full height and still
            rod = Rectangle(width=max(0.05, ch * 0.14), height=top - floor).move_to([x, (top + floor) / 2, 0])
            base = Rectangle(width=col_w * 0.96, height=0.05).move_to([x, floor - 0.03, 0])
            for m in (rod, base):
                m.set_fill(th.muted, 0.7).set_stroke(width=0)
            self.back.add(rod, base)
            if g.label:
                lab = _label(g.label, size, _name_color(g.color) if g.color != th.muted else th.ink)
                if lab.get_width() > col_w:
                    lab.scale(col_w / lab.get_width())
                deco.add(lab.move_to([x, floor - 0.1 - lab.get_height() / 2 - 0.06, 0]))
            self.piles[squash(g.label)] = VGroup(rod, base)
        return deco

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
                u = Unit(gg, m, self.shape, cw, ch, size, self.lc)
                u.move_to([x0 + (col + 0.5) * cw, floor + (row + 0.5) * ch, 0])
                self.units.append((gg, m, u))
            base = Line([x0 - 0.08, floor - 0.04, 0], [x0 + bin_w + 0.08, floor - 0.04, 0])
            deco.add(base.set_stroke(th.muted, 2))
            name = f"{g.label}  {g.count:,}" if g.label else f"{g.count:,}"
            lab = _label(name, size, _name_color(g.color) if g.label else th.muted)
            if lab.get_width() > bin_w + gap * 0.9:
                lab.scale((bin_w + gap * 0.9) / lab.get_width())
            deco.add(lab.move_to([x0 + bin_w / 2, floor - 0.08 - lab.get_height() / 2 - 0.08, 0]))
            self.piles[squash(g.label)] = VGroup(base, lab)
        return deco


def _part(self, name: str) -> Mobject | None:
    """The members of the group ``name`` (``"left-handed > plays chess"`` for a sub-group), with
    its pile when the look has piles (so an empty bin still has a place); None if no such group."""
    key = tuple(squash(p) for p in name.split(">") if p.strip())
    units = [u for g, _, u in self.units if g.path[:len(key)] == key]
    pile = list(self.piles.get(key[0], [])) if len(key) == 1 else []
    if not units and not pile:
        return None
    return VGroup(*units, *pile)


CollectionBlock.part = _part


def _tree(groups: list[Group]) -> list:
    return [[g.label, g.color, g.mark, list(g.source), [(m.text, m.color, m.mark, m.dim, m.strike, m.icon) for m in g.members],
             _tree(g.kids)] for g in groups]


def build(node: Node, world=None) -> CollectionBlock:
    return CollectionBlock(node)


# --- motion ------------------------------------------------------------------------------------
def _fits(old: tuple[str, ...], new: tuple[str, ...]) -> bool:
    """One path continues the other: 'left-handed' split into 'left-handed > plays chess', or merged back."""
    k = min(len(old), len(new))
    return old[:k] == new[:k]


FROM_OTHER = "#"   # from="#drawer > dark": the first step names another collection on screen


def _pairs(old: CollectionBlock, new: CollectionBlock) -> tuple[list[tuple[int | None, int]], list[int]]:
    """(old index or None, new index) for every new member, and the old members nobody took.
    Groups whose ``from`` names another collection (``#id > …``) take nothing from ``old``."""
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
        elif g.source[:1] and g.source[0].startswith(FROM_OTHER):
            i = None
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


def _hop(mob: Mobject, target: Mobject, lift_y: float) -> Animation:
    """Off its post, across above the posts, down onto the new pile."""
    a, b = mob.get_center(), target.get_center()
    pts = [a, np.array([a[0], lift_y, 0]), np.array([b[0], lift_y, 0]), b]
    legs = [np.linalg.norm(q - p) for p, q in zip(pts, pts[1:])]
    total = sum(legs) or 1.0

    def at(t: float) -> np.ndarray:
        d = t * total
        for p, q, n in zip(pts, pts[1:], legs):
            if n and d <= n:
                return p + (q - p) * (d / n)
            d -= n
        return b

    start = mob.copy()

    def update(m, t):
        m.become(start).move_to(at(smooth(t)))
        if t >= 1:
            m.become(target)

    return UpdateFromAlphaFunc(mob, update)


def transfers(blocks: dict) -> dict:
    """Members that move from one collection into another this beat. ``blocks``: id -> (old block
    or None, new block or None) for every collection on screen. Returns
    {(giver id, old index): (taker id, new index)}: the giver's members that its new state no
    longer has, taken in order by the taker's groups whose ``from`` is ``#giver > path``."""
    out: dict = {}
    spare: dict[str, list[int]] = {}
    for gid, (o, n) in blocks.items():
        if o is not None and n is not None:
            spare[gid] = _pairs(o, n)[1]
        elif o is not None:
            spare[gid] = list(range(len(o.units)))
    for tid, (_, n) in blocks.items():
        if n is None:
            continue
        for j, (g, m, _) in enumerate(n.units):
            if not (g.source and g.source[0].startswith(FROM_OTHER)):
                continue
            gid, path = g.source[0][len(FROM_OTHER):], g.source[1:]
            old = blocks.get(gid, (None, None))[0]
            pool = spare.get(gid, [])
            for k, i in enumerate(pool):
                og, om, _ = old.units[i]
                if (squash(om.text) == squash(m.text)) if m.text else (not om.text and _fits(og.path, path)):
                    out[(gid, i)] = (tid, j)
                    pool.pop(k)
                    break
    return out


def _flown(sources) -> dict:
    """The beat's transfers (scene: sources["collection.transfers"]), or none."""
    return (sources or {}).get("collection.transfers", {}) if isinstance(sources, dict) else {}


def _arc(mob: Mobject, target: Mobject) -> Animation:
    """Across to another collection on an arc over the top, turning into its new look."""
    right = target.get_center()[0] >= mob.get_center()[0]
    return Transform(mob, target, path_arc=-0.7 if right else 0.7)


def morph(old: CollectionBlock, new: CollectionBlock, sources=None) -> Animation:
    pairs, gone = _pairs(old, new)
    moves = _flown(sources)
    me = getattr(new, "node_id", None)
    # members leaving for another collection fly there (the taker animates them), not fade out
    gone = [i for i in gone if (me, i) not in moves]
    incoming = {j: (gid, i) for (gid, i), (tid, j) in moves.items() if tid == me}
    pairs = [(i, j) for i, j in pairs if not (i is None and j in incoming)]
    taken = [(incoming[j], j) for j in sorted(incoming)]
    stacks = old.look == new.look == "stacks"
    # the posts first: an animation brings its mobject to the top in this order, and a post drawn
    # after the members would cross the one moving over it
    if stacks and len(old.back) == len(new.back):
        anims = [Transform(old.back, new.back)]
    elif len(old.back) or len(new.back):
        anims = [FadeOut(old.back, rate_func=QUICK), FadeIn(new.back, rate_func=LATE)]
    else:
        anims = []
    lift = None
    if stacks:   # above the posts, in screen terms (the block has been placed and scaled)
        lift = max(old.back.get_top()[1], new.back.get_top()[1]) + 0.9 * new.units[0][2].get_height() \
            if len(new.back) and new.units else None
    for i, j in pairs:
        u = new.units[j][2]
        if i is None:
            anims.append(FadeIn(u, scale=3, rate_func=LATE))   # grows from small
        elif lift is not None and abs(old.units[i][2].get_x() - u.get_x()) > 1e-3:
            anims.append(_hop(old.units[i][2], u, lift))
        else:
            anims.append(Transform(old.units[i][2], u))
    blocks = (sources or {}).get("collection.blocks", {}) if isinstance(sources, dict) else {}
    for (gid, i), j in taken:   # arrives from another collection: that member flies here
        src = blocks.get(gid)
        if src is not None:
            anims.append(_arc(src.units[i][2], new.units[j][2]))
        else:
            anims.append(FadeIn(new.units[j][2], scale=3, rate_func=LATE))
    if gone:
        anims.append(FadeOut(VGroup(*(old.units[i][2] for i in gone)), scale=0.3, rate_func=QUICK))
    if old.names is not None and old.names == new.names:
        anims.append(Transform(old.deco, new.deco))   # the same posts keep their names on screen
    else:   # names go first and the new ones arrive once the members have moved (like captions)
        anims += [FadeOut(old.deco, rate_func=QUICK), FadeIn(new.deco, shift=0.08 * UP, rate_func=LATE)]
    return AnimationGroup(*anims)


def beat_sources(on_screen: dict, mobs: dict) -> dict:
    """What this beat's collection morphs share (scene: merged into ``sources``): every
    collection's old block, and the members moving from one into another (``transfers``)."""
    ids = {i for i, m in {**on_screen, **mobs}.items() if getattr(m, "tag", None) == "collection"}
    blocks = {i: (on_screen.get(i) if getattr(on_screen.get(i), "tag", None) == "collection" else None,
                  mobs.get(i) if getattr(mobs.get(i), "tag", None) == "collection" else None) for i in ids}
    return {"collection.transfers": transfers(blocks),
            "collection.blocks": {i: o for i, (o, _) in blocks.items() if o is not None}}


def enter(node: Node, mob: CollectionBlock, run_time: float) -> Animation:
    """Members appear in a quick wave, then their names."""
    units = [u for _, _, u in mob.units]
    anims = [FadeIn(mob.back, run_time=run_time * 0.5), FadeIn(mob.deco, shift=0.1 * LEFT, run_time=run_time)]
    if units:   # empty bins have none yet
        anims.insert(1, LaggedStart(*(FadeIn(u, scale=2.5) for u in units), lag_ratio=0.6 / len(units),
                                    run_time=run_time))
    return AnimationGroup(*anims)
