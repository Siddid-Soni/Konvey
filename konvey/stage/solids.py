"""General lit 3D actors for ``<world>`` (spec §4.3), driven by :class:`~.field.FieldWorld`.

- ``<sphere id r="1" at="x,y,z" color opacity edges>`` and
  ``<solid id shape="box|cylinder|cone|prism|pyramid|tetrahedron|octahedron|dodecahedron|icosahedron"
  size="w,d,h" | r h sides  at rot="x,y,z" color opacity edges vertices>``: matte solids in the
  theme material, flat-faced ones with crisp edges (``edges="false"`` hides them; on curved
  solids ``edges="true"`` draws a light mesh), ``vertices="true"`` marks the corners. Without
  ``at`` a solid rests on the floor.
  Changing ``at``/``r``/``size``/``rot`` between beats animates it.
  ``shape="hull" points="x,y,z; …"``: the convex solid with exactly these corners (an oblique
  pyramid, a wedge, a dissection piece); ``at`` shifts it, ``rot`` turns it about its centre.
  Same number of corners in a later beat: the corners slide and the solid reshapes.
- ``<light id dir="x,y,z">``: direction the light travels (default straight down).
- ``<shadow id of="solidId">``: the solid's true shadow on the floor along the light,
  recomputed every frame. ``<id>.area`` is its area.
- ``<field id on="sphereId" fn="-y; x; 0" density="300">``: tangent vector field on a
  sphere (fn gives the 3D vector at x, y, z; it is projected onto the tangent plane), or
  on the floor without ``on`` (fn gives ``vx; vy`` in x, y over ``x``/``y``). Arrow length
  follows the magnitude; zeros are marked. Changing ``fn`` morphs the arrows.
  ``<id>.zeros`` is the number of zeros found.
- ``<label3d id at="x,y,z" | of="solidId" text="…" color size>``: text pinned to a 3D
  point (or above a solid), always facing the camera at a constant size.
"""

from __future__ import annotations

import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

from manimlib import *  # noqa: F401,F403

from .parse import BeatError, Node
from .theme import current

SOLID_TAGS = {"sphere", "solid", "light", "shadow", "field", "label3d", "line3d", "angle3d", "face3d"}
SOLID_ATTRS = {
    "sphere": {"id", "r", "at", "rot", "color", "opacity", "edges"},
    "solid": {"id", "shape", "size", "r", "h", "sides", "at", "rot", "color", "opacity", "edges", "vertices",
              "points"},
    "light": {"id", "dir"},
    "shadow": {"id", "of"},
    "field": {"id", "on", "fn", "density", "color", "x", "y"},
    "label3d": {"id", "at", "of", "text", "color", "size"},
    "line3d": {"id", "from", "to", "color", "arrow", "width", "on", "label"},
    "angle3d": {"id", "at", "from", "to", "r", "color"},
    "face3d": {"id", "points", "color", "opacity", "label"},
}
SHAPES = ("box", "cylinder", "cone", "prism", "pyramid",
          "tetrahedron", "octahedron", "dodecahedron", "icosahedron", "hull")
FLAT = ("box", "prism", "pyramid", "tetrahedron", "octahedron", "dodecahedron", "icosahedron", "hull")
ROUND = ("tetrahedron", "octahedron", "dodecahedron", "icosahedron")   # sized by r, like a sphere
ORDER = {"sphere": 0, "solid": 0, "light": 1, "shadow": 2, "field": 2, "line3d": 2, "angle3d": 2,
         "face3d": 1, "label3d": 3}


SEE_THROUGH_GROW = 1.012


def vec(node: Node, key: str, default: str, n: int = 3) -> np.ndarray:
    raw = node.attrs.get(key, default)
    try:
        v = np.array([float(x) for x in raw.replace(";", ",").split(",")], float)
    except ValueError as e:
        raise BeatError(f'<{node.tag} id={node.id}> {key}="{raw}": use {n} numbers like "{default}"') from e
    if len(v) != n:
        raise BeatError(f'<{node.tag} id={node.id}> {key}="{raw}": needs {n} numbers')
    return v


def _num(node: Node, key: str, default: float) -> float:
    try:
        return float(node.attrs.get(key, default))
    except ValueError as e:
        raise BeatError(f'<{node.tag} id={node.id}> {key}="{node.attrs[key]}" is not a number') from e


class Placed:
    """A mobject built once at unit size; each frame its points are re-placed with
    p -> R (p * scale) + at, so position, size and rotation interpolate exactly."""

    def __init__(self, mob: Mobject):
        self.mob = mob
        self.parts = [m for m in mob.get_family() if m.has_points()]
        self.keys = [[k for k in ("point", "du_point", "dv_point") if k in m.data.dtype.names]
                     for m in self.parts]
        self.base = [{k: m.data[k].copy() for k in ks} for m, ks in zip(self.parts, self.keys)]

    def place(self, at, scale, rot_deg, base=None):
        R = Rotation.from_euler("xyz", rot_deg, degrees=True).as_matrix()
        for m, ks, b in zip(self.parts, self.keys, base or self.base):
            for k in ks:
                m.data[k][:] = (b[k] * scale) @ R.T + at
            if isinstance(m, VMobject):   # cached face normals / joints follow the new points
                m.needs_new_unit_normal = True
                m.needs_new_joint_angles = True
            m.note_changed_data()

    def points(self) -> np.ndarray:
        return np.vstack([m.data["point"] for m in self.parts])


# --- solids --------------------------------------------------------------------
def _flag(node: Node, key: str, default: bool) -> bool:
    return node.attrs.get(key, "true" if default else "false").strip().lower() in ("true", "1", "yes")


