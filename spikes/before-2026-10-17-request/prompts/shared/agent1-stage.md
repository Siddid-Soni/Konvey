## DATA FOR THE PICTURES (renderer = stage)

The video draws real charts, rows and grids of cells, and lit 3D objects from your values, so give
the values those pictures need. Every value must be correct for this topic (computed exactly or
from the source), never illustrative.

- **Something changes over time or over steps** (a quantity that grows, decays,
  peaks or accumulates): give the series as lists of 5–12 numbers at evenly spaced,
  stated x values, e.g. `{"year": [0, 1, 2, 3, 4], "balance": [100, 105, 110.25, 115.76, 121.55]}`.
  Several quantities over the same x are several lists of the same length.
- **Items in order or in a table** (a list being processed, a row of digits, a board): give the items
  themselves as a list, e.g. `{"items": [2, 5, 8, 13, 21]}`, plus the positions that matter
  (`{"start": 0, "end": 4}`).
- **Objects in space** (bodies, shapes, a surface): give the sizes, distances and angles that the
  explanation uses.
- **Something passed between parts** (a request between client, server and database; a job
  between threads; an address being translated; a packet through routers): the values are the
  things a viewer reads on screen: the parts' names, the message itself (`"GET /items/5"`), the
  status (`"200 OK"`), what each part stores (`[3, 5, 8]`). Do not measure them to have numbers
  (character counts, byte lengths, line lengths) unless the topic is about size or speed.

## ONE EXAMPLE WORKED ALL THE WAY THROUGH (`walkthrough`, required)

The video will show one concrete instance being solved, step by step, so the viewer sees the idea
work instead of hearing it summarised. Add:

```json
"walkthrough": {
  "concept": "<the key_concepts[].name this example shows working>",
  "question": "<what is worked out, with its concrete inputs>",
  "start": {"<name>": <exact values before the first step>},
  "steps": [
    {"action": "<what happens in this step, with its numbers>",
     "state": {"<name>": <exact values right after this step>}}
  ],
  "result": "<the answer the steps reach, with its number>"
}
```

- Every step is written out: none skipped, none merged, no "and so on". 3–10 steps; 4–6 is best.
  If the real run is longer, choose a smaller instance (fewer items, smaller numbers) whose full
  run fits.
- `state` uses the same names every step (e.g. the whole list, the current range, the running
  total), so the picture can change in place from step to step.
- Work it out exactly and check each step against the previous one: every number must be right.
- Pick the instance that best shows the core claim (a typical case, not a trivial one).
- **A process between parts** (see above): every `state` has `"at"` (the part where the moving
  thing is right after this step), `"carrying"` (what it says now: the request, the reply, the
  job) and one key per part holding that part's contents, e.g.
  `{"at": "server", "carrying": "GET /items/5", "client": [], "server": [], "store": [3, 5, 8]}`.
  One step per hop or per change inside a part, so each step is a visible move.

## COMPUTE, DON'T RECALL (tools: `calc`, `run_python`)

You have two tools. Use them for every number that is calculated rather than quoted from a
source:
- `calc("…")`: one arithmetic expression, e.g. `calc("log2(1048576)")`.
- `run_python("…")`: a short program that print()s the values, for anything with steps or
  many values: trace the walkthrough (print the state after every step), run a recurrence or
  simulation for a series, build a table.

Copy the tool's printed results into the JSON exactly; never redo the arithmetic in your head.
Before you finish, check that every claim in `walkthrough.result` and the key formulas agree
with what the tools printed (e.g. a worst case, a total, a limit).
