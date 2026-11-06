"""More 3D world actors (manimgl): parametric surfaces, traced trajectories, slices of a surface.

- ``<parametric id x="…" y="…" z="…" u="0,2pi" v="-1,1">``: the surface (x, y, z)(u, v), e.g. a
  Möbius strip or a torus. New expressions in a later beat morph it (same grid, points blend).
- ``<trajectory id system="lorenz" starts="x,y,z; …" t="12" tail="4">``: paths of a flow in 3D,
  one per start (or ``count`` starts a hair apart), traced up to time ``t``. Each beat continues
  from where the previous one stopped, drawing during the line (``LIVE``). ``fn="dx; dy; dz"``
  (in x, y, z) for a flow of your own; ``tail`` keeps only the last seconds of each path.
- ``<waves id sources="x,y; x,y" wavelength="1" t="6">``: ripples spreading from point sources over
  a square floor ``size`` across, each point coloured by the sum of the waves there (bright crest,
  dark trough), as 3b1b's LightWaveSlice. The rings leave the sources at t = 0 and travel a unit a
  second; ``lift`` raises the floor into the waves' heights; ``show="intensity"`` shows how
  strongly each point shakes instead (the bright and dark fringes where waves add or cancel).
  New ``sources`` in a later beat move them there. ``fn="…"`` in x, y, t draws any field instead
  (values -1 … 1; e.g. a standing wave ``sin(2*x)*cos(3*t)``); a later beat's new ``fn`` blends in.
- ``<particles id system="figure8|planets|binary|three|charges|springs" t="20" tail="6">`` (also
  ``<orbits>``): bodies pushing and pulling on each other, traced like trajectories, each a glow
  sized by its mass. ``bodies="m, x,y,z, vx,vy,vz[, q]; …"`` for your own; ``force`` = any of
  ``gravity`` (G = 1, the default), ``charge`` (q, like charges repel), ``spring`` (along
  ``links="0-1, 1-2"`` at ``stiffness``, rest length = the starting distance).
- ``<flow id fn="vx; vy; vz" on="sphereId" count="600" t="10">``: lines of a field on a sphere (the
  part of the field along the surface), each the path a point takes in ``life`` seconds, with a
  swell of brightness sliding along each one (3b1b's animated stream lines); coloured by speed, so
  where the field dies out shows dark. ``on`` a ``<parametric>`` surface (a torus …): the lines
  follow the field's part along that surface. Without ``on``: in the box -3 … 3, flat (vz ignored).
- ``<slice id of="surfaceId" dir="1,1" at="0">``: the vertical plane dir·(x, y) = at through a
  height surface, its cut curve lit and the area under the curve shaded; a later beat's ``at``
  sweeps the plane there during the line. Value ``sliceId.area`` (∫ f along the cut).

``LIVE = (now, target)``: state keys the scene's hold runs from now to target (scene._hold)."""

from __future__ import annotations

import math
import re

import numpy as np

from manimlib import *  # noqa: F401,F403
from scipy.integrate import trapezoid
from scipy.spatial.transform import Rotation

from .expr import parse_expr
from .theme import current
from .tree import BeatError

TAGS = {"parametric", "trajectory", "slice", "waves", "orbits", "particles", "flow"}
ATTRS = {
    "parametric": {"id", "x", "y", "z", "u", "v", "color", "opacity", "mesh"},
    "trajectory": {"id", "system", "fn", "starts", "count", "spread", "t", "tail", "scale", "color"},
    "slice": {"id", "of", "dir", "at", "color"},
    "waves": {"id", "sources", "fn", "wavelength", "size", "t", "lift", "show", "color", "decay"},
    "orbits": {"id", "system", "bodies", "force", "links", "stiffness", "t", "tail", "scale", "color"},
    "particles": {"id", "system", "bodies", "force", "links", "stiffness", "t", "tail", "scale", "color"},
    "flow": {"id", "fn", "on", "count", "t", "life", "color", "seed"},
}
ORDER = {"parametric": 0, "trajectory": 2, "slice": 3, "waves": 0, "orbits": 2, "particles": 2, "flow": 3}


def _range(node, key: str, default: str) -> tuple[float, float]:
    raw = node.attrs.get(key, default)
    parts = [re.sub(r"(\d)\s*pi", r"\1*pi", p.strip()) for p in raw.split(",")]
    if len(parts) != 2:
        raise BeatError(f'<{node.tag} id={node.id}> {key}="{raw}": use "min,max" (pi allowed: "0,2pi")')
    return tuple(float(parse_expr(p, ())()) for p in parts)


def _num(node, key: str, default: float) -> float:
    try:
        return float(node.attrs.get(key, default))
    except ValueError:
        raise BeatError(f'<{node.tag} id={node.id}> {key}="{node.attrs.get(key)}": a number') from None


