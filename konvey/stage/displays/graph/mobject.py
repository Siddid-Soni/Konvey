"""``<graph>``: nodes joined by edges; packets flow along them between beats (manimgl)."""

from __future__ import annotations

import numpy as np

from manimlib import *  # noqa: F401,F403

from ...match import UNKNOWN, as_num
from ...tree import BeatError, Node
from ...theme import current
from . import edge_pair
from ..base import LIT_W, lit_color, _label, Block, _swap


NODE_R = 0.3
MAX_GROW, SPARSE_NODES = 1.6, 6   # a graph of this few nodes may grow its nodes and labels
NAME_FLOOR = 0.7     # a long name shrinks to this share of its size, then the node widens
TRAVEL = (0.08, 0.88)  # share of a beat's motion the packets of a flow take


LAYOUTS = ("", "line", "two-lines", "tree")
TREE_GAP = 0.7       # tree: between neighbouring subtrees (in units of one node's width)
TREE_LEVEL = 1.9     # tree: from one level to the next
PAGE_CELL = 1.15     # look="pages": one key's cell, in node widths
LINE_GAP = 0.35      # between neighbouring nodes in a line layout
LINES_APART = 2.6    # two-lines: the second line this far under the first


def _layout(node: Node) -> str:
    lay = node.attrs.get("layout", "").strip().lower()
    if lay not in LAYOUTS:
        raise BeatError(f'<graph id={node.id}> layout="{lay}": use "line" (the nodes in a row, edges arcing '
                        f'above), "two-lines" (nodes="a,b|x,y": two rows, edges between them) or "tree" '
                        f'(the first node on top, each edge parent-child, levels below it)')
    return lay


def _line_groups(node: Node, lay: str) -> list[list[str]]:
    """The node names of a line layout, one list per line (``"a,b,c|x,y"`` for two lines)."""
    raw = node.attrs.get("nodes", "").strip()
    if ":" in raw:
        raise BeatError(f'<graph id={node.id}> layout="{lay}" places the nodes itself: give names only, '
                        f'nodes="a,b,c"' + (' and "|" between the two lines' if lay == "two-lines" else ""))
    groups = [[n.strip() for n in g.replace(";", ",").split(",") if n.strip()] for g in raw.split("|")]
    if lay == "two-lines" and len(groups) != 2:
        raise BeatError(f'<graph id={node.id}> layout="two-lines" needs nodes="the,blue,cat|le,chat,bleu" '
                        f"(the first line, \"|\", the second)")
    if lay == "line" and len(groups) != 1:
        raise BeatError(f'<graph id={node.id}> layout="line": one row of names, no "|"')
    return groups


def _graph_nodes(node: Node) -> dict[str, np.ndarray | None]:
    """``"A:0,0;B:2,1"`` (positions) or ``"A,B,C"`` (placed on a circle) -> name -> position.
    A line layout returns names only (None): the positions follow the drawn names."""
    raw = node.attrs.get("nodes", "").strip()
    if not raw:
        raise BeatError(f'<graph id={node.id}> needs nodes="A:0,0;B:2,1;…" (or "A,B,C")')
    lay = _layout(node)
    if lay == "tree":
        return _tree(node)
    if lay:
        names = [n for g in _line_groups(node, lay) for n in g]
        if len(set(names)) != len(names):
            raise BeatError(f'<graph id={node.id}> nodes: every name once (a repeated word needs its own name, '
                            f'"it" and "it2")')
        return {n: None for n in names}
    out: dict[str, np.ndarray | None] = {}
    if ":" not in raw:
        names = [n.strip() for n in raw.replace(";", ",").split(",") if n.strip()]
        for k, name in enumerate(names):
            a = PI / 2 - k * TAU / len(names)
            out[name] = np.array([np.cos(a), np.sin(a)]) * 1.6
        return out
    for part in (p.strip() for p in raw.split(";") if p.strip()):
        name, _, xy = part.partition(":")
        try:
            x, y = (float(v) for v in xy.split(","))
        except ValueError as e:
            raise BeatError(f'<graph id={node.id}> node "{part}": use name:x,y like "A:0,0"') from e
        out[name.strip()] = np.array([x, y])
    return out


