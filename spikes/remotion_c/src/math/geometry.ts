// Pure math for the cube-shadow lesson. No three.js / React here so it can be
// unit-tested with `bun test` and reused by both the 3D layer and the readouts.
//
// Conventions: z-up world, floor is z = 0, light shines straight down (-z).
// Quaternions are [w, x, y, z].

export type Vec3 = [number, number, number];
export type Vec2 = [number, number];
export type Quat = [number, number, number, number];

export const qIdentity: Quat = [1, 0, 0, 0];

export const qAxisAngle = (axis: Vec3, angle: number): Quat => {
  const [x, y, z] = axis;
  const n = Math.hypot(x, y, z);
  const s = Math.sin(angle / 2) / n;
  return [Math.cos(angle / 2), x * s, y * s, z * s];
};

export const qMul = (a: Quat, b: Quat): Quat => [
  a[0] * b[0] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3],
  a[0] * b[1] + a[1] * b[0] + a[2] * b[3] - a[3] * b[2],
  a[0] * b[2] - a[1] * b[3] + a[2] * b[0] + a[3] * b[1],
  a[0] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[0],
];

export const qConj = (q: Quat): Quat => [q[0], -q[1], -q[2], -q[3]];

export const qNormalize = (q: Quat): Quat => {
  const n = Math.hypot(...q);
  return [q[0] / n, q[1] / n, q[2] / n, q[3] / n];
};

export const qSlerp = (a: Quat, b: Quat, t: number): Quat => {
  let cos = a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3];
  let bb = b;
  if (cos < 0) {
    cos = -cos;
    bb = [-b[0], -b[1], -b[2], -b[3]];
  }
  if (cos > 0.9995) {
    return qNormalize([
      a[0] + (bb[0] - a[0]) * t,
      a[1] + (bb[1] - a[1]) * t,
      a[2] + (bb[2] - a[2]) * t,
      a[3] + (bb[3] - a[3]) * t,
    ]);
  }
  const th = Math.acos(cos);
  const s = Math.sin(th);
  const wa = Math.sin((1 - t) * th) / s;
  const wb = Math.sin(t * th) / s;
  return [
    a[0] * wa + bb[0] * wb,
    a[1] * wa + bb[1] * wb,
    a[2] * wa + bb[2] * wb,
    a[3] * wa + bb[3] * wb,
  ];
};

export const qRotate = (q: Quat, v: Vec3): Vec3 => {
  // v' = q v q*
  const [w, x, y, z] = q;
  const [vx, vy, vz] = v;
  const tx = 2 * (y * vz - z * vy);
  const ty = 2 * (z * vx - x * vz);
  const tz = 2 * (x * vy - y * vx);
  return [
    vx + w * tx + (y * tz - z * ty),
    vy + w * ty + (z * tx - x * tz),
    vz + w * tz + (x * ty - y * tx),
  ];
};

const deg = Math.PI / 180;

/** Named orientations used by the storyboard. */
export const POSES: Record<string, Quat> = {
  faceOn: qIdentity,
  // Rz(45°) first, then Rx(arctan √2): the body diagonal (1,1,1) ends up vertical.
  cornerOn: qMul(qAxisAngle([1, 0, 0], Math.atan(Math.SQRT2)), qAxisAngle([0, 0, 1], 45 * deg)),
  // An unremarkable orientation, to show the rule is not special to symmetric poses.
  generic: qMul(qAxisAngle([0, 1, 0], 22 * deg), qMul(qAxisAngle([1, 0, 0], 38 * deg), qAxisAngle([0, 0, 1], 17 * deg))),
};

/** Light direction expressed in the cube's own frame: u = Rᵀ ẑ. */
export const lightInCubeFrame = (q: Quat): Vec3 => qRotate(qConj(q), [0, 0, 1]);

/** Exact shadow area of a unit cube (side 1) under vertical light. */
export const cubeShadowArea = (q: Quat): number => {
  const u = lightInCubeFrame(q);
  return Math.abs(u[0]) + Math.abs(u[1]) + Math.abs(u[2]);
};

// ---------------------------------------------------------------- 2D hull