# --- parametric surfaces ---------------------------------------------------------------------------
class Parametric:
    RES = (101, 41)   # u × v samples: a smooth silhouette (3b1b uses 101 × 101)
    U_LINES, V_LINES = 24, 8   # mesh lines across u (e.g. the tube's circles) and along it
    MESH_OPACITY = 0.25

    def __init__(self, i, nodes, world):
        self.id = i
        n0 = nodes[0]
        th = current()
        self.u, self.v = _range(n0, "u", "0,2pi"), _range(n0, "v", "-1,1")
        self.keys = list(dict.fromkeys(self._key(n) for n in nodes))
        self.datas = []
        for key in self.keys:
            fx, fy, fz = (parse_expr(e, ("u", "v")) for e in key)
            surf = ParametricSurface(lambda u, v, fx=fx, fy=fy, fz=fz: np.array([fx(u, v), fy(u, v), fz(u, v)]),
                                     u_range=self.u, v_range=self.v, resolution=self.RES)
            self.datas.append({k: surf.data[k].copy() for k in ("point", "du_point", "dv_point")})
        color = th.color(n0.attrs.get("color"), "c2") if n0.attrs.get("color") else th.solid
        self.surf = ParametricSurface(lambda u, v: np.array([u, v, 0.0]), u_range=self.u, v_range=self.v,
                                      resolution=self.RES)
        # see-through, so the whole shape reads; its triangles are drawn far-to-near from the
        # camera every frame (3b1b: surface.always_sort_to_camera), or the far side shows
        # through as patches
        # 3b1b's recipe for a shape to read (inscribed_rect/loops.py): a light surface, its
        # triangles sorted to the camera, a thin mesh drawn on top without the depth test (so
        # the lines on the far side show through and give the shape)
        self.opacity = _num(n0, "opacity", 0.5)
        self.surf.set_color(color, self.opacity).set_shading(0.4, 0.3, 0)
        self.fw = None
        self.mesh = VGroup(*(VMobject() for _ in range(self.U_LINES + self.V_LINES)))
        self.mesh.set_stroke(th.ink, 1, self.MESH_OPACITY)
        self.mob = Group(self.surf, self.mesh)
        self.mesh_on = n0.attrs.get("mesh", "true").lower() not in ("false", "0", "no")

    @staticmethod
    def _key(n) -> tuple[str, str, str]:
        exprs = tuple(n.attrs.get(k, "").strip() for k in ("x", "y", "z"))
        if not all(exprs):
            raise BeatError(f'<parametric id={n.id}> needs x=, y= and z= in u and v '
                            '(a Möbius strip: x="(1+v/2*cos(u/2))*cos(u)" …)')
        return exprs

    def state(self, node, old):
        return {"show": 1.0, "w": np.eye(len(self.keys))[self.keys.index(self._key(node))]}

    def _blend(self, w) -> dict:
        return {k: sum(wi * d[k] for wi, d in zip(w, self.datas) if wi) for k in self.datas[0]}

    def apply(self, st, fw):
        self.fw = fw
        show = st["show"] if st else 0.0
        if st:
            for k, pts in self._blend(st["w"]).items():
                self.surf.data[k][:] = pts
            self.surf.note_changed_data()
            if self.mesh_on:   # lines of constant u and of constant v, so the shape and its twist read
                pts = self.surf.data["point"].reshape(self.RES[0], self.RES[1], 3)   # u-major
                across = [pts[i, :] for i in np.linspace(0, self.RES[0] - 1, self.U_LINES).astype(int)]
                along = [pts[:, j] for j in np.linspace(0, self.RES[1] - 1, self.V_LINES).astype(int)]
                for m, line in zip(self.mesh, across + along):
                    m.set_points_smoothly(line)
        self.surf.set_opacity(self.opacity * show)
        self.mesh.set_stroke(opacity=(self.MESH_OPACITY if self.mesh_on else 0) * show)
        self.view()

    def view(self):   # every frame: far triangles first, as seen from where the camera is now
        if self.fw is not None and self.fw.frame is not None and self.opacity < 1:
            self.surf.sort_faces_back_to_front(self.fw.frame.get_implied_camera_location() - self.surf.get_center())

    def extent(self, st):
        if not st:
            return []
        p = self._blend(st["w"])["point"]
        return [p.min(axis=0).tolist(), p.max(axis=0).tolist()]


# --- trajectories of a flow -------------------------------------------------------------------------
SYSTEMS = {"lorenz": ("10*(y - x)", "x*(28 - z) - y", "x*y - 8/3*z")}
DT = 0.004


