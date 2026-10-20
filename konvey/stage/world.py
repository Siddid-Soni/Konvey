"""3D world actors whose state is declared per beat and interpolated between beats.

Actors: ``ground``, ``cube`` (rotation, height, cube->sphere morph, face tint),
``shadow`` (true orthographic projection: convex hull of the projected solid)
and ``rays`` (parallel light from straight above to the shadow outline).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation, Slerp

from manimlib import *  # noqa: F401,F403

from .field import FieldWorld, is_field
from .parse import BeatError, Node
from .theme import current

SIDE = 2.0               # visual side length; areas are reported for s = 1
SPHERE_R = 1.2
N_RAYS = 12

ACTOR_ATTRS = {
    "ground": set(), "shadow": set(), "rays": set(),
    "cube": {"rot", "z", "shape", "tint", "tumble", "samples", "seed"},
}

CORNER_UP = Rotation.from_euler("zx", [45, np.degrees(np.arctan(np.sqrt(2)))], degrees=True)


def parse_rotation(spec: str) -> Rotation:
    spec = spec.strip()
    if spec in ("", "face"):
        return Rotation.identity()
    if spec == "corner":
        return CORNER_UP
    return Rotation.from_euler("xyz", [float(v) for v in spec.split(",")], degrees=True)


@dataclass
class WorldState:
    show: dict[str, float] = field(default_factory=dict)  # actor -> opacity 0..1
    rot: Rotation = field(default_factory=Rotation.identity)
    z: float = 2.2
    morph: float = 0.0
    tint: float = 0.0
    fields: dict = field(default_factory=dict)   # FieldWorld state, per actor id

    @classmethod
    def from_beat(cls, actors: dict[str, Node], prev: "WorldState | None",
                  fields: "FieldWorld | None" = None) -> "WorldState":
        base = prev or cls()
        cube = actors.get("cube")
        solid = {k: n for k, n in actors.items() if not is_field(n)}
        s = replace(base, show={k: 1.0 for k in solid})
        if fields is not None:
            s.fields = fields.state_from(actors, base.fields)
        for tag, node in solid.items():
            extra = set(node.attrs) - ACTOR_ATTRS.get(tag, set())
            if tag not in ACTOR_ATTRS or extra:
                raise BeatError(f"<world><{tag}>: unknown {'attributes ' + str(sorted(extra)) if tag in ACTOR_ATTRS else 'actor'}; "
                                f"allowed: {ACTOR_ATTRS}")
        if cube is not None:
            a = cube.attrs
            try:
                s.rot = parse_rotation(a["rot"]) if "rot" in a else base.rot
            except ValueError as e:
                raise BeatError(f'<cube rot="{a["rot"]}">: use face, corner or "x,y,z" degrees') from e
            s.z = float(a.get("z", base.z))
            s.morph = 1.0 if a.get("shape") == "sphere" else 0.0
            s.tint = 1.0 if a.get("tint") == "by-light" else 0.0
        return s


def lerp_state(a: WorldState, b: WorldState, t: float, enter_t: float | None = None) -> WorldState:
    """``enter_t``: progress used for actors that are appearing (default ``t``); the scene
    delays it so a new actor fades in where the camera ends up, not where it starts."""
    t = min(max(t, 0.0), 1.0)   # rate functions can land a hair outside [0, 1]; Slerp rejects that
    keys = set(a.show) | set(b.show)
    rot = Slerp([0, 1], Rotation.concatenate([a.rot, b.rot]))(t)
    et = t if enter_t is None else min(max(enter_t, 0.0), 1.0)

    def show(k):
        sa, sb = a.show.get(k, 0), b.show.get(k, 0)
        u = et if sa == 0 and sb > 0 else t
        return (1 - u) * sa + u * sb

    return WorldState(
        show={k: show(k) for k in keys},
        rot=rot, z=(1 - t) * a.z + t * b.z,
        morph=(1 - t) * a.morph + t * b.morph, tint=(1 - t) * a.tint + t * b.tint,
        fields=FieldWorld.lerp(a.fields, b.fields, t, enter_t=et),
    )


def world_exits(a: WorldState, b: WorldState) -> "WorldState | None":
    """``a`` with only the actors that are gone in ``b`` faded out (None if nothing leaves),
    so leaving actors can fade before the next beat's elements enter."""
    show = {k: (0.0 if b.show.get(k, 0) == 0 else v) for k, v in a.show.items()}
    changed = any(v > 0 and show[k] == 0 for k, v in a.show.items())
    fields = {}
    for i, sa in a.fields.items():
        sb = b.fields.get(i)
        leaving = sa is not None and sa.get("show", 0) > 0 and (sb is None or sb.get("show", 0) == 0)
        fields[i] = {**sa, "show": 0.0} if leaving else sa
        changed |= leaving
    if not changed:
        return None
    return replace(a, show=show, fields=fields)