def _unit_vertices(shape: str, sides: int) -> np.ndarray:
    """Corners at unit size: platonic solids on the unit sphere, rotated so a face rests flat;
    a prism/pyramid with an n-gon base of radius 1 between z = -1 and z = 1."""
    g = (1 + 5 ** 0.5) / 2
    ring = np.c_[np.cos(np.arange(sides) * TAU / sides + PI / 2),
                 np.sin(np.arange(sides) * TAU / sides + PI / 2)]
    if shape == "prism":
        return np.r_[np.c_[ring, -np.ones(sides)], np.c_[ring, np.ones(sides)]]
    if shape == "pyramid":
        return np.r_[np.c_[ring, -np.ones(sides)], [[0.0, 0.0, 1.0]]]
    if shape == "box":
        return np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], float)

    def cyc(v):
        return [v, [v[1], v[2], v[0]], [v[2], v[0], v[1]]]
    if shape == "tetrahedron":
        v = np.array([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]], float)
    elif shape == "octahedron":
        v = np.array([[s * (i == k) for k in range(3)] for i in range(3) for s in (1, -1)], float)
    elif shape == "icosahedron":
        v = np.array([p for a in (1, -1) for b in (g, -g) for p in cyc([0, a, b])], float)
    else:   # dodecahedron
        v = np.array([[x, y, z] for x in (1, -1) for y in (1, -1) for z in (1, -1)]
                     + [p for a in (1 / g, -1 / g) for b in (g, -g) for p in cyc([0, a, b])], float)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    faces = _faces(v)
    n = np.cross(v[faces[0][1]] - v[faces[0][0]], v[faces[0][2]] - v[faces[0][0]])
    n /= np.linalg.norm(n)
    if n @ v[faces[0]].mean(axis=0) < 0:
        n = -n
    R, _ = Rotation.align_vectors([[0, 0, -1]], [n])   # that face down, flat on the floor
    return R.apply(v)


def _faces(v: np.ndarray) -> list[list[int]]:
    """Convex hull faces as vertex index loops (coplanar triangles merged, counter-clockwise)."""
    hull = ConvexHull(v)
    groups: dict[tuple, set[int]] = {}
    for simplex, eq in zip(hull.simplices, hull.equations):
        groups.setdefault(tuple(np.round(eq, 4)), set()).update(int(k) for k in simplex)
    faces = []
    for eq, idx in groups.items():
        idx = list(idx)
        n = np.array(eq[:3])
        c = v[idx].mean(axis=0)
        a = v[idx[0]] - c
        b = np.cross(n, a)
        ang = [np.arctan2((v[k] - c) @ b, (v[k] - c) @ a) for k in idx]
        faces.append([idx[k] for k in np.argsort(ang)])
    return faces


def _sphere_mesh(meridians: int = 16, rings: int = 7) -> VGroup:
    """Meridians stop short of the poles (all of them meeting there make a dark blob)."""
    r = 1.006
    polar = np.linspace(0.07 * PI, 0.93 * PI, 40)
    mesh = VGroup()
    for k in range(meridians):
        a = k * TAU / meridians
        mesh.add(VMobject().set_points_smoothly(
            r * np.c_[np.sin(polar) * np.cos(a), np.sin(polar) * np.sin(a), np.cos(polar)]))
    az = np.linspace(0, TAU, 73)
    for k in range(1, rings + 1):
        t = k * PI / (rings + 1)
        mesh.add(VMobject().set_points_smoothly(
            r * np.c_[np.sin(t) * np.cos(az), np.sin(t) * np.sin(az), np.full_like(az, np.cos(t))]))
    return mesh


def _face_surface(loop: np.ndarray) -> Surface:
    """A flat polygon as a Surface (VMobject fills skip the depth test in manimgl, so faces
    behind would show through): u runs from the centre out, v once around the corners
    (counter-clockwise seen from outside, so the normal points out)."""
    k = len(loop)
    c = loop.mean(axis=0)

    def f(u, v):
        t = min(v * k, k - 1e-9)
        i = int(t)
        b = loop[i] + (t - i) * (loop[(i + 1) % k] - loop[i])
        return c + u * (b - c)

    surf = ParametricSurface(f, u_range=(0, 1), v_range=(0, 1), resolution=(2, 4 * k + 1))
    # A flat face has one exact normal. manimgl estimates it per vertex from neighbouring
    # points, which degenerates at the centre and along the seam (a bright star on every face),
    # so set the two tangent points directly: (du - p) x (dv - p) is the outward normal.
    e1 = loop[0] - c
    e1 /= np.linalg.norm(e1)
    n = np.cross(loop[1] - loop[0], loop[2] - loop[1])
    n /= np.linalg.norm(n)
    e2 = np.cross(n, e1)
    surf.data["du_point"][:] = surf.data["point"] + 1e-3 * e1
    surf.data["dv_point"][:] = surf.data["point"] + 1e-3 * e2
    return surf