def _tree(node: Node) -> dict[str, np.ndarray]:
    """``layout="tree"``: the first node is the root; every edge ``parent-child`` (or
    ``parent>child``) hangs the child one level below, children left to right in the order the
    edges are written. Leaves sit side by side, each as wide as its name (a page of several keys
    is wide), and a parent centres over its children, so subtrees never overlap (a tidy tree)."""
    raw = node.attrs.get("nodes", "").strip()
    if ":" in raw:
        raise BeatError(f'<graph id={node.id}> layout="tree" places the nodes itself: give names only, '
                        f'root first, nodes="root,a,b"')
    names = [n.strip() for n in raw.replace(";", ",").split(",") if n.strip()]
    if len(set(names)) != len(names):
        raise BeatError(f'<graph id={node.id}> nodes: every name once')
    kids: dict[str, list[str]] = {n: [] for n in names}
    has_parent: set[str] = set()
    for a, b, *_ in _graph_edges(node, names):
        if b in has_parent or b == names[0]:
            raise BeatError(f'<graph id={node.id}> layout="tree": "{b}" has two parents (or the root has one); '
                            f'in a tree each node hangs from one parent, written first in its edge')
        kids[a].append(b)
        has_parent.add(b)
    if node.attrs.get("look", "").strip() == "pages":   # a page is one cell per key
        width = {n: PAGE_CELL * max(1, len(n.split())) for n in names}
    else:
        width = {n: max(1.0, 0.32 * len(n)) for n in names}   # in node widths: a long name is wide
    pos: dict[str, np.ndarray] = {}
    cursor = [0.0]

    def place(n: str, depth: int, seen: set) -> tuple[float, float]:
        """Lay out n's subtree from the cursor; returns its (left, right) extent."""
        seen.add(n)
        children = [c for c in kids[n] if c not in seen]
        if not children:
            left = cursor[0]
            cursor[0] += width[n] + TREE_GAP
            pos[n] = np.array([left + width[n] / 2, -depth * TREE_LEVEL])
            return left, left + width[n]
        spans = [place(c, depth + 1, seen) for c in children]
        mid = (pos[children[0]][0] + pos[children[-1]][0]) / 2
        left = min(spans[0][0], mid - width[n] / 2)
        right = max(spans[-1][1], mid + width[n] / 2)
        if left < spans[0][0]:   # a parent wider than its children pushes the next subtree on
            cursor[0] = max(cursor[0], right + TREE_GAP)
        pos[n] = np.array([mid, -depth * TREE_LEVEL])
        return left, right

    seen: set[str] = set()
    for root in [names[0]] + [n for n in names[1:] if n not in has_parent]:   # stray nodes: own trees
        if root not in seen:
            place(root, 0, seen)
    return {n: pos[n] for n in names}


def _graph_edges(node: Node, names) -> list[tuple[str, str, bool, str]]:
    """``"A-B:7;B>C"`` -> [(a, b, directed, weight)]."""
    edges = []
    for part in (p.strip() for p in node.attrs.get("edges", "").split(";") if p.strip()):
        pair, _, w = part.partition(":")
        sep = ">" if ">" in pair else "-"
        a, _, b = (x.strip() for x in pair.partition(sep))
        for end in (a, b):
            if end not in names:
                raise BeatError(f'<graph id={node.id}> edge "{part}": no node named "{end}" '
                                f'(nodes: {", ".join(names)})')
        edges.append((a, b, sep == ">", w.strip()))
    return edges


def _named(node: Node, key: str, names) -> set[str]:
    got = {n.strip() for n in node.attrs.get(key, "").replace(";", ",").split(",") if n.strip()}
    bad = sorted(got - set(names))
    if bad:
        raise BeatError(f'<graph id={node.id}> {key}="{node.attrs[key]}": no node named {bad}')
    return got


def _rim(half: float, u: np.ndarray, r: float = NODE_R) -> float:
    """Distance from a node's centre to its outline along unit u: a circle of radius r
    (half=0) or a stadium whose straight sides are 2*half long."""
    ux, uy = abs(u[0]), abs(u[1])
    if half <= 0 or (uy > 1e-9 and r * ux / uy <= half):
        return r / uy if half > 0 else r
    return half * ux + np.sqrt(max(half ** 2 * ux ** 2 - half ** 2 + r ** 2, 0.0))


def _edge_values(node: Node, keys: list[frozenset]) -> dict[int, str]:
    """``edge-values="A-B:-0.3;B>C:1"`` -> edge index -> text (an edge may be named either way)."""
    out = {}
    for part in (p.strip() for p in node.attrs.get("edge-values", "").split(";") if p.strip()):
        key, _, v = part.partition(":")
        pair = edge_pair(key)
        if pair is None or pair not in keys:
            raise BeatError(f'<graph id={node.id}> edge-values "{part}": no edge "{key.strip()}" '
                            f'(write it like the edges, "A-B:value")')
        out[keys.index(pair)] = v.strip()
    return out