def shadow_area(rot: Rotation) -> float:
    """Exact shadow area of a unit cube: |u_x| + |u_y| + |u_z|, u = R^T z."""
    return float(np.abs(rot.inv().apply([0, 0, 1])).sum())


class World:
    def __init__(self, beats=()):
        self.theme = th = current()
        self.field = FieldWorld(beats)
        self.state = WorldState()
        self.values: dict[str, float] = {"tumble.n": 0, "tumble.mean": 0.0}
        self.ground = self._ground()
        self.faces, self.cube_data, self.sphere_data, self.normals = self._faces()
        self.edges, self.edge_cube, self.edge_sphere = self._edges()
        self.shadow = VMobject(fill_color=th.shadow_fill, fill_opacity=0.9,
                               stroke_color=th.accent, stroke_width=3)
        self.rays = VGroup(*(Line(ORIGIN, OUT, stroke_color=th.accent, stroke_width=1.5)
                             for _ in range(N_RAYS)))
        self.rays.apply_depth_test()
        self.edges.apply_depth_test()
        # Draw order matters: the shadow skips the depth test so it sits on the
        # floor without z-fighting, and the cube (drawn later, depth-tested) covers it.
        self.group = Group(self.ground, self.field.group, self.shadow, self.rays, *self.faces, self.edges)
        self.apply(self.state)

    # --- construction -------------------------------------------------
    def _ground(self):
        """``ground`` per theme: a plane with a grid, one faint ring, or nothing.
        Always [surface, strokes] so :meth:`apply` can fade both."""
        th = self.theme
        if th.floor == "plane":
            floor = Square3D(side_length=12, color=th.floor_color, shading=(0.2, 0.2, 0))
            lines = VGroup(*(
                Line([-6, c, 0.005], [6, c, 0.005]) for c in range(-6, 7)
            ), *(
                Line([c, -6, 0.005], [c, 6, 0.005]) for c in range(-6, 7)
            )).set_stroke(th.grid_color, 1)
            self._floor_opacity, self._line_opacity = 1.0, 0.6
        else:
            # No floor surface: even transparent it would hide anything below z=0.
            floor = Group()
            ring = Circle(radius=3.2).shift(0.005 * OUT).set_stroke(th.grid_color, 1)
            lines = VGroup(*([ring] if th.floor == "ring" else []))
            self._floor_opacity, self._line_opacity = 0.0, 0.25
        return Group(floor, lines)

    def _faces(self):
        faces = square_to_cube_faces(Square3D(resolution=(12, 12), side_length=SIDE))
        cube_data, sphere_data, normals = [], [], []
        for f in faces:
            f.set_color(self.theme.solid, 0.88).set_shading(*self.theme.solid_shading)
            cube = {k: f.data[k].copy() for k in ("point", "du_point", "dv_point")}
            sphere = {k: SPHERE_R * v / np.linalg.norm(v, axis=1, keepdims=True)
                      for k, v in cube.items()}
            cube_data.append(cube)
            sphere_data.append(sphere)
            normals.append(f.get_center() / np.linalg.norm(f.get_center()))
        return faces, cube_data, sphere_data, normals

    def _edges(self):
        h = SIDE / 2
        verts = np.array([[x, y, z] for x in (-h, h) for y in (-h, h) for z in (-h, h)])
        t = np.linspace(0, 1, 24)[:, None]
        pairs = [(i, j) for i in range(8) for j in range(i + 1, 8)
                 if np.sum(verts[i] != verts[j]) == 1]
        cube = [verts[i] + t * (verts[j] - verts[i]) for i, j in pairs]
        sphere = [SPHERE_R * p / np.linalg.norm(p, axis=1, keepdims=True) for p in cube]
        edges = VGroup(*(VMobject().set_points_as_corners(p) for p in cube))
        edges.set_stroke(self.theme.ink, 2, 0.9)
        return edges, cube, sphere

    def extent(self, s: WorldState, only=None) -> np.ndarray | None:
        """3D points bounding what the beat shows (floor excluded), for auto-framing;
        ``only``: just these actor ids."""
        pts = []
        if s.show.get("cube", 0) > 0 and (only is None or "cube" in only):
            r = SIDE * 0.9
            pts += [[x, y, z] for x in (-r, r) for y in (-r, r) for z in (0, s.z + r)]
        pts += self.field.extent(s.fields, only)
        return np.array(pts, float) if pts else None

    def shown(self, ids: list[str], s: WorldState, beat_ids) -> tuple[np.ndarray, list]:
        """``<camera show="a,b">``: the points and segments of those actors."""
        missing = [i for i in ids if i not in beat_ids]
        if missing:
            raise BeatError(f'<camera show="{",".join(ids)}">: {missing} not in this beat\'s <world> '
                            f"(ids here: {', '.join(sorted(beat_ids))})")
        # axes are the frame of reference: keep them inside the view too (3D is not clipped to
        # its box, so axes framed out would run across the headline and subtitle)
        axes = {i for i, n in beat_ids.items() if n.tag == "axes3d"}
        pts = self.extent(s, only=set(ids) | axes)
        if pts is None:
            raise BeatError(f'<camera show="{",".join(ids)}">: nothing visible to frame')
        return pts, self.field.segments(s.fields, [i for i in ids if i in self.field.nodes])

    # --- per-frame update -----------------------------------------------
    def apply(self, s: WorldState):
        self.state = s
        self.field.apply(s.fields)
        self.values.update(self.field.values)
        R = s.rot.as_matrix()
        lift = np.array([0, 0, s.z])
        m = s.morph
        show = s.show

        g = show.get("ground", 0)
        self.ground[0].set_opacity(self._floor_opacity * g)
        self.ground[1].set_stroke(opacity=self._line_opacity * g)

        c = show.get("cube", 0)
        solid = []
        for f, cd, sd, n in zip(self.faces, self.cube_data, self.sphere_data, self.normals):
            for k in ("point", "du_point", "dv_point"):
                f.data[k][:] = ((1 - m) * cd[k] + m * sd[k]) @ R.T + lift
            f.note_changed_data()
            up = (R @ n)[2]
            th = self.theme
            tint = interpolate_color(th.solid, th.up_tint if up > 0 else th.down_tint,
                                     s.tint * min(1, abs(up) * 4))
            f.set_color(tint, 0.88 * c)
            solid.append(f.data["point"])
        for e, pc, ps in zip(self.edges, self.edge_cube, self.edge_sphere):
            e.set_points_as_corners(((1 - m) * pc + m * ps) @ R.T + lift)
        self.edges.set_stroke(opacity=0.9 * c * (1 - m) ** 2)

        pts = np.vstack(solid)[:, :2]
        hull = ConvexHull(pts)
        outline = pts[hull.vertices]
        self.values["shadow.area"] = hull.volume / SIDE ** 2
        sh = show.get("shadow", 0)
        self.shadow.set_points_as_corners(
            [*np.c_[outline, np.full(len(outline), 0.01)], [*outline[0], 0.01]])
        self.shadow.set_fill(opacity=0.9 * sh).set_stroke(opacity=sh)

        r = show.get("rays", 0)
        idx = np.linspace(0, len(outline), N_RAYS, endpoint=False).astype(int)
        for ray, i in zip(self.rays, idx):
            x, y = outline[i]
            ray.set_points_as_corners([[x, y, 7.5], [x, y, 0.02]])
        self.rays.set_stroke(opacity=0.45 * r)