class Solid:
    def __init__(self, i: str, nodes: list[Node], world):
        th = current()
        n0 = nodes[0]
        self.id = i
        self.shape = "sphere" if n0.tag == "sphere" else n0.attrs.get("shape", "box")
        shapes = sorted({"sphere" if n.tag == "sphere" else n.attrs.get("shape", "box") for n in nodes})
        if len(shapes) > 1:
            raise BeatError(f'<solid id={i}> is a {" in one beat and a ".join(shapes)} in another: one id is '
                            "one body; give a different shape its own id")
        if self.shape not in ("sphere", *SHAPES):
            raise BeatError(f'<solid id={i}> shape="{self.shape}": use one of {", ".join(SHAPES)} '
                            f"(or <sphere>)")
        sides = int(_num(n0, "sides", 6))
        if self.shape in ("prism", "pyramid") and not 3 <= sides <= 12:
            raise BeatError(f'<solid id={i}> sides="{sides}": use 3 to 12')
        color = th.color(n0.attrs.get("color")) if "color" in n0.attrs else th.solid
        self.color = color
        self.zlow = 1.0          # unit-size distance from centre down to the floor contact
        self.edges = VGroup()
        self.corners = Group()
        if self.shape == "hull":
            counts = {len(hull_points(n)) for n in nodes if "points" in n.attrs}
            if "points" not in n0.attrs:
                raise BeatError(f'<solid id={i} shape="hull"> needs points="x,y,z; x,y,z; …" '
                                "(its corners) the first time it appears")
            if len(counts) != 1:
                raise BeatError(f'<solid id={i} shape="hull">: keep the same number of corners in every '
                                "beat (they slide to their new places); use a new id for a different shape")
            self.show_edges, self.show_vertices = _flag(n0, "edges", True), _flag(n0, "vertices", False)
            self.body = Group()
            self.mob = Group(self.body, self.edges, self.corners)
            self._built = None     # corner positions the faces were last built for
            self.placed = None
            self._build_hull(hull_points(n0))   # shadows/audit read body points before it shows
            return
        if self.shape in FLAT:
            v = _unit_vertices(self.shape, sides)
            self.zlow = -float(v[:, 2].min())
            loops = _faces(v)
            body = Group(*(_face_surface(v[f]) for f in loops))
            body.set_color(color).set_shading(*th.solid_shading)
            pairs = {tuple(sorted((f[k], f[(k + 1) % len(f)]))) for f in loops for k in range(len(f))}
            if _flag(n0, "edges", True):
                # nudged out a hair so the depth test never hides an edge in its own faces
                self.edges = VGroup(*(Line(1.01 * v[a], 1.01 * v[b]) for a, b in sorted(pairs)))
            if _flag(n0, "vertices", False):
                self.corners = Group(*(Sphere(radius=0.045, resolution=(12, 6)).move_to(1.004 * p) for p in v))
                self.corners.set_color(th.accent).set_shading(*th.solid_shading)
            self._outline = v
        else:
            if self.shape == "sphere":
                body = Sphere(radius=1, resolution=(48, 24))
            elif self.shape == "cylinder":
                body = Group(Cylinder(radius=1, height=2, resolution=(48, 4)),
                             Disk3D(radius=1, resolution=(2, 48)).shift(OUT),
                             Disk3D(radius=1, resolution=(2, 48)).shift(IN))
            else:
                cone = Cone(radius=1, height=2, resolution=(48, 8))
                cone.stretch_to_fit_depth(2).move_to(ORIGIN)
                body = Group(cone, Disk3D(radius=1, resolution=(2, 48)).shift(IN))
            body.set_color(color).set_shading(*th.solid_shading)
            if _flag(n0, "edges", False):   # curved: a light mesh of meridians and rings
                if self.shape == "sphere":
                    self.edges = _sphere_mesh()
                else:
                    self.edges = SurfaceMesh(body[0], resolution=(25, 5), normal_nudge=0.006)
            self._outline = _OUTLINE[self.shape]
        self.edges.set_stroke(th.mesh, 2.2 if self.shape in FLAT else 1.2)
        self.edges.apply_depth_test()
        self.body = body
        self.mob = Group(body, self.edges, self.corners)
        self.placed = Placed(self.mob)

    def body_points(self) -> np.ndarray:
        """Surface points of the solid itself (not its edge lines, which sit a hair outside)."""
        return np.vstack([m.data["point"] for m in self.body.get_family() if m.has_points()])

    def half(self, node: Node, prev) -> np.ndarray:
        if self.shape == "hull":
            return prev if prev is not None else np.ones(3)
        if self.shape in ("sphere", *ROUND):
            r = _num(node, "r", prev[0] if prev is not None else 1.0)
            return np.array([r, r, r])
        if self.shape == "box":
            raw = node.attrs.get("size", "").replace(";", ",").split(",")
            if len(raw) == 1 and raw[0].strip():   # one number: a cube of that side
                return np.full(3, _num(node, "size", 2.0) / 2)
            if "size" in node.attrs or prev is None:
                return vec(node, "size", "2,2,2") / 2
            return prev
        r = _num(node, "r", prev[0] if prev is not None else 1.0)
        h = _num(node, "h", 2 * prev[2] if prev is not None else 2.0)
        return np.array([r, r, h / 2])

    def state(self, node: Node, old: dict | None) -> dict:
        if self.shape == "hull":
            return self._hull_state(node, old)
        half = self.half(node, old["scale"] if old else None)
        if "at" in node.attrs:
            at = vec(node, "at", "0,0,1")
        elif old is not None:
            at = old["at"]
        else:
            at = np.array([0.0, 0.0, self.zlow * half[2]])   # resting on the floor
        rot = vec(node, "rot", "0,0,0") if "rot" in node.attrs else (old["rot"] if old else np.zeros(3))
        op = _num(node, "opacity", 1.0) if "opacity" in node.attrs else (old["opacity"] if old else 1.0)
        return {"show": 1.0, "at": at, "scale": half, "rot": rot, "opacity": op}

    def apply(self, st: dict, fw):
        show = st["show"] if st else 0.0
        op = st["opacity"] if st else 1.0
        # A see-through solid is a container: pieces drawn flush inside it (pyramids filling a
        # cube) share its faces, and coplanar faces z-fight into a marbled mess. Grown by a
        # hair, its faces always lie just outside them.
        grow = SEE_THROUGH_GROW if op < 0.95 else 1.0
        if st and self.shape == "hull":
            v = self.hull_world(st)
            c = v.mean(axis=0)
            self._build_hull(c + (v - c) * grow)
        elif st:
            self.placed.place(st["at"], np.asarray(st["scale"]) * grow, st["rot"])
        self.body.set_opacity(op * show)
        self.corners.set_opacity(show)
        # While it is see-through (glass, or fading in or out) its far side must be drawn first,
        # or the back faces land over the front ones as a light crescent that shifts frame to
        # frame (3b1b: surface.always_sort_to_camera)
        if op * show < 0.999 and fw.frame is not None:
            eye = fw.frame.get_implied_camera_location()
            for m in self.body.get_family():
                if isinstance(m, Surface) and m.has_points():
                    m.sort_faces_back_to_front(eye - m.get_center())
        # A faded-out surface is still drawn and still writes depth: an invisible solid would
        # hide whatever later stands in its place (a hidden piece where a new one appears).
        hidden = op * show < 1e-3
        if hidden != getattr(self, "_hidden", False):
            self._hidden = hidden
            for m in (self.body, self.corners):
                (m.deactivate_depth_test if hidden else m.apply_depth_test)()
        # Edges of a see-through solid show all the way round (a wireframe in glass); an
        # opaque solid hides its back edges.
        see_through = op < 0.95
        if see_through != getattr(self, "_see_through", None):
            self._see_through = see_through
            (self.edges.deactivate_depth_test if see_through else self.edges.apply_depth_test)()
        self.edges.set_stroke(opacity=min(1.0, 0.35 + op) * show * (0.55 if self.shape not in FLAT else 1))

    def extent(self, st) -> list:
        """Points on the solid's own outline (not its bounding box: seen at an angle a sphere's
        box projects ~1.8x wider than the sphere, and auto-framing then leaves it small)."""
        if self.shape == "hull":
            pts = self.hull_world(st)
            c = pts.mean(axis=0)
            pts = c + 1.05 * (pts - c)
        else:
            R = Rotation.from_euler("xyz", st["rot"], degrees=True).as_matrix()
            pts = (self._outline * st["scale"] * 1.05) @ R.T + st["at"]
        if current().floor == "plane":   # an opaque floor hides what is below it
            pts[:, 2] = np.maximum(pts[:, 2], 0)
        return pts.tolist()


    # --- shape="hull": a convex solid given by its corners ------------------------------
    def _hull_state(self, node: Node, old: dict | None) -> dict:
        """``pts``: the corners as written; ``at``/``scale`` (centre and half-extent, as other
        solids have) let line3d, label3d and shadows treat it like any solid."""
        pts = hull_points(node) if "points" in node.attrs else old["pts"]
        shift = vec(node, "at", "0,0,0") if "at" in node.attrs else (old["shift"] if old else np.zeros(3))
        rot = vec(node, "rot", "0,0,0") if "rot" in node.attrs else (old["rot"] if old else np.zeros(3))
        op = _num(node, "opacity", 1.0) if "opacity" in node.attrs else (old["opacity"] if old else 1.0)
        try:
            ConvexHull(pts)
        except Exception as e:  # noqa: BLE001 - qhull raises its own error types
            raise BeatError(f'<solid id={node.id} shape="hull"> points are flat (all in one plane) or '
                            "repeated, so they enclose no solid; a flat region is a <face3d>") from e
        st = {"show": 1.0, "pts": pts, "shift": shift, "rot": rot, "opacity": op}
        world = self.hull_world(st)
        st["at"] = world.mean(axis=0)
        st["scale"] = np.abs(world - st["at"]).max(axis=0)
        return st

    @staticmethod
    def hull_world(st: dict) -> np.ndarray:
        pts = np.asarray(st["pts"], float)
        c = pts.mean(axis=0)
        R = Rotation.from_euler("xyz", st["rot"], degrees=True).as_matrix()
        return (pts - c) @ R.T + c + st["shift"]

    def _build_hull(self, v: np.ndarray):
        """Faces, edges and corners rebuilt whenever the corners move (a hull's faces can change
        as corners slide, so nothing is reused); skipped while it holds still."""
        if self._built is not None and np.allclose(self._built, v, atol=1e-6):
            return
        try:
            loops = _faces(v)
        except Exception:  # noqa: BLE001 - corners passing through a flat moment mid-morph
            return
        self._built = v.copy()
        th = current()
        c = v.mean(axis=0)
        body = [_face_surface(v[f]) for f in loops]
        for f in body:
            f.set_color(self.color).set_shading(*th.solid_shading)
        self.body.set_submobjects(body)
        if self.show_edges:
            pairs = {tuple(sorted((f[k], f[(k + 1) % len(f)]))) for f in loops for k in range(len(f))}
            out = lambda p: c + (p - c) * 1.01 + 0.004 * (p - c) / (np.linalg.norm(p - c) or 1)  # noqa: E731
            edges = [Line(out(v[a]), out(v[b])) for a, b in sorted(pairs)]
            self.edges.set_submobjects(edges)
            self.edges.set_stroke(th.mesh, 2.2)
            (self.edges.deactivate_depth_test if getattr(self, "_see_through", False)
             else self.edges.apply_depth_test)()
        if self.show_vertices:
            used = sorted({k for f in loops for k in f})
            dots = [Sphere(radius=0.045, resolution=(12, 6)).move_to(v[k] + 0.004 * (v[k] - c)) for k in used]
            for d in dots:
                d.set_color(th.accent).set_shading(*th.solid_shading)
            self.corners.set_submobjects(dots)

    def hull_edges(self, st: dict) -> list[tuple[np.ndarray, np.ndarray]]:
        v = self.hull_world(st)
        loops = _faces(v)
        pairs = {tuple(sorted((f[k], f[(k + 1) % len(f)]))) for f in loops for k in range(len(f))}
        return [(v[a], v[b]) for a, b in sorted(pairs)]


