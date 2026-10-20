| `relation` | how strongly each item of one list relates to each item of another, or of the same list: the column items in a row with the weight grid under it (row items down the left, a dot per pair sized by its weight), or the items joined by arrows (one list) or lines (two lists) as thick as their weights | `cols="a,fluffy,blue,creature"` (1–10 items; `\|` between them if one has a comma), `rows="le,chat,bleu"` (a second list down the left; leave it out when the list relates to itself), `weights="1,0,0,0;0.4,0.6,0,0;…"` (one group per column, in order: that column's weight for every row; `""` for a column not computed yet), `normalize="columns"` / `"rows"` (each column / each row sums to 1), `op="softmax"` (the step's name, written on the frame that sweeps the lines while they normalise), `mask="later"` (one list: an item sees only itself and earlier items), `focus="creature"` (one column: framed, the rest dimmed; arrows or lines go into it), `focus-row="fluffy"` (one row), `view="grid"` (default) / `"links"` / `"both"` (one list: grid with arrows over the items), `numbers="true"` (weights written in the cells instead of dots), `size` |

**Telling a relation story** (`<relation>`): keep one id and the same `cols` (and `rows`) for
the whole scene and change only the other attributes, beat by beat. The renderer lays everything
out (never place items or dots yourself) and keeps the items still while the picture changes
under them. Each change plays as a step: `view="links"` → grid: the row labels fly from their
items to the left and the dots grow row by row; raw weights → `normalize`: a frame (named by `op`)
sweeps the columns (or rows) and each one's dots resize; adding `mask="later"`: the cells of later
items are struck one by one; a new `focus` slides the frame; `view="links"` with a `focus` grows
arrows (one list) or lines (two lists) from the related items into the focus item (thick = more
weight, the weight beside each when normalised); with two lists and no `focus`, every pair's line
is drawn (an alignment or a matching). Numbers that belong to an item (its embedding, its new
value) are a separate `<vector>` beside the picture: when one of its entries changes to a weight
the focus is showing, it flies in from that cell, arc or line. Weights are per column: group 3 is column 3.
Use `numbers="true"` for the beats where the narration reads values, dots for the pattern.
Topics it fits: attention between words (`normalize="columns" op="softmax" mask="later"`), word
alignment between a sentence and its translation (two lists, `view="links"`), a confusion matrix
(rows = actual, cols = predicted, `normalize="rows"`), similarity or correlation between items,
co-occurrence counts, which word a pronoun refers to, a matching between two sets.
