// Turns the declarative storyboard into a pure function: time → world state.
// Both the 3D layer and the HTML readouts call `worldAt(frame)`, so every
// number on screen is computed from the same geometry that is drawn.
import { BEATS, FPS, TOTAL_SECONDS, type PoseName, type ReadoutName, type WorldKey, type WorldProps } from "./storyboard";
import {
  CUBE_CORNERS, POSES, type Quat, type Vec2, type Vec3, cubeShadowArea, cubeSurfaceGrid, faceProjections, makeTumble,
  morphPoint, morphStats, polygonArea, qAxisAngle, qIdentity, qMul, qSlerp, shadowPolygon,
} from "./math/geometry";

export const CUBE_CENTER: Vec3 = [0, 0, 1.3];

type NumProp = Exclude<keyof WorldProps, "pose">;
const DEFAULTS: Required<Omit<WorldProps, "pose">> = {
  az: 0, el: 20, dist: 8, fov: 34, targetZ: 0.8, shiftX: 0, orbit: 0, spin: 0, reveal: 1, blur: 0, rays: 0, shadow: 0,
  tint: 0, opacity: 1, tilesUp: 0, tilesUpVis: 0, tilesDown: 0, tilesDownVis: 0, morph: 0,
};

const easeInOut = (x: number) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
const clamp01 = (x: number) => Math.min(1, Math.max(0, x));

type Seg<T> = { t0: number; dur: number; to: T };

const keys: (WorldKey & { abs: number })[] = BEATS.flatMap((b) => (b.world ?? []).map((k) => ({ ...k, abs: b.start + k.at })));

const buildTrack = <T,>(get: (k: WorldKey) => T | undefined): Seg<T>[] =>
  keys
    .filter((k) => get(k) !== undefined)
    .map((k) => ({ t0: k.abs, dur: k.dur ?? 1, to: get(k) as T }))
    .sort((a, b) => a.t0 - b.t0);

const evalTrack = <T,>(segs: Seg<T>[], t: number, def: T, mix: (a: T, b: T, e: number) => T, upto = segs.length): T => {
  let v = def;
  for (let i = 0; i < upto; i++) {
    const s = segs[i];
    if (t < s.t0) break;
    const from = i === 0 ? def : evalTrack(segs, s.t0, def, mix, i);
    const e = s.dur <= 0 ? 1 : easeInOut(clamp01((t - s.t0) / s.dur));
    v = mix(from, s.to, e);
  }
  return v;
};

const lerp = (a: number, b: number, e: number) => a + (b - a) * e;
const numTracks = Object.fromEntries(
  (Object.keys(DEFAULTS) as NumProp[]).map((p) => [p, buildTrack<number>((k) => k[p])]),
) as Record<NumProp, Seg<number>[]>;
const poseTrack = buildTrack<PoseName>((k) => k.pose);

const num = (p: NumProp, t: number) => evalTrack(numTracks[p], t, DEFAULTS[p], lerp);

// ---- continuous orbit / spin = integral of the keyframed angular speeds
const NFRAMES = Math.ceil(TOTAL_SECONDS * FPS) + 2;
const integrate = (p: "orbit" | "spin") => {
  const out = new Float64Array(NFRAMES);
  for (let f = 1; f < NFRAMES; f++) out[f] = out[f - 1] + num(p, (f - 0.5) / FPS) / FPS;
  return out;
};
const orbitDeg = integrate("orbit");
const spinDeg = integrate("spin");

// ---- tumble
const tumbleKey = keys.find((k) => k.tumble);
const tumbleSpec = tumbleKey?.tumble;
const tumble = tumbleSpec ? makeTumble(tumbleSpec.seed, tumbleSpec.nMax) : undefined;
const tumbleEnd = tumbleKey ? (poseTrack.find((s) => s.t0 > tumbleKey.abs)?.t0 ?? Infinity) : -Infinity;

const posePlain = (t: number): Quat =>
  evalTrack<Quat>(poseTrack.map((s) => ({ ...s, to: POSES[s.to] })), t, qIdentity, qSlerp);

export type TumbleState = { n: number; mean: number; progress: number };

const tumbleAt = (t: number): { q: Quat; info: TumbleState } | undefined => {
  if (!tumbleKey || !tumbleSpec || !tumble || t < tumbleKey.abs || t >= tumbleEnd) return undefined;
  const { steps, stepDur, ffDur, nMax } = tumbleSpec;
  const tau = t - tumbleKey.abs;
  if (tau < steps * stepDur) {
    const k = Math.floor(tau / stepDur);
    const frac = (tau - k * stepDur) / stepDur;
    const prev = k === 0 ? posePlain(tumbleKey.abs) : tumble.quats[k - 1];
    const snap = clamp01(frac / 0.45);
    const n = k + (snap >= 1 ? 1 : 0);
    return { q: qSlerp(prev, tumble.quats[k], easeInOut(snap)), info: { n, mean: tumble.runningMean[n], progress: 0 } };
  }
  const p = clamp01((tau - steps * stepDur) / ffDur);
  const n = Math.round(steps * Math.pow(nMax / steps, easeInOut(p)));
  return { q: tumble.quats[n - 1], info: { n, mean: tumble.runningMean[n], progress: p } };
};

export const TUMBLE = tumble;

// ---- the state
const grid = cubeSurfaceGrid(16);

export type WorldState = Required<Omit<WorldProps, "pose">> & {
  t: number;
  q: Quat;
  azTotal: number;
  tumble?: TumbleState;
  faces: ReturnType<typeof faceProjections>;
  shadowPoly: Vec2[];
  readouts: Record<ReadoutName, number>;
};

const cache = new Map<number, WorldState>();

export const worldAt = (frame: number): WorldState => {
  const hit = cache.get(frame);
  if (hit) return hit;
  const t = frame / FPS;
  const p = Object.fromEntries((Object.keys(DEFAULTS) as NumProp[]).map((k) => [k, num(k, t)])) as Required<Omit<WorldProps, "pose">>;
  const fi = Math.max(0, Math.min(NFRAMES - 1, frame));
  const tb = tumbleAt(t);
  const base = tb ? tb.q : posePlain(t);
  const q = qMul(qAxisAngle([0, 0, 1], (spinDeg[fi] * Math.PI) / 180), base);
  const faces = faceProjections(q, CUBE_CENTER);
  const pts = p.morph > 0.0005 ? grid.pts.map((v) => morphPoint(v, p.morph)) : CUBE_CORNERS;
  const shadowPoly = shadowPolygon(q, pts, CUBE_CENTER);
  const upSum = faces.reduce((s, f) => s + Math.max(0, f.cos), 0);
  const downSum = faces.reduce((s, f) => s + Math.max(0, -f.cos), 0);
  const ms = morphStats(p.morph);
  const state: WorldState = {
    ...p,
    t,
    q,
    azTotal: p.az + orbitDeg[fi],
    tumble: tb?.info,
    faces,
    shadowPoly,
    readouts: {
      area: cubeShadowArea(q),
      hullArea: polygonArea(shadowPoly),
      upSum,
      downSum,
      halfSum: (upSum + downSum) / 2,
      n: tb?.info.n ?? 0,
      mean: tb?.info.mean ?? 0,
      surface: ms.surface,
      quarterSurface: ms.surface / 4,
      meanShadow: ms.meanShadow,
    },
  };
  cache.set(frame, state);
  return state;
};