class Trajectory:
    LIVE = ("t", "t1")

    def __init__(self, i, nodes, world):
        self.id = i
        n0 = nodes[0]
        th = current()
        self.paths, starts = self._paths(i, n0, nodes)
        self.tail = _num(n0, "tail", 0)
        n = len(starts)
        self._look(n0, n, th)

    def _look(self, n0, n, th, sizes=None, cols=None):
        if cols is not None:
            pass
        elif n0.attrs.get("color"):
            cols = [th.color(n0.attrs["color"])] * n
        else:   # each path its own colour, so the moment they part is visible
            cols = color_gradient([*th.palette, th.accent], max(n, 2))[:n]
        # 3b1b's way (lorenz.py): each path is one smooth curve, built once; a frame shows part of
        # it (pointwise_become_partial, as ShowCreation does), so its points never move: no
        # shimmer, and Bézier curves instead of a chain of corners
        width = 2.0 if n > 3 else 3.2
        every = max(1, int(0.01 / DT))   # a sample per 1/100 s is plenty for a smooth fit
        self.every = every
        self.full = []
        for k, c in enumerate(cols):
            full = VMobject().set_points_smoothly(self.paths[k, ::every])
            full.set_stroke(c, width).set_flat_stroke(False)
            self.full.append(full)
        self.curves = VGroup(*(f.copy() for f in self.full))
        # 3b1b's head: a soft glow, which reads over the lines from any side (a lit sphere
        # broke up where it passed behind them)
        self.heads = Group(*(GlowDot(ORIGIN, radius=0.16 * (1 if sizes is None else sizes[k]), color=c)
                             for k, c in enumerate(cols)))

        self.mob = Group(self.curves, self.heads)

    def _paths(self, i, n0, nodes):
        """(paths in world units: starts × steps × 3, the starts): RK4 of the flow, centred and
        scaled to about 3 units."""
        system = n0.attrs.get("system", "").strip()
        if n0.attrs.get("fn"):
            exprs = [e.strip() for e in n0.attrs["fn"].split(";")]
            if len(exprs) != 3:
                raise BeatError(f'<trajectory id={i}> fn="{n0.attrs["fn"]}": three rates "dx; dy; dz" in x, y, z')
        elif system in SYSTEMS:
            exprs = SYSTEMS[system]
        else:
            raise BeatError(f'<trajectory id={i}> needs system="{"|".join(SYSTEMS)}" or fn="dx; dy; dz"')
        f = [parse_expr(e, ("x", "y", "z")) for e in exprs]
        starts = self._starts(n0)
        t_max = max(_num(n, "t", 0) for n in nodes)
        steps = int(t_max / DT) + 2
        paths = np.empty((len(starts), steps, 3))
        for k, s in enumerate(starts):   # RK4, fixed step: every view of it agrees
            p = np.array(s, float)
            rate = lambda q: np.array([g(*q) for g in f])  # noqa: E731
            for j in range(steps):
                paths[k, j] = p
                a = rate(p)
                b = rate(p + DT / 2 * a)
                c = rate(p + DT / 2 * b)
                d = rate(p + DT * c)
                p = p + DT / 6 * (a + 2 * b + 2 * c + d)
        # into the world: centred, scaled to about 3 units unless scale= says otherwise
        lo, hi = paths.reshape(-1, 3).min(0), paths.reshape(-1, 3).max(0)
        centre = (lo + hi) / 2
        scale = _num(n0, "scale", 3.0 / max(float((hi - lo).max()) / 2, 1e-6))
        return (paths - centre) * scale + np.array([0, 0, 3.0]), starts

    @staticmethod
    def _starts(n) -> list:
        raw = n.attrs.get("starts", "").strip()
        try:
            starts = [[float(v) for v in s.split(",")] for s in raw.split(";") if s.strip()] if raw else [[10, 10, 10]]
        except ValueError:
            raise BeatError(f'<trajectory id={n.id}> starts="{raw}": "x,y,z; x,y,z"') from None
        if any(len(s) != 3 for s in starts):
            raise BeatError(f'<trajectory id={n.id}> starts="{raw}": three numbers each')
        count = int(_num(n, "count", 1))
        if count > 1 and len(starts) == 1:   # many starts a hair apart: watch them part ways
            eps = _num(n, "spread", 1e-3)
            starts = [[starts[0][0], starts[0][1], starts[0][2] + k * eps] for k in range(count)]
        if len(starts) > 40:
            raise BeatError(f"<trajectory id={n.id}>: at most 40 paths")
        return starts

    def state(self, node, old):
        t1 = _num(node, "t", 0)
        t0 = old["t1"] if old else 0.0   # this beat starts where the last one stopped
        return {"show": 1.0, "t": min(t0, t1), "t1": t1}

    def apply(self, st, fw):
        show = st["show"] if st else 0.0
        t = st["t"] if st else 0.0
        span = (self.paths.shape[1] - 1) * DT     # the time the full curves cover
        b = float(np.clip(t / span, 0, 1))
        a = float(np.clip((t - self.tail) / span, 0, b)) if self.tail else 0.0
        for full, curve, head in zip(self.full, self.curves, self.heads):
            curve.pointwise_become_partial(full, a, max(b, 1e-4))
            if self.tail:   # the tail fades toward its old end, like 3b1b's TracingTail
                curve.set_stroke(opacity=np.linspace(0, show, 16) ** 1.5)
            else:
                curve.set_stroke(opacity=show)
            head.move_to(curve.get_end())
            head.set_opacity(show)

    def view(self):
        pass

    def extent(self, st):
        p = self.paths.reshape(-1, 3)
        return [p.min(0).tolist(), p.max(0).tolist()] if st else []


# --- a slice through a height surface ----------------------------------------------------------------
class Slice:
    LIVE = ("at", "at1")

    def __init__(self, i, nodes, world):
        self.id = i
        n0 = nodes[0]
        th = current()
        self.world = world
        self.of = n0.attrs.get("of", "").strip()
        try:
            d = np.array([float(v) for v in n0.attrs.get("dir", "1,1").split(",")])
        except ValueError:
            raise BeatError(f'<slice id={i}> dir="{n0.attrs.get("dir")}": two numbers, the plane\'s normal') from None
        if len(d) != 2 or not np.linalg.norm(d):
            raise BeatError(f'<slice id={i}> dir="{n0.attrs.get("dir")}": two numbers, not both 0')
        self.n = d / np.linalg.norm(d)
        color = th.color(n0.attrs.get("color"), "accent")
        # the plane a faint pane with a thin edge; what it cuts out bright: the curve, and the
        # area under it filled (3b1b's diagonal slices)
        self.plane = VMobject().set_fill(th.ink, 0.05).set_stroke(th.ink, 1.2, 0.35)
        self.curtain = VMobject().set_fill(color, 0.55).set_stroke(width=0)
        self.cut = VMobject().set_stroke(color, 6)
        self.mob = Group(self.plane, self.curtain, self.cut)

    def surface(self):
        if self.of not in self.world.surfaces:
            raise BeatError(f'<slice id={self.id}> of="{self.of}" must name a <surface id> (a height z = f(x, y))')
        return self.world.surfaces[self.of]

    def state(self, node, old):
        at1 = _num(node, "at", 0)
        at0 = old["at1"] if old else at1   # first beat: no sweep; later beats sweep from the last place
        return {"show": 1.0, "at": at0, "at1": at1}

    def _segment(self, surf, at):
        """Where the line n·(x, y) = at crosses the surface's domain rectangle."""
        (x0, x1), (y0, y1) = surf.x, surf.y
        d = np.array([-self.n[1], self.n[0]])
        p0 = self.n * at
        ts = []
        for k, (lo, hi) in enumerate(((x0, x1), (y0, y1))):
            if abs(d[k]) > 1e-9:
                ts += [(lo - p0[k]) / d[k], (hi - p0[k]) / d[k]]
        inside = [t for t in ts if x0 - 1e-6 <= (p0 + t * d)[0] <= x1 + 1e-6 and y0 - 1e-6 <= (p0 + t * d)[1] <= y1 + 1e-6]
        if len(inside) < 2:
            return None
        return p0 + min(inside) * d, p0 + max(inside) * d

    def apply(self, st, fw):
        show = st["show"] if st else 0.0
        surf = self.surface()
        seg = self._segment(surf, st["at"]) if st else None
        if seg is None:
            for m in self.mob:
                m.set_opacity(0)
            return
        a, b = seg
        s = np.linspace(0, 1, 90)
        xy = a[None] + s[:, None] * (b - a)[None]
        curve = np.array([surf.world(x, y) for x, y in xy])
        floor = np.c_[xy, np.zeros(len(xy))]
        top = max(float(surf.zscale * surf.heights.max()), 0.5) * 1.1
        self.plane.set_points_as_corners([[*a, 0], [*b, 0], [*b, top], [*a, top], [*a, 0]])
        self.curtain.set_points_as_corners([*floor, *curve[::-1], floor[0]])
        self.cut.set_points_as_corners(curve + np.array([0, 0, 0.01]))
        self.plane.set_fill(opacity=0.05 * show).set_stroke(opacity=0.35 * show)
        self.curtain.set_fill(opacity=0.55 * show)
        self.cut.set_stroke(opacity=show)
        length = float(np.linalg.norm(b - a))
        f = np.array([surf.f(x, y) for x, y in xy])
        fw.values[f"{self.id}.area"] = float(trapezoid(f, dx=length / (len(f) - 1)))
        fw.values[f"{self.id}.at"] = float(st["at"])

    def view(self):
        pass

    def extent(self, st):
        return []