@dataclass
class CameraState:
    theta: float = -30.0
    phi: float = 70.0
    zoom: float = 1.0
    focus: tuple[float, float] = (0.0, 0.0)   # screen point (fixed-frame units) of the target
    target_z: float = 1.4
    target_xy: tuple[float, float] = (0.0, 0.0)

    @classmethod
    def from_beat(cls, attrs: dict[str, str], boxes, prev: "CameraState | None",
                  extent: np.ndarray | None = None, drift: float = 0.0,
                  shown: tuple | None = None) -> "CameraState":
        """``extent``: 3D points of what is visible. Without explicit ``zoom`` /
        ``target-z`` the camera frames them inside the focus box. ``shown`` (from
        ``<camera show=…>``): (points, segments) to frame instead, and, unless theta/phi are
        given, to choose the viewing angle for."""
        base = prev or cls()
        focus, box = base.focus, (FRAME_WIDTH, FRAME_HEIGHT)
        if "focus" in attrs:
            key = attrs["focus"].lstrip("#")
            if key not in boxes:
                raise BeatError(f'<camera focus="{key}">: this beat has no element with id="{key}" '
                                f'(add e.g. <div id="{key}" class="grow"></div>)')
            b = boxes[key]
            if min(b.w, b.h) < 1.5:
                raise BeatError(f'<camera focus="{key}">: #{key} is only {b.w:.1f} x {b.h:.1f} units, so the '
                                "3D view would shrink to a speck; give it room (class=\"grow\", or a width/height)")
            focus, box = (b.x, b.y), (b.w, b.h)
        theta = float(attrs.get("theta", base.theta))
        phi = float(attrs.get("phi", base.phi))
        if shown is not None:
            # `show` chooses the angle; framing still covers everything visible, since 3D is
            # not clipped to its box and anything framed out would land on the text
            if "theta" not in attrs and "phi" not in attrs:
                theta, phi = best_view(shown[0], shown[1], near=(base.theta, base.phi))
        zoom, tz, txy = base.zoom, base.target_z, base.target_xy
        if extent is not None and len(extent):
            centre = view_centre(extent, theta, phi)
            if "target-z" not in attrs:
                tz, txy = float(centre[2]), (float(centre[0]), float(centre[1]))
            if "zoom" not in attrs:
                # the hold orbits by `drift` degrees: frame the whole sweep, not just its start
                zoom = min(fit_zoom(extent, theta + d, phi, box) for d in np.linspace(0, drift, 4))
        return cls(theta, phi, float(attrs.get("zoom", zoom)), focus,
                   float(attrs.get("target-z", tz)), txy)


