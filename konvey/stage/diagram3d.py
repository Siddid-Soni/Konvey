"""Block diagrams for ``<world>`` (manimgl): boxes, panels, repeat frames and arrows, laid out by
the renderer from a tree; flat like a figure in a paper, or extruded into 3D with every repeated
block fanned out into its copies.

``<diagram id>`` holds the tree (written in full once; a later beat may write it again, the same,
or leave it out and keep it):

- ``<col dir="up|down" gap align>`` / ``<row gap align>``: children stacked (``dir="up"``: the first at
  the bottom, as data flows up a network figure); ``align`` = ``center`` (default), ``start``, ``end``.
- ``<grid cols="5" gap>``: children in reading order into rows of that many columns (a ``ghost`` box
  for an empty cell); each column as wide and each row as tall as its largest child.
- ``<panel id title dir h w>``: a titled backdrop around its children (a column).
- ``<repeat id n dir>``: a dotted frame with ``×n`` beside it; with ``unfold`` its contents fan out
  into the n copies, one behind the other.
- ``<box id text="Main|Q" color shape="rect|op|stack" italic w h ghost>``: ``|`` breaks lines;
  ``op`` a box with a cut corner (an operation), ``stack`` a box with copies behind it (many of a
  thing); ``ghost`` takes room and draws nothing; ``plain`` draws only the words.
- ``<cells id rows cols lit="0,1; 3,4" rows-lit="0,1" text more>``: a box holding a grid of cells
  (positions, scores), some lit, some rows framed.
- ``<edge from to label out="top|bottom|left|right" in="…" label-at="mid|start|end"
  around="below|above">``: an arrow, routed at right angles (``around``: under or over the whole
  figure, to reach something far along the same row).

Per beat on ``<diagram>``: ``depth="1"`` (0 flat, 1 solid blocks), ``unfold="1"`` (repeats fanned
out), ``highlight`` / ``dim`` (ids), ``focus="id"`` (the camera frames that part),
``flow="a>b>c; d>e | e>f"`` (while the line is spoken a lit trail is traced along those arrows, a
glow at its head: routes split by ``;`` run together at one speed, stages split by ``|`` one after
another; the trail stays lit to the end of the beat), ``at="x,y,z"`` and
``scale`` (where it stands: a detail diagram can sit inside a box of another).
"""

from __future__ import annotations

import re

import numpy as np

from manimlib import *  # noqa: F401,F403

from .solids import _face_surface
from .theme import current
from .tree import BeatError

TAGS = {"diagram"}
ATTRS = {"diagram": {"id", "depth", "unfold", "highlight", "dim", "focus", "flow", "at", "scale"}}
ORDER = {"diagram": 0}

LINE = 0.34          # text line height (world units)
CAP = 0.2            # glyph height of a capital
PADX, PADY = 0.32, 0.16
GAP = 0.3
DEPTH = 0.34         # thickness of a solid block
COPY_GAP = 0.36      # copies of an innermost repeat, one behind the other


def _num(node, key, default):
    try:
        return float(node.attrs.get(key, default))
    except ValueError:
        raise BeatError(f'<{node.tag} id={node.id}> {key}="{node.attrs[key]}": a number') from None


def _flag(node, key):
    return node.attrs.get(key, "false").strip().lower() in ("true", "1", "yes", "")


def _ids(spec: str) -> list[str]:
    return [p.strip() for p in re.split(r"[;,]", spec or "") if p.strip()]


class _Item:
    """A laid-out tree node: its kind, rect (x0, z0, x1, z1) and the repeats around it."""

    def __init__(self, node, parent=None):
        self.node, self.parent = node, parent
        self.tag = node.tag
        self.id = node.id
        self.kids = [_Item(c, self) for c in node.children if c.tag != "edge"]
        self.rect = (0.0, 0.0, 0.0, 0.0)
        self.texts: list[Text] = []

    def reps(self) -> list["_Item"]:
        out, p = [], self.parent
        while p is not None:
            if p.tag == "repeat":
                out.append(p)
            p = p.parent
        return out