# --- waves from point sources -----------------------------------------------------------------------------
class Waves:
    LIVE = ("t", "t1")
    RES = 161
    MAX_SOURCES = 12

    def __init__(self, i, nodes, world):
        self.id = i
        n0 = nodes[0]
        th = current()
        self.size = _num(n0, "size", 8)
        self.lam = _num(n0, "wavelength", 1)
        if self.lam <= 0:
            raise BeatError(f'<waves id={i}> wavelength="{self.lam:g}": more than 0')
        self.decay = _num(n0, "decay", 0.5)
        self.lift = max(_num(n, "lift", 0) for n in nodes)   # the most any beat raises it (for framing)
        self.fns = list(dict.fromkeys(n.attrs.get("fn", "").strip() for n in nodes))   # "" = the sources
        self.funcs = [parse_expr(f, ("x", "y", "t")) if f else None for f in self.fns]
        self.n_src = max(len(self._sources(n)) for n in nodes)
        self.color = np.array(color_to_rgb(th.color(n0.attrs.get("color"), "c1") if n0.attrs.get("color") else th.palette[0]))
        self.bg = np.array(color_to_rgb(th.bg))
        self.hot = np.array(color_to_rgb(th.ink))
        half = self.size / 2
        self.surf = ParametricSurface(lambda u, v: np.array([u, v, 0.0]), u_range=(-half, half), v_range=(-half, half),
                                      resolution=(self.RES, self.RES))
        # flat: only the colour speaks; raised: light and shade show the crests (3b1b's surfaces)
        self.surf.set_shading(*((0.3, 0.2, 0) if any(_num(n, "lift", 0) for n in nodes) else (0.15, 0.1, 0)))
        self.xy = self.surf.data["point"][:, :2].copy()
        self.edge = Square(self.size).set_stroke(th.muted, 1.5, 0.6).set_fill(opacity=0)
        self.dots = Group(*(GlowDot(ORIGIN, radius=0.25, color=th.accent) for _ in range(self.n_src)))
        self.mob = Group(self.surf, self.edge, self.dots)

    def _sources(self, n) -> list:
        raw = n.attrs.get("sources", "0,0").strip()
        try:
            pts = [[float(v) for v in s.split(",")] for s in raw.split(";") if s.strip()]
        except ValueError:
            raise BeatError(f'<waves id={self.id}> sources="{raw}": "x,y; x,y"') from None
        if not pts or any(len(p) != 2 for p in pts):
            raise BeatError(f'<waves id={self.id}> sources="{raw}": two numbers each, "x,y; x,y"')
        if len(pts) > self.MAX_SOURCES:
            raise BeatError(f'<waves id={self.id}>: at most {self.MAX_SOURCES} sources')
        return pts

    def state(self, node, old):
        t1 = _num(node, "t", 0)
        t0 = old["t1"] if old else 0.0
        pts = self._sources(node)
        src = np.full((self.n_src, 3), np.nan)
        src[:len(pts), :2] = pts
        src[:len(pts), 2] = 1.0                         # third column: this source is on
        src[len(pts):] = [*pts[-1], 0.0]                # unused: sits on the last one, off
        intensity = 1.0 if node.attrs.get("show", "wave").strip() == "intensity" else 0.0
        fn = node.attrs.get("fn", "").strip()
        if fn:
            src[:, 2] = 0.0                             # a field of its own: no source dots
        return {"show": 1.0, "t": min(t0, t1), "t1": t1, "src": src, "intensity": intensity,
                "w": np.eye(len(self.fns))[self.fns.index(fn)],
                "lift": _num(node, "lift", 0)}

    def field(self, src, t):
        """Wave value at every floor point, -1 … 1, and how strongly each point shakes, 0 … 1."""
        k = 2 * math.pi / self.lam
        total = np.zeros(len(self.xy), complex)
        reach = np.zeros(len(self.xy))
        on = src[:, 2]
        for (x, y, w) in src:
            if w < 1e-3:
                continue
            d = np.hypot(self.xy[:, 0] - x, self.xy[:, 1] - y)
            front = np.clip((t - d) / (0.6 * self.lam) + 1, 0, 1)   # the ring has not got here yet
            amp = w * (d + 1) ** -self.decay * front
            total += amp * np.exp(1j * (k * d - k * t))
            reach = np.maximum(reach, front)
        norm = max(float(on.sum()), 1.0) ** 0.75
        value = total.real / norm
        strength = np.abs(total) / norm
        return np.clip(value, -1, 1), np.clip(strength, 0, 1)

    def apply(self, st, fw):
        show = st["show"] if st else 0.0
        if not st:
            self.surf.set_opacity(0)
            self.edge.set_stroke(opacity=0)
            self.dots.set_opacity(0)
            return
        value = strength = height = 0.0
        for wk, f in zip(st["w"], self.funcs):   # blend the beats' fields while one gives way
            if wk < 1e-6:
                continue
            if f is None:
                v, s_ = self.field(st["src"], st["t"])
            else:
                v = np.clip(np.broadcast_to(np.asarray(f(self.xy[:, 0], self.xy[:, 1], st["t"]), float), len(self.xy)), -1, 1)
                s_ = np.abs(v)
            value, strength = value + wk * v, strength + wk * s_
            # sources' sums are small a few units out: raised 2.5x so a ring stands ~lift high
            height = height + wk * (np.clip(2.5 * v, -1.5, 1.5) if f is None else v)
        mix = st["intensity"]
        b = (1 - mix) * (value + 1) / 2 + mix * strength ** 1.4
        # trough → background, still water → a dim tint, crest → the colour, then ink at the top
        dim = self.bg + 0.3 * (self.color - self.bg)
        lo, hi = np.clip(2 * b, 0, 1)[:, None], np.clip(2 * b - 1, 0, 1)[:, None]
        rgb = self.bg[None] + (dim - self.bg)[None] * lo + (self.color - dim)[None] * hi \
            + (self.hot - self.color)[None] * np.clip(2 * b - 1.6, 0, 1)[:, None] * 2.5
        rgba = np.c_[rgb, np.full(len(rgb), show)]
        self.surf.data["rgba"][:] = rgba
        z = st["lift"] * (1 - mix) * height
        pts = self.surf.data["point"]
        pts[:, 2] = z
        g = z.reshape(self.RES, self.RES)
        step = self.size / (self.RES - 1)
        dzu, dzv = np.gradient(g, step)
        self.surf.data["du_point"][:] = pts + np.c_[np.full(len(z), step), np.zeros(len(z)), dzu.ravel() * step]
        self.surf.data["dv_point"][:] = pts + np.c_[np.zeros(len(z)), np.full(len(z), step), dzv.ravel() * step]
        self.surf.note_changed_data()
        self.edge.set_stroke(opacity=0.6 * show)
        for dot, (x, y, w) in zip(self.dots, st["src"]):
            dot.move_to([x, y, 0.02 + 1.6 * st["lift"]])
            dot.set_opacity(show * float(np.clip(w, 0, 1)))
        fw.values[f"{self.id}.t"] = float(st["t"])

    def view(self):
        pass

    def extent(self, st):
        half = self.size / 2
        return [[-half, -half, -self.lift], [half, half, self.lift]] if st else []


