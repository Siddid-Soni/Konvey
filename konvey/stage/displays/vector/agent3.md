| `vector` | a list of numbers in square brackets, a column (or a row), with an optional name beside it: an embedding, a state, a gradient, a velocity, coordinates, a distribution, the result of a matrix times a vector | `values="0.9,-0.4,0.2"` (1–8 entries; `\|` between them if one has a comma; `?` for not known yet), `label="\vec{E}"` (a name written before it with `=`, or under it when the vector is a term of a formula row; LaTeX allowed), `orient="column"` (default) / `"row"`, `highlight="0,2"` (entries lit: the ones the narration is reading), `color`, `size` |

**Vectors** (`<vector>`): keep the id across beats and change `values`: entries that keep their
number stay still; a changed entry slides to its new number, or flies in from a cell that is
lit elsewhere on screen (a grid's marked cell, an array cell under a pointer, a highlighted entry
of another vector) when it takes that number. Several vectors side by side (`<div class="row">`)
show a list of them (one per word, per point, per step); put a vector beside the picture it
belongs to rather than inside it. A grid of numbers is a `grid`, a formula with a matrix is `tex`.
