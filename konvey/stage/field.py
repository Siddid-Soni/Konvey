"""General 3D actors for ``<world>``: function surfaces and things that live on them.

Every actor has an ``id``; its state is declared per beat and interpolated
between beats like the cube's. All geometry is computed from the declared
math, so what is drawn is always exact:

- ``<axes3d id x="-3,3" y="-3,3" z="0,4" grid="true" ticks="true" labels="x,y,z">``: axes with
  heads and names at the positive ends; ``grid`` adds a faint floor grid, ``ticks`` numbers
  the whole units.
- ``<surface id fn="x^2 + y^2" x="-3,3" y="-3,3" color opacity zscale>``:
  height field z = f(x, y). Changing ``fn`` morphs the surface.
- ``<point id on="surf" at="x,y" color descend="lr" steps="n">``: a ball on
  the surface. With ``descend``, the hold animates n real gradient-descent
  steps (x <- x - lr * grad f) and leaves a trail.
- ``<gradient id of="pointId" dir="down|up" scale="1">``: arrow from the point
  along the steepest-descent (or ascent) direction, tangent to the surface.
- ``<contours id of="surf" levels="1,2,4,8" z="0">``: level curves of f on the floor.

Bound values for ``<value bind=…>``: ``<point>.x``, ``.y``, ``.f`` (height =
f(x, y)), ``.step``, ``.slope`` (|grad f|).
"""

from __future__ import annotations

import numpy as np
from scipy.interpolate import RegularGridInterpolator
from scipy.spatial.transform import Rotation

from manimlib import *  # noqa: F401,F403

from .expr import parse_expr
from .parse import BeatError, Node
from . import actors3d
from .solids import CLASSES, ORDER, SOLID_ATTRS, SOLID_TAGS

CLASSES.update(actors3d.CLASSES)   # parametric surfaces, trajectories, slices (konvey.stage.actors3d)
ORDER.update(actors3d.ORDER)
from .theme import current

FIELD_TAGS = {"axes3d", "surface", "point", "gradient", "contours"} | SOLID_TAGS | actors3d.TAGS
FIELD_ATTRS = {**SOLID_ATTRS, **actors3d.ATTRS,
    "axes3d": {"id", "x", "y", "z", "grid", "ticks", "labels"},
    "surface": {"id", "fn", "x", "y", "color", "opacity", "zscale"},
    "point": {"id", "on", "at", "color", "descend", "steps"},
    "gradient": {"id", "of", "dir", "scale", "color"},
    "contours": {"id", "of", "levels", "z", "color"},
}
GRID = 41
MAX_HEIGHT = 3.5          # auto zscale keeps the tallest part of a surface this high


def is_field(node: Node) -> bool:
    """Actors FieldWorld owns. A bare ``<shadow>`` (no ``of``) is the cube kit's."""
    return node.tag in FIELD_TAGS and not (node.tag == "shadow" and "of" not in node.attrs)


def _pair(node: Node, key: str, default: str) -> tuple[float, float]:
    try:
        a, b = (float(v) for v in node.attrs.get(key, default).split(",")[:2])
    except ValueError as e:
        raise BeatError(f'<{node.tag} id={node.id}> {key}="{node.attrs.get(key)}": use "min,max"') from e
    return a, b