# --- bodies under gravity ------------------------------------------------------------------------------------
ORBIT_SYSTEMS = {   # m, x,y,z, vx,vy,vz (G = 1)
    "figure8": "1, 0.97000436,-0.24308753,0, 0.466203685,0.43236573,0; "
               "1, -0.97000436,0.24308753,0, 0.466203685,0.43236573,0; "
               "1, 0,0,0, -0.93240737,-0.86473146,0",
    "planets": "40, 0,0,0, 0,0,0; 0.02, 1.2,0,0, 0,5.77,0.25; 0.05, 2.2,0,0, 0,4.26,-0.2; "
               "0.1, 3.4,0,0, 0,3.43,0.12",
    "binary": "10, -0.6,0,0, 0,-2.04,0; 10, 0.6,0,0, 0,2.04,0; 0.01, 3.2,0,0, 0,2.5,0.3",
    "three": "3, 1,3,0, 0,0,0; 4, -2,-1,0, 0,0,0; 5, 1,-1,0, 0,0,0",
    # light charges shot past a heavy one of the same sign: each swerves away, the nearer the more
    "charges": "200, 0,0,0, 0,0,0, 12; 1, -2.5,0.4,0, 2.2,0,0, 1; 1, -2.5,1.1,0, 2.2,0,0, 1; "
               "1, -2.5,2,0, 2.2,0,0, 1; 1, -2.5,-0.7,0, 2.2,0,0, 1",
    # four weights on springs in a ring, one kicked
    "springs": "1, 1,0,0, 0,0,0.6; 1, 0,1,0, 0,0,0; 1, -1,0,0, 0,0,0; 1, 0,-1,0, 1.5,0,0",
}
ORBIT_FORCES = {"charges": "charge", "springs": "spring"}
ORBIT_LINKS = {"springs": "0-1, 1-2, 2-3, 3-0, 0-2"}


