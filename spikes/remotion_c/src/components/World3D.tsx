// The 3D layer. Draws whatever `worldAt(frame)` says: cube (or morphing solid),
// its exact shadow polygon, light rays that stop where they hit the solid,
// and the per-face floor projections used in the "why" beat.
import { ThreeCanvas } from "@remotion/three";
import { useThree } from "@react-three/fiber";
import React, { useMemo } from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import * as THREE from "three";
import { LineMaterial } from "three/examples/jsm/lines/LineMaterial.js";
import { LineSegments2 } from "three/examples/jsm/lines/LineSegments2.js";
import { LineSegmentsGeometry } from "three/examples/jsm/lines/LineSegmentsGeometry.js";
import { CUBE_FACES, SPHERE_R, cubeSurfaceGrid, morphPoint, qConj, qRotate, type Vec3 } from "../math/geometry";
import { CUBE_CENTER, worldAt, type WorldState } from "../timeline";
import { COLORS } from "../theme";

const C = (hex: string) => new THREE.Color(hex);

// --------------------------------------------------------------- camera
const CameraRig: React.FC<{ s: WorldState }> = ({ s }) => {
  const { camera, size } = useThree();
  const cam = camera as THREE.PerspectiveCamera;
  const az = (s.azTotal * Math.PI) / 180;
  const el = (s.el * Math.PI) / 180;
  const target = new THREE.Vector3(0, s.targetZ, 0);
  cam.fov = s.fov;
  cam.near = 0.1;
  cam.far = 100;
  cam.position.set(
    target.x + s.dist * Math.cos(el) * Math.sin(az),
    target.y + s.dist * Math.sin(el),
    target.z + s.dist * Math.cos(el) * Math.cos(az),
  );
  cam.lookAt(target);
  cam.setViewOffset(size.width, size.height, s.shiftX, 0, size.width, size.height);
  cam.updateProjectionMatrix();
  return null;
};

// --------------------------------------------------------------- thick lines helper
const useLines = (color: string, width: number, res: [number, number]) =>
  useMemo(() => {
    const mat = new LineMaterial({ color: C(color).getHex(), linewidth: width, transparent: true, depthWrite: false });
    mat.resolution.set(res[0], res[1]);
    const geo = new LineSegmentsGeometry();
    const obj = new LineSegments2(geo, mat);
    obj.frustumCulled = false;
    return { obj, mat, setSegments: (flat: number[]) => {
      const g = new LineSegmentsGeometry();
      g.setPositions(flat.length ? flat : [0, 0, 0, 0, 0, 0]);
      obj.geometry.dispose();
      obj.geometry = g;
    } };
  }, [color, width, res[0], res[1]]);

// --------------------------------------------------------------- the solid
const GRID = cubeSurfaceGrid(16);
const PER_FACE = GRID.pts.length / 6;

const Solid: React.FC<{ s: WorldState; res: [number, number] }> = ({ s, res }) => {
  const { geo, mats } = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(GRID.pts.length * 3), 3));
    g.setAttribute("normal", new THREE.BufferAttribute(new Float32Array(GRID.pts.length * 3), 3));
    g.setIndex(GRID.tris.flat());
    const trisPerFace = GRID.tris.length / 6;
    for (let f = 0; f < 6; f++) g.addGroup(f * trisPerFace * 3, trisPerFace * 3, f);
    const m = CUBE_FACES.map(() => new THREE.MeshStandardMaterial({ color: COLORS.cube, roughness: 0.55, metalness: 0.05, transparent: true }));
    return { geo: g, mats: m };
  }, []);
  const pos = geo.getAttribute("position") as THREE.BufferAttribute;
  const nor = geo.getAttribute("normal") as THREE.BufferAttribute;
  GRID.pts.forEach((p, i) => {
    const m = morphPoint(p, s.morph);
    pos.setXYZ(i, m[0], m[1], m[2]);
    const fn = CUBE_FACES[Math.floor(i / PER_FACE)].normal;
    const r = Math.hypot(...p);
    const n = new THREE.Vector3(
      (1 - s.morph) * fn[0] + (s.morph * p[0]) / r,
      (1 - s.morph) * fn[1] + (s.morph * p[1]) / r,
      (1 - s.morph) * fn[2] + (s.morph * p[2]) / r,
    ).normalize();
    nor.setXYZ(i, n.x, n.y, n.z);
  });
  pos.needsUpdate = true;
  nor.needsUpdate = true;
  geo.computeBoundingSphere();

  // face tint: up-facing warm, down-facing cool (strength ∝ |cos θ|)
  s.faces.forEach((f, i) => {
    const base = C(COLORS.cube);
    const target = C(f.cos > 0 ? COLORS.warm : COLORS.cool);
    const k = s.tint * Math.min(1, Math.abs(f.cos) * 1.6 + 0.25);
    mats[i].color.copy(base.lerp(target, k));
    mats[i].opacity = s.opacity;
    mats[i].depthWrite = s.opacity > 0.95;
  });

  // edges fade out as the cube rounds off
  const edges = useLines(COLORS.cubeEdge, 2.2, res);
  const flat: number[] = [];
  for (const a of [[-1, -1], [-1, 1], [1, -1], [1, 1]])
    for (let axis = 0; axis < 3; axis++) {
      const p0: Vec3 = [0, 0, 0], p1: Vec3 = [0, 0, 0];
      const o1 = (axis + 1) % 3, o2 = (axis + 2) % 3;
      p0[axis] = -0.5; p1[axis] = 0.5;
      p0[o1] = p1[o1] = a[0] * 0.5; p0[o2] = p1[o2] = a[1] * 0.5;
      flat.push(...p0, ...p1);
    }
  edges.setSegments(flat);
  edges.mat.opacity = Math.max(0, 1 - s.morph * 4) * (0.35 + 0.65 * s.opacity);

  const quat = new THREE.Quaternion(s.q[1], s.q[2], s.q[3], s.q[0]);
  return (
    <group position={CUBE_CENTER} quaternion={quat}>
      <mesh geometry={geo} material={mats} renderOrder={2} />
      <primitive object={edges.obj} renderOrder={3} />
    </group>
  );
};