_SCRATCH_FRAME = None


def _view_axes(theta: float, phi: float) -> np.ndarray:
    """Camera axes (columns: screen right, screen up, towards the viewer) for (theta, phi)."""
    global _SCRATCH_FRAME
    if _SCRATCH_FRAME is None:
        from manimlib.camera.camera_frame import CameraFrame

        _SCRATCH_FRAME = CameraFrame()
    _SCRATCH_FRAME.reorient(theta, phi, 0)
    return _SCRATCH_FRAME.get_orientation().as_matrix()


def view_centre(points: np.ndarray, theta: float, phi: float) -> np.ndarray:
    """World point that projects to the centre of ``points``' on-screen bounding box (the 3D
    box centre does not, once seen at an angle, and the scene then sits off-centre)."""
    R = _view_axes(theta, phi)
    proj = points @ R
    mid = (proj.min(axis=0) + proj.max(axis=0)) / 2
    mid[2] = proj[:, 2].mean()
    return R @ mid


def best_view(points: np.ndarray, segs: list, near: tuple[float, float] = (-30.0, 70.0)
              ) -> tuple[float, float]:
    """Camera angle that shows these things most openly: every segment as close to its true
    length on screen as possible (the worst one counts most), or with no segments the widest
    outline; ties go to the angle nearest ``near`` (the current view), so the camera moves
    no more than it must."""
    from scipy.spatial import ConvexHull, QhullError

    cands = []
    for th in np.arange(-180, 180, 10.0):
        for ph in np.arange(15, 81, 5.0):
            R = _view_axes(th, ph)[:, :2]
            if segs:
                r = [np.linalg.norm((b - a) @ R) / np.linalg.norm(b - a) for a, b in segs]
                score = 0.7 * min(r) + 0.3 * float(np.mean(r))
            else:
                try:
                    score = ConvexHull(points @ R).volume
                except (QhullError, ValueError):
                    score = 0.0
            cands.append((th, ph, score))
    top = max(c[2] for c in cands) or 1.0
    turn = lambda a, b: abs((a - b + 180) % 360 - 180)  # noqa: E731
    th, ph, _ = max(cands, key=lambda c: c[2] / top - 0.12 * turn(c[0], near[0]) / 180
                    - 0.08 * abs(c[1] - near[1]) / 90)
    # unwrap so the camera turns the short way from where it is
    th = near[0] + ((th - near[0] + 180) % 360 - 180)
    return float(th), float(ph)