def _flows(node: Node, keys: list[frozenset]) -> list[tuple[str, ...]]:
    """``flow="A>B>C;A>D"`` -> routes; every step must follow an edge (either way round)."""
    routes = []
    for part in (p.strip() for p in node.attrs.get("flow", "").split(";") if p.strip()):
        r = tuple(x.strip() for x in part.split(">") if x.strip())
        bad = [f"{a}-{b}" for a, b in zip(r, r[1:]) if frozenset((a, b)) not in keys]
        if len(r) < 2 or bad:
            raise BeatError(f'<graph id={node.id}> flow="{part}": a route like "A>B>C" along edges'
                            + (f"; no edge {bad}" if bad else ""))
        routes.append(r)
    return routes


class GraphBlock(Block):
    """Nodes and (weighted, optionally directed) edges. ``highlight``/``dim`` name nodes,
    ``path="A-C-F"`` lights a route, ``values="A:0;B:7"`` shows a number by each node,
    ``edge-values`` a second number by each edge, ``strength`` draws edges thick or thin by their
    number (a strength; ``weighted`` only asks every edge for a number), ``flow``
    sends packets along edges into this beat. The parts keep their order across beats, so a
    step that re-styles the graph morphs in place."""

    tag = "graph"

    def __init__(self, node: Node):
        th = current()
        pos = _graph_nodes(node)
        names = list(pos)
        edges = _graph_edges(node, names)
        size = float(node.attrs.get("size", 32))
        hot, dim = _named(node, "highlight", names), _named(node, "dim", names)
        lc = self.lc = lit_color(node)
        route = [n.strip() for n in node.attrs.get("path", "").split("-") if n.strip()]
        bad = [n for n in route if n not in pos]
        if bad:
            raise BeatError(f'<graph id={node.id}> path="{node.attrs["path"]}": no node named {bad}')
        on_route = {frozenset(p) for p in zip(route, route[1:])}
        vals = {}
        for part in (p.strip() for p in node.attrs.get("values", "").split(";") if p.strip()):
            name, _, v = part.partition(":")
            if name.strip() not in pos:
                raise BeatError(f'<graph id={node.id}> values "{part}": no node named "{name.strip()}"')
            if v.strip().lower() not in UNKNOWN:      # no value yet: nothing by the node
                vals[name.strip()] = v.strip()
        keys = [frozenset((a, b)) for a, b, *_ in edges]
        evals = _edge_values(node, keys)
        self.flows = _flows(node, keys)
        # strength: the edges' numbers are drawn as thickness (attention, a probability). A cost
        # or a distance is not: "weighted" only asks for a number on every edge, drawn as a label.
        flag = lambda k: node.attrs.get(k, "").strip().lower() in ("true", "yes", "1")  # noqa: E731
        weighted = flag("strength")
        top = 1.0
        if weighted or flag("weighted"):
            nums = [as_num(w) for *_, w in edges]
            if any(n is None for n in nums):
                key = "strength" if weighted else "weighted"
                raise BeatError(f'<graph id={node.id}> {key}="true": every edge needs a number weight ("A>B:0.7")')
            top = max((abs(n) for n in nums), default=1.0) or 1.0
        lay = _layout(node)
        if lay in ("line", "two-lines"):
            self._init_lines(node, names, edges, size, hot, dim, on_route, vals, evals, weighted, top, lay)
            return
        # fit the layout into w x h, keeping its shape
        xy = np.array([pos[n] for n in names], float)
        w, h = float(node.attrs.get("w", 6)), float(node.attrs.get("h", 3.6))
        span = np.ptp(xy, axis=0)
        k = min(w / span[0] if span[0] > 1e-9 else np.inf, h / span[1] if span[1] > 1e-9 else np.inf)
        k = 1.0 if not np.isfinite(k) else k
        if lay == "tree":   # laid out in node widths: kept at true size (the page layout scales the block)
            k = 2 * NODE_R
        xy = (xy - xy.mean(axis=0)) * k
        at = {n: np.array([*xy[i], 0.0]) for i, n in enumerate(names)}
        # a sparse graph (a chain of a few units across the screen) gets bigger nodes and labels
        # for its spacing; the layout's growth (Display.grow) scales evenly and cannot change that
        gaps = [np.linalg.norm(xy[i] - xy[j]) for i in range(len(names)) for j in range(i)]
        g = 1.0
        if len(names) <= SPARSE_NODES:
            g = float(np.clip(0.11 * min(gaps, default=0.0) / NODE_R, 1.0, MAX_GROW))
        R = NODE_R * g
        size *= g
        self.grow = g

        # look="pages": each node a row of cells, one per key (a page of a B-tree, a bucket of
        # values); the edge to a page's k-th child leaves from the line between keys k-1 and k
        pages = node.attrs.get("look", "").strip() == "pages"
        if node.attrs.get("look", "").strip() not in ("", "pages"):
            raise BeatError(f'<graph id={node.id}> look="{node.attrs["look"]}": "pages" (each node a row of key cells)')
        cell = PAGE_CELL * 2 * R
        page_w = {n: cell * max(1, len(n.split())) for n in names}
        kids = {}
        for a, b, *_ in edges:
            kids.setdefault(a, []).append(b)

        def page_anchor(a: str, b: str) -> np.ndarray:
            """Where the edge from page a to its child b leaves a's bottom edge."""
            ks, ch = len(a.split()), kids.get(a, [])
            i = ch.index(b) if b in ch else 0
            frac = i / ks if len(ch) == ks + 1 else (i + 1) / (len(ch) + 1)
            return at[a] + np.array([-page_w[a] / 2 + frac * page_w[a], -R, 0.0])

        def page_rim(n: str, u: np.ndarray) -> float:
            hw, hh = page_w[n] / 2, R
            return min(hw / abs(u[0]) if abs(u[0]) > 1e-9 else np.inf, hh / abs(u[1]) if abs(u[1]) > 1e-9 else np.inf)

        # names first: a long name widens its node (a stadium), and edges stop at the outline
        name_mobs, half = {}, {}
        for n in names:
            if pages:
                name_mobs[n] = VGroup(*(_label(key, 0.8 * size, th.ink) for key in n.split()))
                half[n] = 0.0
                continue
            lab = _label(n, 0.8 * size, th.ink)
            room = 1.5 * R
            if lab.get_width() > room:
                lab.set_width(max(room, lab.get_width() * NAME_FLOOR))
            name_mobs[n], half[n] = lab, max(0.0, (lab.get_width() - room) / 2)

        pairs = {(a, b) for a, b, *_ in edges}
        self.free_side = []       # per edge: the side its edge value (and a passing packet's label) takes
        self.edges, self.weights, self.edge_labels = VGroup(), VGroup(), VGroup()
        for i, (a, b, directed, wt) in enumerate(edges):
            u = at[b] - at[a]
            u = u / (np.linalg.norm(u) or 1)
            normal = np.array([-u[1], u[0], 0])
            lit = frozenset((a, b)) in on_route
            color = th.accent if lit else th.muted
            # a pair of opposite one-way edges (A>B and B>A) run side by side, each on its left
            shift = normal * 0.1 * g if directed and (b, a) in pairs else ORIGIN
            start, end = at[a] + u * _rim(half[a], u, R) + shift, at[b] - u * _rim(half[b], -u, R) + shift
            if pages:
                if lay == "tree" and at[b][1] < at[a][1] - 1e-6:   # down to a child: from between two keys
                    start = page_anchor(a, b)
                    end = at[b] + np.array([0.0, R, 0.0])
                    u = (end - start) / (np.linalg.norm(end - start) or 1)
                    normal = np.array([-u[1], u[0], 0])
                else:
                    start, end = at[a] + u * page_rim(a, u), at[b] - u * page_rim(b, -u)
            tip = VMobject()
            if directed:
                side = normal * 0.11 * g
                tip = Polygon(end, end - 0.22 * g * u + side, end - 0.22 * g * u - side)
                tip.set_fill(color, 1).set_stroke(width=0)
                end = end - 0.18 * g * u
            width, opacity = (6 if lit else 3), 1.0
            if weighted:
                share = abs(as_num(wt)) / top
                width, opacity = 1.5 + 8 * share, 0.25 + 0.75 * share
            line = VGroup(Line(start, end).set_stroke(color, width, opacity), tip.set_opacity(opacity) if directed else tip)
            if a in dim or b in dim:
                line.set_opacity(0.3)
            self.edges.add(line)
            # the weight sits above (or left of) its edge, the edge value on the other side;
            # a side-by-side pair keeps both on its own outer side
            up = normal if normal[1] > 1e-6 or (abs(normal[1]) < 1e-6 and normal[0] > 0) else -normal
            sides = (normal, normal) if np.any(shift) else (up, -up)
            mid = (at[a] + at[b]) / 2 + shift
            self.free_side.append(sides[1])
            lab = _label(wt, 0.7 * size, lc if lit else th.muted) if wt else VMobject()
            gap = 0.0
            if wt:
                gap = 0.08 + 0.5 * self._across(lab, u)
                lab.move_to(mid + sides[0] * gap).set_backstroke(th.bg, 4)
            self.weights.add(lab)
            ev = evals.get(i)
            elab = _label(ev, 0.7 * size, th.palette[0]) if ev else VMobject()
            if ev:
                out = 0.08 + 0.5 * self._across(elab, u)
                if np.any(shift) and wt:
                    out += 2 * gap          # stacked beyond the weight
                elab.move_to(mid + sides[1] * out).set_backstroke(th.bg, 4)
            self.edge_labels.add(elab)
        self.nodes, self.values = VGroup(), VGroup()
        for n in names:
            lit = n in hot
            if pages:
                keys = name_mobs[n]
                shape = VGroup(*(Square(cell).set_fill(th.panel_fill, 1).set_stroke(*((lc, LIT_W) if lit else (th.ink, 2)))
                                 for _ in keys)).arrange(RIGHT, buff=0)
                shape.stretch_to_fit_height(2 * R)
                for c, key in zip(shape, keys):
                    if key.get_width() > 0.86 * cell:
                        key.set_width(0.86 * cell)
                    key.move_to(c)
                dot = VGroup(shape, keys).move_to(at[n])
            else:
                if half[n] > 0:
                    shape = RoundedRectangle(2 * (half[n] + R), 2 * R, corner_radius=R)
                else:
                    shape = Circle(radius=R)
                shape.set_fill(th.panel_fill, 1).set_stroke(*((lc, LIT_W) if lit else (th.ink, 2.5)))
                dot = VGroup(shape, name_mobs[n].move_to(shape)).move_to(at[n])
            if n in dim:
                dot.set_opacity(0.3)
            self.nodes.add(dot)
            v = vals.get(n)
            lab = _label(v, 0.75 * size, th.accent) if v else VMobject()
            if v:
                # outward from the layout's centre, so values stay clear of the edges inside;
                # as far out as the label reaches along that direction (a wide label beside a node)
                out = at[n] / (np.linalg.norm(at[n]) or 1) if np.linalg.norm(at[n]) > 1e-6 else UP
                reach = 0.5 * (abs(out[0]) * lab.get_width() + abs(out[1]) * lab.get_height())
                rim = page_rim(n, out) if pages else _rim(half[n], out, R)
                lab.move_to(at[n] + out * (rim + 0.12 + reach))
                lab.set_backstroke(th.bg, 4)
            self.values.add(lab)
        self.names, self.edge_keys = names, [(a, b) for a, b, *_ in edges]
        self.value_text = [vals.get(n, "") for n in names]
        self.edge_text = [evals.get(i, "") for i in range(len(edges))]
        self.size = size
        super().__init__(self.edges, self.weights, self.edge_labels, self.nodes, self.values)
        self.unit = self.nodes[0][0].get_height() if names else 2 * R    # to read the layout's scale later
        self.set_content(node, "nodes", "edges", "highlight", "dim", "path", "values",
                         "edge-values", "weighted", "flow", "layout", "look")

    def _init_lines(self, node, names, edges, size, hot, dim, on_route, vals, evals, weighted, top, lay) -> None:
        """``layout="line"``: the nodes in a row, spaced by their names, every edge an arc above
        the row (arcs into one node land side by side on its top). ``layout="two-lines"``: two
        rows, each centred, edges straight between them. Values sit under a row (over the top
        row of two)."""
        th = current()
        R = NODE_R
        self.grow = 1.0
        groups = _line_groups(node, lay)
        name_mobs, half = {}, {}
        for n in names:
            lab = _label(n, 0.8 * size, th.ink)
            name_mobs[n], half[n] = lab, max(0.0, (lab.get_width() - 1.5 * R) / 2)
        at = {}
        for gi, g in enumerate(groups):
            widths = [2 * (half[n] + R) for n in g]
            x = -(sum(widths) + LINE_GAP * (len(g) - 1)) / 2
            for n, w in zip(g, widths):
                at[n] = np.array([x + w / 2, -gi * LINES_APART, 0.0])
                x += w + LINE_GAP
        weight_labels = node.attrs.get("weight-labels", "").strip().lower() not in ("false", "no", "0", "none")
        # arcs into one node land side by side on its top, ordered by where they come from
        ends: dict[str, list[str]] = {}
        for a, b, *_ in edges:
            ends.setdefault(b, []).append(a)
        self.free_side, self.paths = [], VGroup()
        self.edges, self.weights, self.edge_labels = VGroup(), VGroup(), VGroup()
        pairs = {(a, b) for a, b, *_ in edges}
        for i, (a, b, directed, wt) in enumerate(edges):
            lit = frozenset((a, b)) in on_route
            color = self.lc if lit else th.muted
            width, opacity = (6 if lit else 3), 1.0
            if weighted:
                share = abs(as_num(wt)) / top
                width, opacity = 1.5 + 8 * share, 0.25 + 0.75 * share
                color = self.lc if lit else th.accent if share > 0.5 else _mix(th.muted, th.accent, share)
            if lay == "line":
                srcs = sorted(ends[b], key=lambda n: at[n][0])
                spread = min(0.18, (2 * (half[b] + R) - 0.3) / max(len(srcs), 1))
                off = (srcs.index(a) - (len(srcs) - 1) / 2) * spread
                start = at[a] + UP * (R + 0.04)
                end = at[b] + np.array([off, R + 0.04, 0])
                d = abs(end[0] - start[0]) or 1e-3
                h = 0.3 + 0.16 * d
                theta = 4 * np.arctan(2 * h / d) * (-1 if start[0] < end[0] else 1)
                path = Line(start, end, path_arc=theta)
            else:
                u = at[b] - at[a]
                u = u / (np.linalg.norm(u) or 1)
                start, end = at[a] + u * _rim(half[a], u, R), at[b] - u * _rim(half[b], -u, R)
                path = Line(start, end)
            tip = VMobject()
            if directed:
                tan = end - path.point_from_proportion(0.96)
                tan = tan / (np.linalg.norm(tan) or 1)
                side = np.array([-tan[1], tan[0], 0]) * 0.11
                tip = Polygon(end, end - 0.22 * tan + side, end - 0.22 * tan - side)
                tip.set_fill(color, opacity).set_stroke(width=0)
            curve = path.copy().set_stroke(color, width, opacity)
            if directed:
                curve.pointwise_become_partial(path, 0, 0.985)
                curve.set_stroke(color, width, opacity)
            line = VGroup(curve, tip)
            if a in dim or b in dim:
                line.set_opacity(0.3)
            self.edges.add(line)
            self.paths.add(path.set_stroke(opacity=0))
            mid = path.point_from_proportion(0.5)
            if lay == "line":
                lab_at, away = mid + UP * 0.2, UP
            else:                       # nearer the top row, on the outer side of the crossing
                lab_at, away = path.point_from_proportion(0.25), RIGHT if at[b][0] >= at[a][0] else LEFT
            self.free_side.append(away)
            lab = _label(wt, 0.7 * size, color) if wt and weight_labels else VMobject()
            if wt and weight_labels:
                lab.move_to(lab_at + away * 0.5 * lab.get_width() * (lay != "line")).set_backstroke(th.bg, 4)
            self.weights.add(lab)
            ev = evals.get(i)
            elab = _label(ev, 0.7 * size, th.palette[0]) if ev else VMobject()
            if ev:
                elab.move_to(lab_at + UP * 0.3 + away * 0.3).set_backstroke(th.bg, 4)
            self.edge_labels.add(elab)
        self.nodes, self.values = VGroup(), VGroup()
        first = set(groups[0])
        for n in names:
            lit = n in hot
            shape = RoundedRectangle(2 * (half[n] + R), 2 * R, corner_radius=R) if half[n] > 0 else Circle(radius=R)
            shape.set_fill(th.panel_fill, 1).set_stroke(*((self.lc, LIT_W) if lit else (th.ink, 2.5)))
            dot = VGroup(shape, name_mobs[n].move_to(shape)).move_to(at[n])
            if n in dim:
                dot.set_opacity(0.3)
            self.nodes.add(dot)
            v = vals.get(n)
            lab = _label(v, 0.75 * size, th.accent) if v else VMobject()
            if v:
                out = UP if lay == "two-lines" and n in first else DOWN
                lab.next_to(dot, out, buff=0.12).set_backstroke(th.bg, 4)
            self.values.add(lab)
        self.names, self.edge_keys = names, [(a, b) for a, b, *_ in edges]
        self.value_text = [vals.get(n, "") for n in names]
        self.edge_text = [evals.get(i, "") for i in range(len(edges))]
        self.size = size
        Block.__init__(self, self.edges, self.weights, self.edge_labels, self.nodes, self.values, self.paths)
        self.unit = self.nodes[0][0].get_height() if names else 2 * R
        self.set_content(node, "nodes", "edges", "highlight", "dim", "path", "values",
                         "edge-values", "weighted", "flow", "layout", "weight-labels")

    @staticmethod
    def _across(lab: Mobject, u: np.ndarray) -> float:
        """A label's extent across an edge of direction u."""
        return abs(u[1]) * lab.get_width() + abs(u[0]) * lab.get_height()

    def scale_now(self) -> float:
        """How much the layout scaled the block since it was built."""
        return self.nodes[0][0].get_height() / self.unit if len(self.nodes) else 1.0

    def leg(self, a: str, b: str) -> tuple[int, np.ndarray, np.ndarray]:
        """The edge a packet from a to b runs along, and its ends as drawn now."""
        i = next(k for k, e in enumerate(self.edge_keys) if set(e) == {a, b})
        if getattr(self, "paths", None) is not None:   # a line layout: the drawn curve, end to end
            path = self.paths[i]
            p, q = path.get_start(), path.get_end()
            return (i, p, q) if self.edge_keys[i][0] == a else (i, q, p)
        line = self.edges[i][0]
        p, q = line.get_start(), line.get_end()
        if self.edges[i][1].has_points():          # a one-way edge ends at its tip's point
            q = self.edges[i][1].get_start()
        return (i, p, q) if self.edge_keys[i][0] == a else (i, q, p)