def hull_points(node: Node) -> np.ndarray:
    raw = node.attrs.get("points", "").strip()
    try:
        rows = []
        for c in (c.strip() for c in raw.split(";") if c.strip()):
            xyz, _, times = c.partition("*")       # "1,1,2*3": that corner three times
            rows += [[float(x) for x in xyz.split(",")]] * (int(times) if times.strip() else 1)
        pts = np.array(rows)
    except ValueError:
        pts = np.zeros((0, 0))
    if pts.ndim != 2 or pts.shape[1] != 3 or len(pts) < 4:
        raise BeatError(f'<solid id={node.id} shape="hull"> points="{raw}": give 4 or more corners '
                        '"x,y,z; x,y,z; x,y,z; x,y,z"')
    return pts


_RING = np.c_[np.cos(np.linspace(0, 2 * np.pi, 24, endpoint=False)),
              np.sin(np.linspace(0, 2 * np.pi, 24, endpoint=False))]
# Unit outlines (solid scale 1 = half-size 1) used for camera framing.
_OUTLINE = {
    "sphere": None,  # filled in below, once fibonacci_sphere is defined
    "box": np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], float),
    "cylinder": np.r_[np.c_[_RING, -np.ones(24)], np.c_[_RING, np.ones(24)]],
    "cone": np.r_[np.c_[_RING, -np.ones(24)], [[0.0, 0.0, 1.0]]],
}


