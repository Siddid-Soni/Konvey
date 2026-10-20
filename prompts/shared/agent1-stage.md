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
     "why": "<the rule or comparison that decides this step, with its numbers>",
     "state": {"<name>": <exact values right after this step>}}
  ],
  "result": "<the answer the steps reach, with its number>"
}
```

- Every step is written out: none skipped, none merged, no "and so on". 3–10 steps; 4–6 is best.
- `why` answers the question a viewer would ask at that step: why this item, why this value, why
  it goes there (e.g. "9 is bigger than the best so far, 4, so 9 becomes the best"). Give the rule
  and the numbers it compares, never "because that is how it works". When one step changes
  several things, `why` says how they follow from each other.
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

## WHAT THE REQUEST ASKS FOR (`requested`, `more_walkthroughs`)

A request often says what the video should show, not only the topic: "show the working beside
the number", "use an example", "show both methods". The planner after you plans from your JSON,
so anything the request asks to be shown that is not in it is lost.

- `requested`: a list, one entry per thing the request asks to be shown or done, in the
  request's own words (a picture, a table next to something, a particular example, a method, a
  comparison). `[]` when the request only names a topic. Example: for "Explain converting a
  number to binary: show the repeated division by 2 with the remainders collected in a column,
  then the other method, subtracting powers of two", `requested` is
  `["repeated division by 2", "the remainders collected in a column", "subtracting powers of two"]`.
- Give every `requested` item the data it needs: a table to update gets its values in every
  walkthrough `state`; a method to show gets a key concept and worked numbers.
- **More than one method or process to see working**: `walkthrough` works the first one through;
  add one more walkthrough (same shape) per further method to `more_walkthroughs`, each on the
  same small instance where it fits, so the two can be compared. In the example above, the second
  method gets its own walkthrough converting the same number. Usually `more_walkthroughs` is `[]`.
- When the request names what to show, the video is about those things: put related topics it
  did not ask for (costs, variants, implementation details, ways to tune it) in
  `scope_exclusions`, unless a requested item cannot be understood without them.

## THE STORY: HOW THE VIDEO APPROACHES THE QUESTION

The facts above say what is true. These fields decide how the video gets there. 3Blue1Brown
approaches every question the same way, and leaves no "why?" open by the end:

1. **The hook**: a concrete thing on screen, what is strange about it, and a question the viewer
   cannot answer yet. Then **why it is worth the time** (what it matters for, what it is really
   a lesson in), still without the answer.
2. **The obvious attempt**, and exactly where it falls short. That failure turns into a sharper
   question, and a concrete **promise** of what the viewer will see by the end.
3. **Small cases**, simplest first, growing until one of them is troublesome.
4. **A hunch** from those cases, **made precise** (usually by putting a number to it), which
   leads to **the key insight**: why it holds, and why it settles the question in every case.
5. **Objections and edge cases** ("you might think…"), each answered.
6. **A step back**: what this was an example of, the general rule, a different situation the
   same idea settles, and the opening's why answered.

Fill each part (another topic as the example: why a lever lets a small push lift a heavy load):

**`examples_considered` + `chosen_example`.** When the request names its example ("with a
seesaw"), keep it: one entry, `"named_in_request": true`. Otherwise think of 3–4 genuinely
different examples (different objects and scales, not one example with new numbers) and choose
the one that lets the viewer *see* the idea happen and leads furthest. For the lever: a child
lifting an adult on a seesaw; a crowbar under a crate; a bottle opener; a wheelbarrow. The seesaw
wins: both weights and both distances are visible at once.

**`hook`**: how 3Blue1Brown opens. He never starts with the conclusion or a slogan about it. He
puts one concrete thing in front of the viewer, points at what is strange about it, and stops on
a question; the answer comes much later. His own openings:
- "This is a 3. It's sloppily written at 28 by 28 pixels, but your brain has no trouble
  recognising it. Take a moment to appreciate how crazy it is that brains can do this so
  effortlessly… Now sit down and write a program that does it."
- "Three sellers offer the same product: 100% positive from 10 reviews, 96% from 50, 93% from
  200. Which one should you buy from? We all have an instinct here… but how do you make that
  intuition quantitative?"
- "Here is a sequence of computations, and each one equals pi. You might think the pattern goes
  on forever. But it doesn't. At some point it stops."
- "Behind this glass there appears to be a three-dimensional scene. But it's an illusion: all
  that's there is an empty table and a laser."

Fill it in this order:
- `shown`: the one concrete thing on screen, with its numbers (for the lever: "a 25 kg child on
  one end of a seesaw lifts a 75 kg adult on the other").
- `tension`: what is strange about it, or the instinct the viewer has but cannot justify
  ("the lighter one wins; three times lighter").
- `question`: the open question the opening ends on ("how can the light end win?").
- `withheld`: 1–4 short phrases that would give the answer away, which the narration must not
  say before the insight (the result, the method's or principle's name, its key word: "distance
  times weight", "torque", "the far end").
- `why_care`, after the question: what it matters for or what it is really a lesson in, without
  the answer ("every crane and every pair of pliers runs on the same trade").
- `problem`: the concrete question the video then works on ("where must they sit to balance?").
- `type`: `stakes`, `vehicle`, `surprise` or `confusion`, the kind of `why_care`.

Never open with the conclusion as a claim ("you can be certain without looking", "a greedy rule
is always right", "it takes one step"): that answers the question the video exists to ask.

**`naive_attempt`**: `attempt` (what anyone tries first: "put them at equal distances"),
`falls_short` (exactly where it fails, with numbers: "the adult's side drops; 75 kg beats 25 kg"),
`sharper_question` ("what has to be equal, if not the weights?"). **`promise`**: what the
viewer will see by the end, concretely ("the one product that is the same on both sides").

**`exploration`**: 2–4 small cases, simplest first, up to the troublesome one, each `case` and
`what_happens` with numbers (equal weights at equal distances; double weight at half distance…).

**`insight`**: `hunch` (what the cases suggest), `made_precise` (the hunch with a number put to
it), `idea` (the key insight), `why_it_holds` (step by step), `why_it_settles` (why it answers the
sharper question in every case, not just the ones tried).

**`viewer_questions`**: 3–8 "why?"s and objections a smart beginner would raise while watching,
each answered. Think of: why this number and not another; why not fewer or more; why the rule
holds in every case; why the formula has this shape; what a symbol means; why it has its name;
"you might think…" objections; edge cases. `shown_by` says how the screen answers it:
`picture` (the example shows it happening), `derivation` (built step by step from the picture),
`counterexample` (the case where it would fail, shown failing or ruled out), `trials` (every
case, or many random cases, run one after another). An answer only heard does not count.

**`payoff`**: `lesson` (what this was an example of: the technique or idea to keep),
`generalisation` (the general rule, with its formula or numbers), `surprise` (a *different*
situation the same idea settles, which the viewer would not expect, with real numbers; not the
same example with bigger numbers), `closes_opening` (how this answers `hook.why_care`). None of
these may go in `scope_exclusions`.