def _packet(start: np.ndarray, end: np.ndarray, text: str, color: str, size: float,
            lo: float, hi: float, side: np.ndarray = UP, r: float = 0.11, path: Mobject | None = None) -> Animation:
    """A dot (with what it carries written above) running from start to end between lo and hi
    of the beat's motion, lighting the edge behind it. A carrier of fixed structure, removed
    afterwards (see displays/system/_send); UpdateFromAlphaFunc ignores rate_func, so the
    timing is done here."""
    th = current()
    trail = VMobject().set_points_as_corners([start, start]).set_stroke(color, 5, 0).set_fill(opacity=0)
    dot = Dot(radius=r).set_fill(color, 1).set_stroke(th.bg, 2).move_to(start)
    lab = _label(text, size, color) if text else VMobject()
    if text:
        lab.set_backstroke(th.bg, 5)
    # the label rides on the edge's free side (the weight is on the other one)
    u = (end - start) / (np.linalg.norm(end - start) or 1)
    off = side * (r + 0.08 + 0.5 * GraphBlock._across(lab, u)) if text else ORIGIN
    carrier = VGroup(trail, dot, lab)
    carrier.fix_in_frame()      # overlay space (a fresh mobject is not)

    pts = None
    if path is not None:     # along the drawn curve (an arc), from start to end
        pts = [path.point_from_proportion(x) for x in np.linspace(0, 1, 40)]
        if np.linalg.norm(pts[0] - start) > np.linalg.norm(pts[-1] - start):
            pts = pts[::-1]

    def update(c, alpha):
        tr, d, lb = c
        t = (alpha - lo) / ((hi - lo) or 1)
        s_ = smooth(float(np.clip(t, 0, 1)))
        seen = 0.0 if t <= 0 or t >= 1 else min(1.0, 8 * t, 8 * (1 - t))
        if pts is not None:
            k = max(2, int(round(s_ * 39)) + 1)
            at = pts[k - 1]
            tr.set_points_as_corners(pts[:k])
        else:
            at = start + (end - start) * s_
            tr.set_points_as_corners([start, at] if np.linalg.norm(at - start) > 1e-4 else [start, start + 1e-4 * RIGHT])
        tr.set_stroke(color, 5, 0.85 * seen)
        d.move_to(at).set_opacity(seen)
        if text:
            lb.move_to(at + off).set_opacity(seen)
    return UpdateFromAlphaFunc(carrier, update, rate_func=linear, remover=True)