class Surface:
    def __init__(self, node: Node, fns: list[str]):
        self.x = _pair(node, "x", "-3,3")
        self.y = _pair(node, "y", "-3,3")
        self.xs = np.linspace(*self.x, GRID)
        self.ys = np.linspace(*self.y, GRID)
        X, Y = np.meshgrid(self.xs, self.ys, indexing="ij")
        self.X, self.Y = X, Y
        # The exact functions are kept: heights, slopes and descent use the formula
        # (a weighted mix of them while one surface morphs into another), never the grid.
        self.fns = list(fns)
        self.funcs = [parse_expr(fn, ("x", "y")) for fn in self.fns]
        self.grids = {fn: np.vectorize(f)(X, Y).astype(float) for fn, f in zip(self.fns, self.funcs)}
        top = max(np.abs(g).max() for g in self.grids.values()) or 1.0
        self.zscale = float(node.attrs.get("zscale", min(1.0, MAX_HEIGHT / top)))
        self.color = current().color(node.attrs.get("color"), "c1") if node.attrs.get("color") \
            else current().solid
        self.span = max(self.x[1] - self.x[0], self.y[1] - self.y[0])
        self.mob = Surface3D(self)
        self.weights = np.eye(len(self.fns))[0]

    def onehot(self, fn: str) -> np.ndarray:
        return np.eye(len(self.fns))[self.fns.index(fn)]

    def set_weights(self, w: np.ndarray):
        self.weights = np.asarray(w, float)

    @property
    def heights(self) -> np.ndarray:
        return sum(w * self.grids[fn] for w, fn in zip(self.weights, self.fns) if w)

    def f(self, x, y) -> float:
        return float(sum(w * f(x, y) for w, f in zip(self.weights, self.funcs) if w))

    def grad(self, x, y, h=1e-5) -> np.ndarray:
        return np.array([(self.f(x + h, y) - self.f(x - h, y)) / (2 * h),
                         (self.f(x, y + h) - self.f(x, y - h)) / (2 * h)])

    def world(self, x, y, z=None) -> np.ndarray:
        return np.array([x, y, self.zscale * (self.f(x, y) if z is None else z)])


class Surface3D(Group):
    """A height field: a shaded ParametricSurface plus a light mesh, rebuilt from a grid."""

    def __init__(self, owner: Surface):
        self.owner = owner
        surf = ParametricSurface(lambda u, v: np.array([u, v, 0]),
                                 u_range=owner.x, v_range=owner.y, resolution=(GRID - 1, GRID - 1))
        surf.set_color(owner.color, 0.85).set_shading(*current().solid_shading)
        mesh = VGroup(*(VMobject() for _ in range(2 * 11)))
        mesh.set_stroke(current().mesh, 1, 0.25)
        mesh.apply_depth_test()
        super().__init__(surf, mesh)
        self.surf, self.mesh = surf, mesh
        self._base = {k: surf.data[k].copy() for k in ("point", "du_point", "dv_point")}

    def update_heights(self, h: np.ndarray, opacity: float):
        o = self.owner
        interp = RegularGridInterpolator((o.xs, o.ys), h, bounds_error=False, fill_value=None)
        for k, base in self._base.items():
            pts = base.copy()
            pts[:, 2] = o.zscale * interp(pts[:, :2])
            self.surf.data[k][:] = pts
        self.surf.note_changed_data()
        self.surf.set_opacity(0.85 * opacity)
        idx = np.linspace(0, GRID - 1, 11).astype(int)
        lines = [np.c_[o.xs, np.full(GRID, o.ys[j]), o.zscale * h[:, j] + 0.01] for j in idx]
        lines += [np.c_[np.full(GRID, o.xs[i]), o.ys, o.zscale * h[i, :] + 0.01] for i in idx]
        for m, pts in zip(self.mesh, lines):
            m.set_points_as_corners(pts)
        self.mesh.set_stroke(opacity=0.25 * opacity)


