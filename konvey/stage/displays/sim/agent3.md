| `sim` | a simulation that runs while the line is spoken: balls through pegs, cases piling up, blocks colliding, a crowd passing something on, a pendulum, arrows spinning tip to tail, a quantity along a line evening out or swinging, random walkers | `rule` (below), `t` (model time reached by the end of the beat, or `"end"`), the rule's own numbers, `seed`, `w`/`h` |

### `<sim>`: simulations that play during the line

A beat says how far the simulation has got by its end; what happens since the previous beat plays
while the line is spoken (keep the id and the rule's numbers across beats; change only `t`, or
`balls`/`shown`). A long line shows a long stretch: give a beat as much model time as its line can
watch. Every number is computed by the engine, seeded: never write results into the narration
the engine has not shown (bind them with `<value bind="id.channel">`).

| `rule` | the picture | its numbers | live values (`id.…`) | parts (`id>…`) |
|---|---|---|---|---|
| `drop` | balls bouncing down a triangle of pegs into bins; the first few fall slowly, then they pour | `rows`, `balls` (by the end of this beat), `p` (chance of right) | `balls`, `bin0` … | `4` (bin 4) |
| `trials` | every case as a card; the ones that count light up | `cases`, `hits`, `shown` | `shown`, `hits` | `3` (card), `hits` |
| `blocks` | a block sliding into a smaller one by a wall, every collision counted | `mass` (big / small), `v` | `clacks`, `v1`, `v2` | `small`, `big` |
| `spread` | people wandering in a box, passing something on to those near them | `people`, `radius`, `p` (per day), `sick-days`, `distancing`; time in days | `healthy`, `sick`, `recovered` | those three groups |
| `pendulum` | a swinging pendulum, with friction | `angle` (degrees), `damping`, `length`, `g` | `theta`, `omega` | `bob`, `rod` |
| `circles` | arrows tip to tail, each spinning at its own rate; the last tip draws | `shape="\pi"` (any TeX outline: the arrows that draw it, `terms` of them) or `curve="x(u); y(u)"`, or the arrows themselves `arrows="length, angle°, turns; …"`; `period` (seconds a loop), `ghost="on"` (the target shape, faint) | `turns`, `x`, `y` (the tip) | `curve`, `1` (the first arrow and its circle) |
| `line` | a quantity along a line from 0 to 1 changing in time: `look="rod"` coloured by value under its graph, or `"string"` | `start` (`step`, `spike`, or an expression in x), `equation="heat"` (evens out at `rate`) or `"wave"` (swings at `speed`, `damping`), `ends="sealed"` (nothing flows out) or `"fixed"` (held at 0); arrows show how fast each point changes | `left`, `middle`, `right`, `spread` | `curve`, `rod`, `arrows` |
| `walk` | walkers in lanes hopping at random, the pile of where they stand below; `bell="on"` adds the bell √steps predicts | `walkers`, `pace` (steps a second), `step="-1,1"` (equally likely moves; `"1,2,3,4,5,6"` a die: the pile is a running total), `p` | `steps`, `spread`, `far`, `mean` | `walkers`, `pile`, `bell` |

- `circles` with a shape: few arrows draw a rough version, many the shape itself; put two `<sim>`s
  with different `terms` in a `compare` shot to show the difference. With `arrows`, slow first.
- `line`: the arrows are the point (the curve bends → that point moves): keep them on screen
  while the line talks about why a part changes fast or slow.
- Pair a `<sim>` with a `<simview>` (another view of the same run, in step) in a `compare` shot.