def _mix(a: str, b: str, t: float) -> str:
    """Between two colours in perceived lightness (a weak link muted, a strong one the accent)."""
    x, y = np.array(color_to_rgb(a)), np.array(color_to_rgb(b))
    return rgb_to_hex(np.sqrt(x ** 2 + (y ** 2 - x ** 2) * float(np.clip(t, 0, 1))))


def _rated(anim: Animation, lo: float, hi: float) -> Animation:
    anim.rate_func = squish_rate_func(smooth, lo, hi)
    return anim


def _graph(old: GraphBlock, new: GraphBlock) -> Animation:
    """Same nodes and edges: nodes and edges re-colour in place (a route lights up edge by
    edge), and a node's value is replaced where it stands. A new ``flow`` sends a packet along
    each route, leg after leg; a node's new value (and its highlight) and an edge's new edge
    value appear as the packet reaches them, so the values are seen to travel; the rest
    changes before the packets leave."""
    th = current()
    routes = [r for r in new.flows if r not in old.flows]
    edge_at: dict[int, float] = {}    # when a packet has crossed an edge
    node_at: dict[int, float] = {}    # when a packet reaches a node
    sent: dict[int, float] = {}       # a route's first node: changes as it sends
    travel = []
    t0, t1 = TRAVEL
    k = 0.7 * new.size * new.scale_now()
    for r in routes:
        legs = list(zip(r, r[1:]))
        for j, (a, b) in enumerate(legs):
            lo, hi = t0 + (t1 - t0) * j / len(legs), t0 + (t1 - t0) * (j + 1) / len(legs)
            i, p, q = new.leg(a, b)
            ia, ib = new.names.index(a), new.names.index(b)
            grad = new.edge_text[i] and new.edge_text[i] != old.edge_text[i]
            # what travels: the edge's new value (flowing back), else the value leaving the node
            text = new.edge_text[i] if grad else new.value_text[ia]
            color = th.palette[0] if grad else th.accent
            travel.append(_packet(p, q, text, color, k, lo, hi, new.free_side[i],
                                  0.11 * new.grow * new.scale_now(),
                                  new.paths[i] if getattr(new, "paths", None) is not None else None))
            edge_at[i] = min(edge_at.get(i, 1.0), hi)
            node_at[ib] = min(node_at.get(ib, 1.0), hi)
            if j == 0:
                sent[ia] = min(sent.get(ia, 1.0), lo)

    def when(t: float | None, anim: Animation) -> Animation:
        if not routes:
            return anim
        if t is None:                           # off the routes: before the packets leave
            return _rated(anim, 0.0, t0 + 0.04)
        return _rated(anim, max(0.0, t - 0.06), min(1.0, t + 0.1))

    # packets run on the NEW edges: if the layout moved the graph this beat, it moves first
    moved = any(np.linalg.norm(a.get_center() - b.get_center()) > 0.02 for a, b in zip(old.nodes, new.nodes))
    anims = []
    for i, (a, b) in enumerate(zip(old.edges, new.edges)):
        anims.append(when(None if moved else edge_at.get(i), Transform(a, b)))
    for i, (a, b) in enumerate(zip(old.nodes, new.nodes)):
        anims.append(when(None if moved else node_at.get(i, sent.get(i)), Transform(a, b)))
    anims += [when(None, _swap(a, b)) for a, b in zip(old.weights, new.weights)]
    anims += [when(edge_at.get(i), Transform(a, b) if u == v else _swap(a, b))
              for i, (a, b, u, v) in enumerate(zip(old.edge_labels, new.edge_labels, old.edge_text, new.edge_text))]
    anims += [when(node_at.get(i, sent.get(i)), Transform(a, b) if u == v else _swap(a, b))
              for i, (a, b, u, v) in enumerate(zip(old.values, new.values, old.value_text, new.value_text))]
    return AnimationGroup(*anims, *travel)


