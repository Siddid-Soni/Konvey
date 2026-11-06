| `plot` | graphs of functions y = f(x) on real axes, traced exactly by the engine | `fn="f: x^2; g: 2x - 1"` (`label: expression`, `;` between curves), `x="-2pi,2pi"`, `y="-2,2"`, `color="ink,accent"` (one per curve), `points="E: 4,6; A: 2,supply"`, `mark="x=pi: a; y=4: price"`, `gap="supply,demand@y=4: shortage"`, `shade="demand,supply: 2,4: lost trade"`, `fn="S: a \| b \| c"` (steps played during the line), `slide="0 -> 2"`, `drop="true"`, `{x}` `{y}` `{gap}` in labels (live numbers), `xlabel`, `ylabel`, `w`/`h` (axes size in u) |

### `<plot>`: function graphs

Write the function, never its points: the engine traces each `fn` exactly, puts the axes through
(0, 0), numbers the ticks (in π when `x` is given in pi), cuts a curve cleanly where it leaves
`y` (a diverging polynomial leaves at the top or bottom edge), and labels each curve at its end.
Never draw a function with `<draw>` lines.

- `fn`: expressions in `x` with numbers, `pi`, `e`, `+ - * / ^`, `sin cos tan exp log sqrt abs
  arctan asin acos sinh cosh tanh floor ceil sign` (`2x`, `3(x+1)`, `2pi` are fine). The label is shown
  at the curve's end: words (`total`, `cost`) or math (`f`, `g_2`, `x^2`, `\cos x`).
- `x`, `y`: the full range the narration talks about (a "wider range" claim needs that range).
- `points`: `name: x,y`; y may be a curve's label (the dot sits on it). `mark`: a dashed line at
  `x=VALUE` (vertical) or `y=VALUE` (horizontal). `gap`: the distance between two curves along
  a level (`@y=4`, the engine finds where each curve meets it) or at an x (`@x=pi`, an error bar).
  `shade`: the region between two curves, or a curve and a level (`demand,6: 0,4`), from x to x.
- Same id, change only what changes: the plot re-traces in place. A changed `fn` (one more
  term) bends into the new curve; a `mark`, `points` or `gap` value slides; a new curve draws in;
  a new range rescales smoothly. Keep curve order, colours and `xlabel`/`ylabel` across beats and scenes (the first names stay).
- **Motion during the line** (3b1b's slider: the picture changes while it is talked about):
  - Steps: `fn="sin x: sin(x); S_1 | S_2 | S_3: sin(x) | sin(x) + sin(3x)/3 | sin(x) + sin(3x)/3 + sin(5x)/5"`.
    The curve enters as the first expression and bends through the rest, one step about every
    second, while the line is spoken: terms added one by one, or a knob turned
    (`1 + 0.5x^2 | 1 | 1 - 0.5x^2`). One label, or one per step between `|`. Give the beat
    room (`t`) for its steps; the next beat starts from the last step. A sum built term by
    term shows 3-4 stages, not one bend: start from its first term or two.
  - Slide: `slide="0 -> 2"` moves everything of this plot written at x=0 (a `points` dot, an
    `x=0` mark, a `@x=0` gap) to x=2 during the line, smoothly; points on a curve ride along it.
    With `drop="true"` each point has a dashed line down to the x axis.
  - Live numbers: a point's name, a gap's or a mark's label may hold `{x}`, `{y}` (the point's
    height) or `{gap}` (the gap's length): `points="x = {x}: 0,f"`, `gap="f,g@x=0: error {gap}"`.
    They count as it slides, and show each step's value.
