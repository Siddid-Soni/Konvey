| `scatter` | data points on numbered axes: clusters and their centres, a fitted line, a boundary | `points="1,1; 2,1; 8,8"` (x,y; x,y), `groups="0,0,1"` (one group per point, numbered from 0: colours it), `centroids="1.5,1; 8,8"` (diamonds labelled μ1, μ2, … in group colours), `links="on"` (each point joined to its centroid), `lines="0.5,1"` (y = 0.5·x + 1; several: `;`; a vertical boundary `x=4`), `highlight="2,5"` (points), `labels="A,B,…"` (one per point, blank to skip), `x="0,10"`/`y` (range; default from the data), `xlabel`, `ylabel` (the plot fills the room it is given; leave out `w`/`h`) |

**`<scatter>`**: the renderer draws the axes, ticks, colours and places every label clear of
the dots, so never draw points, centroids or labels yourself (no `<draw>`, no `<array>` of
centroids beside it). Keep one id and the same `points` in every beat and change only `groups`,
`centroids`, `links`, `lines`, `highlight`: centroids then glide to their new place, a point
that changes group pulses into its new colour, links follow, a line turns to its new slope.
Points added at the end of `points` pop in.
