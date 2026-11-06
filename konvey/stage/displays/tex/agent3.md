| `tex` | LaTeX math (inner text, no `$`) | `size` (44), `color` (keep the id and it morphs from the previous formula), `from="a: id>part; b: id>part"` (those symbols fly out of the picture's parts into place), `inline` (an operator kept between two pictures in a shot), `follow="plot id"` with stages between `\|\|` (`y = 1 \|\| y = 1 + x`: it changes on the same beats as that plot's `fn` steps, one stage per step), `paint="y: accent; \sin x: c1"` (those parts in their curve's colour) |

### `<tex follow>`: stages

The stages of a formula that follows a plot are split by two plain bars, written without backslashes: `<tex id="eq" follow="g">y = 1 || y = 1 + x || y = 1 + x + x^2/2</tex>`. (The table above escapes them only because a bar ends a table cell.)