class Diagram:
    LIVE = ("ft", "ft1")

    def __init__(self, i, nodes, world):
        th = current()
        self.id, self.fw = i, None
        trees = [n for n in nodes if n.children]
        if not trees:
            raise BeatError(f'<diagram id={i}> is empty: write its boxes, panels and edges inside it')
        sig = {self._sig(n) for n in trees}
        if len(sig) > 1:
            raise BeatError(f'<diagram id={i}>: its boxes and edges must be the same in every beat that writes '
                            "them (change highlight, dim, depth, unfold, focus or flow instead; a new picture "
                            "is a new id)")
        root = trees[0]
        self.th = th
        self.root = _Item(root)
        self.items: dict[str, _Item] = {}
        for it in self._walk(self.root):
            if it.id:
                if it.id in self.items:
                    raise BeatError(f'<diagram id={i}>: id="{it.id}" is used twice')
                self.items[it.id] = it
        ref = Text("Hg", font_size=48)
        self.tscale = (LINE * 0.78) / ref.get_height()
        self._measure(self.root)
        w, h = self.root.size
        self._place(self.root, -w / 2, -h / 2)
        self.edges = [self._edge(e) for e in root.children if e.tag == "edge"]
        self.flows: list[str] = []
        for n in nodes:
            f = n.attrs.get("flow", "").strip()
            if f and f not in self.flows:
                self._flow_path(f, n)          # check it now
                self.flows.append(f)
        # a trail and a glow per route of every flow (two flows show at once while one fades out)
        self.routes = sum(len(st) for f in self.flows for st in self._flow_path(f, None))
        self.starts: dict[int, int] = {}       # flow clock at a beat's start -> the flow it runs
        self._build(th)

    @staticmethod
    def _sig(node) -> str:
        def s(n):
            return n.tag + repr(sorted(n.attrs.items())) + "[" + ",".join(s(c) for c in n.children) + "]"
        return ",".join(s(c) for c in node.children)    # the tree, not the beat's own attributes

    def _walk(self, it):
        yield it
        for k in it.kids:
            yield from self._walk(k)

    # --- layout ---------------------------------------------------------------------------------
    def _text(self, it, text, italic=False, bold=False, color=None, size=1.0) -> Text:
        th = self.th
        t = Text(text, font=th.body_font, font_size=48, fill_color=color or th.ink,
                 slant=ITALIC if italic else NORMAL, weight=BOLD if bold else NORMAL)
        t.scale(self.tscale * size)
        it.texts.append(t)
        return t

    def _measure(self, it):
        n = it.node
        if it.tag == "box":
            lines = [l.strip() for l in n.attrs.get("text", "").split("|")] if n.attrs.get("text") else []
            it.lines = [self._text(it, l, italic=_flag(n, "italic")) for l in lines]
            tw = max((t.get_width() for t in it.lines), default=0)
            w = max(_num(n, "w", 0), tw + 2 * PADX + (0.25 if n.attrs.get("shape") == "op" else 0), 0.6)
            h = max(_num(n, "h", 0), len(lines) * LINE + 2 * PADY)
            it.size = (w, h)
        elif it.tag == "cells":
            R, C = int(_num(n, "rows", 4)), int(_num(n, "cols", 8))
            if not (1 <= R <= 16 and 1 <= C <= 16):
                raise BeatError(f'<cells id={it.id}>: rows and cols 1..16')
            it.grid = (R, C)
            it.title = self._text(it, n.attrs["text"]) if n.attrs.get("text") else None
            gw, gh = C * 0.26 + 0.12, R * 0.3
            tw = it.title.get_width() if it.title else 0
            it.size = (max(gw, tw) + 2 * PADX, gh + 2 * PADY + (LINE + 0.08 if it.title else 0)
                       + (0.26 if _flag(n, "more") else 0))
        else:
            for k in it.kids:
                self._measure(k)
            gap = _num(n, "gap", GAP if it.tag != "row" else 0.6)
            sizes = [k.size for k in it.kids]
            if it.tag == "grid":
                C = int(_num(n, "cols", 2))
                rows = [sizes[r:r + C] for r in range(0, len(sizes), C)]
                it.colw = [max((r[c][0] for r in rows if c < len(r)), default=0) for c in range(C)]
                it.rowh = [max(s[1] for s in r) for r in rows]
                gx = _num(n, "gap-x", 0.5)
                w = sum(it.colw) + gx * (C - 1)
                h = sum(it.rowh) + gap * (len(rows) - 1)
            elif it.tag == "row":
                w = sum(s[0] for s in sizes) + gap * max(0, len(sizes) - 1)
                h = max((s[1] for s in sizes), default=0)
            else:
                w = max((s[0] for s in sizes), default=0)
                h = sum(s[1] for s in sizes) + gap * max(0, len(sizes) - 1)
            it.inner = (w, h)
            it.pad = (0, 0, 0, 0)          # left, bottom, right, top
            if it.tag == "panel":
                it.title = self._text(it, n.attrs["title"], bold=True) if n.attrs.get("title") else None
                it.pad = (0.38, 0.38, 0.38, 0.38 + (LINE + 0.12 if it.title else 0))
            elif it.tag == "repeat":
                it.mark = self._text(it, f"×{int(_num(n, 'n', 2))}")
                it.pad = (0.22, 0.22, 0.22 + it.mark.get_width() + 0.3, 0.22)
            l, b, r, t = it.pad
            it.size = (max(w + l + r, _num(n, "w", 0)), max(h + b + t, _num(n, "h", 0)))

    def _place(self, it, x0, z0):
        w, h = it.size
        it.rect = (x0, z0, x0 + w, z0 + h)
        if not it.kids:
            return
        n = it.node
        l, b, r, t = it.pad
        ix0, iz0, ix1, iz1 = x0 + l, z0 + b, x0 + w - r, z0 + h - t
        gap = _num(n, "gap", GAP if it.tag != "row" else 0.6)
        align = n.attrs.get("align", "center")
        if it.tag == "grid":
            C = len(it.colw)
            gx = _num(n, "gap-x", 0.5)
            xs = [ix0 + ((ix1 - ix0) - it.inner[0]) / 2 + sum(it.colw[:c]) + gx * c for c in range(C)]
            z = (iz0 + iz1 + it.inner[1]) / 2
            for j, k in enumerate(it.kids):
                r, c = divmod(j, C)
                if c == 0 and r:
                    z -= it.rowh[r - 1] + gap
                kw, kh = k.size
                self._place(k, xs[c] + (it.colw[c] - kw) / 2, z - it.rowh[r] / 2 - kh / 2)
            return
        if it.tag == "row":
            x = ix0 + ((ix1 - ix0) - it.inner[0]) / 2
            for k in it.kids:
                kw, kh = k.size
                z = {"start": iz0, "end": iz1 - kh}.get(align, (iz0 + iz1 - kh) / 2)
                if align == "top":
                    z = iz1 - kh
                elif align == "bottom":
                    z = iz0
                self._place(k, x, z)
                x += kw + gap
        else:
            up = n.attrs.get("dir", "down") == "up"
            total = it.inner[1]
            z = (iz0 + iz1 - total) / 2 if up else (iz0 + iz1 + total) / 2
            for k in it.kids:
                kw, kh = k.size
                x = {"start": ix0, "end": ix1 - kw}.get(align, (ix0 + ix1 - kw) / 2)
                if align == "left":
                    x = ix0
                elif align == "right":
                    x = ix1 - kw
                if up:
                    self._place(k, x, z)
                    z += kh + gap
                else:
                    self._place(k, x, z - kh)
                    z -= kh + gap

    # --- edges ----------------------------------------------------------------------------------
    def _edge(self, e) -> dict:
        a, b = e.attrs.get("from", "").strip(), e.attrs.get("to", "").strip()
        for ref in (a, b):
            if ref not in self.items:
                raise BeatError(f'<diagram id={self.id}> <edge from="{a}" to="{b}">: no box, cells, panel or '
                                f'repeat with id="{ref}"')
        ra, rb = self.items[a].rect, self.items[b].rect
        around = e.attrs.get("around", "").strip()
        if around:
            if around not in ("below", "above"):
                raise BeatError(f'<edge from="{a}" to="{b}"> around="{around}": below or above')
            pts = self._around(ra, rb, around, e.attrs.get("in", "left"))
        else:
            pts = self._route(ra, rb, e.attrs.get("out"), e.attrs.get("in"))
        label = None
        if e.attrs.get("label"):
            label = Text(e.attrs["label"], font=self.th.body_font, font_size=48, slant=ITALIC,
                         fill_color=interpolate_color(self.th.muted, self.th.ink, 0.45))
            label.scale(self.tscale * 0.92)
        return {"from": a, "to": b, "pts": pts, "label": label, "at": e.attrs.get("label-at", "mid")}

    def _around(self, ra, rb, way, inn) -> np.ndarray:
        """Out of a's bottom (top), under (over) the whole figure, up (down) into b's side."""
        x0, z0, x1, z1 = self.root.rect
        vz = z0 - 0.35 if way == "below" else z1 + 0.35
        p0 = np.array([(ra[0] + ra[2]) / 2, ra[1] if way == "below" else ra[3]])
        if inn in ("left", "right"):
            px = rb[0] if inn == "left" else rb[2]
            ax = px - 0.35 if inn == "left" else px + 0.35
            p1 = np.array([px, (rb[1] + rb[3]) / 2])
            return np.array([p0, [p0[0], vz], [ax, vz], [ax, p1[1]], p1])
        p1 = np.array([(rb[0] + rb[2]) / 2, rb[1] if way == "below" else rb[3]])
        return np.array([p0, [p0[0], vz], [p1[0], vz], p1])

    @staticmethod
    def _route(ra, rb, out=None, inn=None) -> np.ndarray:
        """Right-angled path (x, z) from rect a to rect b: straight when they face each other, an
        L from a side to a top or bottom, a Z between two parallel sides."""
        ax0, az0, ax1, az1 = ra
        bx0, bz0, bx1, bz1 = rb
        acx, acz, bcx, bcz = (ax0 + ax1) / 2, (az0 + az1) / 2, (bx0 + bx1) / 2, (bz0 + bz1) / 2
        ox = min(ax1, bx1) - max(ax0, bx0)
        oz = min(az1, bz1) - max(az0, bz0)
        if not out or not inn:
            if ox > 0.2:
                out, inn = ("top", "bottom") if bcz > acz else ("bottom", "top")
            elif oz > 0.15:
                out, inn = ("right", "left") if bcx > acx else ("left", "right")
            else:
                out = out or ("top" if bcz > acz else "bottom")
                inn = inn or ("left" if acx < bcx else "right")
        vertical = lambda s: s in ("top", "bottom")  # noqa: E731

        def port(r, side, other_mid, overlap_mid):
            x0, z0, x1, z1 = r
            if side in ("top", "bottom"):
                x = overlap_mid if overlap_mid is not None else (x0 + x1) / 2
                return np.array([x, z1 if side == "top" else z0])
            z = overlap_mid if overlap_mid is not None else (z0 + z1) / 2
            return np.array([x1 if side == "right" else x0, z])

        mx = (max(ax0, bx0) + min(ax1, bx1)) / 2 if ox > 0.2 and vertical(out) and vertical(inn) else None
        mz = (max(az0, bz0) + min(az1, bz1)) / 2 if oz > 0.15 and not vertical(out) and not vertical(inn) else None
        p0 = port(ra, out, None, mx if vertical(out) else mz)
        p1 = port(rb, inn, None, mx if vertical(inn) else mz)
        pts = [p0]
        if vertical(out) and vertical(inn):
            if out == inn:      # around: out of the bottom of both, say
                far = (min(az0, bz0) - 0.4) if out == "bottom" else (max(az1, bz1) + 0.4)
                pts += [np.array([p0[0], far]), np.array([p1[0], far])]
            elif abs(p0[0] - p1[0]) > 1e-6:
                zm = (p0[1] + p1[1]) / 2
                pts += [np.array([p0[0], zm]), np.array([p1[0], zm])]
        elif not vertical(out) and not vertical(inn):
            if out == inn:
                far = (max(ax1, bx1) + 0.4) if out == "right" else (min(ax0, bx0) - 0.4)
                pts += [np.array([far, p0[1]]), np.array([far, p1[1]])]
            elif abs(p0[1] - p1[1]) > 1e-6:
                xm = (p0[0] + p1[0]) / 2
                pts += [np.array([xm, p0[1]]), np.array([xm, p1[1]])]
        elif vertical(out):
            pts.append(np.array([p0[0], p1[1]]))
        else:
            pts.append(np.array([p1[0], p0[1]]))
        pts.append(p1)
        clean = [pts[0]]
        for p in pts[1:]:
            if np.linalg.norm(p - clean[-1]) > 1e-6:
                clean.append(p)
        return np.array(clean)

    def _flow_path(self, spec: str, node) -> list[list[list[np.ndarray]]]:
        """The stages ("|") of a flow, each a list of routes (";"); a route "a>b>c" as the list of
        its edges' polylines (a>b, then b>c): one box's way in and way out are different sides,
        so the trail runs edge by edge and jumps across the box between them."""
        stages = []
        for stage in spec.split("|"):
            paths = []
            for route in stage.split(";"):
                ids = [s.strip() for s in route.split(">") if s.strip()]
                if len(ids) < 2:
                    raise BeatError(f'<diagram id={self.id}> flow="{spec}": a route is "a>b>c", two ids or more')
                legs = []
                for a, b in zip(ids, ids[1:]):
                    e = next((e for e in self.edges if e["from"] == a and e["to"] == b), None)
                    if e is None:
                        raise BeatError(f'<diagram id={self.id}> flow="{route.strip()}": no edge from {a} to {b}')
                    legs.append(np.array(e["pts"]))
                paths.append(legs)
            stages.append(paths)
        return stages

    # --- build ----------------------------------------------------------------------------------
    def _fill(self, it) -> tuple[str, str]:
        th = self.th
        c = it.node.attrs.get("color")
        if c:
            col = th.color(c)
            return interpolate_color(th.bg, col, 0.42), col
        return interpolate_color(th.panel_fill, th.ink, 0.07), interpolate_color(th.panel_stroke, th.ink, 0.25)

    def _poly(self, it) -> np.ndarray:
        x0, z0, x1, z1 = it.rect
        if it.node.attrs.get("shape") == "op":   # the paper's operation box: a corner cut away
            c = min(0.22, (z1 - z0) * 0.45)
            return np.array([[x0, z0], [x1 - c, z0], [x1, z0 + c], [x1, z1], [x0, z1]])
        return np.array([[x0, z0], [x1, z0], [x1, z1], [x0, z1]])

    def _prism(self, poly, fill) -> tuple[list, list, list]:
        """Faces of the polygon extruded from y = -1 (front) to y = 0 (back); scaled in y every
        frame by the depth. Returns (faces, their outward normals, edge segments as vertex pairs)."""
        th = self.th
        front = np.c_[poly[:, 0], -np.ones(len(poly)), poly[:, 1]]
        back = np.c_[poly[:, 0], np.zeros(len(poly)), poly[:, 1]]
        faces, normals = [], []
        f = _face_surface(front[::-1].copy())
        faces.append(f)
        normals.append(np.array([0, -1.0, 0]))
        f = _face_surface(back.copy())
        faces.append(f)
        normals.append(np.array([0, 1.0, 0]))
        k = len(poly)
        for j in range(k):
            a, b = poly[j], poly[(j + 1) % k]
            d = b - a
            nrm = np.array([d[1], 0, -d[0]])
            nrm /= np.linalg.norm(nrm) or 1
            quad = np.array([front[j], front[(j + 1) % k], back[(j + 1) % k], back[j]])
            faces.append(_face_surface(quad))
            normals.append(nrm)
        for face in faces:
            face.set_color(fill).set_shading(0.25, 0.2, 0.0)
            face.deactivate_depth_test()
        return faces, normals, (front, back)

    def _build(self, th):
        self.blocks = []     # one per drawn box copy: dict
        self._static_at: dict[int, tuple] = {}
        self.plates, self.frames = [], []
        for it in self._walk(self.root):
            if it.tag in ("box", "cells") and not _flag(it.node, "ghost"):
                for off in self._offsets(it):
                    if it.node.attrs.get("shape") == "stack":   # copies behind it, up and to the right
                        for k in (2, 1):
                            self.blocks.append(self._block(it, off, th, nudge=np.array([0.09 * k, 0.05 * k, 0.09 * k])))
                    self.blocks.append(self._block(it, off, th))
            elif it.tag == "panel":
                x0, z0, x1, z1 = it.rect
                plate = _face_surface(np.array([[x0, 0.04, z0], [x1, 0.04, z0], [x1, 0.04, z1], [x0, 0.04, z1]]))
                plate.set_color(th.panel_fill).set_shading(0, 0, 0).deactivate_depth_test()
                rim = VMobject().set_points_as_corners([[x0, 0.03, z0], [x1, 0.03, z0], [x1, 0.03, z1],
                                                        [x0, 0.03, z1], [x0, 0.03, z0]])
                rim.set_stroke(th.panel_stroke, 1.6).deactivate_depth_test()
                ttl = None
                if it.title is not None:
                    ttl = it.title.copy().rotate(PI / 2, RIGHT)
                    ttl.move_to([x1 - 0.3 - ttl.get_width() / 2, 0.02, z1 - 0.3 - LINE / 2 + 0.06])
                    ttl.deactivate_depth_test()
                self.plates.append((it, plate, rim, ttl))
            elif it.tag == "repeat":
                x0, z0, x1, z1 = it.rect
                xr = x1 - (it.pad[2] - 0.22)
                frame = DashedVMobject(VMobject().set_points_as_corners(
                    [[x0, 0, z0], [xr, 0, z0], [xr, 0, z1], [x0, 0, z1], [x0, 0, z0]]), num_dashes=int((xr - x0 + z1 - z0) * 9))
                frame.set_stroke(interpolate_color(th.muted, th.ink, 0.2), 1.6).deactivate_depth_test()
                mark = it.mark.copy().rotate(PI / 2, RIGHT)
                mark.move_to([xr + 0.18 + mark.get_width() / 2, 0, (z0 + z1) / 2]).deactivate_depth_test()
                self.frames.append((it, frame, mark))
        self.edge_mobs = []
        for e in self.edges:
            line = VMobject().deactivate_depth_test()
            tip = VMobject().set_stroke(width=0).deactivate_depth_test()
            lab = e["label"].copy().rotate(PI / 2, RIGHT).deactivate_depth_test() if e["label"] is not None else None
            self.edge_mobs.append((e, line, tip, lab))
        self.trails = VGroup(*(VMobject().set_stroke(th.accent, 4.5).deactivate_depth_test()
                               for _ in range(self.routes)))
        self.glows = Group(*(GlowDot(ORIGIN, radius=0.3, color=th.accent).deactivate_depth_test()
                             for _ in range(self.routes)))
        self.body = Group(*(b["group"] for b in self.blocks))
        self.mob = Group(Group(*(m for p in self.plates for m in p[1:] if m is not None)),
                         Group(*(m for f in self.frames for m in f[1:])),
                         self.body,
                         Group(*(m for em in self.edge_mobs for m in em[1:] if m is not None)),
                         self.trails, self.glows)

    def _offsets(self, it) -> list[np.ndarray]:
        """Where each copy of a box stands relative to the first (all at 0 until unfolded): the
        product of the repeats around it, an inner repeat's copies closer together."""
        offs = [np.zeros(3)]
        step = COPY_GAP
        for rep in it.reps():            # innermost first
            n = int(_num(rep.node, "n", 2))
            offs = [o + np.array([0, c * step, 0]) for c in range(n) for o in offs]
            step = step * n + 0.25
        return offs

    def _block(self, it, off, th, nudge=None) -> dict:
        fill, stroke = self._fill(it)
        poly = self._poly(it)
        faces, normals, (front, back) = self._prism(poly, fill)
        if _flag(it.node, "plain"):
            for f in faces:
                f.set_opacity(0)
        outline = VMobject().deactivate_depth_test()
        deco = VGroup()
        if it.tag == "box":
            texts = [t.copy() for t in it.lines]
            x0, z0, x1, z1 = it.rect
            cx = (x0 + x1) / 2 - (0.1 if it.node.attrs.get("shape") == "op" else 0)
            top = (z0 + z1) / 2 + (len(texts) - 1) * LINE / 2
            for j, t in enumerate(texts):
                t.rotate(PI / 2, RIGHT)
                t.move_to([cx, 0, top - j * LINE])
            deco.add(*texts)
        else:
            deco.add(*self._cells(it, th))
        deco.deactivate_depth_test()
        base = {id(f): {k: f.data[k].copy() for k in ("point", "du_point", "dv_point")} for f in faces}
        group = Group(*faces, outline, deco)
        return {"item": it, "off": off, "faces": faces, "normals": normals, "front": front, "back": back,
                "outline": outline, "deco": deco, "group": group, "base": base, "fill": fill, "stroke": stroke,
                "nudge": nudge, "placed": (1.0, np.zeros(3))}

    def _cells(self, it, th) -> list:
        n = it.node
        R, C = it.grid
        x0, z0, x1, z1 = it.rect
        out = []
        top = z1 - PADY
        if it.title is not None:
            t = it.title.copy().rotate(PI / 2, RIGHT)
            t.move_to([(x0 + x1) / 2, 0, top - LINE / 2])
            out.append(t)
            top -= LINE + 0.08
        lit = set()
        for p in (n.attrs.get("lit") or "").split(";"):
            if p.strip():
                r, c = (int(v) for v in p.split(","))
                lit.add((r, c))
        rows_lit = {int(v) for v in _ids(n.attrs.get("rows-lit", ""))}
        gx0 = (x0 + x1) / 2 - (C * 0.26) / 2
        for r in range(R):
            zc = top - 0.15 - r * 0.3
            if r in rows_lit:
                fr = RoundedRectangle(width=C * 0.26 + 0.1, height=0.27, corner_radius=0.06)
                fr.rotate(PI / 2, RIGHT).move_to([(x0 + x1) / 2, 0, zc])
                fr.set_fill(th.palette[0], 0.25).set_stroke(th.palette[0], 2)
                out.append(fr)
            for c in range(C):
                sq = Square(0.2).rotate(PI / 2, RIGHT).move_to([gx0 + 0.13 + c * 0.26, 0, zc])
                on = (r, c) in lit
                sq.set_fill(th.palette[1] if on else th.panel_fill, 0.95 if on else 1)
                sq.set_stroke(interpolate_color(th.panel_stroke, th.ink, 0.3), 1)
                out.append(sq)
        if _flag(n, "more"):
            dots = Text("···", font=th.body_font, font_size=48, fill_color=th.muted).scale(self.tscale)
            dots.rotate(PI / 2, RIGHT).move_to([(x0 + x1) / 2, 0, top - R * 0.3 - 0.1])
            out.append(dots)
        return out

    # --- state ----------------------------------------------------------------------------------
    def state(self, node, old):
        def mask(key):
            ids = _ids(node.attrs.get(key, ""))
            for i in ids:
                if i not in self.items:
                    raise BeatError(f'<diagram id={node.id}> {key}="{i}": no part with that id '
                                    f'(ids: {", ".join(list(self.items)[:12])}…)')
            return np.array([1.0 if b["item"].id in ids or self._inside(b["item"], ids) else 0.0
                             for b in self.blocks])
        focus = node.attrs.get("focus", "").strip()
        if focus and focus not in self.items:
            raise BeatError(f'<diagram id={node.id}> focus="{focus}": no part with that id')
        flow = node.attrs.get("flow", "").strip()
        fl = np.array([1.0 if f == flow else 0.0 for f in self.flows])
        same = old is not None and np.array_equal(old.get("fl"), fl)
        # a flow clock that only goes forward: a beat that starts a flow runs it from k to k + 1
        # (k a whole number, recorded with the flow it runs), so the move from the last beat is
        # forward too, and progress is the clock's fraction
        k = float(round(old["ft1"])) if old is not None and "ft1" in old else 0.0
        run = bool(flow) and not same
        if run:
            self.starts[int(k)] = self.flows.index(flow)
        at = np.array([float(v) for v in node.attrs.get("at", "0,0,0").split(",")])
        return {"show": 1.0, "depth": float(np.clip(_num(node, "depth", 0), 0, 1)),
                "unfold": float(np.clip(_num(node, "unfold", 0), 0, 1)),
                "lit": mask("highlight"), "dim": mask("dim"), "fl": fl,
                "ft": k, "ft1": k + 1.0 if run else k,
                "focus": np.array([1.0 if k == focus else 0.0 for k in self.items]),
                "at": at, "scale": _num(node, "scale", 1.0)}

    @staticmethod
    def _inside(it, ids) -> bool:
        p = it.parent
        while p is not None:
            if p.id in ids:
                return True
            p = p.parent
        return False

    # --- per frame ------------------------------------------------------------------------------
    def _xf(self, st):
        s, at = float(st["scale"]), np.asarray(st["at"], float)
        return lambda p: np.asarray(p) * s + at

    @staticmethod
    def _retarget(mob, rec, scale, shift):
        """Move a mobject built at layout coordinates (rec: the scale and shift it has now) to
        p -> scale * p + shift."""
        s0, t0 = rec
        if abs(s0 - scale) < 1e-9 and np.allclose(t0, shift):
            return rec
        mob.shift(-t0)
        if abs(s0 - scale) > 1e-9:
            mob.scale(scale / s0, about_point=ORIGIN)
        mob.shift(shift)
        return (scale, np.array(shift, float))

    def apply(self, st, fw):
        self.fw = fw
        self._st = st
        if not st:
            self.mob.set_opacity(0)
            return
        th = self.th
        show, d, u = st["show"], DEPTH * smooth(st["depth"]), smooth(st["unfold"])
        s, at = float(st["scale"]), np.asarray(st["at"], float)
        xf = self._xf(st)
        # a hold changes only the flow clock: the blocks, edges and outlines stay as they are
        key = tuple((k, tuple(np.ravel(v)) if isinstance(v, np.ndarray) else v)
                    for k, v in sorted(st.items()) if k not in self.LIVE)
        if key == getattr(self, "_key", None):
            self._flows(st, show, d, xf)
            return
        self._key, self._view_key = key, None
        for b, lit, dim in zip(self.blocks, st["lit"], st["dim"]):
            off = b["off"] * u
            a = show * (1 - 0.75 * dim)
            if np.linalg.norm(b["off"]) > 1e-9:   # a copy fades in as its repeat unfolds, far ones fainter
                a *= u * max(0.25, 1 - 0.1 * b["off"][1] / COPY_GAP)
            if b["nudge"] is not None:            # the sheets behind a stack
                off = off + b["nudge"]
                a *= 0.55
            b["alpha"], b["dd"], b["offn"] = a, d, off
            for f in b["faces"]:
                for k, pts in b["base"][id(f)].items():
                    q = pts.copy()
                    q[:, 1] = q[:, 1] * d - 0.002
                    f.data[k][:] = xf(q + off)
                f.note_changed_data()
            fill = interpolate_color(b["fill"], th.lit, 0.25 * float(lit))
            side_a = float(np.clip(d / 0.05, 0, 1))
            plain = _flag(b["item"].node, "plain")
            for j, f in enumerate(b["faces"]):
                f.set_color(fill if j < 2 else interpolate_color(fill, th.bg, 0.3),
                            0 if plain else a * (1.0 if j < 2 else side_a))
            # texts and cells sit just in front of the front face, following the copy
            b["placed"] = self._retarget(b["deco"], b["placed"], s, s * (off + np.array([0, -d - 0.006, 0])) + at)
            b["deco"].set_opacity(a)
            b["stroke_now"] = interpolate_color(b["stroke"], th.lit, float(lit))
            b["width_now"] = 1.6 + 2.4 * float(lit)
        for rec in self.plates:
            it, plate, rim, ttl = rec[:4]
            pa = show * (1 - 0.7 * u)
            self._static(rec, s, at)
            plate.set_opacity(pa)
            rim.set_stroke(opacity=pa)
            if ttl is not None:
                ttl.set_opacity(pa)
        for rec in self.frames:
            it, frame, mark = rec[:3]
            self._static(rec, s, at)
            frame.set_stroke(opacity=show * (1 - u))
            mark.set_opacity(show)
        col = interpolate_color(th.muted, th.ink, 0.45)
        for e, line, tip, lab in self.edge_mobs:
            pts = [xf([p[0], -d / 2, p[1]]) for p in e["pts"]]
            end, prev = pts[-1], pts[-2]
            dvec = (end - prev) / (np.linalg.norm(end - prev) or 1)
            tl = 0.16 * s
            line.set_points_as_corners([*pts[:-1], end - dvec * tl])
            line.set_stroke(col, 2.2, show)
            e["tip_at"], e["tip_dir"], e["tip_len"] = end, dvec, tl
            tip.set_fill(col, show)
            if lab is not None:
                e["lab_rec"] = self._retarget(lab, e.get("lab_rec", (1.0, np.zeros(3))), s, np.zeros(3))
                self._place_label(e, lab, pts)
                lab.set_opacity(show)
        self._flows(st, show, d, xf)
        self.view()

    def _static(self, rec, s, at):
        """Panels and repeat frames: built at layout coordinates, scaled and moved as one."""
        mobs = [m for m in rec[1:] if isinstance(m, Mobject)]
        key = id(rec[0])
        cur = self._static_at.get(key, (1.0, np.zeros(3)))
        g = Group(*mobs)
        self._static_at[key] = self._retarget(g, cur, s, at)

    def _place_label(self, e, lab, pts):
        """On the longest stretch (or the first / last), beside it: above a level one, right of an
        upright one."""
        segs = list(zip(pts[:-1], pts[1:]))
        if e["at"] == "start":
            a, b = segs[0]
        elif e["at"] == "end":
            a, b = segs[-1]
        else:
            a, b = max(segs, key=lambda ab: np.linalg.norm(ab[1] - ab[0]))
        mid = (a + b) / 2
        if abs(b[2] - a[2]) < 1e-6:   # level: above it
            lab.move_to(mid + np.array([0, 0, 0.08 + lab.get_depth() / 2 + lab.get_height() / 2]))
        else:
            lab.move_to(mid + np.array([0.12 + lab.get_width() / 2, 0, 0]))

    def _flows(self, st, show, d, xf):
        for g in self.glows:
            g.set_opacity(0)
        for tr in self.trails:
            tr.set_stroke(opacity=0)
        fl = np.asarray(st["fl"], float)
        if not len(fl) or fl.max() < 0.01:
            return
        ft, ft1 = float(st["ft"]), float(st["ft1"])
        running = ft < ft1 - 1e-6
        k = int(np.floor(ft + 1e-9))
        now = self.starts.get(k) if running else None
        s = float(st["scale"])
        slot = 0
        for j, spec in enumerate(self.flows):
            if fl[j] < 0.01:
                continue
            # the running flow is at its clock's fraction (its last stretch held lit); the others
            # are finished, fading with their weight
            p = min(1.0, (ft - k) / 0.85) if j == now else 1.0
            stages = [[[np.array([xf([q[0], -d / 2 - 0.01, q[1]]) for q in leg]) for leg in route] for route in stage]
                      for stage in self._flow_path(spec, None)]
            lens = [[sum(float(np.linalg.norm(np.diff(leg, axis=0), axis=1).sum()) for leg in route)
                     for route in stage] for stage in stages]
            span = [max(ls) for ls in lens]
            clock = p * sum(span)
            for stage, ls, sp in zip(stages, lens, span):
                here = min(max(clock, 0.0), sp)
                clock -= sp
                for pts, L in zip(stage, ls):
                    tr, g = self.trails[slot], self.glows[slot]
                    slot += 1
                    if here <= 1e-6:
                        continue
                    legs, head = self._partial(pts, min(here, L))
                    tr.clear_points()
                    for leg in legs:
                        tr.start_new_path(leg[0])
                        tr.add_points_as_corners(leg[1:])
                    a = show * fl[j]
                    tr.set_stroke(self.th.accent, 4.5 * s ** 0.5, a)
                    if here < L:
                        g.move_to(head)
                        g.set_radius(0.3 * s)
                        g.set_opacity(a * min(1.0, here / (0.4 * s)))

    @staticmethod
    def _partial(legs, dist):
        """The route's edges from its start to ``dist`` along them (the last one cut there), and
        the point there."""
        out = []
        for leg in legs:
            part = [leg[0]]
            for a, b in zip(leg[:-1], leg[1:]):
                L = float(np.linalg.norm(b - a))
                if dist <= L:
                    p = a + (b - a) * (dist / (L or 1))
                    part.append(p)
                    out.append(np.array(part))
                    return out, p
                part.append(b)
                dist -= L
            out.append(np.array(part))
        return out, legs[-1][-1]

    def view(self):
        fw, st = self.fw, getattr(self, "_st", None)
        if fw is None or fw.frame is None or not st:
            return
        eye = fw.frame.get_implied_camera_location()
        vkey = (tuple(np.round(eye, 6)), getattr(self, "_key", None))
        if vkey == getattr(self, "_view_key", None):    # same picture from the same place
            return
        self._view_key = vkey
        xf = self._xf(st)
        keys = []
        for b in self.blocks:
            a = b.get("alpha", 0)
            seen = []
            for f, nrm in zip(b["faces"], b["normals"]):
                c = f.get_center()
                vis = float(np.dot(eye - c, nrm)) > 0
                seen.append(vis)
                if not vis:
                    f.set_opacity(0)
            dd = b.get("dd", 0)
            front_seen = seen[0] or dd < 1e-3
            b["deco"].set_opacity(a if front_seen else 0)
            # outline: an edge of the solid shows when a face beside it is seen
            fr, bk = b["front"], b["back"]
            k = len(fr)
            segs, ops = [], []
            P = lambda v: xf(np.array([v[0], v[1] * dd - 0.002, v[2]]) + b["offn"])  # noqa: E731
            for j in range(k):
                side = seen[2 + j] and dd > 0.02
                prev_side = seen[2 + (j - 1) % k] and dd > 0.02
                if seen[0] or side:
                    segs.append((P(fr[j]), P(fr[(j + 1) % k])))
                    ops.append(1.0)
                if dd > 0.02 and (seen[1] or side):
                    segs.append((P(bk[j]), P(bk[(j + 1) % k])))
                    ops.append(1.0)
                if dd > 0.02 and (side or prev_side):
                    segs.append((P(fr[j]), P(bk[j])))
                    ops.append(1.0)
            from .layers3d import _set_segments
            if _flag(b["item"].node, "plain"):
                segs, ops = [], []
            _set_segments(b["outline"], segs, [o * a for o in ops])
            b["outline"].set_stroke(b.get("stroke_now", b["stroke"]), b.get("width_now", 1.6))
            keys.append(np.mean([P(v) for v in fr], axis=0) + 0 * eye)
        order = [self.blocks[j]["group"] for j in np.argsort([-np.linalg.norm(k - eye) for k in keys])]
        if [id(m) for m in order] != [id(m) for m in self.body.submobjects]:
            self.body.set_submobjects(order)
        for e, line, tip, lab in self.edge_mobs:   # heads turned to face the camera
            if "tip_at" not in e:
                continue
            p, dv, tl = e["tip_at"], e["tip_dir"], e["tip_len"]
            side = np.cross(dv, eye - p)
            side = 0.4 * tl * side / (np.linalg.norm(side) or 1)
            tip.set_points_as_corners([p, p - dv * tl + side, p - dv * tl - side, p])

    def extent(self, st):
        if not st:
            return []
        xf = self._xf(st)
        focus = [k for k, v in zip(self.items, st["focus"]) if v > 0.5]
        if focus:
            x0, z0, x1, z1 = self.items[focus[0]].rect
            m = 0.25
            return [list(xf([x, y, z])) for x in (x0 - m, x1 + m) for y in (-DEPTH, 0) for z in (z0 - m, z1 + m)]
        x0, z0, x1, z1 = self.root.rect
        back = 0.05
        if st["unfold"] > 0.5:
            back = max((b["off"][1] for b in self.blocks), default=0) + 0.05
        front = -DEPTH * st["depth"]
        return [list(xf([x, y, z])) for x in (x0, x1) for y in (front, back) for z in (z0, z1)]


CLASSES = {"diagram": Diagram}