class FieldWorld:
    """All id'd field actors of a beat file. Built once from every beat, so ids persist."""

    def __init__(self, beats):
        self.nodes: dict[str, list[Node]] = {}
        for b in beats:
            for key, node in b.world.items():
                if not is_field(node):
                    continue
                if not node.id:
                    raise BeatError(f"beat {b.index}: <{node.tag}> in <world> needs an id")
                seen = self.nodes.get(node.id)
                if seen and seen[0].tag != node.tag:
                    raise BeatError(f'beat {b.index}: id="{node.id}" is a <{node.tag}> here but a '
                                    f"<{seen[0].tag}> in an earlier beat; one id is one actor, so give "
                                    f"the <{node.tag}> a new id")
                extra = set(node.attrs) - FIELD_ATTRS[node.tag]
                if extra:
                    raise BeatError(f"beat {b.index}: <{node.tag} id={node.id}> unknown attributes "
                                    f"{sorted(extra)}; allowed {sorted(FIELD_ATTRS[node.tag])}")
                self.nodes.setdefault(node.id, []).append(node)
        self.surfaces: dict[str, Surface] = {}
        self.radius: dict[str, float] = {}
        self.mobs: dict[str, Mobject] = {}
        self.trails: dict[str, VMobject] = {}
        self.values: dict[str, float] = {}
        self.actors: dict = {}           # solids.py actors, by id
        self.frame = None                # camera frame (set by the scene; label3d projects with it)
        self._state: dict = {}
        # Solids first, so actors that refer to them (shadow, field, line3d, ...) can check the ref.
        for i, ns in sorted(self.nodes.items(), key=lambda kv: ORDER.get(kv[1][0].tag, 0)):
            tag = ns[0].tag
            if tag in CLASSES:
                self.actors[i] = CLASSES[tag](i, ns, self)
                self.mobs[i] = self.actors[i].mob
            elif tag == "surface":
                fns = list(dict.fromkeys(n.attrs.get("fn", "") for n in ns))
                if not all(fns):
                    raise BeatError(f"<surface id={i}> needs fn=")
                self.surfaces[i] = Surface(ns[0], fns)
                self.mobs[i] = self.surfaces[i].mob
            elif tag == "axes3d":
                x, y, z = (_pair(ns[0], k, d) for k, d in (("x", "-3,3"), ("y", "-3,3"), ("z", "0,4")))
                self.mobs[i] = self._axes(ns[0], x, y, z)
            elif tag == "point":
                self.radius[i] = 0.028 * self._span(ns[0].attrs.get("on"))
                self.mobs[i] = Sphere(radius=self.radius[i], color=current().color(ns[0].attrs.get("color"))
                                     if "color" in ns[0].attrs else current().marker)
                self.trails[i] = VMobject().set_stroke(current().trail, 3)
            elif tag == "gradient":
                point = self.nodes.get(ns[0].attrs.get("of"), [ns[0]])[0]
                arrow_color = current().color(ns[0].attrs.get("color"), "accent")
                self.mobs[i] = Arrow(ORIGIN, RIGHT, buff=0, fill_color=arrow_color,
                                     thickness=0.5 * self._span(point.attrs.get("on")),
                                     max_width_to_length_ratio=0.25,
                                     stroke_color=arrow_color, stroke_width=6)
            elif tag == "contours":
                self.mobs[i] = VGroup().apply_depth_test()
        if self.surfaces:
            # Heights are drawn scaled to fit; scale the axes' z the same way so they agree.
            zs = next(iter(self.surfaces.values())).zscale
            for i, ns in self.nodes.items():
                if ns[0].tag == "axes3d":
                    ax, _, heads, labels = self.mobs[i]
                    ax.stretch(zs, 2, about_point=ORIGIN)
                    heads[2].shift((zs - 1) * heads[2].get_center()[2] * OUT)
                    for lab in labels:
                        lab.at = lab.at * np.array([1, 1, zs])
        for i, ns in self.nodes.items():
            for n in ns:
                ref = n.attrs.get("on") or n.attrs.get("of")
                if n.tag in ("point", "contours") and ref not in self.surfaces:
                    raise BeatError(f"<{n.tag} id={i}> {('on' if n.tag == 'point' else 'of')}="
                                    f"\"{ref}\" must name a <surface id>")
                if n.tag == "gradient" and (ref not in self.nodes or self.nodes[ref][0].tag != "point"):
                    raise BeatError(f'<gradient id={i}> of="{ref}" must name a <point id>')
                if n.tag == "flow" and n.attrs.get("on") and self.nodes.get(n.attrs["on"], [n])[0].tag == "parametric":
                    continue   # lines on any (u, v) surface
                want = {"shadow": "of", "label3d": "of", "field": "on", "flow": "on"}.get(n.tag)
                if want and n.attrs.get(want) and not self._is_solid(n.attrs[want], sphere=n.tag in ("field", "flow")):
                    kind = "<sphere id>" if n.tag in ("field", "flow") else "<sphere id> or <solid id>"
                    raise BeatError(f'<{n.tag} id={i}> {want}="{n.attrs[want]}" must name a {kind}')
                if n.tag == "shadow" and not n.attrs.get("of"):
                    raise BeatError(f'<shadow id={i}> needs of="solidId"')
        # Shadows lie on the floor without a depth test, so they draw before the solids.
        first = [m for i, m in self.mobs.items() if self.nodes[i][0].tag == "shadow"]
        rest = [m for i, m in self.mobs.items() if self.nodes[i][0].tag != "shadow"]
        self.group = Group(*first, *rest, *self.trails.values())
        self._order = list(self.group.submobjects)

    def _axes(self, node: Node, x, y, z) -> Group:
        """[axes, floor grid, heads, pinned labels]: 3b1b-style axes, readable from any angle."""
        from .solids import _pinned_text, project

        th = current()
        flag = lambda k: node.attrs.get(k, "false").strip().lower() in ("true", "1", "yes")  # noqa: E731
        ax = ThreeDAxes(x, y, z, width=x[1] - x[0], height=y[1] - y[0], depth=z[1] - z[0],
                        axis_config={"include_tip": False, "stroke_color": th.muted, "stroke_width": 2.5})
        ax.shift(-ax.c2p(0, 0, 0))
        grid = VGroup()
        if flag("grid"):
            grid.add(*(Line([gx, y[0], 0], [gx, y[1], 0]) for gx in range(int(np.ceil(x[0])), int(x[1]) + 1)),
                     *(Line([x[0], gy, 0], [x[1], gy, 0]) for gy in range(int(np.ceil(y[0])), int(y[1]) + 1)))
            grid.set_stroke(th.muted, 1.2)
        ends = [np.array(v) for v in ([x[1], 0, 0], [0, y[1], 0], [0, 0, z[1]])]
        heads = Group()
        for e in ends:
            cone = Cone(radius=0.07, height=0.22, resolution=(16, 2))
            d = e / np.linalg.norm(e)
            R, _ = Rotation.align_vectors([d], [[0, 0, 1]])
            cone.apply_matrix(R.as_matrix(), about_point=ORIGIN).move_to(e + 0.05 * d)
            heads.add(cone.set_color(th.muted))
        names = [n.strip() for n in node.attrs.get("labels", "x,y,z").split(",")] + ["", "", ""]
        pins = [(e + 0.42 * e / np.linalg.norm(e), names[k]) for k, e in enumerate(ends) if names[k]]
        pins = [(at, text, None) for at, text in pins]
        if flag("ticks"):
            for k, (lo, hi) in enumerate((x, y, z)):
                step = 1 if hi - lo <= 6 else 2 if hi - lo <= 12 else 5   # no crowded numbers
                for t in range(int(np.ceil(lo)), int(np.floor(hi))):   # the end carries the name
                    if t and t % step == 0:
                        p = np.zeros(3)
                        p[k] = t
                        pins.append((p, str(t), k))
        labels = Group()
        for at, text, axis in pins:
            lab = _pinned_text(text, th.muted, 22 if axis is not None else 30)
            lab.at, lab.axis = at, axis
            labels.add(lab)
        return Group(ax, grid, heads, labels)

    def refresh_view(self):
        """Every rendered frame (the scene calls it): what depends on where the camera is.
        Pinned labels follow their 3D points and arrow heads turn to face the camera, also
        while the camera orbits during a hold."""
        if self.frame is None:
            return
        from .solids import project

        for a in self.actors.values():
            view = getattr(a, "view", None)
            if view is not None:
                view()
        for i, ns in self.nodes.items():
            if ns[0].tag == "axes3d":
                for lab in self.mobs[i][3]:
                    p = project(self.frame, lab.at)
                    if lab.axis is not None:
                        # beside its tick, off the axis as it runs on screen (an axis pointing
                        # into the screen would otherwise stack its numbers on the others)
                        d = project(self.frame, lab.at + np.eye(3)[lab.axis]) - p
                        perp = np.array([d[1], -d[0], 0.0])
                        n = np.linalg.norm(perp)
                        perp = perp / n if n > 1e-6 else DOWN
                        if perp[1] > 0.3 or (abs(perp[1]) <= 0.3 and perp[0] > 0):
                            perp = -perp      # below or left of the axis
                        p = p + 0.28 * perp
                    lab.move_to(p)

    def _is_solid(self, ref: str, sphere: bool = False) -> bool:
        a = self.actors.get(ref)
        return a is not None and hasattr(a, "placed") and (not sphere or a.shape == "sphere")

    def raw_state(self, i: str) -> dict | None:
        return self._state.get(i)

    def state_of(self, i: str) -> float:
        st = self._state.get(i)
        return float(st["show"]) if st else 0.0

    def light_dir(self) -> np.ndarray:
        for i, a in self.actors.items():
            st = self._state.get(i)
            if self.nodes[i][0].tag == "light" and st and st["show"] > 0:
                return st["dir"] / np.linalg.norm(st["dir"])
        return np.array([0.0, 0.0, -1.0])

    def _span(self, surface_id) -> float:
        """Size of a surface's domain, so balls and arrows scale with what they sit on."""
        node = self.nodes.get(surface_id, [None])[0]
        if node is None:
            return 6.0
        (x0, x1), (y0, y1) = _pair(node, "x", "-3,3"), _pair(node, "y", "-3,3")
        return max(x1 - x0, y1 - y0)

    # --- state ---------------------------------------------------------
    def state_from(self, actors: dict[str, Node], prev: dict | None) -> dict:
        """Per-id numeric state for one beat (arrays and floats interpolate)."""
        prev = prev or {}
        s = {}
        self.pending = s   # this beat's states so far: line3d/angle3d resolve solid ids from it
        for i in sorted(self.nodes, key=lambda k: ORDER.get(self.nodes[k][0].tag, 0)):
            node = actors.get(i)
            old = prev.get(i)
            if node is None:
                s[i] = {**old, "show": 0.0} if old else None
                continue
            st = {"show": 1.0}
            if i in self.actors:
                st = self.actors[i].state(node, old)
            elif node.tag == "surface":
                st["w"] = self.surfaces[i].onehot(node.attrs["fn"])
            elif node.tag == "point":
                if "at" in node.attrs:
                    st["xy"] = np.array(_pair(node, "at", "0,0"))
                elif old is not None:
                    st["xy"] = old["xy"]
                else:
                    raise BeatError(f'<point id={i}> needs at="x,y" the first time it appears')
            s[i] = st
        return s

    @staticmethod
    def lerp(a: dict, b: dict, t: float, enter_t: float | None = None) -> dict:
        out = {}
        for i in set(a) | set(b):
            sa, sb = a.get(i), b.get(i)
            if sa is None and sb is None:
                out[i] = None
                continue
            if sa is None:
                sa = {**sb, "show": 0.0}
            if sb is None:
                sb = {**sa, "show": 0.0}
            out[i] = {k: (1 - t) * sa[k] + t * sb[k] if k in sa else sb[k] for k in sb}
            if enter_t is not None and sa.get("show", 0) == 0 and sb.get("show", 0) > 0:
                out[i]["show"] = enter_t * sb["show"]   # appearing: fade in late (see lerp_state)
        return out

    # --- per-frame ---------------------------------------------------------
    def apply(self, s: dict):
        self._state = s
        for i in sorted(self.actors, key=lambda k: ORDER[self.nodes[k][0].tag]):
            self.actors[i].apply(s.get(i), self)
        self._draw_see_through_last(s)
        for i, sid in self.surfaces.items():
            st = s.get(i)
            if st is not None:
                sid.set_weights(st["w"])
            sid.mob.update_heights(sid.heights, st["show"] if st else 0.0)
        for i, ns in self.nodes.items():
            tag, st = ns[0].tag, s.get(i)
            show = st["show"] if st else 0.0
            mob = self.mobs[i]
            if tag == "axes3d":
                mob[0].set_opacity(show)
                mob[1].set_stroke(opacity=0.22 * show)
                mob[2].set_opacity(show)
                for lab in mob[3]:
                    lab.set_opacity(show)
            elif tag == "point":
                surf = self.surfaces[ns[0].attrs["on"]]
                xy = st["xy"] if st else np.zeros(2)
                mob.move_to(surf.world(*xy) + self.radius[i] * OUT)
                mob.set_opacity(show)
                self.trails[i].set_stroke(opacity=show)
                g = surf.grad(*xy)
                self.values.update({f"{i}.x": xy[0], f"{i}.y": xy[1], f"{i}.f": surf.f(*xy),
                                    f"{i}.slope": float(np.linalg.norm(g))})
                self._points = getattr(self, "_points", {})
                self._points[i] = (surf, xy, show)
            elif tag == "contours":
                self._contours(i, ns[0], show)
        for i, ns in self.nodes.items():
            if ns[0].tag == "gradient":
                self._gradient(i, s.get(i), s)

    def _draw_see_through_last(self, s: dict):
        """A see-through solid still writes depth, so whatever is drawn after it and lies inside
        it (pyramids filling a glass cube) vanishes. Solids that are see-through now are drawn
        after the opaque ones (also while one fades in: it would cut a black hole into a glass
        solid around it)."""
        solids = {id(self.mobs[i]) for i, a in self.actors.items() if hasattr(a, "placed")}
        # fading in or out counts: half-shown, a solid is as see-through as glass
        glass = {id(self.mobs[i]) for i, a in self.actors.items() if hasattr(a, "placed")
                 and s.get(i) and s[i].get("opacity", 1.0) * s[i].get("show", 1.0) < 0.95}
        if not glass:
            order = self._order
        else:
            last = max(k for k, m in enumerate(self._order) if id(m) in solids)
            head = [m for m in self._order[:last + 1] if id(m) not in glass]
            order = head + [m for m in self._order if id(m) in glass] + self._order[last + 1:]
        if [id(m) for m in order] != [id(m) for m in self.group.submobjects]:
            self.group.set_submobjects(order)

    def _gradient(self, i, st, s):
        node = self.nodes[i][0]
        show = st["show"] if st else 0.0
        surf, xy, pshow = self._points[node.attrs["of"]]
        g = surf.grad(*xy)
        n = np.linalg.norm(g)
        sign = 1 if node.attrs.get("dir", "down") == "up" else -1
        d = sign * g / n if n > 1e-6 else np.zeros(2)
        # Arrow length follows the slope, so it visibly shrinks near a minimum.
        length = float(node.attrs.get("scale", 1.0)) * min(0.25 * surf.span, 0.06 * surf.span * n)
        start = surf.world(*xy) + self.radius[node.attrs["of"]] * OUT
        rise = surf.zscale * float(g @ d) * length
        end = start + np.array([*(d * length), rise])
        if n > 1e-6:
            self.mobs[i].put_start_and_end_on(start, end)
        self.mobs[i].set_opacity(show * pshow * (1 if length > 0.05 else 0))

    def _contours(self, i, node, show):
        import contourpy

        surf = self.surfaces[node.attrs["of"]]
        levels = [float(v) for v in node.attrs.get("levels", "").split(",") if v.strip()]
        if not levels:
            lo, hi = float(surf.heights.min()), float(surf.heights.max())
            levels = list(np.linspace(lo, hi, 7)[1:-1])
        gen = contourpy.contour_generator(surf.X, surf.Y, surf.heights)
        z = float(node.attrs.get("z", 0.02))
        group = self.mobs[i]
        lines = [ln for lv in levels for ln in gen.lines(lv) if len(ln) > 2]
        while len(group) < len(lines):
            group.add(VMobject().set_stroke(current().color(node.attrs.get("color"), "accent"), 2).apply_depth_test())
        for m, ln in zip(group, lines):
            m.set_points_as_corners(np.c_[ln, np.full(len(ln), z)])
            m.set_stroke(opacity=0.8 * show)
        for m in group[len(lines):]:
            m.set_stroke(opacity=0)

    def segments(self, s: dict, only) -> list[tuple[np.ndarray, np.ndarray]]:
        """The straight pieces a viewer must read (lines, face sides, angle legs) of ``only``,
        for choosing a camera angle that shows them without foreshortening."""
        segs = []
        for i in only:
            st, tag = s.get(i), self.nodes[i][0].tag
            if not st:
                continue
            if tag in ("line3d", "angle3d"):
                ends = self.actors[i].ends(st)
                segs += [(ends[0], ends[1])] if tag == "line3d" else [(ends[0], ends[1]), (ends[0], ends[2])]
            elif tag == "face3d":
                pts = st["pts"]
                segs += [(pts[k], pts[(k + 1) % len(pts)]) for k in range(len(pts))]
            elif tag == "solid" and getattr(self.actors[i], "shape", "") == "hull":
                segs += self.actors[i].hull_edges(st)
        return [(np.asarray(a, float), np.asarray(b, float)) for a, b in segs
                if np.linalg.norm(np.asarray(b) - np.asarray(a)) > 1e-6]

    def extent(self, s: dict, only=None) -> list:
        pts = []
        for i, st in s.items():
            if not st or st.get("show", 0) <= 0 or (only is not None and i not in only):
                continue
            ns = self.nodes[i][0]
            if ns.tag == "surface":
                surf = self.surfaces[i]
                surf.set_weights(st["w"])
                h = surf.heights
                zs = (surf.zscale * float(h.min()), surf.zscale * float(h.max()))
                pts += [[x, y, z] for x in surf.x for y in surf.y for z in zs]
            elif ns.tag == "axes3d":
                pts += [list(self.mobs[i][0].get_corner(c)) for c in (IN + DL, OUT + UR)]
                pts += [list(lab.at) for lab in self.mobs[i][3] if lab.axis is None]   # axis names
            elif i in self.actors:
                pts += self.actors[i].extent(st)
        return pts

    # --- hold actions ----------------------------------------------------------
    def descent_path(self, node: Node, xy: np.ndarray) -> np.ndarray:
        surf = self.surfaces[node.attrs["on"]]
        lr, steps = float(node.attrs["descend"]), int(node.attrs.get("steps", 10))
        span = max(surf.x[1] - surf.x[0], surf.y[1] - surf.y[0])
        path = [np.array(xy, float)]
        for _ in range(steps):
            p = path[-1] - lr * surf.grad(*path[-1])
            path.append(p)
            if np.abs(p).max() > 1.5 * span:   # diverged far off the surface: stop here
                break
        return np.array(path)

    def hop(self, i: str, p0, p1, s: float) -> np.ndarray:
        """Point at fraction ``s`` of the step p0 -> p1: a short arc over the surface,
        so every update reads as a jump (and an overshoot as a leap across)."""
        surf = self.surfaces[self.nodes[i][0].attrs["on"]]
        a, b = surf.world(*p0), surf.world(*p1)
        lift = 0.25 * np.linalg.norm(b[:2] - a[:2]) * np.sin(np.pi * s)
        return a + s * (b - a) + (lift + self.radius[i]) * OUT

    def set_trail(self, i: str, path_xy: np.ndarray, frac: float = 1.0):
        """Trail through the completed hops of ``path_xy`` plus ``frac`` of the last one."""
        pts = []
        for k in range(len(path_xy) - 1):
            last = k == len(path_xy) - 2
            for s in np.linspace(0, frac if last else 1, 16):
                pts.append(self.hop(i, path_xy[k], path_xy[k + 1], s))
        if len(pts) < 2:
            surf = self.surfaces[self.nodes[i][0].attrs["on"]]
            pts = [surf.world(*path_xy[0]) + self.radius[i] * OUT] * 2
        self.trails[i].set_points_as_corners(pts)