# --- light + shadow ---------------------------------------------------------------
class Light:
    def __init__(self, i, nodes, world):
        self.mob = Group()

    def state(self, node, old):
        d = vec(node, "dir", "0,0,-1")
        if d[2] >= -1e-6:
            raise BeatError(f'<light id={node.id}> dir="{node.attrs["dir"]}": the light must travel '
                            f"downward (negative z), e.g. \"1,0,-2\"")
        return {"show": 1.0, "dir": d / np.linalg.norm(d)}

    def apply(self, st, fw):
        pass

    def extent(self, st):
        return []


class Shadow:
    def __init__(self, i, nodes, world):
        th = current()
        self.id = i
        self.of = nodes[0].attrs.get("of", "")
        self.mob = VMobject(fill_color=th.shadow_fill, fill_opacity=0.9,
                            stroke_color=th.accent, stroke_width=2)

    def state(self, node, old):
        return {"show": 1.0}

    def apply(self, st, fw):
        show = st["show"] if st else 0.0
        solid = fw.actors[self.of]
        d = fw.light_dir()
        pts = solid.body_points()
        flat = pts[:, :2] - (pts[:, 2:3] / d[2]) * d[:2]
        hull = ConvexHull(flat)
        outline = flat[hull.vertices]
        fw.values[f"{self.id}.area"] = float(hull.volume)
        ring = np.c_[outline, np.full(len(outline), 0.01)]
        self.mob.set_points_as_corners([*ring, ring[0]])
        solid_show = fw.state_of(self.of)
        self.mob.set_fill(opacity=0.9 * show * solid_show).set_stroke(opacity=show * solid_show)

    def extent(self, st):
        return []


# --- vector field ----------------------------------------------------------------
def fibonacci_sphere(n: int) -> np.ndarray:
    k = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * k / n)
    theta = np.pi * (1 + 5 ** 0.5) * k
    return np.c_[np.cos(theta) * np.sin(phi), np.sin(theta) * np.sin(phi), np.cos(phi)]


_OUTLINE["sphere"] = fibonacci_sphere(64)


