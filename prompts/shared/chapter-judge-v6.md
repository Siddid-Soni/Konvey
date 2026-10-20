# Is each chapter a new setting?

A video explains a topic in two parts. Part 1 makes the idea visible on one first example and
gives the argument for why it holds. Part 2 has chapters, and each one should take the
understood idea into a **new setting** that shows something Part 1 could not.

You get Part 1 (the first example, and the findings that give the insight and why it holds) and
the chapters (setting, what each reveals, its findings). For each chapter, decide which of
these it is:

- `new`: the idea is applied to a different thing, or one of Part 1's assumptions changes, and
  the chapter shows something Part 1 did not.
- `replays_argument`: the chapter re-derives Part 1's argument, or zooms into one of its steps
  (the same reframe, the same diagram, the same proof, told again with more detail).
- `same_example`: the first example again with other numbers, sizes or units, and nothing new
  about the idea.

Example (another topic: why a lever lets a small push lift a heavy load). Part 1: a seesaw where
a 25 kg child balances a 75 kg adult; the insight is that weight times distance is equal on both
sides, because the ends trace arcs and the work done on each side is the same.
- "a wheelbarrow: the load sits between the pivot and the hands" → `new` (a different
  arrangement; the same rule still holds).
- "the arcs traced by the two ends, measured carefully: the work is the same" → `replays_argument`.
- "a 40 kg child on a 4 m board" → `same_example`.

A chapter that uses Part 1's result as a tool in a new setting is `new`. Mark a chapter as
something other than `new` only when you are sure; a wrong verdict makes the author rewrite a
good chapter.

## Output: ONLY JSON

```json
{"chapters": [{"id": "C1", "verdict": "new", "why": "<one sentence>"}]}
```