export const convexHull = (pts: Vec2[]): Vec2[] => {
  const p = [...pts].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  if (p.length < 3) return p;
  const cross = (o: Vec2, a: Vec2, b: Vec2) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lower: Vec2[] = [];
  for (const pt of p) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], pt) <= 1e-12) lower.pop();
    lower.push(pt);
  }
  const upper: Vec2[] = [];
  for (let i = p.length - 1; i >= 0; i--) {
    const pt = p[i];
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], pt) <= 1e-12) upper.pop();
    upper.push(pt);
  }
  upper.pop();
  lower.pop();
  return lower.concat(upper); // counter-clockwise
};

export const polygonArea = (poly: Vec2[]): number => {
  let a = 0;
  for (let i = 0; i < poly.length; i++) {
    const [x1, y1] = poly[i];
    const [x2, y2] = poly[(i + 1) % poly.length];
    a += x1 * y2 - x2 * y1;
  }
  return Math.abs(a) / 2;
};

// ---------------------------------------------------------------- cube

export const CUBE_CORNERS: Vec3[] = [];
for (const x of [-0.5, 0.5]) for (const y of [-0.5, 0.5]) for (const z of [-0.5, 0.5]) CUBE_CORNERS.push([x, y, z]);

/** The 6 faces as (outward normal, 4 corners in order). Order matches three.js BoxGeometry groups: +x, -x, +y, -y, +z, -z. */
export const CUBE_FACES: { normal: Vec3; corners: Vec3[] }[] = (() => {
  const faces: { normal: Vec3; corners: Vec3[] }[] = [];
  for (const axis of [0, 1, 2]) {
    for (const sign of [1, -1]) {
      const normal: Vec3 = [0, 0, 0];
      normal[axis] = sign;
      const a = (axis + 1) % 3;
      const b = (axis + 2) % 3;
      const corners: Vec3[] = [];
      for (const [sa, sb] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
        const c: Vec3 = [0, 0, 0];
        c[axis] = sign * 0.5;
        c[a] = sa * 0.5;
        c[b] = sb * 0.5;
        corners.push(c);
      }
      faces.push({ normal, corners });
    }
  }
  return faces;
})();

/** Shadow polygon (convex hull of projected points) on the floor, for points in body frame placed at `center` with pose q. */
export const shadowPolygon = (q: Quat, bodyPoints: Vec3[], center: Vec3 = [0, 0, 0]): Vec2[] =>
  convexHull(bodyPoints.map((p) => {
    const r = qRotate(q, p);
    return [r[0] + center[0], r[1] + center[1]] as Vec2;
  }));

/** Per-face data: world normal's z (= cos θ), and the face's floor projection. */
export const faceProjections = (q: Quat, center: Vec3) =>
  CUBE_FACES.map((f) => {
    const n = qRotate(q, f.normal);
    const world = f.corners.map((c) => {
      const r = qRotate(q, c);
      return [r[0] + center[0], r[1] + center[1], r[2] + center[2]] as Vec3;
    });
    return { cos: n[2], world, floor: world.map((w) => [w[0], w[1]] as Vec2) };
  });

// ---------------------------------------------------------------- randomness

export const mulberry32 = (seed: number) => () => {
  seed |= 0;
  seed = (seed + 0x6d2b79f5) | 0;
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};

/** Uniformly random rotation (Shoemake 1992). */
export const randomQuat = (rand: () => number): Quat => {
  const u1 = rand(), u2 = rand(), u3 = rand();
  const a = Math.sqrt(1 - u1), b = Math.sqrt(u1);
  return [a * Math.sin(2 * Math.PI * u2), a * Math.cos(2 * Math.PI * u2), b * Math.sin(2 * Math.PI * u3), b * Math.cos(2 * Math.PI * u3)];
};

export type Tumble = { quats: Quat[]; areas: number[]; runningMean: number[] };

export const makeTumble = (seed: number, n: number): Tumble => {
  const rand = mulberry32(seed);
  const quats: Quat[] = [];
  const areas: number[] = [];
  const runningMean: number[] = [0];
  let sum = 0;
  for (let i = 0; i < n; i++) {
    const q = randomQuat(rand);
    quats.push(q);
    const a = cubeShadowArea(q);
    areas.push(a);
    sum += a;
    runningMean.push(sum / (i + 1)); // runningMean[k] = mean of first k samples
  }
  return { quats, areas, runningMean };
};

// ---------------------------------------------------------------- cube → sphere

