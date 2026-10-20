// ============================================================================
// THE STORYBOARD — the only file an author (human or LLM agent) edits per video.
//
// Everything below is plain data. Times are absolute seconds on the video
// timeline (beats) or seconds relative to the beat start (`world` keys,
// `card.at`, `center.stages[].at`). Components never hard-code content; they
// read this file. The 3D world is a single continuous "state machine": each
// `world` key eases some properties from their current value to a new one.
// ============================================================================

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

/** Named live quantities the readouts can show (computed from the real geometry each frame). */
export type ReadoutName =
  | "area" // |u_x|+|u_y|+|u_z| for the current pose
  | "hullArea" // shoelace area of the drawn shadow polygon
  | "upSum" // Σ over up-facing faces of A|cos θ|
  | "downSum" // Σ over down-facing faces of A|cos θ|
  | "halfSum" // ½ Σ over all faces
  | "n" // tumble: samples so far
  | "mean" // tumble: running mean of the shadow area
  | "surface" // surface area of the (morphing) solid
  | "quarterSurface"
  | "meanShadow"; // mean shadow of the (morphing) solid over 256 directions

export type PoseName = "faceOn" | "cornerOn" | "generic";

/** Properties of the 3D world that can be keyframed. Unset = keep current value. */
export type WorldProps = {
  // camera (degrees / world units). az: around the vertical, el: above the floor.
  az?: number;
  el?: number;
  dist?: number;
  fov?: number; // vertical field of view (deg); small fov + large dist ≈ orthographic (dolly zoom)
  targetZ?: number;
  shiftX?: number; // px: slide the framing left to make room for a card on the right
  orbit?: number; // deg/s continuous camera orbit
  spin?: number; // deg/s cube spin about the vertical (does not change the shadow area)
  pose?: PoseName;
  reveal?: number; // 0..1 world brightness
  blur?: number; // px, depth-of-field-ish blur of the whole world
  rays?: number; // 0..1 light ray visibility
  shadow?: number; // 0..1 shadow visibility
  tint?: number; // 0..1 colour faces by up (warm) / down (cool)
  opacity?: number; // cube opacity (to see the floor through it)
  tilesUp?: number; // 0 = on the cube, 1 = dropped onto the floor (projections of up faces)
  tilesUpVis?: number;
  tilesDown?: number;
  tilesDownVis?: number;
  morph?: number; // 0 = cube, 1 = sphere (same surface area)
};

export type WorldKey = WorldProps & {
  at: number; // seconds from beat start (may be negative)
  dur?: number; // seconds to ease in (default 1)
  tumble?: { seed: number; steps: number; stepDur: number; ffDur: number; nMax: number };
};

export type Card = {
  at?: number; // seconds from beat start the card enters (default 0.3)
  heading: string;
  tex?: string;
  readouts?: { label: string; value: ReadoutName; digits?: number }[];
  chart?: "runningMean";
};

export type Center = {
  stages: { at: number; tex: string }[]; // successive forms of one equation (each replaces the previous)
  kinetic?: { at: number; text: string; highlight: string[] };
  note?: { at: number; text: string };
};

export type SceneId = "world1" | "payoff" | "world2";

export type Beat = {
  id: string;
  start: number;
  end: number;
  scene: SceneId;
  caption?: string;
  card?: Card;
  center?: Center;
  world?: WorldKey[];
};

/** Scene order and the transition *into* each scene (centred on the boundary). */
export const SCENES: { id: SceneId; kind: "world" | "formula"; transitionIn?: { type: "wipe" | "iris"; dur: number } }[] = [
  { id: "world1", kind: "world" },
  { id: "payoff", kind: "formula", transitionIn: { type: "wipe", dur: 0.8 } },
  { id: "world2", kind: "world", transitionIn: { type: "iris", dur: 0.8 } },
];

export const TITLE = {
  lines: [["What", "is", "the"], ["average", "shadow", "of", "a", "cube?"]],
  highlight: ["average", "shadow"],
  shrinkAt: 5.2, // seconds: moves to the top-left corner
};

export const LETTERBOX = { open: [0, 1.2], close: [54.6, 56], bar: 64 };