class Orbits(Trajectory):
    """Bodies under each other's gravity: Trajectory's look (smooth curves, fading tails, glowing
    heads), paths from Newton's law. Fixed small steps with a little softening, so a close pass
    stays finite and every frame of a beat agrees."""

    def __init__(self, i, nodes, world):
        self.id = i
        n0 = nodes[0]
        th = current()
        self.links = []
        self.charges = None
        self.paths, self.masses = self._paths(i, n0, nodes)
        self.tail = _num(n0, "tail", 0)
        sizes = 1.1 + 1.1 * (self.masses / self.masses.max()) ** (1 / 3)
        cols = None
        if self.charges is not None and not n0.attrs.get("color"):   # + warm, - cool, 0 grey
            cols = [th.palette[2] if c > 0 else th.palette[0] if c < 0 else th.muted for c in self.charges]
        self._look(n0, len(self.masses), th, sizes=sizes, cols=cols)
        # springs drawn between the bodies they join
        self.springs = VGroup(*(Line(ORIGIN, RIGHT).set_stroke(th.muted, 2.5) for _ in self.links))
        self.springs.apply_depth_test()
        self.mob = Group(self.springs, self.curves, self.heads)

    def apply(self, st, fw):
        super().apply(st, fw)
        show = st["show"] if st else 0.0
        for line, (a, b) in zip(self.springs, self.links):
            p, q = self.heads[a].get_center(), self.heads[b].get_center()
            if np.linalg.norm(q - p) > 1e-6:
                line.put_start_and_end_on(p, q)
            line.set_stroke(opacity=0.7 * show)

    def _paths(self, i, n0, nodes):
        raw = n0.attrs.get("bodies", "").strip() or ORBIT_SYSTEMS.get(n0.attrs.get("system", "figure8").strip(), "")
        if not raw:
            raise BeatError(f'<orbits id={i}> system="{n0.attrs.get("system")}": use one of '
                            f'{", ".join(ORBIT_SYSTEMS)}, or bodies="m, x,y,z, vx,vy,vz; …"')
        try:
            rows = [[float(v) for v in b.split(",")] for b in raw.split(";") if b.strip()]
        except ValueError:
            raise BeatError(f'<orbits id={i}> bodies="{raw}": "m, x,y,z, vx,vy,vz" per body (a charge q 8th)') from None
        if not 1 <= len(rows) <= 12 or any(len(r) not in (7, 8) for r in rows) or any(r[0] <= 0 for r in rows):
            raise BeatError(f'<orbits id={i}> bodies: 1 to 12 bodies, each "m, x,y,z, vx,vy,vz" (+ charge q), m > 0')
        rows = np.array([r + [0.0] * (8 - len(r)) for r in rows])
        m, x, v, q = rows[:, 0], rows[:, 1:4].copy(), rows[:, 4:7].copy(), rows[:, 7]
        system = n0.attrs.get("system", "figure8").strip()
        forces = {f.strip() for f in n0.attrs.get("force", ORBIT_FORCES.get(system, "gravity")).split(",") if f.strip()}
        if not forces or forces - {"gravity", "charge", "spring"}:
            raise BeatError(f'<orbits id={i}> force="{n0.attrs.get("force")}": any of gravity, charge, spring')
        links = []
        if "spring" in forces:
            raw_links = n0.attrs.get("links", ORBIT_LINKS.get(system, ""))
            try:
                links = [tuple(int(k) for k in l.split("-")) for l in raw_links.split(",") if l.strip()]
            except ValueError:
                raise BeatError(f'<orbits id={i}> links="{raw_links}": pairs of body numbers from 0, "0-1, 1-2"') from None
            if not links or any(len(l) != 2 or not all(0 <= k < len(m) for k in l) for l in links):
                raise BeatError(f'<orbits id={i}> force="spring" needs links="0-1, 1-2" (body numbers from 0)')
        stiff = _num(n0, "stiffness", 8)
        self.links = links
        if "charge" in forces:
            self.charges = q
        rest = {l: float(np.linalg.norm(x[l[0]] - x[l[1]])) for l in links}
        x -= (m[:, None] * x).sum(0) / m.sum()   # watch from the centre of mass, which stays put
        v -= (m[:, None] * v).sum(0) / m.sum()
        t_max = max(_num(n, "t", 0) for n in nodes)
        steps = int(t_max / DT) + 2
        sub = 4
        h = DT / sub
        eps2 = 0.01 ** 2

        def acc(p):
            d = p[None, :, :] - p[:, None, :]          # d[i, j] = p_j - p_i
            r2 = (d ** 2).sum(-1) + eps2
            np.fill_diagonal(r2, np.inf)
            inv3 = r2[..., None] ** -1.5
            out = np.zeros_like(p)
            if "gravity" in forces:
                out += (m[None, :, None] * d * inv3).sum(1)
            if "charge" in forces:                    # like charges push apart
                out -= (q[:, None, None] * q[None, :, None] * d * inv3).sum(1) / m[:, None]
            for (a_, b_) in links:
                dv = p[b_] - p[a_]
                L = float(np.linalg.norm(dv)) or 1e-9
                f = stiff * (L - rest[(a_, b_)]) * dv / L
                out[a_] += f / m[a_]
                out[b_] -= f / m[b_]
            return out

        paths = np.empty((len(m), steps, 3))
        a = acc(x)
        for j in range(steps):   # velocity Verlet: energy stays put over many orbits
            paths[:, j] = x
            for _ in range(sub):
                v += 0.5 * h * a
                x += h * v
                a = acc(x)
                v += 0.5 * h * a
        lo, hi = paths.reshape(-1, 3).min(0), paths.reshape(-1, 3).max(0)
        # framed on where the bodies mostly are: one flung far away should not shrink the rest
        reach = float(np.percentile(np.abs(paths[..., :2]), 97))
        scale = _num(n0, "scale", 3.2 / max(reach, 1e-6))
        return paths * scale + np.array([0, 0, 1.0]), m

    def extent(self, st):   # the camera frames where they mostly are, as the scale does
        if not st:
            return []
        p = np.clip(self.paths.reshape(-1, 3), -3.4, 3.4 + 1.0)
        return [p.min(0).tolist(), p.max(0).tolist()]