// --------------------------------------------------------------- shadow
const Shadow: React.FC<{ s: WorldState; res: [number, number] }> = ({ s, res }) => {
  const shape = new THREE.Shape(s.shadowPoly.map(([x, y]) => new THREE.Vector2(x, y)));
  const geo = useMemo(() => new THREE.ShapeGeometry(shape), [s.t]);
  const outline = useLines(COLORS.accent, 3.2, res);
  const flat: number[] = [];
  s.shadowPoly.forEach((p, i) => {
    const q = s.shadowPoly[(i + 1) % s.shadowPoly.length];
    flat.push(p[0], p[1], 0.006, q[0], q[1], 0.006);
  });
  outline.setSegments(flat);
  outline.mat.opacity = s.shadow;
  return (
    <group>
      <mesh geometry={geo} position={[0, 0, 0.003]} renderOrder={1}>
        <meshBasicMaterial color={COLORS.shadow} transparent opacity={0.88 * s.shadow} depthWrite={false} />
      </mesh>
      <primitive object={outline.obj} renderOrder={1} />
    </group>
  );
};

// --------------------------------------------------------------- per-face projections ("tilted copies")
const WARM = ["#fb923c", "#f59e0b", "#ef4444"];
const COOL = ["#22d3ee", "#38bdf8", "#818cf8"];

const Tiles: React.FC<{ s: WorldState; res: [number, number] }> = ({ s, res }) => {
  const up = s.faces.map((f, i) => ({ f, i })).filter((x) => x.f.cos > 1e-6);
  const down = s.faces.map((f, i) => ({ f, i })).filter((x) => x.f.cos < -1e-6);
  const outline = useLines("#ffffff", 1.6, res);
  const flat: number[] = [];
  const meshes: React.ReactNode[] = [];
  const draw = (list: typeof up, progress: number, vis: number, palette: string[], lift: number) => {
    if (vis <= 0.001) return;
    list.forEach(({ f, i }, rank) => {
      const p = Math.min(1, Math.max(0, progress * 1.6 - rank * 0.3));
      const e = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
      const pts = f.world.map((w) => [w[0], w[1], w[2] + (lift + 0.002 * rank - w[2]) * e] as Vec3);
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.BufferAttribute(new Float32Array([...pts[0], ...pts[1], ...pts[2], ...pts[0], ...pts[2], ...pts[3]]), 3));
      meshes.push(
        <mesh key={`${palette[0]}${i}`} geometry={g} renderOrder={4}>
          <meshBasicMaterial color={palette[rank % 3]} transparent opacity={0.72 * vis} side={THREE.DoubleSide} depthWrite={false} depthTest={false} />
        </mesh>,
      );
      pts.forEach((a, k) => flat.push(...a, ...pts[(k + 1) % 4]));
    });
  };
  draw(up, s.tilesUp, s.tilesUpVis, WARM, 0.01);
  draw(down, s.tilesDown, s.tilesDownVis, COOL, 0.012);
  outline.setSegments(flat);
  outline.mat.opacity = Math.max(s.tilesUpVis, s.tilesDownVis) * 0.9;
  outline.mat.depthTest = false;
  return (
    <group>
      {meshes}
      <primitive object={outline.obj} renderOrder={5} />
    </group>
  );
};

// --------------------------------------------------------------- light rays
const RAY_TOP = 3.8;
const RAYS: [number, number][] = [];
for (let i = -5; i <= 5; i++) for (let j = -5; j <= 5; j++) if (Math.hypot(i, j) <= 5.2) RAYS.push([i * 0.27, j * 0.27]);