export const BEATS: Beat[] = [
  {
    id: "hook",
    start: 0,
    end: 5,
    scene: "world1",
    world: [
      { at: 0, dur: 0, pose: "faceOn", spin: 30, reveal: 0.35, blur: 10, az: 0, el: 4, dist: 8.5, targetZ: 1.0, shadow: 0, rays: 0, opacity: 1 },
    ],
  },
  {
    id: "setup",
    start: 5,
    end: 11,
    scene: "world1",
    caption: "Light shines straight down. The shadow is the cube flattened onto the floor.",
    world: [
      { at: 0, dur: 1.5, reveal: 1, blur: 0 },
      { at: 0.3, dur: 4.2, az: 35, el: 30, dist: 6.4, targetZ: 0.75 },
      { at: 0, dur: 3, spin: 0 },
      { at: 1.5, dur: 1.2, rays: 1 },
      { at: 2.5, dur: 1.2, shadow: 1 },
    ],
  },
  {
    id: "faceOn",
    start: 11,
    end: 16,
    scene: "world1",
    caption: "Face-on, the shadow is a square: area 1.",
    card: { heading: "Face-on", tex: "A = s^2 = 1", readouts: [{ label: "shadow area", value: "area" }] },
    world: [{ at: 0, dur: 1.5, shiftX: 300, orbit: 3 }],
  },
  {
    id: "cornerOn",
    start: 16,
    end: 23,
    scene: "world1",
    caption: "Tip it onto a corner: a hexagon, √3 times bigger.",
    card: { heading: "Corner-on", tex: "A = \\sqrt{3} \\approx 1.73", readouts: [{ label: "shadow area", value: "area" }] },
    world: [
      { at: 0.4, dur: 3.6, pose: "cornerOn" },
      { at: 0.4, dur: 2, orbit: 9, el: 26 },
    ],
  },
  {
    id: "why",
    start: 23,
    end: 31,
    scene: "world1",
    caption: "Each face casts a tilted copy, area A·|cos θ|. Up faces cover the shadow once, down faces once more — so halve the sum.",
    card: {
      heading: "Why?",
      tex: "\\text{shadow} = \\tfrac12 \\sum_i A_i\\,|\\cos\\theta_i|",
      readouts: [
        { label: "up faces  Σ A|cos θ|", value: "upSum" },
        { label: "down faces  Σ A|cos θ|", value: "downSum" },
        { label: "½ Σ all faces", value: "halfSum" },
        { label: "shadow area", value: "hullArea" },
      ],
    },
    world: [
      { at: 0, dur: 2.0, el: 50, dist: 6.2, orbit: 0, tint: 1, rays: 0.2 },
      { at: 0.6, dur: 1.4, opacity: 0.42 },
      { at: 1.0, dur: 0.3, tilesUpVis: 1 },
      { at: 1.0, dur: 2.2, tilesUp: 1 },
      { at: 3.0, dur: 2.2, el: 88, dist: 15, fov: 14 }, // dolly-zoom to a near-orthographic top view: up faces sit exactly on their tiles
      { at: 5.0, dur: 0.6, tilesUpVis: 0 },
      { at: 5.0, dur: 0.3, tilesDownVis: 1 },
      { at: 5.0, dur: 1.4, tilesDown: 1 },
      { at: 6.4, dur: 1.6, pose: "generic" }, // any orientation: sums still match the shadow
    ],
  },
  {
    id: "tumble",
    start: 31,
    end: 40,
    scene: "world1",
    caption: "Tumble it randomly. Over all directions, |cos θ| averages to ½.",
    card: {
      heading: "Random tumbles",
      tex: "\\langle|\\cos\\theta|\\rangle = \\tfrac12",
      readouts: [
        { label: "tumbles n", value: "n", digits: 0 },
        { label: "mean shadow", value: "mean", digits: 3 },
      ],
      chart: "runningMean",
    },
    world: [
      { at: 0, dur: 1.4, el: 32, dist: 6.6, fov: 34, tint: 0, opacity: 1, tilesDownVis: 0, tilesUpVis: 0, rays: 1, orbit: 6 },
      { at: 0.8, tumble: { seed: 7, steps: 10, stepDur: 0.45, ffDur: 3.4, nMax: 5000 } },
    ],
  },
  {
    id: "payoff",
    start: 40,
    end: 46,
    scene: "payoff",
    caption: "Average shadow = ¼ of the surface area.",
    center: {
      stages: [
        { at: 0.4, tex: "\\overline{\\text{shadow}} = \\tfrac12 \\sum_i A_i\\,\\langle|\\cos\\theta_i|\\rangle" },
        { at: 1.7, tex: "\\overline{\\text{shadow}} = \\tfrac12\\cdot\\tfrac12 \\sum_i A_i" },
        { at: 3.0, tex: "\\overline{\\text{shadow}} = \\tfrac14\\,\\text{surface area}" },
        { at: 4.3, tex: "\\overline{\\text{shadow}} = \\tfrac14\\cdot 6 = 1.5" },
      ],
      kinetic: { at: 3.2, text: "¼ of the surface area", highlight: ["¼"] },
    },
  },
  {
    id: "generalize",
    start: 46,
    end: 53,
    scene: "world2",
    caption: "True for every convex shape — Cauchy's formula.",
    card: {
      at: 0.6,
      heading: "Any convex shape",
      tex: "\\pi r^2 = \\tfrac14\\cdot 4\\pi r^2",
      readouts: [
        { label: "surface area S", value: "surface" },
        { label: "¼ S", value: "quarterSurface" },
        { label: "mean shadow (256 directions)", value: "meanShadow" },
      ],
    },
    world: [
      {
        at: -1, dur: 0, pose: "generic", spin: 14, az: 20, el: 30, dist: 6.4, targetZ: 0.75, shiftX: 300, orbit: 8,
        tint: 0, opacity: 1, rays: 1, shadow: 1, reveal: 1, blur: 0, tilesUpVis: 0, tilesDownVis: 0, morph: 0,
      },
      { at: 1.2, dur: 3.8, morph: 1 },
    ],
  },
  {
    id: "end",
    start: 53,
    end: 56,
    scene: "world2",
    center: {
      stages: [{ at: 0.2, tex: "\\overline{\\text{shadow}} = \\tfrac14 \\times \\text{surface area}" }],
      note: { at: 0.6, text: "cube: 6 / 4 = 1.5     sphere: πr² = ¼ · 4πr²" },
    },
    world: [{ at: 0, dur: 1.5, shiftX: 0, reveal: 0.3, blur: 8, rays: 0.3 }],
  },
];

export const TOTAL_SECONDS = BEATS[BEATS.length - 1].end;