def fit_zoom(points: np.ndarray, theta: float, phi: float, box: tuple[float, float],
             margin: float = 0.8) -> float:
    """Zoom at which ``points`` seen from (theta, phi) fill ``margin`` of the box."""
    R = _view_axes(theta, phi)
    ext_x, ext_y = np.ptp(points @ R[:, 0]), np.ptp(points @ R[:, 1])
    # Frame height H shows H/FRAME_HEIGHT world units per fixed-frame unit.
    need = max(FRAME_HEIGHT * ext_x / (margin * box[0]), FRAME_HEIGHT * ext_y / (margin * box[1]), 1e-3)
    return float(np.clip(FRAME_HEIGHT / need, 0.25, 2.5))


def lerp_camera(a: CameraState, b: CameraState, t: float, extra_theta: float = 0.0) -> CameraState:
    mix = lambda p, q: (1 - t) * p + t * q  # noqa: E731
    return CameraState(mix(a.theta, b.theta) + extra_theta, mix(a.phi, b.phi), mix(a.zoom, b.zoom),
                       (mix(a.focus[0], b.focus[0]), mix(a.focus[1], b.focus[1])),
                       mix(a.target_z, b.target_z),
                       (mix(a.target_xy[0], b.target_xy[0]), mix(a.target_xy[1], b.target_xy[1])))


def apply_camera(frame, c: CameraState):
    """Orient the camera and shift it in its own plane so the world target lands on ``focus``."""
    frame.reorient(c.theta, c.phi, 0, center=ORIGIN, height=FRAME_HEIGHT / c.zoom)
    R = frame.get_orientation().as_matrix()
    scale = frame.get_scale()
    target = np.array([*c.target_xy, c.target_z])
    frame.move_to(target - scale * (R[:, 0] * c.focus[0] + R[:, 1] * c.focus[1]))


def tumble_rotations(seed: int, n: int) -> list[Rotation]:
    return list(Rotation.random(n, random_state=seed))