# --- lines of a field, with flow passing along them ----------------------------------------------------
class Flow:
    """3b1b's stream lines (manimlib StreamLines + AnimatedStreamLines; his sphere scenes): each
    line is the path a point takes along the field for ``life`` seconds, drawn once as a smooth
    curve on the surface; what moves is only a soft swell of width passing along it
    (VShowPassingFlash), each line on its own delay. The points never move, so nothing shimmers."""
    LIVE = ("t", "t1")
    DT = 0.05
    RATE = 0.2          # his rate_multiple: a pulse takes life / RATE seconds to run along its line
    WIDTH = 2.4

    def __init__(self, i, nodes, world):
        from .solids import fibonacci_sphere
        from .theme import _blend

        self.id = i
        n0 = nodes[0]
        th = current()
        self.on = n0.attrs.get("on", "").strip() or None
        fn = n0.attrs.get("fn", "").strip()
        parts = [p.strip() for p in fn.split(";")]
        if len(parts) != 3:
            raise BeatError(f'<flow id={i}> fn="{fn}": three components "vx; vy; vz" in x, y, z')
        funcs = [parse_expr(p, ("x", "y", "z")) for p in parts]
        n = int(_num(n0, "count", 600))
        if not 20 <= n <= 4000:
            raise BeatError(f'<flow id={i}> count="{n}": 20 to 4000 lines')
        life = _num(n0, "life", 1)
        rng = np.random.default_rng(int(_num(n0, "seed", 3)))

        def field(p):
            return np.stack([np.broadcast_to(np.asarray(f(p[:, 0], p[:, 1], p[:, 2]), float), len(p)) for f in funcs], 1)

        host = world.actors.get(self.on) if self.on else None
        self.kind = "surface" if isinstance(host, Parametric) else "ball" if self.on else "plane"
        steps = max(3, int(life / self.DT))
        if self.kind == "surface":
            path, speed, normals = self._on_surface(host, field, n, steps, rng)
        else:
            normals = None

            def vel(p):
                v = field(p)
                if self.on:
                    v -= (v * p).sum(1, keepdims=True) * p     # along the surface only
                else:
                    v[:, 2] = 0
                return v

            if self.on:   # evenly over the ball, jittered a little so no rows show
                p = fibonacci_sphere(n) + rng.normal(0, 0.6 / math.sqrt(n), (n, 3))
                p /= np.linalg.norm(p, axis=1, keepdims=True)
            else:
                p = np.c_[rng.uniform(-3, 3, (n, 2)), np.zeros(n)]
            path = np.empty((steps + 1, n, 3))
            speed = np.empty((steps + 1, n))
            for j in range(steps + 1):   # RK2, as his ode_solution_points
                path[j] = p
                k1 = vel(p)
                speed[j] = np.linalg.norm(k1, axis=1)
                p = p + self.DT * vel(p + self.DT / 2 * k1)
                if self.on:
                    p /= np.linalg.norm(p, axis=1, keepdims=True)
        top = max(float(np.percentile(speed, 70)), 1e-9)
        slow = np.array(color_to_rgb(th.color(n0.attrs.get("color"), "c1")))
        fast = np.array(color_to_rgb(th.accent))
        # all lines in one mobject: each a smooth curve, joined by manimgl's break (its end repeated)
        mob = VMobject()
        chunks, xs, which, mags, nrm = [], [], [], [], []
        ball = self.kind == "ball"
        for k in range(n):
            line = VMobject().set_points_smoothly(path[:, k] * (1.01 if ball else 1.0))
            pts = line.get_points()
            if ball:   # the smooth fit bows a hair off the ball between samples: back onto it
                pts = pts / np.linalg.norm(pts, axis=1, keepdims=True) * 1.01
            chunks.append(pts)
            m = len(pts)
            xs.append(np.linspace(0, 1, m))
            which.append(np.full(m, k))
            at = np.linspace(0, steps, m)
            mags.append(np.interp(at, np.arange(steps + 1), speed[:, k]))
            if normals is not None:
                nrm.append(np.stack([np.interp(at, np.arange(steps + 1), normals[:, k, c]) for c in range(3)], 1))
            if k < n - 1:   # the break point
                chunks.append(pts[-1:])
                xs.append([1.0])
                which.append([k])
                mags.append([0.0])
                if normals is not None:
                    nrm.append(nrm[-1][-1:])
        self.normals = np.vstack(nrm) if normals is not None else None
        self.base = np.vstack(chunks)
        mob.set_points(self.base)
        self.xs, self.which = np.concatenate(xs), np.concatenate(which)
        sp = np.clip(np.concatenate(mags) / top, 0, 1)[:, None]
        rgba = np.empty((len(self.base), 4))
        rgba[:, :3] = slow[None] * (1 - sp) + fast[None] * sp
        rgba[:, 3] = 0.85
        self.rgba = rgba
        mob.data["stroke_rgba"][:] = rgba
        mob.set_stroke(width=0)
        if self.kind != "ball":
            mob.apply_depth_test()
        # on a ball the far side's lines are faded out by hand (facing, in apply), so the lines
        # need no depth test: tested against the ball, their ribbons fight its surface pixel by
        # pixel and sparkle from frame to frame. A general surface can hide parts of itself (a
        # torus's far side behind its near side), so there the lines keep the depth test and
        # sit further off the surface instead
        self.lines = mob
        self.run = life / self.RATE
        self.lag = rng.uniform(0, 4, n)        # his lag_range: lines start their pulses apart
        # taper both ends (his taper kernel), fixed per point
        self.taper = np.clip(np.minimum(self.xs, 1 - self.xs) / 0.05, 0, 1)
        if self.kind == "surface":   # the same backdrop on a surface: solid, dark, no mesh
            host.opacity, host.mesh_on = 1.0, False
            host.surf.set_color(_blend(th.bg, th.ink, 0.07)).set_shading(0.05, 0.05, 0.25)
        elif self.on and self.on in world.actors:
            # 3b1b's backdrop for lines on a ball: near black, matte, barely lit, so the lines
            # carry the picture and no glossy highlight washes them out
            body = getattr(world.actors[self.on], "body", world.mobs[self.on])
            body.set_color(_blend(th.bg, th.ink, 0.07)).set_shading(0.05, 0.05, 0.25)
        self.mob = Group(self.lines)

    def _on_surface(self, host, field, n, steps, rng):
        """Lines on a (u, v) surface: the field's part along the surface, followed in u, v (so a
        line stays on it), wrapping round where a range is a full turn. Seeds spread by area."""
        fx, fy, fz = (parse_expr(e, ("u", "v")) for e in host.keys[0])
        (u0, u1), (v0, v1) = host.u, host.v
        wrap = [abs((hi - lo) - 2 * math.pi) < 1e-6 for lo, hi in (host.u, host.v)]

        def P(uv):
            u, v = uv[:, 0], uv[:, 1]
            return np.stack([np.broadcast_to(np.asarray(f(u, v), float), len(u)) for f in (fx, fy, fz)], 1)

        def frame(uv):
            e = 1e-4
            pu = (P(uv + [e, 0]) - P(uv - [e, 0])) / (2 * e)
            pv = (P(uv + [0, e]) - P(uv - [0, e])) / (2 * e)
            return pu, pv

        def duv(uv):
            pu, pv = frame(uv)
            V = field(P(uv))
            g11, g12, g22 = (pu * pu).sum(1), (pu * pv).sum(1), (pv * pv).sum(1)
            b1, b2 = (pu * V).sum(1), (pv * V).sum(1)
            det = g11 * g22 - g12 * g12
            det = np.where(np.abs(det) < 1e-12, 1e-12, det)
            du, dv = (g22 * b1 - g12 * b2) / det, (g11 * b2 - g12 * b1) / det
            return np.c_[du, dv], np.linalg.norm(pu * du[:, None] + pv * dv[:, None], axis=1)

        def keep(uv):
            for k, (lo, hi) in enumerate((host.u, host.v)):
                uv[:, k] = lo + (uv[:, k] - lo) % (hi - lo) if wrap[k] else np.clip(uv[:, k], lo, hi)
            return uv

        cand = np.c_[rng.uniform(u0, u1, 8 * n), rng.uniform(v0, v1, 8 * n)]
        pu, pv = frame(cand)
        area = np.linalg.norm(np.cross(pu, pv), axis=1)
        uv = cand[rng.choice(len(cand), n, replace=False, p=area / area.sum())]
        lo, hi = P(cand).min(0), P(cand).max(0)
        lift = 0.02 * float((hi - lo).max())
        path = np.empty((steps + 1, n, 3))
        speed = np.empty((steps + 1, n))
        normals = np.empty((steps + 1, n, 3))
        for j in range(steps + 1):
            pu, pv = frame(uv)
            nr = np.cross(pu, pv)
            nr /= np.maximum(np.linalg.norm(nr, axis=1, keepdims=True), 1e-12)
            path[j] = P(uv) + lift * nr
            normals[j] = nr
            k1, speed[j] = duv(uv)
            k2, _ = duv(keep(uv + self.DT / 2 * k1))
            uv = keep(uv + self.DT * k2)
        return path, speed, normals

    def state(self, node, old):
        t1 = _num(node, "t", 0)
        t0 = old["t1"] if old else 0.0
        return {"show": 1.0, "t": min(t0, t1), "t1": t1}

    def apply(self, st, fw):
        show = st["show"] if st else 0.0
        t = st["t"] if st else 0.0
        pts = self.base
        R = np.eye(3)
        if self.kind == "surface":
            show *= float(np.clip((fw.state_of(self.on) - 0.6) / 0.4, 0, 1))
        elif self.on:
            host = fw.raw_state(self.on)
            if host:
                R = Rotation.from_euler("xyz", host["rot"], degrees=True).as_matrix()
                pts = (self.base * host["scale"]) @ R.T + host["at"]
                # through a ball still fading in, the far side's lines would show and flicker:
                # the lines come in once the ball is nearly solid
                show *= float(np.clip((fw.state_of(self.on) - 0.6) / 0.4, 0, 1))
            self.lines.set_points(pts)
        # the passing flash: a gaussian swell of width, 3 sigma = half the line, sliding from
        # before the line's start to past its end, then round again
        alpha = ((t + self.lag) % self.run) / self.run
        tw = 1.0
        mu = -tw / 2 + alpha * (1 + tw)
        z = (self.xs - mu[self.which]) / (tw / 6)
        swell = np.exp(-0.5 * z * z) * (np.abs(z) <= 3)
        # his VShowPassingFlash: the swell is in width (smooth under the scene's multisampling)
        self.lines.set_stroke(width=self.WIDTH * swell * self.taper)
        rgba = self.rgba.copy()
        rgba[:, 3] *= show
        if self.kind == "surface" and fw.frame is not None:   # edge-on parts fade (either side)
            eye = fw.frame.get_implied_camera_location()
            to_eye = eye[None] - self.base
            to_eye /= np.linalg.norm(to_eye, axis=1, keepdims=True)
            facing = np.abs((self.normals * to_eye).sum(1))
            rgba[:, 3] *= np.clip((facing - 0.1) / 0.35, 0, 1)
        elif self.on and fw.frame is not None:
            # lines seen edge-on near the outline stack into a bright ring: fade them out there
            host = fw.raw_state(self.on)
            eye = fw.frame.get_implied_camera_location() - (host["at"] if host else 0)
            facing = (self.base @ R.T) @ (eye / np.linalg.norm(eye)) / 1.01
            rgba[:, 3] *= np.clip((facing - 0.2) / 0.5, 0, 1) ** 2
        self.lines.data["stroke_rgba"][:] = rgba
        self.lines.note_changed_data()

    def view(self):
        pass

    def extent(self, st):
        return [] if self.on or not st else [[-3, -3, 0], [3, 3, 0]]


CLASSES = {"parametric": Parametric, "trajectory": Trajectory, "slice": Slice, "waves": Waves,
           "orbits": Orbits, "particles": Orbits, "flow": Flow}