/** Height at which a vertical ray through (x, y) first hits the solid (or 0 for the floor). */
const rayStop = (s: WorldState, x: number, y: number) => {
  const o: Vec3 = [x - CUBE_CENTER[0], y - CUBE_CENTER[1], RAY_TOP - CUBE_CENTER[2]];
  // cube: slab test in the body frame
  const qi = qConj(s.q);
  const ob = qRotate(qi, o), d = qRotate(qi, [0, 0, -1]);
  let tmin = -Infinity, tmax = Infinity;
  for (let k = 0; k < 3; k++) {
    if (Math.abs(d[k]) < 1e-9) {
      if (Math.abs(ob[k]) > 0.5) { tmin = Infinity; break; }
      continue;
    }
    const t1 = (-0.5 - ob[k]) / d[k], t2 = (0.5 - ob[k]) / d[k];
    tmin = Math.max(tmin, Math.min(t1, t2));
    tmax = Math.min(tmax, Math.max(t1, t2));
  }
  const cubeHit = tmin <= tmax && tmin < Infinity ? RAY_TOP - tmin : null;
  // sphere
  const r2 = (x - CUBE_CENTER[0]) ** 2 + (y - CUBE_CENTER[1]) ** 2;
  const sphHit = r2 <= SPHERE_R ** 2 ? CUBE_CENTER[2] + Math.sqrt(SPHERE_R ** 2 - r2) : null;
  const m = s.morph;
  if (m < 0.001) return cubeHit ?? 0;
  if (m > 0.999) return sphHit ?? 0;
  // intermediate shapes: hit if inside the drawn shadow polygon
  const inside = pointInPoly([x, y], s.shadowPoly);
  if (!inside) return 0;
  return (cubeHit ?? sphHit ?? CUBE_CENTER[2]) * (1 - m) + (sphHit ?? cubeHit ?? CUBE_CENTER[2]) * m;
};

const pointInPoly = (p: [number, number], poly: [number, number][]) => {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if (yi > p[1] !== yj > p[1] && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi) c = !c;
  }
  return c;
};

const Rays: React.FC<{ s: WorldState; res: [number, number] }> = ({ s, res }) => {
  const beams = useLines(COLORS.ray, 1.3, res);
  const photons = useLines("#fde68a", 2.6, res);
  const fb: number[] = [], fp: number[] = [];
  RAYS.forEach(([x, y], i) => {
    const stop = rayStop(s, x, y);
    fb.push(x, y, RAY_TOP, x, y, stop + 0.004);
    const phase = ((s.t * 0.9 + ((i * 0.6180339) % 1)) % 1);
    const zTop = RAY_TOP - phase * (RAY_TOP - stop + 0.3);
    const zBot = Math.max(stop, zTop - 0.32);
    if (zTop > zBot + 0.02) fp.push(x, y, zTop, x, y, zBot);
  });
  beams.setSegments(fb);
  photons.setSegments(fp);
  beams.mat.opacity = 0.16 * s.rays;
  photons.mat.opacity = 0.6 * s.rays;
  return (
    <group>
      <primitive object={beams.obj} />
      <primitive object={photons.obj} />
    </group>
  );
};

// --------------------------------------------------------------- scene
export const World3D: React.FC<{ frameOffset: number }> = ({ frameOffset }) => {
  const frame = useCurrentFrame() + frameOffset;
  const { width, height } = useVideoConfig();
  const s = worldAt(frame);
  const res: [number, number] = [width, height];
  return (
    <div style={{ position: "absolute", inset: 0, filter: `blur(${s.blur.toFixed(2)}px) brightness(${s.reveal.toFixed(3)})` }}>
      <ThreeCanvas width={width} height={height} gl={{ antialias: true, preserveDrawingBuffer: true }} dpr={1}>
        <CameraRig s={s} />
        <color attach="background" args={[COLORS.bg]} />
        <fog attach="fog" args={[COLORS.bg, s.dist + 3, s.dist + 15]} />
        <hemisphereLight args={["#dbeafe", "#0b0f14", 0.9]} />
        <directionalLight position={[2.5, 8, 3.5]} intensity={1.7} />
        <directionalLight position={[-4, 2, -3]} intensity={0.35} />
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.001, 0]}>
          <planeGeometry args={[60, 60]} />
          <meshStandardMaterial color={COLORS.floor} roughness={1} />
        </mesh>
        <gridHelper args={[24, 48, COLORS.grid, COLORS.grid]} position={[0, 0.0005, 0]} />
        <group rotation={[-Math.PI / 2, 0, 0]}>
          <Shadow s={s} res={res} />
          <Tiles s={s} res={res} />
          <Rays s={s} res={res} />
          <Solid s={s} res={res} />
        </group>
      </ThreeCanvas>
    </div>
  );
};
