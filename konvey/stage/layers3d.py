"""Layered 3D pictures for ``<world>`` (manimgl): a stack of layers that data flows through, and a
block of cells.

- ``<stack3d id layers="SWA*2, (Full, Reuse*5)*3">``: one slab per layer, standing in a row along
  x in the order written (``name*n`` repeats a layer, ``( … )*n`` a pattern), laid out by the
  renderer the way 3b1b draws a transformer (videos/_2024/transformers/network_flow.py: glass
  blocks the column vectors pass through). Each kind of layer has its own colour
  (``colors="Full:accent; Reuse:c2"`` to choose). Runs of one kind are named once
  (``Reuse ×5``) under the stack, or for a long stack in a key above it
  (``labels="runs|key|none"``). ``groups="encoder:0-19; decoder:20-39"``: a bracket and a name
  under each run of layers, with a wider gap between them. ``highlight`` / ``dim``: layers by
  index (``"2,5-7"``) or by kind (``"Full"``). ``links="19>20-39:KV"``: what one layer hands to
  others (a shared cache, a skip): a rail above the stack from that layer down into each target.
  ``at="7"`` with ``tokens="the,cat,sat"`` (or a count): a sheet of column vectors, one per
  token, standing at that layer (-1: in front of the first, the layer count: past the last). A
  later beat's ``at`` sends it through the layers between while the line is spoken (``LIVE``);
  each layer lights as it passes and the vectors' entries change in it.
- ``<grid3d id shape="nx,ny,nz">``: a block of nx × ny × nz cells (a tensor, an image's pixels
  and channels, a box of unit cubes). ``labels="layers,tokens,bytes"`` names the three edges;
  ``merge="1,4,1"`` merges cells in groups along an axis: the lines between them fade and the
  block shortens to the merged count (a compression, a pooling). ``slices="x"`` cuts the block
  into its slices along an axis: ``gap`` pulls them apart, ``paint="0-1:c3; 2-9:c1"`` colours
  them, ``highlight="3"`` lights some.

Both are drawn without the depth test and sorted far-to-near from the camera every frame (3b1b's
blocks: ``deactivate_depth_test`` + ``sort``), so glass in front of glass reads correctly.
"""

from __future__ import annotations

import re
import zlib

import numpy as np

from manimlib import *  # noqa: F401,F403

from .displays.base import index_set
from .solids import _face_surface, _faces, _pinned_text, _unit_vertices, project
from .theme import current
from .tree import BeatError

TAGS = {"stack3d", "grid3d"}
ATTRS = {
    "stack3d": {"id", "layers", "colors", "labels", "groups", "highlight", "dim", "links", "at", "tokens",
                "entries", "look", "open"},
    "grid3d": {"id", "shape", "labels", "merge", "slices", "gap", "paint", "highlight", "color", "cell"},
}
ORDER = {"stack3d": 0, "grid3d": 0}


# --- small parsers ---------------------------------------------------------------------------------
def _split_top(spec: str, seps: str = ",;") -> list[str]:
    """Split at separators outside parentheses."""
    out, depth, cur = [], 0, ""
    for ch in spec:
        depth += (ch == "(") - (ch == ")")
        if ch in seps and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    out.append(cur.strip())
    return [p for p in out if p]


def _refs(node, key: str, names: list[str]) -> set[int]:
    """Layers by index (``"2,5-7"``) or by kind (``"Full"``)."""
    out: set[int] = set()
    for part in (p.strip() for p in node.attrs.get(key, "").split(",") if p.strip()):
        if re.fullmatch(r"\d+(\s*-\s*\d+)?", part):
            out |= index_set(part.replace(" ", ""), len(names), f"<{node.tag} id={node.id}> {key}")
        elif part in names:
            out |= {k for k, n in enumerate(names) if n == part}
        else:
            raise BeatError(f'<{node.tag} id={node.id}> {key}="{part}": not a layer index (0..{len(names) - 1}) '
                            f"or a kind ({', '.join(dict.fromkeys(names))})")
    return out


def _named_ranges(node, key: str, n: int) -> list[tuple[str, set[int]]]:
    """``"encoder:0-19; decoder:20-39"`` -> [(name, indices)]."""
    out = []
    for item in _split_top(node.attrs.get(key, ""), ";"):
        name, _, rng = item.rpartition(":")
        if not name.strip():
            raise BeatError(f'<{node.tag} id={node.id}> {key}="{item}": use "name:0-19"')
        out.append((name.strip(), index_set(rng, n, f"<{node.tag} id={node.id}> {key}")))
    return out


def _num(node, key: str, default: float) -> float:
    try:
        return float(node.attrs.get(key, default))
    except ValueError:
        raise BeatError(f'<{node.tag} id={node.id}> {key}="{node.attrs.get(key)}": a number') from None


def _box_faces(c: np.ndarray, half: np.ndarray) -> list[Surface]:
    v = _unit_vertices("box", 4) * half + c
    return [_face_surface(v[f]) for f in _faces(v)]


def _box_edges(c: np.ndarray, half: np.ndarray) -> VMobject:
    v = _unit_vertices("box", 4) * half + c
    edge = VMobject()
    for a in range(8):
        for b in range(a + 1, 8):
            if np.count_nonzero(np.abs(v[a] - v[b]) > 1e-9) == 1:   # differ along one axis: an edge
                edge.start_new_path(v[a])
                edge.add_line_to(v[b])
    return edge


def _set_segments(vm: VMobject, segs, ops):
    """Many separate straight lines as one VMobject, each with its own opacity. manimgl marks a
    new sub-path by a handle sitting on the previous anchor: a0 m0 b0 | b0 a1 m1 b1 | …"""
    if not segs:
        vm.set_points(np.zeros((1, 3)))
        vm.set_stroke(opacity=0)
        return
    pts, alpha = [], []
    for k, ((a, b), o) in enumerate(zip(segs, ops)):
        block = [a, (a + b) / 2, b] if k == 0 else [segs[k - 1][1], a, (a + b) / 2, b]
        pts += block
        alpha += [o] * len(block)
    vm.set_points(np.array(pts))
    vm.set_stroke(opacity=np.array(alpha))


def _flat(mob):
    mob.deactivate_depth_test()
    return mob