export const SPHERE_R = Math.sqrt(6 / (4 * Math.PI)); // same surface area as the unit cube (6)

/** Morph a point on the unit cube's surface toward the sphere of radius SPHERE_R. */
export const morphPoint = (p: Vec3, t: number): Vec3 => {
  const n = Math.hypot(p[0], p[1], p[2]);
  const s = SPHERE_R / n;
  return [p[0] * (1 - t + t * s), p[1] * (1 - t + t * s), p[2] * (1 - t + t * s)];
};

const sub = (a: Vec3, b: Vec3): Vec3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const crossV = (a: Vec3, b: Vec3): Vec3 => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];

/** A gridded cube surface: per face (n+1)² points and 2n² triangles. */
export const cubeSurfaceGrid = (n: number) => {
  const pts: Vec3[] = [];
  const tris: [number, number, number][] = [];
  for (const f of CUBE_FACES) {
    const [c0, c1, , c3] = f.corners;
    const base = pts.length;
    // keep triangles counter-clockwise seen from outside (so back-face culling works)
    const e1 = sub(c1, c0), e3 = sub(c3, c0), cr = crossV(e1, e3);
    const outward = cr[0] * f.normal[0] + cr[1] * f.normal[1] + cr[2] * f.normal[2] > 0;
    for (let i = 0; i <= n; i++)
      for (let j = 0; j <= n; j++) {
        const u = i / n, v = j / n;
        pts.push([
          c0[0] + (c1[0] - c0[0]) * u + (c3[0] - c0[0]) * v,
          c0[1] + (c1[1] - c0[1]) * u + (c3[1] - c0[1]) * v,
          c0[2] + (c1[2] - c0[2]) * u + (c3[2] - c0[2]) * v,
        ]);
      }
    for (let i = 0; i < n; i++)
      for (let j = 0; j < n; j++) {
        const a = base + i * (n + 1) + j;
        const b = a + n + 1;
        if (outward) tris.push([a, b, b + 1], [a, b + 1, a + 1]);
        else tris.push([a, b + 1, b], [a, a + 1, b + 1]);
      }
  }
  return { pts, tris };
};


export const surfaceArea = (pts: Vec3[], tris: [number, number, number][]) =>
  tris.reduce((s, [a, b, c]) => s + Math.hypot(...crossV(sub(pts[b], pts[a]), sub(pts[c], pts[a]))) / 2, 0);

/** Evenly spread unit directions (Fibonacci sphere). */
export const fibonacciDirections = (n: number): Vec3[] => {
  const out: Vec3[] = [];
  const ga = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < n; i++) {
    const z = 1 - (2 * (i + 0.5)) / n;
    const r = Math.sqrt(1 - z * z);
    out.push([r * Math.cos(ga * i), r * Math.sin(ga * i), z]);
  }
  return out;
};

/** Shadow area of a point set when light comes along direction d (orthographic). */
export const shadowAreaAlong = (pts: Vec3[], d: Vec3): number => {
  const helper: Vec3 = Math.abs(d[2]) < 0.9 ? [0, 0, 1] : [1, 0, 0];
  const a = crossV(d, helper);
  const an = Math.hypot(...a);
  const e1: Vec3 = [a[0] / an, a[1] / an, a[2] / an];
  const e2 = crossV(d, e1);
  return polygonArea(convexHull(pts.map((p) => [p[0] * e1[0] + p[1] * e1[1] + p[2] * e1[2], p[0] * e2[0] + p[1] * e2[1] + p[2] * e2[2]] as Vec2)));
};

/** Mean shadow over many directions, and the surface area, for the shape at morph t. */
export const morphStats = (() => {
  const grid = cubeSurfaceGrid(20);
  const dirs = fibonacciDirections(256);
  const cache = new Map<number, { surface: number; meanShadow: number }>();
  return (t: number) => {
    const key = Math.round(t * 200) / 200;
    const hit = cache.get(key);
    if (hit) return hit;
    const pts = grid.pts.map((p) => morphPoint(p, key));
    const surface = surfaceArea(pts, grid.tris);
    const meanShadow = dirs.reduce((s, d) => s + shadowAreaAlong(pts, d), 0) / dirs.length;
    const res = { surface, meanShadow };
    cache.set(key, res);
    return res;
  };
})();
