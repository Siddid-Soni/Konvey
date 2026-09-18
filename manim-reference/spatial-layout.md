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