class VectorField:
    def __init__(self, i: str, nodes: list[Node], world):
        from .expr import parse_expr

        th = current()
        self.id = i
        n0 = nodes[0]
        self.on = n0.attrs.get("on")
        self.fns = list(dict.fromkeys(n.attrs.get("fn", "") for n in nodes))
        if not all(self.fns):
            raise BeatError(f"<field id={i}> needs fn=")
        dims = 3 if self.on else 2
        names = ("x", "y", "z") if self.on else ("x", "y")
        self.funcs = []
        for fn in self.fns:
            parts = [p.strip() for p in fn.split(";")]
            if len(parts) != dims:
                raise BeatError(f'<field id={i}> fn="{fn}": needs {dims} components separated by ";" '
                                f'({"vx; vy; vz in x, y, z" if self.on else "vx; vy in x, y"})')
            self.funcs.append([parse_expr(p, names) for p in parts])
        # Fewer than ~80 arrows reads as scattered scribbles, not a field.
        density = max(80, int(_num(n0, "density", 160 if self.on else 144)))
        if self.on:
            self.base = fibonacci_sphere(density) * 1.02
            fine = fibonacci_sphere(6000)
            self.normal = lambda p: p / np.linalg.norm(p, axis=1, keepdims=True)
            self.spacing = 2.4 / np.sqrt(density)
        else:
            from .field import _pair

            (x0, x1), (y0, y1) = _pair(n0, "x", "-3,3"), _pair(n0, "y", "-3,3")
            k = max(2, int(round(np.sqrt(density))))
            gx, gy = np.meshgrid(np.linspace(x0, x1, k), np.linspace(y0, y1, k))
            self.base = np.c_[gx.ravel(), gy.ravel(), np.full(k * k, 0.02)]
            fx, fy = np.meshgrid(np.linspace(x0, x1, 120), np.linspace(y0, y1, 120))
            fine = np.c_[fx.ravel(), fy.ravel(), np.zeros(fx.size)]
            self.normal = lambda p: np.tile([0.0, 0.0, 1.0], (len(p), 1))
            self.spacing = max(x1 - x0, y1 - y0) / k
        color = th.color(n0.attrs.get("color"), "muted")
        self.paths = [self._arrows(f) for f in self.funcs]
        self.arrows = VMobject().set_stroke(color, 3)
        self.arrows.set_points(self.paths[0])
        self.arrows.apply_depth_test()
        self.zeros = [self._zeros(f, fine) for f in self.funcs]
        self.markers = Group(*(Group(*(Sphere(radius=0.1, resolution=(16, 8)).move_to(z * 1.04)
                                         .set_color(th.accent) for z in zs)) for zs in self.zeros))
        self.mob = Group(self.arrows, self.markers)
        self.arrow_placed = None
        self.marker_placed = Placed(self.markers) if self.on else None

    def _vectors(self, funcs, p: np.ndarray) -> np.ndarray:
        args = (p[:, 0], p[:, 1], p[:, 2]) if self.on else (p[:, 0], p[:, 1])
        v = np.stack([np.broadcast_to(np.asarray(f(*args), float), len(p)) for f in funcs], axis=1)
        if not self.on:
            v = np.c_[v, np.zeros(len(p))]
        nrm = self.normal(p)
        return v - np.sum(v * nrm, axis=1, keepdims=True) * nrm   # tangent part

    def _arrows(self, funcs) -> np.ndarray:
        """All arrows of one fn as one path: shaft then a two-stroke head, per arrow."""
        p = self.base
        v = self._vectors(funcs, p)
        mag = np.linalg.norm(v, axis=1)
        top = mag.max() or 1.0
        length = 1.1 * self.spacing * mag / top
        t = np.where(mag[:, None] > 1e-9, v / np.maximum(mag, 1e-9)[:, None], 0)
        side = np.cross(self.normal(p), t)
        tip = p + t * length[:, None]
        back = tip - 0.35 * t * length[:, None]
        h1, h2 = back + 0.22 * side * length[:, None], back - 0.22 * side * length[:, None]
        mob = VMobject()
        for a, b, c, d in zip(p, tip, h1, h2):
            mob.start_new_path(a)
            mob.add_line_to(b)
            mob.start_new_path(c)
            mob.add_line_to(b)
            mob.add_line_to(d)
        return mob.get_points().copy()

    def _zeros(self, funcs, fine: np.ndarray) -> list[np.ndarray]:
        mag = np.linalg.norm(self._vectors(funcs, fine), axis=1)
        top = mag.max() or 1.0
        cands = fine[np.argsort(mag)]
        cands = cands[np.sort(mag) < 0.03 * top]
        found: list[np.ndarray] = []
        for c in cands:   # greedy clustering: strongest zero first
            if all(np.linalg.norm(c - f) > 0.35 * (1 if self.on else self.spacing * 3) for f in found):
                found.append(c)
            if len(found) >= 12:
                break
        return found

    def state(self, node, old):
        return {"show": 1.0, "w": np.eye(len(self.fns))[self.fns.index(node.attrs["fn"])]}

    def apply(self, st, fw):
        show = st["show"] if st else 0.0
        w = st["w"] if st else np.eye(len(self.fns))[0]
        pts = sum(wk * p for wk, p in zip(w, self.paths) if wk)
        host = fw.actors.get(self.on) if self.on else None
        hs = fw.raw_state(self.on) if host else None
        if host and hs:
            R = Rotation.from_euler("xyz", hs["rot"], degrees=True).as_matrix()
            pts = (pts * hs["scale"]) @ R.T + hs["at"]
            self.marker_placed.place(hs["at"], hs["scale"], hs["rot"])
        self.arrows.set_points(pts)
        host_show = fw.state_of(self.on) if self.on else 1.0
        self.arrows.set_stroke(opacity=show * host_show)
        dominant = int(np.argmax(w))
        for k, group in enumerate(self.markers):
            group.set_opacity(show * host_show * float(w[k]))
        fw.values[f"{self.id}.zeros"] = len(self.zeros[dominant])

    def extent(self, st):
        return [list(p) for p in self.base[[0, -1]]] if not self.on else []


# --- labels ----------------------------------------------------------------------------
class Label3D:
    def __init__(self, i, nodes, world):
        th = current()
        n0 = nodes[0]
        self.id, self.of = i, n0.attrs.get("of")
        text = n0.attrs.get("text", "").strip()
        if not text:
            raise BeatError(f'<label3d id={i}> needs text="…"')
        self.mob = Text(text, font=th.body_font, font_size=_num(n0, "size", 26),
                        fill_color=th.color(n0.attrs.get("color"), "ink"))
        self.mob.set_backstroke(th.bg, 5)
        self.mob.fix_in_frame()
        self.at = np.zeros(3)
        self.show = 0.0
        self.frame = None

    def state(self, node, old):
        if "at" in node.attrs:
            at = vec(node, "at", "0,0,0")
        elif self.of is None and old is not None:
            at = old["at"]
        elif self.of is None:
            raise BeatError(f'<label3d id={node.id}> needs at="x,y,z" or of="solidId"')
        else:
            at = np.zeros(3)
        return {"show": 1.0, "at": at}

    def apply(self, st, fw):
        self.show = st["show"] if st else 0.0
        at = st["at"] if st else self.at
        if self.of and fw.raw_state(self.of):
            s = fw.raw_state(self.of)
            at = s["at"] + np.array([0, 0, s["scale"][2] + 0.35])
        self.at = np.asarray(at, float)
        self.frame = fw.frame
        self._place()

    def view(self):
        self._place()

    def _place(self):
        """Project the 3D point exactly as the shader does, then pin the text there."""
        frame = self.frame
        if frame is None:
            return
        self.mob.move_to(project(frame, self.at) + 0.3 * UP)
        self.mob.set_opacity(self.show)

    def extent(self, st):
        return [list(st["at"])] if st and self.of is None else []