class _Painter:
    """Glass drawn far-to-near: every frame the items are re-ordered by their distance from the
    camera (only when the order changes, which re-submits the group)."""

    def _sort(self, group: Group, items: list, keys: list[np.ndarray]):
        if self.fw is None or self.fw.frame is None:
            return
        eye = self.fw.frame.get_implied_camera_location()
        d = [float(np.linalg.norm(k - eye)) for k in keys]
        order = [items[j] for j in np.argsort(d)[::-1]]
        if [id(m) for m in order] != [id(m) for m in group.submobjects]:
            group.set_submobjects(order)


# --- <stack3d> -------------------------------------------------------------------------------------
def parse_layers(spec: str) -> list:
    """``"in*2, (a, b*2)*3"`` -> [("leaf", "in", 2), ("rep", [("leaf", "a", 1), ("leaf", "b", 2)], 3)]."""
    out = []
    for item in _split_top(spec, ","):
        m = re.fullmatch(r"(.*)\*\s*(\d+)", item)
        body, n = (m.group(1).strip(), int(m.group(2))) if m else (item, 1)
        if body.startswith("(") and body.endswith(")"):
            out.append(("rep", parse_layers(body[1:-1]), n))
        elif body and not set(body) & set("()*"):
            out.append(("leaf", body, n))
        else:
            raise BeatError(f'layers: "{item}" — write a name, name*n, or (a, b)*n')
    return out


def _unfold(tree) -> tuple[list[tuple[str, int]], list[tuple[int, int, int]], list[tuple[str, int, int]]]:
    """(leaves as written: (name, count); repeats: (first leaf, last leaf, times); every layer in
    order: (name, its leaf, its place in that leaf's run))."""
    leaves, reps, ids = [], [], {}

    def visit(nodes):
        for nd in nodes:
            if nd[0] == "leaf":
                ids[id(nd)] = len(leaves)
                leaves.append((nd[1], nd[2]))
            else:
                first = len(leaves)
                visit(nd[1])
                reps.append((first, len(leaves) - 1, nd[2]))

    def expand(nodes):
        for nd in nodes:
            if nd[0] == "leaf":
                yield from ((nd[1], ids[id(nd)], j) for j in range(nd[2]))
            else:
                for _ in range(nd[2]):
                    yield from expand(nd[1])

    visit(tree)
    return leaves, reps, list(expand(tree))


def expand_layers(spec: str) -> list[str]:
    """``"SWA*2, (Full, Reuse*2)*2"`` -> SWA SWA Full Reuse Reuse Full Reuse Reuse."""
    return [name for name, _, _ in _unfold(parse_layers(spec))[2]]


def _quad(x0, x1, z0, z1, y=0.0) -> Surface:
    """A flat rectangle standing in the x-z plane, facing -y (the diagram's paper)."""
    return _face_surface(np.array([[x0, y, z0], [x1, y, z0], [x1, y, z1], [x0, y, z1]]))


class _Placed:
    """Unit-box faces and edges placed every frame at a centre and half-size."""

    def __init__(self, faces, edges):
        self.faces, self.edges = faces, edges
        self.fbase = [{k: f.data[k].copy() for k in ("point", "du_point", "dv_point")} for f in faces]
        self.ebase = edges.get_points().copy()

    def place(self, c, half):
        for f, base in zip(self.faces, self.fbase):
            for k, pts in base.items():
                f.data[k][:] = pts * half + c
            f.note_changed_data()
        self.edges.set_points(self.ebase * half + c)


