| `places` | places that hold things, and things moving between them: machines and services, accounts, containers, people, levels of a hierarchy, stages of a process; laid out for you (see below) | `parts="client,server,store"` (left to right; `client,balancer,web1|web2|web3` stacks a tier into a column, wired to every part of the tier before), `holds="server:id 5; store:1|5|8"` (part:item|item; …), `highlight="store:5"` (a slot) or `highlight="web2"` (a whole part), `notes="store:found"` (a word above a part), `shapes="store:cylinder"` (box | cylinder: a store | circle: a cell, a person, a node | bin: an open container), `wires="client-server:HTTP"`, `layout="column"` (top to bottom: levels) / `"grid"` (rows of places) / `"ring"` (when the plan says so: peers on a circle, every two wired), `links="none"` (no wires: things jump from place to place) or `links="a-b;b-c"` (only these wires), `w`/`h` (default 12 × 4.2); children `<item>` |

**`<places>`: the plan's `places` object.** Its state is copied from the plan for that beat:
`parts`, `holds`, and one `<item>` per planned item with the same `id`, place and `text`/`lines`.
How it looks is yours:

| `<item>` attribute | |
|---|---|
| `id` | keep it in every beat (and scene): the same id is the same thing, so it travels |
| `in="server"` | the part it is in (stacked under its slots, in order). Items always sit in a part |
| `from="client"` | only on an item that is new in this beat: it is born in that part and sent here (a SYN, a ping) |
| `text`, `lines="name: mug\|price: 4.0"` | its words; `lines` make a card: header + lines (a response with its body) |
| `style` | `slot` (default), `pill` (a message; default with `from`), `card` (header + lines; default with `lines`), `chip` (a small tag) |
| `color` | any theme colour (default accent; slots take their part's colour) |

When an item's `in` changes between beats it is sent: it shrinks into a small packet (a dot with
its name) at the side of its part, runs along the wires (they light up; through any parts in
between; with no wire between the two places it jumps across in an arc) and opens into its new look in the receiver. So the look in the receiver may differ from
the sender's (a `pill` request can arrive as a `slot`); a new item or slot with the same text as
one that left another part is the same thing arriving (a value taken out of a store and sent, a
reply stored by the client). The renderer lays out
everything; no coordinates, and never rebuild places with `<draw>`. Use `shapes` for what a
part is (a database is a `cylinder`), `notes` for a part's verdict ("miss", "404"), `highlight`
for the slot being used, `wires` to name the link.
Places are wide: give them the whole width (`<div class="grow center">` of its own) and put any
readout, formula or caption **under** it in a column, never beside it in a row (beside it, the
places are shrunk, and by a different amount in each beat, so it jumps). Keep the same `w`/`h` in
every beat.
