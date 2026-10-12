# ManimGL Spatial Layout (paper predicates -> real calls)

> Paper `2509.04481 Sec 3.2 + 3.5` uses symbolic `above/below/at left of/at right of/on top of` + offsets `(-3,0)/(+3,0)/(0,-3)/(0,+3)/overlap`. Below is how Agent 2 must compile each to `manimlib/mobject/mobject.py` calls.

## Ops

| op | call | example from `3b1b/videos` |
|---|---|---|
| `next_to` | `a.next_to(b, UP/DOWN/LEFT/RIGHT, buff=0.5)` | `answer.next_to(phrase_mob, DOWN, buff=0.5)` (attention.py), `question.next_to(rect, UP)` (mlp.py) |
| `to_edge` | `a.to_edge(UP/DOWN/LEFT/RIGHT, buff=0.25)` | `thumbnails.to_edge(UP, buff=0.25)` (mlp.py) |
| `to_corner` | `a.to_corner(UL/UR/DL/DR)` | corner labels |
| `move_to` | `a.move_to(b)` / `a.move_to(2*UP)` | `phrase_mob.move_to(2*UP)` (attention.py) |
| `arrange` | `g.arrange(RIGHT/DOWN/OUT, buff=0.5)` | `blocks.arrange(OUT, buff=0.5)` (mlp.py) |
| `arrange_in_grid` / `arrange_to_fit_width` | grid fit | `subgroup.arrange_to_fit_width(w)` (attention.py) |
| `align_to` / `match_x/match_y/match_height` | alignment | `rect.match_y(phrase)` (attention.py) |
| `shift` / `scale` | `a.shift(4*LEFT)`, `a.scale(0.5)` | `att_blocks.shift(4*LEFT)` (mlp.py) |
| `frame_reorient` | `frame.animate.reorient(theta,phi,gamma,center,height)` | `frame.animate.reorient(-32,0,0,(0.56,2.48,0.32),12.75)` (mlp.py) |
| `target` | `m.target=m.generate_target(); ...become(...); MoveToTarget(m)` | `emb_arrows.target=...; MoveToTarget(emb_arrows)` (attention.py) |

## Predicate mapping (Agent 2 must do this)

- `A above B` -> `A.next_to(B, UP, buff=...)`
- `A below B` -> `A.next_to(B, DOWN, buff=...)`
- `A at left of B` -> `A.next_to(B, LEFT, ...)` or `A.shift(LEFT)` / `to_edge(LEFT)`
- `A at right of B` -> `RIGHT` variant
- `A on top of B` -> `A.move_to(B)` + layer order (add after)

Normalize open language first: `contains -> on top of`, `stands near -> at left/right of` (paper Sec 3.2 + human verify).

## Screen budget (hard rules — the layout check enforces these)

The frame is 14.22 x 8 units, centered at ORIGIN. Everything must stay inside x ∈ [-6.96, 6.96], y ∈ [-3.85, 3.85]. After every `self.wait()` the scene is executed and measured: text touching text, text drawn over lines/curves, and anything off-frame are errors that get sent back for repair.

**1. Place groups into regions, not into `next_to` chains.** Long chains (`b.next_to(a)`, `c.next_to(b)`, …) drift off-frame because nobody knows how big `a` is. Anchor each top-level group to a region and shrink it to fit:

| region | center | max width × height | use for |
|---|---|---|---|
| `TITLE` | `3.3*UP` | 13 × 0.9 | heading / question |
| `MAIN` | `0.3*DOWN` | 12 × 5.0 | the one main visual when it is alone |
| `LEFT` | `3.4*LEFT + 0.3*DOWN` | 6.2 × 5.0 | visual in a two-panel beat |
| `RIGHT` | `3.4*RIGHT + 0.3*DOWN` | 6.2 × 5.0 | formula / labels / second visual |
| `CAPTION` | `3.3*DOWN` | 13 × 0.9 | one-line takeaway |

```python
REGIONS = {
    "TITLE": (3.3 * UP, 13, 0.9), "MAIN": (0.3 * DOWN, 12, 5.0),
    "LEFT": (3.4 * LEFT + 0.3 * DOWN, 6.2, 5.0), "RIGHT": (3.4 * RIGHT + 0.3 * DOWN, 6.2, 5.0),
    "CAPTION": (3.3 * DOWN, 13, 0.9),
}

def place(mob, region):
    center, w, h = REGIONS[region]
    mob.set_max_width(w).set_max_height(h).move_to(center)
    return mob
```

One group per region at a time. `next_to` is still right for *attached* things (a label next to its bar, a brace under its formula) — but only one hop from an object that was itself placed in a region.

**2. Object lifecycle: every beat cleans up.** Anything the current VO line does not talk about gets `FadeOut` (or `FadeTransform` into the next thing) before new objects take its region. Aim for ≤ 6 independent groups on screen.

**3. Labels never sit on drawings.** Put a label `next_to(target, direction, buff=0.25)` toward empty space, never `move_to` a point on a curve/axis. If it must overlap, call `label.add_background_rectangle()`.

**4. Text sizing.** `font_size >= 24` for anything the viewer must read; size long text with `set_max_width(...)`, not `scale(...)`. A `VGroup` of texts must be `arrange(...)`d or `arrange_in_grid(...)`d — never left stacked at the origin.

**5. Agent 2: name things once.** The names used in `objects`, `spatial_predicates` and `layout[].args` must be the same identifiers (e.g. `balls`, not `many_balls` in one place and `balls` in another), and each beat's layout should say which region a new group goes to (`place(balls, "MAIN")`).