class Stack3D(_Painter):
    LIVE = ("at", "at1")
    H, D = 2.4, 2.4           # slab height (z) and depth (y)
    BODY = 0.22               # glass opacity of a resting slab
    HD = 1.0                  # height of a box in the flat diagram
    PANEL = (7.2, 4.05)       # an opened layer: a panel this wide and tall, facing the camera

    def __init__(self, i, nodes, world):
        th = current()
        self.id, self.fw = i, None
        specs = {n.attrs["layers"].strip() for n in nodes if n.attrs.get("layers", "").strip()}
        if not specs:
            raise BeatError(f'<stack3d id={i}> needs layers="…" (e.g. "embed, (attention, mlp)*3")')
        if len(specs) > 1:
            raise BeatError(f'<stack3d id={i}>: keep the same layers= in every beat (a different stack is '
                            "a new id); change highlight, dim, links or at instead")
        self.leaves, self.reps, slabs = _unfold(parse_layers(specs.pop()))
        self.names = names = [s[0] for s in slabs]
        N = len(names)
        if not 1 <= N <= 120:
            raise BeatError(f'<stack3d id={i}> has {N} layers; use 1 to 120')
        n0 = nodes[0]
        for n in nodes:
            if n.attrs.get("look", "glass") not in ("glass", "diagram"):
                raise BeatError(f'<stack3d id={i}> look="{n.attrs["look"]}": use glass or diagram')
        self.kinds = list(dict.fromkeys(names))
        pal = [*th.palette]
        self.kind_color = {k: pal[j] if j < len(pal) else th.muted for j, k in enumerate(self.kinds)}
        for item in _split_top(n0.attrs.get("colors", ""), ";,"):
            k, _, c = item.rpartition(":")
            if k.strip() not in self.kind_color:
                raise BeatError(f'<stack3d id={i}> colors="{item}": no layer kind "{k.strip()}"')
            self.kind_color[k.strip()] = th.color(c.strip())
        mode = n0.attrs.get("labels", "auto").strip()
        if mode not in ("auto", "runs", "key", "none"):
            raise BeatError(f'<stack3d id={i}> labels="{mode}": use runs, key or none')
        self.mode = ("runs" if N <= 12 else "key") if mode == "auto" else mode

        # groups and links: every spec any beat uses, each faded in and out by the state
        self.groups: list[tuple[str, set[int]]] = []
        self.links: list[tuple[int, list[int], str]] = []
        for n in nodes:
            for g in _named_ranges(n, "groups", N):
                if g[0] not in [h[0] for h in self.groups]:
                    self.groups.append(g)
            for spec in _split_top(n.attrs.get("links", ""), ";"):
                key = self._link(n, spec)
                if key not in self.links:
                    self.links.append(key)

        # glass layout along x: the pitch shrinks with the count so the stack stays ~10 units long
        pitch = float(np.clip(10.0 / N, 0.25, 1.3))
        self.t = pitch * (0.4 if N > 12 else 0.42)
        self.body = self.BODY if N <= 12 else 0.12   # many panes of glass add up: each one fainter
        starts = {min(g) for _, g in self.groups}
        xs, x = [], 0.0
        for k in range(N):
            if k and k in starts:
                x += max(0.5, pitch)
            xs.append(x)
            x += pitch
        xs = np.array(xs) - (xs[0] + xs[-1]) / 2
        self.xs = xs
        lead = max(1.5 * pitch, 1.4)
        self.track = (np.arange(-1, N + 1), np.r_[xs[0] - lead, xs, xs[-1] + lead])
        H, D = self.H, self.D
        self._diagram_layout(slabs, starts)

        # slabs: glass faces + edges, placed every frame, sorted far-to-near
        self.slab_faces, self.slab_edges, self.colors, self.placed = [], [], [], []
        for k, name in enumerate(names):
            col = self.kind_color[name]
            faces = [_flat(f.set_color(col, self.body).set_shading(0.35, 0.25, 0.0))
                     for f in _box_faces(np.zeros(3), np.ones(3))]
            edges = _flat(_box_edges(np.zeros(3), np.full(3, 1.002)).set_stroke(col, 1.6, 0.9))
            self.slab_faces.append(faces)
            self.slab_edges.append(edges)
            self.colors.append(col)
            self.placed.append(_Placed(faces, edges))
        self.glass = Group(*(f for fs in self.slab_faces for f in fs), *self.slab_edges)

        # rails that do not overlap share a height (interval packing, in the order first used)
        self.level, taken = [], []
        for src, dst, _ in self.links:
            span = (min(src, dst[0]), max(src, dst[-1]))
            lv = 0
            while any(l == lv and not (span[1] < a or b < span[0]) for l, (a, b) in taken):
                lv += 1
            self.level.append(lv)
            taken.append((lv, span))
        self._sheet(nodes, th)
        self.rails = Group(*(self._rail(k, link, th) for k, link in enumerate(self.links)))
        self.brackets = VGroup(*(_flat(VMobject().set_stroke(th.muted, 2)) for _ in self.groups))
        self.pins: list[tuple[Mobject, np.ndarray, np.ndarray]] = []   # (text, 3D point, screen nudge)
        self._labels(th)
        self.diagram = self._diagram(th)
        self.mob = Group(self.diagram, self.glass, self.rails, self.brackets, Group(*(p[0] for p in self.pins)))

    # --- the flat diagram -------------------------------------------------------
    def _diagram_layout(self, slabs, starts):
        """One box per run as written (``Reuse ×5``), left to right with room for an arrow
        between boxes; a repeated pattern gets a frame (``×3``). Each group is a row of its own,
        the first on top (the paper's figure, not one long line of small boxes)."""
        self.leaf_label = [name + (f" ×{n}" if n > 1 else "") for name, n in self.leaves]
        row_of = [0] * len(self.leaves)
        for k, (_, leaf, _) in enumerate(slabs):
            if slabs[k][2] == 0 and k == next(j for j, sl in enumerate(slabs) if sl[1] == leaf):
                row_of[leaf] = next((g for g, (_, idx) in enumerate(self.groups) if k in idx), 0)
        rows = sorted(set(row_of))
        rep_start = {a for a, _, _ in self.reps}
        rep_end = {b for _, b, _ in self.reps}
        self.row_gap = self.HD + 1.7
        zc = self.H / 2
        boxes = [None] * len(self.leaves)
        for r, row in enumerate(rows):
            members = [L for L in range(len(self.leaves)) if row_of[L] == row]
            x, spans = 0.0, []
            for n_, L in enumerate(members):
                if n_:
                    x += 0.75 + (0.3 if L in rep_start else 0) + (0.3 if L - 1 in rep_end else 0)
                w = max(1.3, 0.2 * len(self.leaf_label[L]) + 0.6)
                spans.append((L, x, x + w))
                x += w
            z = zc + (len(rows) - 1) / 2 * self.row_gap - r * self.row_gap
            for L, x0, x1 in spans:
                boxes[L] = (x0 - x / 2, x1 - x / 2, z)
        self.dbox = boxes
        self.row_of = [rows.index(r) for r in row_of]
        self.slab_flat = []      # (centre, half) of each layer inside its box
        for name, leaf, j in slabs:
            x0, x1, z = boxes[leaf]
            n = self.leaves[leaf][1]
            w = (x1 - x0) / n
            self.slab_flat.append((np.array([x0 + (j + 0.5) * w, 0, z]), np.array([w / 2, 0.01, self.HD / 2])))
        self.slab_leaf = [leaf for _, leaf, _ in slabs]

    def _diagram(self, th) -> Group:
        h = self.HD / 2
        parts = Group()
        self.d_faces, self.d_lines, self.d_tips, self.d_edges = [], [], [], []
        for L, ((x0, x1, zc), (name, _)) in enumerate(zip(self.dbox, self.leaves)):
            col = self.kind_color[name]
            face = _flat(_quad(x0, x1, zc - h, zc + h).set_color(col, 0.22).set_shading(0, 0, 0))
            edge = _flat(VMobject().set_points_as_corners(
                [[x0, 0, zc - h], [x1, 0, zc - h], [x1, 0, zc + h], [x0, 0, zc + h], [x0, 0, zc - h]]))
            parts.add(face, edge.set_stroke(col, 2.6))
            self.d_faces.append(face)
            self.d_lines.append(edge)
            self.d_edges.append((edge, col))
            self._pin(_pinned_text(self.leaf_label[L], th.ink, 24), [(x0 + x1) / 2, 0, zc], ORIGIN, ("dia",))
        arrows = VMobject()

        def tip_at(p, d):     # an arrow head at p pointing along the unit vector d (in x-z)
            side = np.array([-d[2], 0, d[0]])
            tip = VMobject().set_points_as_corners([p, p - 0.2 * d + 0.09 * side, p - 0.2 * d - 0.09 * side, p])
            parts.add(_flat(tip.set_fill(th.muted, 1).set_stroke(width=0)))
            self.d_tips.append(tip)

        for L in range(len(self.leaves) - 1):
            za, (b0, _, zb) = self.dbox[L][2], self.dbox[L + 1]
            a = self.dbox[L][1] + 0.08
            if abs(za - zb) < 1e-6:
                arrows.start_new_path([a, 0, za])
                arrows.add_line_to([b0 - 0.22, 0, za])
                tip_at(np.array([b0 - 0.08, 0, za]), RIGHT)
            else:    # to the start of the next row: out, down between the rows, back, in
                zm = zb + self.HD / 2 + 0.5    # just above the next row, under the last row's name
                xr, xl = a + 0.35, b0 - 0.45
                arrows.start_new_path([a, 0, za])
                for q in ([xr, 0, za], [xr, 0, zm], [xl, 0, zm], [xl, 0, zb], [b0 - 0.22, 0, zb]):
                    arrows.add_line_to(q)
                tip_at(np.array([b0 - 0.08, 0, zb]), RIGHT)
        parts.add(_flat(arrows.set_stroke(th.muted, 2.2)))
        self.d_lines.append(arrows)
        pad = 0.24
        for a, b, n in self.reps:
            x0, x1, zc = self.dbox[a][0] - pad, self.dbox[b][1] + pad, self.dbox[a][2]
            frame = VMobject().set_points_as_corners(
                [[x0, 0, zc - h - pad], [x1, 0, zc - h - pad], [x1, 0, zc + h + pad], [x0, 0, zc + h + pad],
                 [x0, 0, zc - h - pad]])
            parts.add(_flat(frame.set_stroke(th.muted, 1.6)))
            self.d_lines.append(frame)
            self._pin(_pinned_text(f"×{n}", th.ink, 26), [x1, 0, zc + h + pad], 0.32 * RIGHT, ("dia",))
        return parts

    # --- parts ----------------------------------------------------------------
    def _link(self, n, spec: str) -> tuple[int, tuple[int, ...], str]:
        m = re.fullmatch(r"\s*(\d+)\s*>\s*([\d,\s-]+?)\s*(?::(.*))?", spec)
        if not m:
            raise BeatError(f'<stack3d id={n.id}> links="{spec}": use "from>to" like "19>20-39" or "3>5,7:skip"')
        N = len(self.names)
        src = int(m.group(1))
        if src >= N:
            raise BeatError(f'<stack3d id={n.id}> links="{spec}": layer {src} is outside 0..{N - 1}')
        dst = tuple(sorted(index_set(m.group(2), N, f"<stack3d id={n.id}> links")))
        return src, dst, (m.group(3) or "").strip()

    def _sheet(self, nodes, th):
        specs = {n.attrs["tokens"].strip() for n in nodes if n.attrs.get("tokens", "").strip()}
        if len(specs) > 1:
            raise BeatError(f'<stack3d id={self.id}>: keep the same tokens= in every beat')
        spec = specs.pop() if specs else "5"
        self.tok_names = [] if spec.isdigit() else [s.strip() for s in spec.split(",")]
        T = int(spec) if spec.isdigit() else len(self.tok_names)
        E = int(_num(nodes[0], "entries", 6))
        if not (1 <= T <= 16 and 2 <= E <= 12):
            raise BeatError(f'<stack3d id={self.id}>: tokens 1..16 and entries 2..12')
        H, D = self.H, self.D
        py = min(0.46, 0.86 * D / T)
        w = 0.72 * py
        hc = min(0.8 * H / E, 1.3 * w)
        ys = (np.arange(T) - (T - 1) / 2) * py
        zs = H / 2 + (np.arange(E)[::-1] - (E - 1) / 2) * hc
        self.tok_y, self.col_top = ys, H / 2 + E * hc / 2
        cells = []
        for y in ys:
            for z in zs:
                a, b = w / 2, 0.43 * hc     # half width, half height: a hair apart, like matrix entries
                loop = np.array([[0, y - a, z - b], [0, y + a, z - b], [0, y + a, z + b], [0, y - a, z + b]])
                cells.append(_flat(_face_surface(loop).set_shading(0.2, 0.2, 0)))
        self.cells = Group(*cells)
        self._cell_base = [c.data["point"].copy() for c in cells]
        self._cell_tan = [{k: c.data[k] - c.data["point"] for k in ("du_point", "dv_point")} for c in cells]
        rng = np.random.default_rng(zlib.crc32(self.id.encode()))   # the same in every scene's process
        self.values = rng.uniform(-1, 1, (len(self.names) + 1, T * E))   # entries after 0, 1, … layers
        self.neg, self.pos, self.zero = th.palette[2], th.palette[0], th.panel_stroke
        self.glass.add(self.cells)

    def _rail(self, k, link, th) -> Group:
        src, dst, _ = link
        H, xs = self.H, self.xs
        z = self.rail_z(self.level[k])
        path = VMobject()
        path.start_new_path([xs[src], 0, H + 0.02])
        path.add_line_to([xs[src], 0, z])
        lo, hi = min(xs[src], xs[dst[0]]), max(xs[src], xs[dst[-1]])
        path.start_new_path([lo, 0, z])
        path.add_line_to([hi, 0, z])
        for d in dst:
            path.start_new_path([xs[d], 0, z])
            path.add_line_to([xs[d], 0, H + 0.16])
        path.set_stroke(th.accent, 2.4)
        tips = VGroup(*(VMobject().set_fill(th.accent, 1).set_stroke(width=0) for _ in dst))
        dot = Sphere(radius=0.055, resolution=(10, 6)).move_to([xs[src], 0, H + 0.02]).set_color(th.accent)
        g = Group(_flat(path), _flat(tips), _flat(dot))
        g.tips_at = [np.array([xs[d], 0, H + 0.01]) for d in dst]
        return g

    def rail_z(self, k: int) -> float:
        return self.H + 0.32 + 0.3 * k

    def _top(self) -> float:
        """Above the slabs, the rails and the rails' names."""
        if not self.links:
            return self.H + 0.3
        return self.rail_z(max(self.level)) + (0.75 if any(l[2] for l in self.links) else 0.3)

    def _bracket_z(self) -> float:
        return -0.62 if self.mode == "runs" else -0.22

    def _labels(self, th):
        H, D, xs = self.H, self.D, self.xs
        self.pin_kind = []          # ("run", k0, k1) | ("group", g) | ("link", k) | ("tok", j) | ("key",) | ("dia",)
        if self.mode == "runs":
            k = 0
            while k < len(self.names):
                j = k
                while j + 1 < len(self.names) and self.names[j + 1] == self.names[k]:
                    j += 1
                text = self.names[k] + (f" ×{j - k + 1}" if j > k else "")
                self._pin(_pinned_text(text, th.ink, 24), [(xs[k] + xs[j]) / 2, -D / 2, 0], 0.26 * DOWN, ("run", k, j))
                k = j + 1
        elif self.mode == "key":
            key = VGroup()
            for kind in self.kinds:
                sw = Square(0.2).set_fill(self.kind_color[kind], 0.85).set_stroke(self.kind_color[kind], 1.5)
                key.add(VGroup(sw, _pinned_text(kind, th.ink, 22)).arrange(RIGHT, buff=0.12))
            key.arrange(RIGHT, buff=0.42)
            key.fix_in_frame()
            self._pin(key, [0, 0, self._top()], 0.3 * UP, ("key",))
        for g, (name, idx) in enumerate(self.groups):
            self._pin(_pinned_text(name, th.muted, 26), np.zeros(3), 0.3 * DOWN, ("group", g))
        for k, (src, dst, label) in enumerate(self.links):
            if label:
                mid = (min(xs[src], xs[dst[0]]) + max(xs[src], xs[dst[-1]])) / 2
                self._pin(_pinned_text(label, th.accent, 24), [mid, 0, self.rail_z(self.level[k])], 0.24 * UP, ("link", k))
        for j, name in enumerate(self.tok_names):
            self._pin(_pinned_text(name, th.ink, 22), [0, self.tok_y[j], self.col_top], 0.22 * UP, ("tok", j))

    def _pin(self, mob, at, nudge, kind):
        self.pins.append((mob, np.array(at, float), nudge))
        self.pin_kind.append(kind)

    # --- state ----------------------------------------------------------------
    def state(self, node, old):
        N = len(self.names)
        lit, dim, opened = np.zeros(N), np.zeros(N), np.zeros(N)
        lit[list(_refs(node, "highlight", self.names))] = 1
        dim[list(_refs(node, "dim", self.names))] = 1
        if node.attrs.get("open", "").strip():
            k = node.attrs["open"].strip()
            if not k.isdigit() or int(k) >= N:
                raise BeatError(f'<stack3d id={node.id}> open="{k}": one layer index, 0..{N - 1}')
            opened[int(k)] = 1
        here = {self._link(node, s) for s in _split_top(node.attrs.get("links", ""), ";")}
        groups = {g[0] for g in _named_ranges(node, "groups", N)}
        sheet = 1.0 if ("at" in node.attrs or "tokens" in node.attrs) else 0.0
        at1 = float(np.clip(_num(node, "at", old["at1"] if old else -1), -1, N))
        at0 = old["at1"] if old and old.get("sheet", 0) > 0 and sheet else at1
        flat = 1.0 if node.attrs.get("look", "glass") == "diagram" else 0.0
        return {"show": 1.0, "lit": lit, "dim": dim, "sheet": sheet, "at": at0, "at1": at1,
                "flat": flat, "open": opened,
                "links": np.array([1.0 if l in here else 0.0 for l in self.links]),
                "groups": np.array([1.0 if g[0] in groups else 0.0 for g in self.groups])}

    def sheet_x(self, at: float) -> float:
        return float(np.interp(at, *self.track))

    def _panel(self) -> tuple[np.ndarray, np.ndarray]:
        w, h = self.PANEL
        return np.array([0.0, -self.D / 2 - 2.6, self.H / 2 + 0.4]), np.array([w / 2, 0.03, h / 2])

    def _slab_box(self, k, f, o) -> tuple[np.ndarray, np.ndarray]:
        """Centre and half-size of layer k: in its diagram box (f = 0) or the glass stack (f = 1),
        on the way to the opened panel by o."""
        gc, gh = np.array([self.xs[k], 0, self.H / 2]), np.array([self.t / 2, self.D / 2, self.H / 2])
        dc, dh = self.slab_flat[k]
        e = smooth(f)
        c, h = (1 - e) * dc + e * gc, (1 - e) * dh + e * gh
        if o > 0:
            pc, ph = self._panel()
            e = smooth(o)
            c, h = (1 - e) * c + e * pc, (1 - e) * h + e * ph
        return c, h

    # --- per frame ------------------------------------------------------------
    def apply(self, st, fw):
        self.fw = fw
        th = current()
        show = st["show"] if st else 0.0
        if not st:
            self.mob.set_opacity(0)
            return
        f = 1 - float(st["flat"])
        glass_a = float(np.clip((f - 0.1) / 0.5, 0, 1))      # the layers come out of the boxes
        dia_a = 1 - float(np.clip(f / 0.55, 0, 1))
        at = float(st["at"])
        sheet = float(st["sheet"]) * show * glass_a
        opened = np.asarray(st["open"], float)
        any_open = float(opened.max()) if len(opened) else 0.0
        N = len(self.names)
        self._centres = []
        for k in range(N):
            o = float(opened[k])
            c, h = self._slab_box(k, f, o)
            self.placed[k].place(c, h)
            self._centres.append(c)
            glow = sheet * max(0.0, 1 - abs(at - k) / 0.7)
            lit, dim = float(st["lit"][k]), float(st["dim"][k])
            fade = show * glass_a * (1 - 0.72 * dim) * (1 - (any_open - o))
            body = (self.body + 0.3 * lit + 0.35 * glow) * fade
            col = interpolate_color(self.colors[k], th.ink, 0.35 * glow)
            # opened: a dark panel in the layer's colour, the backdrop for what is drawn on it
            col = interpolate_color(col, th.panel_fill, 0.96 * o)
            body = body * (1 - o) + o * show
            for face in self.slab_faces[k]:
                face.set_color(col, body)
            edge = interpolate_color(self.colors[k], th.lit, lit)
            self.slab_edges[k].set_stroke(edge, 1.6 + 1.6 * lit + 1.0 * glow + 0.8 * o,
                                          (0.85 + 0.15 * lit) * fade + o * show)
        for m in self.d_faces:      # (set_opacity would fill the outlines in)
            m.set_opacity(0.22 * dia_a * show)
        for m in self.d_lines:
            m.set_stroke(opacity=dia_a * show)
        for m in self.d_tips:
            m.set_fill(opacity=dia_a * show)
        for L, (edge, col) in enumerate(self.d_edges):    # a box is lit when its layers are
            lit = max(float(st["lit"][k]) for k in range(N) if self.slab_leaf[k] == L)
            dim = min(float(st["dim"][k]) for k in range(N) if self.slab_leaf[k] == L)
            edge.set_stroke(interpolate_color(col, th.lit, lit), 2.6 + 1.8 * lit, dia_a * show * (1 - 0.7 * dim))
            self.d_faces[L].set_opacity((0.22 + 0.2 * lit) * dia_a * show * (1 - 0.7 * dim))
        # the sheet: entries change as it passes each layer
        x = self.sheet_x(at)
        passed = float(np.clip(at + 0.5, 0, N))
        j = min(int(passed), N - 1)
        u = smooth(float(np.clip((passed - j - 0.3) / 0.4, 0, 1)))
        vals = (1 - u) * self.values[j] + u * self.values[j + 1]
        shift = np.array([x, 0, 0])
        for c, base, tan, v in zip(self.cells, self._cell_base, self._cell_tan, vals):
            c.data["point"][:] = base + shift
            for k2, d in tan.items():
                c.data[k2][:] = base + shift + d
            c.note_changed_data()
            c.set_color(interpolate_color(self.zero, self.pos if v > 0 else self.neg, min(1.0, abs(v) ** 0.7)),
                        0.95 * sheet * (1 - any_open))
        rail_a = show * glass_a * (1 - any_open)
        for k, g in enumerate(self.rails):
            o = float(st["links"][k]) * rail_a
            g[0].set_stroke(opacity=o)
            g[1].set_fill(opacity=o)
            g[2].set_opacity(o)
        self._brackets(st, f, show * (1 - any_open))
        self._pin_opacity(st, show, sheet, at, glass_a, dia_a, any_open)
        self.view()

    def _brackets(self, st, f, show):
        e = smooth(f)
        for g, ((_, idx), br) in enumerate(zip(self.groups, self.brackets)):
            leaves = sorted({self.slab_leaf[k] for k in idx})
            da, db = min(self.dbox[L][0] for L in leaves), max(self.dbox[L][1] for L in leaves)
            dz = min(self.dbox[L][2] for L in leaves)
            ga, gb = self.xs[min(idx)] - self.t / 2, self.xs[max(idx)] + self.t / 2
            a, b = (1 - e) * da + e * ga, (1 - e) * db + e * gb
            y = e * (-self.D / 2)
            z0 = (1 - e) * (dz - self.HD / 2 - 0.42) + e * self._bracket_z()
            br.set_points_as_corners([[a, y, z0 + 0.14], [a, y, z0], [b, y, z0], [b, y, z0 + 0.14]])
            br.set_stroke(opacity=float(st["groups"][g]) * show)
            self.pins[self._group_pin[g]][1][:] = [(a + b) / 2, y, z0]

    @property
    def _group_pin(self) -> dict[int, int]:
        return {kind[1]: j for j, kind in enumerate(self.pin_kind) if kind[0] == "group"}

    def _pin_opacity(self, st, show, sheet, at, glass_a, dia_a, any_open):
        for (mob, at3, _), kind in zip(self.pins, self.pin_kind):
            if kind[0] == "group":
                o = float(st["groups"][kind[1]]) * (1 - any_open)
            elif kind[0] == "link":
                o = float(st["links"][kind[1]]) * glass_a * (1 - any_open)
            elif kind[0] == "tok":
                o = sheet * float(np.clip((-0.35 - at) / 0.4, 0, 1)) * (1 - any_open)   # named only before it enters
            elif kind[0] == "dia":
                o = dia_a
            else:
                o = glass_a * (1 - any_open)
            mob.set_opacity(o * show)
        self._sheet_x = self.sheet_x(at)

    def view(self):
        fw = self.fw
        if fw is None or fw.frame is None or not hasattr(self, "_centres"):
            return
        keys, items = [], []
        for k in range(len(self.names)):
            for face in self.slab_faces[k]:
                items.append(face)
                keys.append(face.get_center())
            items.append(self.slab_edges[k])
            keys.append(self._centres[k])
        items.append(self.cells)
        keys.append(np.array([getattr(self, "_sheet_x", 0.0), 0, self.H / 2]))
        self._sort(self.glass, items, keys)
        eye = fw.frame.get_implied_camera_location()
        for g in self.rails:   # arrow heads turned to face the camera
            for tip, p in zip(g[1], g.tips_at):
                side = np.cross(OUT, eye - p)
                side = 0.065 * side / (np.linalg.norm(side) or 1)
                tip.set_points_as_corners([p, p + 0.17 * OUT + side, p + 0.17 * OUT - side, p])
        for (mob, at, nudge), kind in zip(self.pins, self.pin_kind):
            if kind[0] == "tok":
                at = at + np.array([getattr(self, "_sheet_x", 0.0), 0, 0])
            mob.move_to(project(fw.frame, at) + nudge)

    def extent(self, st):
        if not st:
            return []
        H, D = self.H, self.D
        if np.max(st["open"], initial=0) > 0.5:      # the camera pushes in on the opened layer
            c, h = self._panel()
            return [list(c + h * np.array([sx, sy, sz])) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
        if st["flat"] > 0.5:                          # the diagram: its boxes, frames and brackets
            x0, x1 = min(b[0] for b in self.dbox) - 0.6, max(b[1] for b in self.dbox) + 0.6
            zs = [b[2] for b in self.dbox]
            bot = min(zs) - self.HD / 2 - (0.9 if self.groups and st["groups"].any() else 0.3)
            return [[x, y, z] for x in (x0, x1) for y in (-0.05, 0.05) for z in (bot, max(zs) + self.HD / 2 + 0.75)]
        x0, x1 = self.xs[0] - self.t, self.xs[-1] + self.t
        if st.get("sheet", 0) > 0:
            x0, x1 = min(x0, self.sheet_x(min(st["at"], st["at1"]))), max(x1, self.sheet_x(max(st["at"], st["at1"])))
        shown = [self.level[k] + (0.5 if self.links[k][2] else 0) for k in range(len(self.links)) if st["links"][k] > 0]
        top = self.rail_z(max(shown)) + 0.3 if shown else H
        if self.mode == "key":
            top = self._top() + 0.3
        bot = self._bracket_z() - 0.3 if self.groups and st["groups"].any() else (-0.3 if self.mode == "runs" else 0)
        return [[x, y, z] for x in (x0, x1) for y in (-D / 2, D / 2) for z in (bot, top)]


# --- <grid3d> --------------------------------------------------------------------------------------
AXES = "xyz"


class Grid3D(_Painter):
    """A block of cells, drawn as opaque boxes (one per slice when ``slices`` cuts it, else one).
    Along each axis the state holds where every original slice starts and how long it is (in
    cells), so merging, pulling apart and their reverse all interpolate slice by slice.

    Drawn like the stack: no depth test, boxes painted far-to-near, only the faces turned to the
    camera, each with its cell lines on it. Lines that were depth-tested a hair above the faces
    broke into dashes at grazing angles, and glued slices each drew their own end (doubled)."""

    MAX = 64

    def __init__(self, i, nodes, world):
        th = current()
        self.id, self.fw = i, None
        shapes = {n.attrs["shape"].strip() for n in nodes if n.attrs.get("shape", "").strip()}
        if len(shapes) != 1:
            raise BeatError(f'<grid3d id={i}> needs shape="nx,ny,nz" (cells along x, y, z), the same in '
                            "every beat (a different block is a new id)")
        try:
            self.n = n = [int(v) for v in shapes.pop().split(",")]
            assert len(n) == 3 and all(1 <= v <= self.MAX for v in n)
        except (ValueError, AssertionError):
            raise BeatError(f'<grid3d id={i}> shape: three whole numbers 1..{self.MAX} like "8,16,4" '
                            "(scale a big tensor down: the picture shows its shape, not every cell)") from None
        axes = {n_.attrs["slices"].strip() for n_ in nodes if n_.attrs.get("slices", "").strip()}
        if len(axes) > 1 or (axes and next(iter(axes)) not in AXES):
            raise BeatError(f'<grid3d id={i}> slices: one axis, x, y or z, the same in every beat')
        self.sa = AXES.index(axes.pop()) if axes else None
        self.cell = _num(nodes[0], "cell", min(0.5, 6.5 / max(n)))
        self.base_color = th.color(nodes[0].attrs.get("color"), "c1") if nodes[0].attrs.get("color") else th.solid
        self.factors = [sorted({self._merge(nd)[a] for nd in nodes} | {1}) for a in range(3)]
        for a, fs in enumerate(self.factors):
            if any(f2 % f1 for f1, f2 in zip(fs, fs[1:])):
                raise BeatError(f'<grid3d id={i}> merge along {AXES[a]} uses {fs}: each must divide the next '
                                "(1, 2, 4), so merged cells merge again")
        nb = n[self.sa] if self.sa is not None else 1
        self.boxes = []    # per box: (faces, lines)
        for _ in range(nb):
            faces = [_flat(f.set_color(self.base_color).set_shading(*th.solid_shading))
                     for f in _box_faces(np.zeros(3), np.ones(3))]
            self.boxes.append((faces, _flat(VMobject().set_stroke(th.mesh, 1.6))))
        self._unit = [{k: f.data[k].copy() for k in ("point", "du_point", "dv_point")} for f in self.boxes[0][0]]
        self._normals = [np.round(f.get_center()).astype(int) for f in self.boxes[0][0]]   # unit cube: centre = normal
        self.body = Group(*(Group(*faces, lines) for faces, lines in self.boxes))
        self._box_groups = list(self.body.submobjects)
        self.labels = [[] for _ in range(3)]   # per axis: [(text, pinned mob)]
        for nd in nodes:
            for a, text in enumerate(self._labels(nd)):
                if text and text not in [t for t, _ in self.labels[a]]:
                    self.labels[a].append((text, _pinned_text(text, th.ink, 24)))
        self.pins = Group(*(m for a in range(3) for _, m in self.labels[a]))
        self.mob = Group(self.body, self.pins)
        self._st = None

    @staticmethod
    def _merge(node) -> list[int]:
        raw = node.attrs.get("merge", "1,1,1")
        try:
            m = [int(v) for v in raw.split(",")]
            assert len(m) == 3 and min(m) >= 1
        except (ValueError, AssertionError):
            raise BeatError(f'<grid3d id={node.id}> merge="{raw}": three whole numbers like "1,4,1"') from None
        return m

    def _labels(self, node) -> list[str]:
        raw = node.attrs.get("labels", "")
        parts = [p.strip() for p in raw.split(",")] if raw.strip() else []
        if parts and len(parts) != 3:
            raise BeatError(f'<grid3d id={node.id}> labels="{raw}": three names, x,y,z (an empty one is skipped)')
        return parts or ["", "", ""]

    def _slice_map(self, node, key: str) -> dict[int, str]:
        out = {}
        if not node.attrs.get(key, "").strip():
            return out
        if self.sa is None:
            raise BeatError(f'<grid3d id={node.id}> {key}= needs slices="x|y|z" (the axis it counts along)')
        for item in _split_top(node.attrs[key], ";"):
            rng, _, col = item.partition(":")
            for k in index_set(rng, self.n[self.sa], f"<grid3d id={node.id}> {key}"):
                out[k] = col.strip()
        return out

    def state(self, node, old):
        th = current()
        m = self._merge(node)
        gap = _num(node, "gap", 0.0)
        st = {"show": 1.0}
        for a in range(3):
            k = np.arange(self.n[a])
            g = gap if a == self.sa else 0.0
            st[f"off{a}"] = k / m[a] + g * (k // m[a])
            st[f"len{a}"] = np.full(self.n[a], 1.0 / m[a])
            b = np.arange(self.n[a] + 1)
            st[f"vis{a}"] = ((b % m[a]) == 0).astype(float)
        for key in ("paint", "highlight"):
            if node.attrs.get(key, "").strip() and self.sa is None:
                raise BeatError(f'<grid3d id={node.id}> {key}= needs slices="x|y|z" (the axis it counts along)')
        if self.sa is not None:
            rgb = np.tile(color_to_rgb(self.base_color), (self.n[self.sa], 1))
            for k, c in self._slice_map(node, "paint").items():
                rgb[k] = color_to_rgb(th.color(c or "accent"))
            lit = np.zeros(self.n[self.sa])
            lit[list(self._slice_map(node, "highlight"))] = 1
            st["rgb"], st["lit"] = rgb, lit
        names = self._labels(node)
        st["lab"] = np.array([1.0 if names[a] == t else 0.0 for a in range(3) for t, _ in self.labels[a]])
        return st

    def _span(self, st, a) -> float:
        return float(st[f"off{a}"][-1] + st[f"len{a}"][-1])

    def _boxes(self, st):
        """(lo, hi) corners of each drawn box, block centred on x, y and standing on z = 0."""
        c = self.cell
        ext = np.array([self._span(st, a) for a in range(3)]) * c
        origin = np.array([-ext[0] / 2, -ext[1] / 2, 0.0])
        if self.sa is None:
            return [(origin, origin + ext)], origin
        out = []
        for k in range(self.n[self.sa]):
            lo, hi = origin.copy(), origin + ext
            lo[self.sa] = origin[self.sa] + c * st[f"off{self.sa}"][k]
            hi[self.sa] = lo[self.sa] + c * st[f"len{self.sa}"][k]
            out.append((lo, hi))
        return out, origin

    def apply(self, st, fw):
        self.fw = fw
        self._st = st
        if not st:
            self.mob.set_opacity(0)
            return
        th = current()
        boxes, _ = self._boxes(st)
        show = st["show"]
        cols = []
        for j in range(len(boxes)):
            col = self.base_color
            if self.sa is not None:
                col = interpolate_color(rgb_to_hex(np.clip(st["rgb"][j], 0, 1)), th.lit, float(st["lit"][j]))
            cols.append(col)
        self._boxes_now, self._cols = boxes, cols
        self._lo = np.min([b[0] for b in boxes], axis=0)
        self._hi = np.max([b[1] for b in boxes], axis=0)
        j = 0
        for a in range(3):
            for _, mob in self.labels[a]:
                mob.set_opacity(show * float(st["lab"][j]))
                j += 1
        self.view()

    def _units(self) -> list[tuple[list[int], np.ndarray, np.ndarray]]:
        """Boxes drawn as one: slices that touch and share a colour (one box per slice would leave
        an anti-aliased seam between every two)."""
        units = []
        for j, (lo, hi) in enumerate(self._boxes_now):
            u = units[-1] if units else None
            if (u and self.sa is not None and lo[self.sa] - u[2][self.sa] < 1e-3
                    and self._cols[j] == self._cols[u[0][0]]):
                u[0].append(j)
                u[2] = hi.copy()
            else:
                units.append([[j], lo.copy(), hi.copy()])
        return units

    def _marks(self, a, js, lo, hi, st) -> list[tuple[float, float]]:
        """Where a unit of boxes has a cell line across axis a, and how strongly (merged lines fade)."""
        if a == self.sa:
            v = st[f"vis{a}"]
            return [(self._boxes_now[j][0][a], float(v[j])) for j in js] + [(hi[a], float(v[js[-1] + 1]))]
        n, c = self.n[a], self.cell
        off, vis = st[f"off{a}"], st[f"vis{a}"]
        out = [(lo[a] + c * off[k], float(vis[k]) if k else 1.0) for k in range(n)]
        return out + [(hi[a], 1.0)]

    def _draw(self):
        st, fw = self._st, self.fw
        if not st or fw is None or fw.frame is None:
            return
        eye = fw.frame.get_implied_camera_location()
        show = st["show"]
        centres = [np.zeros(3)] * len(self.boxes)
        drawn = set()
        for js, lo, hi in self._units():
            j0 = js[0]
            drawn.add(j0)
            faces, lines = self.boxes[j0]
            mid, half = (lo + hi) / 2, np.maximum((hi - lo) / 2, 1e-4)
            centres[j0] = mid
            segs, ops = [], []
            for f, base, nrm in zip(faces, self._unit, self._normals):
                for k, pts in base.items():
                    f.data[k][:] = pts * half + mid
                f.note_changed_data()
                f.set_color(self._cols[j0])
                fa = int(np.flatnonzero(nrm)[0])
                centre = mid + nrm * half
                seen = float(np.dot(eye - centre, nrm)) > 0
                f.set_opacity(show if seen else 0.0)
                if not seen:
                    continue
                for a in (x for x in range(3) if x != fa):
                    b_ = 3 - fa - a
                    for pos, op in self._marks(a, js, lo, hi, st):
                        if op * show < 0.01:
                            continue
                        p0 = centre.copy()
                        p0[a], p0[b_] = pos, lo[b_]
                        p1 = p0.copy()
                        p1[b_] = hi[b_]
                        segs.append((p0, p1))
                        ops.append(op * show)
            _set_segments(lines, segs, ops)
        for j, (faces, lines) in enumerate(self.boxes):
            if j not in drawn:   # part of a unit drawn by its first box
                for f in faces:
                    f.set_opacity(0)
                _set_segments(lines, [], [])
                centres[j] = self._boxes_now[j][0]
        self._sort(self.body, self._box_groups, centres)

    def view(self):
        """Faces turned to the camera, painted far-to-near; each axis named beside the one of its
        four edges that is farthest out on screen (on the outline, never on a face)."""
        self._draw()
        if self.fw is None or self.fw.frame is None or not hasattr(self, "_lo"):
            return
        frame, lo, hi = self.fw.frame, self._lo, self._hi
        corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        centre = np.mean([project(frame, q) for q in corners], axis=0)
        used = []
        for a in range(3):
            b_, c_ = [x for x in range(3) if x != a]
            best = None
            for u in (lo[b_], hi[b_]):
                for v in (lo[c_], hi[c_]):
                    m = (lo + hi) / 2
                    m[b_], m[c_] = u, v
                    p = project(frame, m)
                    d = p - centre
                    # outward, and below or left rather than above: names sit under a picture
                    score = np.linalg.norm(d) - 0.6 * d[1] - (0.6 if any(np.allclose(p, q) for q in used) else 0)
                    if best is None or score > best[0]:
                        best = (score, p, d)
            _, p, d = best
            used.append(p)
            out = d / (np.linalg.norm(d) or 1)
            for _, mob in self.labels[a]:
                mob.move_to(p + out * (0.3 + abs(out[0]) * mob.get_width() / 2 + abs(out[1]) * mob.get_height() / 2))

    def extent(self, st):
        if not st:
            return []
        boxes, _ = self._boxes(st)
        lo = np.min([b[0] for b in boxes], axis=0)
        hi = np.max([b[1] for b in boxes], axis=0)
        return [[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


CLASSES = {"stack3d": Stack3D, "grid3d": Grid3D}
