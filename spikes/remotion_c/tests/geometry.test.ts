import { expect, test } from "bun:test";
import { POSES, cubeShadowArea, shadowPolygon, polygonArea, CUBE_CORNERS, makeTumble, morphStats, faceProjections, mulberry32, randomQuat } from "../src/math/geometry";

test("face-on = 1, corner-on = √3", () => {
  expect(cubeShadowArea(POSES.faceOn)).toBeCloseTo(1, 9);
  expect(cubeShadowArea(POSES.cornerOn)).toBeCloseTo(Math.sqrt(3), 9);
  expect(shadowPolygon(POSES.faceOn, CUBE_CORNERS).length).toBe(4);
  expect(shadowPolygon(POSES.cornerOn, CUBE_CORNERS).length).toBe(6);
});

test("hull area equals |ux|+|uy|+|uz| and ½Σ A|cosθ|", () => {
  const r = mulberry32(3);
  for (let i = 0; i < 200; i++) {
    const q = randomQuat(r);
    const hull = polygonArea(shadowPolygon(q, CUBE_CORNERS));
    expect(hull).toBeCloseTo(cubeShadowArea(q), 9);
    const half = faceProjections(q, [0, 0, 0]).reduce((s, f) => s + Math.abs(f.cos), 0) / 2;
    expect(half).toBeCloseTo(hull, 9);
  }
});

test("tumble mean → 1.5", () => {
  const t = makeTumble(7, 5000);
  console.log("mean@10", t.runningMean[10], "mean@5000", t.runningMean[5000]);
  expect(Math.abs(t.runningMean[5000] - 1.5)).toBeLessThan(0.01);
});

test("Cauchy along the morph", () => {
  for (const m of [0, 0.5, 1]) {
    const s = morphStats(m);
    console.log(m, s);
    expect(s.meanShadow).toBeCloseTo(s.surface / 4, 2);
  }
});
