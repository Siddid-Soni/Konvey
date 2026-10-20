| `plane` | a coordinate plane with arrows from the origin, seen through a matrix (linear maps, eigenvectors, the complex plane, the unit circle); laid out for you (see below) | `vectors="v:1,0; w:1,-1"` (name:x,y), `points="P:2,1"`, `lines="1,0; 1,1"` (lines through the origin along these directions), `matrix="3,1;0,2"` (row by row), `circle="true"` (unit circle), `angle="z:45"` (a point on the unit circle, degrees from +x), `projections="true"`, `theta="θ"` (the angle's label), `coords="true"`, `complex="true"`, `x="-4,4"` `y="-3,3"` (leave out: chosen to hold everything), `grid="none"` and `ticks="none"` (a clean plane for a geometric figure: a circle, a triangle, a path of points), `xlabel`/`ylabel` (axis names, maths), `size` (30); leave out `w`/`h`: alone in its box it grows into the room it is given |

**`<plane>`: the plan's `plane` object.** Write `vectors`/`points`/`matrix`/`angle` exactly as
planned. Vectors are always written **before** the matrix acts: `vectors="v:1,0" matrix="3,1;0,2"`
draws v where A sends it, (2, 1), with the plane's grid carried along and the original grid
faint behind. The renderer picks the range, the ticks and where every label goes; never position
anything yourself.

- Same plane `id` in every beat, so it moves instead of being redrawn: adding `matrix=` in a beat
  shows the whole plane being transformed (every grid line moves); dropping it moves it back;
  a vector whose coordinates change slides its tip; a new name fades in. `angle` changing from
  45 to 90 turns the point along the circle, and its projections follow.
- `lines` stay where they are when the matrix acts: draw a vector's own line (its span) to show
  that it is knocked off it, or that an eigenvector stays on it and only stretches.
- `coords="true"` writes each arrow's coordinates where it is drawn: `v=(2,1)`.
- `angle="e^{i\theta}:45"` names the point (LaTeX allowed); `projections="true"` adds its legs
  `cos θ` along the real axis and `sin θ` up to the point; `complex="true"` labels the axes Re/Im
  and the vertical ticks `i`, `2i`. Names are the labels on screen, written as maths: `v`, `Av`, `e_1`, `\lambda v` (never ids like `p11`).
- Keep the matrix itself readable beside it with a `<tex>` (`A=\begin{pmatrix}2&1\\1&2\end{pmatrix}`).
