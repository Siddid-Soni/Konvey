| `draw` | a flat diagram you build from shapes (see below) | `w`, `h` (size in u, default 8 × 4), `x="0,12"` `y="0,5"` (its own coordinates, default 0..w and 0..h, y up), `size` (label font, 26) |

**`<draw>`: when no tag above is the object the narration talks about** (points on a plotted curve are not: they are `<dots on="plot id" at="x,y">` on that plot), build it from shapes
instead of forcing it into cells or bars that only resemble it (a number line with marks, a
balance, a lever, a plane figure with given corners; things piled on posts are a
`<collection look="stacks">`). Children,
each with an `id` unique inside the draw, at coordinates in the draw's own units, painted in
order: later children cover earlier ones, so write what stands behind first (a shelf before the
boxes on it). `z="1"` on any child lifts it above the ones with the default `z="0"` (`z="-1"`
sends it back):

| shape | attributes |
|---|---|
| `<rect>` | `x`, `y` (centre), `w`, `h`, `round` (corner radius), `color` (c1), `fill` (opacity 0–1, default 0.85; `none` = outline), `label` (text in the middle) |
| `<circle>` | `x`, `y`, `r`, `color`, `fill`, `dashed="true"` (a dashed outline, no fill), `label` |
| `<polygon>` | `points="x,y; x,y; x,y"`, `color`, `fill`, `label` |
| `<line>` | `from="x,y" to="x,y"` or `points="x,y; x,y; …"`, `arrow="true"`, `dashed="true"`, `width` (4), `color` (ink), `label` |
| `<label>` | `x`, `y`, `text`, `color`, `size` (22 or more) |
| `<icon>` | `x`, `y` (centre), `h` (height), `name` (a line icon from the built-in Tabler set: `cpu`, `server`, `database`, `user`, `file-text`…), `color` (c1), `label` (under it): a thing with a look of its own (a processor, a disk, a person) instead of a labelled box |
| `<arc>` | `x`, `y` (centre), `r`, `from`, `to` (degrees counter-clockwise from the +x direction), `color`, `width` (3), `fill` (a value fills the wedge), `dashed="true"`, `label` (placed inside the angle, just past the arc). An angle mark: centre on the vertex, `from`/`to` = the directions of its two sides; the same angle copied elsewhere gets the same colour |

Write the whole drawing in every beat (it is a snapshot like everything else) with the same draw
id and the same shape ids: a shape whose `x`/`y`/size/colour/label changed slides and morphs to
its new look (one that moves across more than a quarter of the canvas hops over, like a box
lifted to another shelf), new ids fade in, missing ids fade out. `move=` on a child sets how it
reaches its place in that beat: `move="slide"` goes straight (a message travelling along a wire,
a time marker moving right, however far), `move="hop"` always arcs over, `auto` (default) = the
quarter-canvas rule. To show something travel, keep its id and change its `x`/`y` one hop per
beat instead of drawing a new shape at each stop. Something that turns (a clock hand, a spoke
from the origin, a point on the unit circle) needs nothing extra: a line that keeps one end and
its length, and a shape that stays on a circle drawn in both beats, turn along the arc (the short
way); anything else that should circle a centre gets `around="x,y"`. An `<arc>` whose `from`/`to`
change opens like an angle. The drawing keeps the `w`/`h`/`x`/`y` of its first beat (also from
the previous scene): write the same ones in every beat. Labels are shown at 22 or larger and step
aside from each other and from lines on their own; still put each next to what it names. Put
things where they really are: a box on a shelf sits on the box below it.