def build(node: Node, world=None) -> GraphBlock:
    return GraphBlock(node)


def morph(old: GraphBlock, new: GraphBlock, sources=None) -> Animation | None:
    if old.names == new.names and old.edge_keys == new.edge_keys:
        return _graph(old, new)
    return _relink(old, new)


def _relink(old: GraphBlock, new: GraphBlock) -> Animation:
    """Other nodes or edges, or the same ones listed in another order: every node and edge
    turns into the one of the same name, wherever it now stands. Nodes and edges that go fade
    first, new edges grow from their source node, new nodes fade in. (Matched by position in
    the list, a node listed in another place turned into its neighbour: two towns swapped.)"""
    anims = []
    at = {n: i for i, n in enumerate(old.names)}
    for j, n in enumerate(new.names):
        if n in at:
            anims += [Transform(old.nodes[at[n]], new.nodes[j]), _swap(old.values[at[n]], new.values[j])]
        else:
            anims.append(_rated(FadeIn(VGroup(new.nodes[j], new.values[j])), 0.2, 0.6))
    gone_nodes = [i for n, i in at.items() if n not in set(new.names)]
    anims += [_rated(FadeOut(VGroup(old.nodes[i], old.values[i])), 0.0, 0.25) for i in gone_nodes]
    kept = {e: i for i, e in enumerate(old.edge_keys)}
    used = set()
    for j, e in enumerate(new.edge_keys):
        i = kept.get(e, kept.get(e[::-1]))    # an edge named the other way round is the same road
        if i is not None and i not in used:
            used.add(i)
            anims += [Transform(old.edges[i], new.edges[j]), _swap(old.weights[i], new.weights[j]),
                      _swap(old.edge_labels[i], new.edge_labels[j])]
        else:
            lo = 0.25 + 0.3 * j / max(len(new.edge_keys), 1)
            anims += [_rated(ShowCreation(new.edges[j][0]), lo, lo + 0.4),
                      _rated(FadeIn(new.edges[j][1]), lo + 0.35, lo + 0.45),
                      _rated(FadeIn(new.weights[j]), lo + 0.3, lo + 0.5),
                      _rated(FadeIn(new.edge_labels[j]), lo + 0.3, lo + 0.5)]
    gone = [i for i in range(len(old.edge_keys)) if i not in used]
    anims += [_rated(FadeOut(VGroup(old.edges[i], old.weights[i], old.edge_labels[i])), 0.0, 0.25) for i in gone]
    return AnimationGroup(*anims)
