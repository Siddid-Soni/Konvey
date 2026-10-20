| `plot` | graphs of functions y = f(x) on real axes, traced exactly by the engine | `fn="f: x^2; g: 2x - 1"` (`label: expression`, `;` between curves), `x="-2pi,2pi"`, `y="-2,2"`, `color="ink,accent"` (one per curve), `points="E: 4,6; A: 2,supply"`, `mark="x=pi: a; y=4: price"`, `gap="supply,demand@y=4: shortage"`, `shade="demand,supply: 2,4: lost trade"`, `xlabel`, `ylabel`, `w`/`h` (axes size in u) |

### `<plot>`: function graphs

Write the function, never its points: the engine traces each `fn` exactly, puts the axes through
(0, 0), numbers the ticks (in π when `x` is given in pi), cuts a curve cleanly where it leaves
`y` (a diverging polynomial leaves at the top or bottom edge), and labels each curve at its end.
Never draw a function with `<draw>` lines.

- `fn`: expressions in `x` with numbers, `pi`, `e`, `+ - * / ^`, `sin cos tan exp log sqrt abs
  arctan sinh cosh tanh floor ceil sign` (`2x`, `3(x+1)`, `2pi` are fine). The label is shown
  at the curve's end: words (`total`, `cost`) or math (`f`, `g_2`, `x^2`, `\cos x`).
- `x`, `y`: the full range the narration talks about (a "wider range" claim needs that range).
- `points`: `name: x,y`; y may be a curve's label (the dot sits on it). `mark`: a dashed line at
  `x=VALUE` (vertical) or `y=VALUE` (horizontal). `gap`: the distance between two curves along
  a level (`@y=4`, the engine finds where each curve meets it) or at an x (`@x=pi`, an error bar).
  `shade`: the region between two curves, or a curve and a level (`demand,6: 0,4`), from x to x.
- Same id, change only what changes: the plot re-traces in place. A changed `fn` (one more
  term) bends into the new curve; a `mark`, `points` or `gap` value slides; a new curve draws in;
  a new range rescales smoothly. Keep curve order, colours and `xlabel`/`ylabel` across beats and scenes (the first names stay).
