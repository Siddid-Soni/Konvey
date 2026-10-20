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

from .parse import Node

SIDE = 2.0               # visual side length; areas are reported for s = 1
SPHERE_R = 1.2
CUBE_COLOR = "#3b82f6"
UP_TINT = "#f59e0b"      # faces facing the light
DOWN_TINT = "#8b5cf6"    # faces facing the floor
SHADOW_FILL = "#020617"
SHADOW_EDGE = "#facc15"
GROUND_COLOR = "#1e293b"
N_RAYS = 12

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

    @classmethod
    def from_beat(cls, actors: dict[str, Node], prev: "WorldState | None") -> "WorldState":
        base = prev or cls()
        cube = actors.get("cube")
        s = replace(base, show={k: 1.0 for k in actors})
        if cube is not None:
            a = cube.attrs
            s.rot = parse_rotation(a["rot"]) if "rot" in a else base.rot
            s.z = float(a.get("z", base.z))
            s.morph = 1.0 if a.get("shape") == "sphere" else 0.0
            s.tint = 1.0 if a.get("tint") == "by-light" else 0.0
        return s


def lerp_state(a: WorldState, b: WorldState, t: float) -> WorldState:
    keys = set(a.show) | set(b.show)
    rot = Slerp([0, 1], Rotation.concatenate([a.rot, b.rot]))(t)
    return WorldState(
        show={k: (1 - t) * a.show.get(k, 0) + t * b.show.get(k, 0) for k in keys},
        rot=rot, z=(1 - t) * a.z + t * b.z,
        morph=(1 - t) * a.morph + t * b.morph, tint=(1 - t) * a.tint + t * b.tint,
    )


def shadow_area(rot: Rotation) -> float:
    """Exact shadow area of a unit cube: |u_x| + |u_y| + |u_z|, u = R^T z."""
    return float(np.abs(rot.inv().apply([0, 0, 1])).sum())


class World:
    def __init__(self):
        self.state = WorldState()
        self.values: dict[str, float] = {"tumble.n": 0, "tumble.mean": 0.0}
        self.ground = self._ground()
        self.faces, self.cube_data, self.sphere_data, self.normals = self._faces()
        self.edges, self.edge_cube, self.edge_sphere = self._edges()
        self.shadow = VMobject(fill_color=SHADOW_FILL, fill_opacity=0.9,
                               stroke_color=SHADOW_EDGE, stroke_width=3)
        self.rays = VGroup(*(Line(ORIGIN, OUT, stroke_color=SHADOW_EDGE, stroke_width=1.5)
                             for _ in range(N_RAYS)))
        self.rays.apply_depth_test()
        self.edges.apply_depth_test()
        # Draw order matters: the shadow skips the depth test so it sits on the
        # floor without z-fighting, and the cube (drawn later, depth-tested) covers it.
        self.group = Group(self.ground, self.shadow, self.rays, *self.faces, self.edges)
        self.apply(self.state)

    # --- construction -------------------------------------------------
    def _ground(self):
        floor = Square3D(side_length=12, color=GROUND_COLOR, shading=(0.2, 0.2, 0))
        grid = VGroup(*(
            Line([-6, c, 0.005], [6, c, 0.005]) for c in range(-6, 7)
        ), *(
            Line([c, -6, 0.005], [c, 6, 0.005]) for c in range(-6, 7)
        )).set_stroke("#334155", 1)
        return Group(floor, grid)

    def _faces(self):
        faces = square_to_cube_faces(Square3D(resolution=(12, 12), side_length=SIDE))
        cube_data, sphere_data, normals = [], [], []
        for f in faces:
            f.set_color(CUBE_COLOR, 0.88).set_shading(0.3, 0.4, 0.2)
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
        edges.set_stroke(WHITE, 2, 0.9)
        return edges, cube, sphere

    # --- per-frame update -----------------------------------------------
    def apply(self, s: WorldState):
        self.state = s
        R = s.rot.as_matrix()
        lift = np.array([0, 0, s.z])
        m = s.morph
        show = s.show

        g = show.get("ground", 0)
        self.ground[0].set_opacity(g)
        self.ground[1].set_stroke(opacity=0.6 * g)

        c = show.get("cube", 0)
        solid = []
        for f, cd, sd, n in zip(self.faces, self.cube_data, self.sphere_data, self.normals):
            for k in ("point", "du_point", "dv_point"):
                f.data[k][:] = ((1 - m) * cd[k] + m * sd[k]) @ R.T + lift
            f.note_changed_data()
            up = (R @ n)[2]
            tint = interpolate_color(CUBE_COLOR, UP_TINT if up > 0 else DOWN_TINT,
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

    @classmethod
    def from_beat(cls, attrs: dict[str, str], boxes, prev: "CameraState | None") -> "CameraState":
        base = prev or cls()
        focus = base.focus
        if "focus" in attrs:
            b = boxes[attrs["focus"].lstrip("#")]
            focus = (b.x, b.y)
        return cls(float(attrs.get("theta", base.theta)), float(attrs.get("phi", base.phi)),
                   float(attrs.get("zoom", base.zoom)), focus,
                   float(attrs.get("target-z", base.target_z)))


def lerp_camera(a: CameraState, b: CameraState, t: float, extra_theta: float = 0.0) -> CameraState:
    mix = lambda p, q: (1 - t) * p + t * q  # noqa: E731
    return CameraState(mix(a.theta, b.theta) + extra_theta, mix(a.phi, b.phi), mix(a.zoom, b.zoom),
                       (mix(a.focus[0], b.focus[0]), mix(a.focus[1], b.focus[1])),
                       mix(a.target_z, b.target_z))


def apply_camera(frame, c: CameraState):
    """Orient the camera and shift it in its own plane so the world target lands on ``focus``."""
    frame.reorient(c.theta, c.phi, 0, center=ORIGIN, height=FRAME_HEIGHT / c.zoom)
    R = frame.get_orientation().as_matrix()
    scale = frame.get_scale()
    target = np.array([0, 0, c.target_z])
    frame.move_to(target - scale * (R[:, 0] * c.focus[0] + R[:, 1] * c.focus[1]))


def tumble_rotations(seed: int, n: int) -> list[Rotation]:
    return list(Rotation.random(n, random_state=seed))
