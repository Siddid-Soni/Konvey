| `graph` | nodes joined by edges (a network, a map of roads, states and moves, units of a layered model, words attending to words) | `nodes="A:0,0;B:2,1;C:2,-1"` (name:x,y, any units; or just `"A,B,C"` for a circle), `edges="A-B:7;B-C:2;A>C"` (`-` two-way, `>` one-way, `:weight` optional), `highlight="A,B"` (nodes), `dim="C"`, `path="A-B-C"` (a route, drawn bold), `values="A:0;B:7;C:∞"` (a number beside each node), `edge-values="A-B:-0.3"` (a second number on an edge, under it: a gradient, a flow), `strength="true"` (edges thick and bright by their number: only for a strength such as attention or a probability; a cost, distance or time stays a plain line with its number), `flow="A>B>C"` (packets run along these edges into this beat; `;` between several), `layout="line"` (names only, `nodes="the,cat,sat"`: the nodes in a row, edges arcing above it into their target: one word looking at the words before it) / `"two-lines"` (`nodes="the,blue,cat|le,chat,bleu"`: two rows, edges straight between them: a sentence and its translation, a matching between two sets), `layout="tree"` (names only, root first: `nodes="root,a,b,c"`, every edge parent→child in left-to-right order; the renderer lays out the levels), `look="pages"` (each node a row of key cells, its name the keys separated by spaces: `nodes="17 35,4 9 12,20 28"`; a page's k-th child hangs from between its keys k−1 and k), `weight-labels="false"` (no numbers on the edges; with `strength`, thickness only), `w`/`h` (u), `size`. Keep `nodes`/`edges` the same across beats and change only highlight/path/values: the graph then re-colours in place, step by step. A node with no value yet: leave it out of `values` (it shows nothing; `∞` for a distance not reached yet), never `?` or `None`. |

**Values travelling along edges** (`flow`): a new `flow` sends a dot along each route, leg after
leg; a node's new value appears as the dot reaches it, and an edge's new `edge-values` number
rides on the dot and lands on that edge. A forward pass: `flow="x>h>y"` with the new `values`
of h and y. Backward: `flow="y>h>x"` with `edge-values="h-y:-0.09;x-h:0.03"` (a route may run
against an edge's arrow). A flow plays once, in the beat where it first appears; to send again,
change it. `strength="true"` needs a number on every edge; two opposite one-way edges
(`A>B;B>A`) are drawn side by side, so words attending to each other read both ways.

**Rows of nodes** (`layout`): with `"line"` or `"two-lines"` the renderer places the nodes (give
names only, never positions) and keeps them still while edges come and go: a beat with other
edges fades the old ones and grows the new ones from their source, so `edges="fluffy>creature:0.57;
blue>creature:0.42"` with `strength="true"` shows which words one word reads, and a later
`flow="fluffy>creature;blue>creature"` sends their values along the arcs.

**Trees** (`layout="tree"`): give names only, root first, and one edge per parent→child, children in
the order they sit left to right; the renderer places every level so subtrees never overlap, a
parent centred over its children. Keep `nodes` and `edges` the same across beats and light the way
down with `path` and `highlight`. With `look="pages"` each node is a row of key cells (a page of
keys): write a page's keys in its name with spaces, `"20 28"`, and list its children in key order,
so the pointer to the child between 20 and 28 leaves from between those two cells.
