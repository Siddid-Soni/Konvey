---
genre: linear-maps
kinds: plane, tex
topic_keywords: eigenvector, eigenvectors, eigenvalue, eigenvalues, eigen
---
### Example: a matrix acting on the plane (topic: eigenvectors of [[2,1],[1,2]])

SCENE_SPEC (abridged): beats = [
 {vo_line: "Take v, one step along x. Its line is the x-axis.", objects: [{id: pl, kind: plane, data: {vectors: {v: [1, 0]}, lines: [[1, 0]]}}, {id: A, kind: tex, data: {tex: "A=\\begin{pmatrix}2&1\\\\1&2\\end{pmatrix}"}}]},
 {vo_line: "Apply A: the whole plane moves, and v lands at 2, 1, knocked off its line.", objects: [{id: pl, kind: plane, data: {vectors: {v: [1, 0]}, lines: [[1, 0]], matrix: [[2, 1], [1, 2]]}}]},
 {vo_line: "Undo it, and look at two other directions: 1, 1 and 1, minus 1.", objects: [{id: pl, kind: plane, data: {vectors: {e_1: [1, 1], e_2: [1, -1]}, lines: [[1, 1], [1, -1]]}}]},
 {vo_line: "Apply A again. e1 stays on its line, stretched by 3; e2 stays put, stretched by 1.", objects: [{id: pl, kind: plane, data: {vectors: {e_1: [1, 1], e_2: [1, -1]}, lines: [[1, 1], [1, -1]], matrix: [[2, 1], [1, 2]]}}, {id: A, kind: tex, data: {tex: "A e_1 = 3 e_1 \\qquad A e_2 = 1 e_2"}}]} ]

```html
<beats>
<beat vo="Take v, one step along x. Its line is the x-axis." t="1.6" shot="derive">
  <plane id="pl" vectors="v:1,0" lines="1,0" coords="true"></plane>
  <tex id="A">A=\begin{pmatrix}2&1\\1&2\end{pmatrix}</tex>
</beat>

<beat vo="Apply A: the whole plane moves, and v lands at 2, 1, knocked off its line." t="2.6" shot="derive">
  <plane id="pl" vectors="v:1,0" lines="1,0" matrix="2,1;1,2" coords="true"></plane>
  <tex id="A">A=\begin{pmatrix}2&1\\1&2\end{pmatrix}</tex>
</beat>

<beat vo="Undo it, and look at two other directions: 1, 1 and 1, minus 1." t="2.2" shot="derive">
  <plane id="pl" vectors="e_1:1,1; e_2:1,-1" lines="1,1; 1,-1" coords="true"></plane>
  <tex id="A">A=\begin{pmatrix}2&1\\1&2\end{pmatrix}</tex>
</beat>

<beat vo="Apply A again. e1 stays on its line, stretched by 3; e2 stays put, stretched by 1." t="2.8" shot="derive">
  <plane id="pl" vectors="e_1:1,1; e_2:1,-1" lines="1,1; 1,-1" matrix="2,1;1,2" coords="true"></plane>
  <tex id="A">A e_1 = 3 e_1 \qquad A e_2 = 1 e_2</tex>
</beat>
</beats>
```

Why it works: one `plane` id in every beat, and the vectors are always written as they were
before the matrix acts. Adding `matrix=` is the whole animation: the grid, the arrows and their
coordinates move to where A sends them, while the `lines` stay put, so v visibly leaves its line
and the eigenvectors visibly stay on theirs, one three times longer. Dropping the matrix in the
third beat moves the plane back before the new vectors are tested. The renderer chose one range
for the scene (it holds (3, 3)), the ticks and every label's place; the matrix itself stays
readable in a `<tex>` beside it (`derive`).
