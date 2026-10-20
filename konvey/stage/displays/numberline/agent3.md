| `numberline` | a number line with numbered ticks and small ticks between, and named markers (a triangle with its name) that slide when their value changes: a value being varied, where a number sits among others, an input and its output on stacked lines; spans the width of its column; marks go on it (`x,0`) | `x="0,3"` (range; `pi` allowed), `markers="x: 1.5; x^2: 2.25"` (name: value; names are maths), `step` (numbered tick spacing; default about 10 numbers), `numbers="none"`, `colors="accent,c2"`, `size` |

**`<numberline>`: stacked lines for a chain of steps.** Several lines in a column (no shot, a
`<div class="grow col center" style="gap: 0.7u; padding-right: 2u">`), each with its marker, show a
value going through steps; an `<arrow from="a>x=3.2" to="b>x=9.6" label="(\dots)^2">` between their
right ends names each step (leave the right padding for it). Markers keep their names across beats
and only their values change, so they slide. A small change of the input is a `<brace on="a"
from="1.5,0" to="1.6,0" label="dx">`.
