# Spike storyboard — "The average shadow of a cube"

Shared by spike A (`spikes/stage_a`, HTML beats → Chromium layout → Manim) and
spike C (`spikes/remotion_c`, Remotion/React + three.js). Same lesson, same
beats, so the two renderers can be compared side by side.

Goal: a ~55 s silent explainer (captions carry the narration). It should look
cinematic (kinetic typography, morphing shapes, 3D, camera moves, transitions),
but every effect has to carry the math. The viewer should come away with:

1. A shadow (light straight down) is an orthographic projection onto the floor.
2. Its area depends on orientation: face-on = 1 (side s = 1), corner-on = √3 ≈ 1.73.
3. Why: shadow = ½ Σ A_i |cos θ_i| (top faces cover the shadow once, bottom faces once more).
4. Averaged over random orientations, |cos θ| averages to ½ → mean shadow = ¼ × surface area = 6/4 = 1.5.
5. The same holds for every convex shape (Cauchy's formula); a sphere checks it: πr² = ¼·4πr².

## Math (exact, use it for live readouts)

- Cube side s = 1 (visual size is free). Rotation R; light direction in cube frame u = Rᵀ·ẑ.
  Shadow area = |u_x| + |u_y| + |u_z|. Face-on (R = I) → 1.
- Corner-on: Rz(45°) then Rx(arctan √2 ≈ 54.7356°) → diagonal points up → area √3.
- Shadow polygon = convex hull of the cube vertices projected to z = 0 (square ↔ hexagon, a true morph).
- Uniformly random rotations (random unit quaternions, seeded) → mean area → 1.5.

## Beats (≈ seconds)

| # | Beat | On screen | Caption / text |
|---|------|-----------|----------------|
| 1 | Hook (0–5) | Letterbox bars open. Kinetic title, words stagger in, "average shadow" highlighted. | **What is the average shadow of a cube?** |
| 2 | Setup (5–11) | Title shrinks to top-left. Floor, floating cube, parallel light rays from above, shadow on floor. Camera swoops from low front to ¾ elevated. | Light shines straight down. The shadow is the cube flattened onto the floor. |
| 3 | Face-on (11–16) | Card on the right: "Face-on", `A = s^2 = 1`, live readout "shadow area 1.00". | Face-on, the shadow is a square: area 1. |
| 4 | Corner-on (16–23) | Cube rotates onto a corner; shadow morphs square → hexagon live; readout climbs to 1.73; slow orbit. Card: "Corner-on", `A = \sqrt{3} \approx 1.73`. | Tip it onto a corner: a hexagon, √3 times bigger. |
| 5 | Why (23–31) | Faces tinted: up-facing warm, down-facing cool. Camera tilts toward top-down. Formula `\text{shadow} = \tfrac12 \sum_i A_i\,|\cos\theta_i|`. | Each face casts a tilted copy, area A·\|cos θ\|. Up faces cover the shadow once, down faces once more — so halve the sum. |
| 6 | Tumble (31–40) | Cube snaps through ~10 random orientations; live "n" and "mean" readouts, then fast-forward to n = 5000, mean → 1.50. Formula `\langle|\cos\theta|\rangle = \tfrac12`. | Tumble it randomly. Over all directions, \|cos θ\| averages to ½. |
| 7 | Payoff (40–46) | Cinematic wipe. Centre formula morphs `\tfrac12\cdot\tfrac12\sum A_i` → `\tfrac14\,\text{surface area}` → `\tfrac14\cdot 6 = 1.5`. Kinetic "¼ of the surface area". | Average shadow = ¼ of the surface area. |
| 8 | Generalize (46–53) | Cube morphs into a sphere; shadow becomes a disk; `\pi r^2 = \tfrac14\cdot 4\pi r^2`. Orbit. | True for every convex shape — Cauchy's formula. |
| 9 | End (53–56) | Summary card, letterbox closes. | Average shadow = ¼ × surface area. |

Style: dark background (#0e1116-ish), cube blue (#3b82f6-ish), shadow near-black with
a yellow (#facc15) outline, light rays faint yellow, accent yellow for highlighted words.
Font: Noto Sans. 1920×1080 or 1422×800 at 30 fps.