# --- lines and angles between bodies ----------------------------------------------------
class _Anchored:
    """Ends given as a solid id or as "x,y,z". The state holds each end's resolved centre and
    the radius to stop at, so ends interpolate like everything else: a line attached to a
    moving solid follows it exactly, and re-aiming a line between beats animates."""

    KEYS: tuple[str, ...] = ()

    def __init__(self, i, nodes, world):
        self.id = i
        self.world = world
        for n in nodes:
            for k in self.KEYS:
                ref = n.attrs.get(k, "").strip()
                if not ref:
                    raise BeatError(f'<{n.tag} id={i}> needs {k}="solidId" or {k}="x,y,z"')
                if not _is_point(ref) and not world._is_solid(ref):
                    raise BeatError(f'<{n.tag} id={i}> {k}="{ref}" must name a <sphere id>/<solid id> '
                                    'or be "x,y,z"')

    def state(self, node, old):
        st = {"show": 1.0}
        for k in self.KEYS:
            ref = node.attrs[k].strip()
            if _is_point(ref):
                st[k], st[k + "_r"] = np.array([float(v) for v in ref.split(",")]), 0.0
            else:
                solid = self.world.pending.get(ref)
                if not solid:
                    raise BeatError(f'<{node.tag} id={node.id}> {k}="{ref}": that solid is not in '
                                    'this beat')
                st[k], st[k + "_r"] = np.asarray(solid["at"], float), float(np.max(solid["scale"]))
        return st

    def extent(self, st):
        return [list(st[k]) for k in self.KEYS if st and st[k + "_r"] == 0.0]

    def ends(self, st):
        return [np.asarray(st[k], float) for k in self.KEYS]


def _is_point(ref: str) -> bool:
    try:
        return len([float(v) for v in ref.split(",")]) == 3
    except ValueError:
        return False


def project(frame, point) -> np.ndarray:
    """Where a world point lands in fixed-frame coordinates (as the shader projects it)."""
    v = frame.to_fixed_frame_point(point)
    w = 1 - v[2] * frame.get_scale() / frame.get_focal_distance()
    return np.array([v[0] / w, v[1] / w, 0.0])


def _pinned_text(text: str, color: str, size: float = 26) -> Text:
    th = current()
    mob = Text(text, font=th.body_font, font_size=size, fill_color=color)
    mob.set_backstroke(th.bg, 5)
    mob.fix_in_frame()
    return mob


class Line3D(_Anchored):
    """``<line3d from to>``: a segment between two bodies or points, from surface to surface;
    ``arrow="true"`` makes it an arrow: a flat ribbon turned to face the camera every frame, so
    it reads as an arrow from any angle. ``on="sphereId"``: the path runs along that sphere's
    surface (its back half hidden behind the sphere). ``label`` pins text at the tip. A straight
    line is drawn on top (no depth test): it is a diagram mark, and inside a see-through solid
    (a box diagonal) it must stay visible."""

    KEYS = ("from", "to")

    def __init__(self, i, nodes, world):
        super().__init__(i, nodes, world)
        n0 = nodes[0]
        self.color = color = current().color(n0.attrs.get("color"), "muted")
        self.arrow = n0.attrs.get("arrow", "false").lower() in ("true", "1", "yes")
        self.width = _num(n0, "width", 4)
        self.on = n0.attrs.get("on", "").strip() or None
        if self.on and not world._is_solid(self.on, sphere=True):
            raise BeatError(f'<line3d id={i}> on="{self.on}" must name a <sphere id>')
        self.line = VMobject().set_stroke(color, self.width)
        self.head = VMobject().set_fill(color, 1).set_stroke(width=0)
        if self.on:
            self.line.apply_depth_test()
            self.head.apply_depth_test()
        text = n0.attrs.get("label", "").strip()
        self.label = _pinned_text(text, color) if text else None
        self.mob = Group(self.line, self.head, *([self.label] if self.label else []))
        self.st, self.fw = None, None

    def apply(self, st, fw):
        self.st, self.fw = st, fw
        self._draw()

    def view(self):   # every frame: the head turns to the camera, the label follows the tip
        self._draw()

    def _path(self, st) -> np.ndarray:
        a, b = self.ends(st)
        if self.on and self.fw and self.fw.raw_state(self.on):
            hs = self.fw.raw_state(self.on)
            c, r = np.asarray(hs["at"], float), float(np.max(hs["scale"])) * 1.012
            for end in (a, b):
                if np.linalg.norm(end - c) < 1e-6:
                    raise BeatError(
                        f'<line3d id={self.id} on="{self.on}">: the end {",".join(f"{v:g}" for v in end)} is '
                        f'the sphere\'s centre ({",".join(f"{v:g}" for v in c)}), not a point on it. A sphere '
                        'without at= rests on the floor; give it at="0,0,0" to centre it at the origin')
            ua, ub = (a - c) / np.linalg.norm(a - c), (b - c) / np.linalg.norm(b - c)
            ang = np.arccos(np.clip(ua @ ub, -1, 1))
            if ang < 1e-4:
                return np.array([c + r * ua, c + r * ub])
            ts = np.linspace(0, 1, max(8, int(ang * 40)))
            return np.array([c + r * (np.sin((1 - t) * ang) * ua + np.sin(t * ang) * ub) / np.sin(ang)
                             for t in ts])
        u = (b - a) / np.linalg.norm(b - a)
        return np.array([a + u * st["from_r"], b - u * st["to_r"]])

    def _draw(self):
        st, fw = self.st, self.fw
        show = st["show"] if st else 0.0
        if st and np.linalg.norm(st["to"] - st["from"]) > 1e-6:
            path = self._path(st)
            if self.arrow and fw is not None and fw.frame is not None:
                self._ribbon(path, fw.frame)
            else:
                self.line.set_points_as_corners(path)
                self.head.clear_points()
            if self.label is not None and fw is not None and fw.frame is not None:
                # beside the shaft, 70% of the way along, on its left as seen on screen: arrows
                # that share a tip (a sum and its last term) keep their labels apart
                k = min(len(path) - 1, int(0.7 * (len(path) - 1)))
                a3 = path[0] + 0.7 * (path[-1] - path[0]) if len(path) == 2 else path[k]
                a, b = project(fw.frame, path[0]), project(fw.frame, path[-1])
                d = b - a
                d = d / (np.linalg.norm(d) or 1)
                left = np.array([-d[1], d[0], 0.0])
                half = 0.5 * np.hypot(self.label.get_width() * left[0], self.label.get_height() * left[1])
                self.label.move_to(project(fw.frame, a3) + left * (0.22 + half))
        self.line.set_stroke(opacity=show)
        self.head.set_fill(opacity=show if self.arrow else 0)
        if self.label is not None:
            self.label.set_opacity(show)

    def _ribbon(self, path: np.ndarray, frame):
        """Shaft as a stroke along the path, head as a filled triangle in the plane that faces
        the camera (like an arrow drawn on paper held up to the viewer)."""
        end, prev = path[-1], path[-2]
        L = sum(np.linalg.norm(np.diff(path, axis=0), axis=1))
        u = (end - prev) / (np.linalg.norm(end - prev) or 1)
        to_cam = frame.get_implied_camera_location() - end
        side = np.cross(u, to_cam)
        if np.linalg.norm(side) < 1e-6:
            side = np.cross(u, [0, 0, 1]) if abs(u[2]) < 0.9 else np.cross(u, [1, 0, 0])
        side /= np.linalg.norm(side)
        tip_len = min(0.07 * self.width + 0.08, 0.35 * L)
        tip_w = 0.85 * tip_len
        base = end - u * tip_len
        self.head.set_points_as_corners([end, base + side * tip_w / 2, base - side * tip_w / 2, end])
        # shaft stops inside the head so its square end never pokes out of the tip
        keep = path[:-1] if len(path) > 2 else path[:1]
        self.line.set_points_as_corners([*keep, base + u * 0.3 * tip_len])


