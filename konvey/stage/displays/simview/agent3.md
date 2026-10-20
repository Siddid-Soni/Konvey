| `simview` | another view of a `<sim>`'s run, moving in step with it: its phase plane, or its numbers over time | `sim` (the `<sim>`'s id, in the same beat), `show="phase"` or `"graph"`, `y="spread, far"` (graph: up to 4 of the sim's live values), `ref="sqrt(t)"` (graph: a dashed curve in t to compare against), `time` (the time axis' name), `x`/`y` (phase: which two values) |

### `<simview>`: the same run, seen another way

`sim=` names the `<sim>` (not `of=`, which means "sits on"): both read one run, so a point on the
phase plane and the pendulum swing together, and a graph grows as the walkers spread.
- `show="phase"`: two of the run's numbers as a point with its trail (blocks: the two velocities on
  a circle; pendulum: angle and speed, spiralling in, with the flow's arrows).
- `show="graph" y="…"`: those numbers over time, each line growing as the clock runs; its time
  axis reaches the furthest time any beat takes the run. `ref` draws the curve a rule predicts
  (a square root, an exponential) so the viewer sees the data follow it.
- Parts: a graphed value's name (`g>spread`), `ref`.
