| `dots` | points of a picture, at its own coordinates, each with an optional name or number (where something lands, the corners of a figure, the steps of a run); other marks name them `id.k`; takes no room in the layout | `on` (the picture), `at="x,y; x,y"`, `labels="A,,C"` (blank skips one; `|` between them when a name has a comma: `"12,367 books|91,380 books"`) or `numbered="true"`, `color` (accent), `dim="true"`, `size` |

### Marks on a picture: building it up step by step (`dots`, `path`, `arc`, `angle`, `brace on`, `note`)

3Blue1Brown builds a scene by adding to **one** picture at its own coordinates: dots where things
land, a path through them, an arc between two, the angle at a corner, a brace along a side, a note
with an arrow to the spot the line is about. These tags do that on any picture with coordinates:

| `on=` picture | its coordinates |
|---|---|
| `plane` | `x,y` as on its axes |
| `plot` | `x,y` as on its axes |
| `numberline` | `x,0` (a point on the line); `x,0.5` half a unit above it |
| `draw` | `x,y` in its own `x`/`y` ranges (the shapes' coordinates) |
| `grid` | `row,col` of a cell's centre (fractions fall between cells: `-0.5,0` is the top edge) |

- A point is written `x,y`, or as a point of a `<dots>` in the same beat: `hits.3` (the third),
  `hits.2-5` (second to fifth), `hits` (all). Put the points the plan gives in a `<dots>` once and
  name them everywhere else, so every mark hangs off the same exact points.
- **One step per beat.** Keep the ids and add one mark per line (the path one point longer, the
  angle, then the arc); a mark the line has moved past gets `dim="true"` instead of vanishing. A
  `path` whose `through` grows draws only its new stretch.
- Marks are drawn after the layout, so their lines and words keep their size however big the
  picture grows; never shrink or move them yourself, and never draw these with `<draw>`.