class Angle3D(_Anchored):
    """``<angle3d at from to>``: the angle at ``at`` between the directions to ``from`` and
    ``to``: an arc, or a small square when it is a right angle."""

    KEYS = ("at", "from", "to")

    def __init__(self, i, nodes, world):
        super().__init__(i, nodes, world)
        n0 = nodes[0]
        self.r = _num(n0, "r", 0) or None
        self.mob = VMobject().set_stroke(current().color(n0.attrs.get("color"), "accent"), 4)

    def apply(self, st, fw):
        show = st["show"] if st else 0.0
        if st:
            self._draw(st)
        self.mob.set_stroke(opacity=show)

    def _draw(self, st):
        v, a, b = self.ends(st)
        da, db = a - v, b - v
        la, lb = np.linalg.norm(da), np.linalg.norm(db)
        if la < 1e-6 or lb < 1e-6:
            return
        ua, ub = da / la, db / lb
        # outside the vertex body, inside the shorter side
        r = self.r or max(0.3 * min(la, lb), st["at_r"] * 1.4)
        ang = np.arccos(np.clip(ua @ ub, -1, 1))
        if abs(np.degrees(ang) - 90) < 1.5:
            pts = [v + ua * r, v + (ua + ub) * r, v + ub * r]
        elif ang < 1e-3:
            return
        else:
            ts = np.linspace(0, 1, 32)
            pts = [v + r * (np.sin((1 - t) * ang) * ua + np.sin(t * ang) * ub) / np.sin(ang) for t in ts]
        self.mob.set_points_as_corners(pts)


class Face3D:
    """``<face3d points="x,y,z; x,y,z; …">``: a flat see-through polygon in space (a span, a
    plane, a cross-section), outlined. Same number of corners in a later beat: it reshapes."""

    def __init__(self, i, nodes, world):
        n0 = nodes[0]
        th = current()
        self.id = i
        color = th.color(n0.attrs.get("color"), "accent")
        counts = {len(self._points(n)) for n in nodes}
        if len(counts) != 1:
            raise BeatError(f"<face3d id={i}>: keep the same number of corners in every beat "
                            "(use a new id for a different shape)")
        self.fill = VMobject().set_fill(color, 1).set_stroke(width=0)
        self.edge = VMobject().set_stroke(color, 3)
        text = n0.attrs.get("label", "").strip()
        self.label = _pinned_text(text, color) if text else None
        self.mob = Group(self.fill, self.edge, *([self.label] if self.label else []))
        self.op = 0.0
        self.st, self.fw = None, None

    @staticmethod
    def _points(node) -> np.ndarray:
        raw = node.attrs.get("points", "").strip()
        try:
            pts = np.array([[float(v) for v in c.split(",")] for c in raw.split(";") if c.strip()])
        except ValueError:
            pts = np.zeros((0, 0))
        if pts.ndim != 2 or pts.shape[1] != 3 or len(pts) < 3:
            raise BeatError(f'<face3d id={node.id}> points="{raw}": give 3 or more corners '
                            '"x,y,z; x,y,z; x,y,z"')
        return pts

    def state(self, node, old):
        op = _num(node, "opacity", 0.3) if "opacity" in node.attrs else (old["opacity"] if old else 0.3)
        return {"show": 1.0, "pts": self._points(node), "opacity": op}

    def apply(self, st, fw):
        self.st, self.fw = st, fw
        show = st["show"] if st else 0.0
        if st:
            loop = [*st["pts"], st["pts"][0]]
            self.fill.set_points_as_corners(loop)
            self.edge.set_points_as_corners(loop)
        self.fill.set_fill(opacity=(st["opacity"] if st else 0.3) * show)
        self.edge.set_stroke(opacity=show)
        if self.label is not None:
            self.label.set_opacity(show)
            self._place_label()

    def view(self):
        if self.label is not None:
            self._place_label()

    def _place_label(self):
        if self.st is not None and self.fw is not None and self.fw.frame is not None:
            self.label.move_to(project(self.fw.frame, self.st["pts"].mean(axis=0)))

    def extent(self, st):
        return st["pts"].tolist() if st else []


CLASSES = {"sphere": Solid, "solid": Solid, "light": Light, "shadow": Shadow,
           "field": VectorField, "label3d": Label3D, "line3d": Line3D, "angle3d": Angle3D, "face3d": Face3D}
