# Problems: why Konvey videos still fall short of 3Blue1Brown

Date: 2026-10-19 · Branch `design/html-layout` · Sources: user review of the pigeonhole video
(`out/dramabox-demo/pigeonhole-v2-tight`), github.com/3b1b/videos (scene code, counts over
`_2022`–`_2026`, 133 files, unless noted) and github.com/3b1b/captions (transcripts).

## A. The pigeonhole video

1. Socks are not socks: grey dots, then blue/green squares. The "black" sock is blue: the voice
   says one colour while the screen shows another (the narration note already forbids this;
   haiku ignored it).
2. Nothing travels: no drawer, no sock moves into a hole; the bins are redrawn with new counts.
3. "2 might not be enough" is said, never shown (black + white escaping a match is never drawn).
4. "Lucky draws only make the match come sooner" is asserted, not shown.
5. ⌈3/2⌉ = 2 appears from nowhere: the ceiling is never explained or derived.
6. The real reason is missing: avoiding a match needs one hole per sock, and 3 socks > 2 holes.
7. The name is never explained: no pigeons ever appear.
8. No payoff: no generalisation or surprising use; the last scene holds nearly the same frame
   for 4 lines.
9. Mostly empty screen: small shapes in the middle, a "socks drawn" number floating far right,
   attached to nothing.

## B. Every video has the same layout

10. Fixed template: heading top-left, formula under it, picture in the centre, numbers beside
    it. Hard-coded in `prompts/agent3-stage/reference.md` (rule 6 + "Screen pattern"); all 24
    Agent 3 examples open with `<h2>`. 3b1b: `Title(` 17 uses in 133 files.
11. No 2D camera: the camera only drives the 3D world. 3b1b moves the frame ~1691 times (pan,
    zoom into a detail, move to a new area of a larger canvas).
12. Visible elements cannot be placed freely: `position: absolute` is allowed only on invisible
    anchors.

## C. "Why?"s left unanswered

13. Claims and formulas go on screen without being shown or derived.
14. No agent lists the "why?" questions a viewer would ask and maps each to the beat that
    answers it.
15. Agent 1's `scope_exclusions` cut generalisation and payoff, so videos stop at the toy case.
16. No check catches an unexplained claim.

## D. Visual techniques we lack

17. Pieces do not fly from the picture into the equation (`TransformFromCopy`: 934 uses).
    Formulas fade in; only numbers fly today.
18. Little dimming of context (opacity/fade: ~2282 uses); only `dim` on some displays.
19. Few arrows, braces and surrounding boxes tied to the exact part being discussed
    (Arrow/Vector 1180, Brace 274, SurroundingRectangle 714).
20. Numbers are separate floating widgets instead of riding on their objects
    (DecimalNumber/ValueTracker/updaters: 1586 uses).
21. No recognisable objects: dots and squares instead of the real thing (sock, pigeon, person,
    the actual numbers).
22. No fast run of many trials: 3b1b's subsets scene flashes 40 attempts at 0.5 s each so you
    feel there is no escape; we show one case.
23. No real pause for the viewer: "take a guess" and straight on, instead of pause → tempting
    wrong answer → correction.

## E. Same example and same hook every time

24. Socks came from our own request ("Explain the pigeonhole principle with socks: grab 3
    socks…"), reused for all 7 pigeonhole runs. The model never chose the example.
25. The professor-style request names the example, so Agent 1 never weighs alternatives.
26. Every opening clones one template: `prompts/agent2-stage/plan-narration.md` has one
    narrated script (handshakes: "5 people walk into a room… Take a guess before we count…
    Most people say 25"), and every topic copies it ("N towns, M roads, a cost on each… take a
    guess"; dijkstra, hashtable, harmonic, pigeonhole).
27. Older runs all open with `[clear throat]`: an earlier prompt version required it on the
    first line.
28. No variety of hook types. 3b1b opens with stakes (windmills: the IMO), a real-world mystery
    (hamming: a scratched CD), a paradox (better-bayes), an object ("This is a Galton board."),
    a spoiler (subsets), his own confusion (prism) or a puzzle story (chessboard).

## F. No simulations

29. Beats are still pictures: nothing moves during a beat except `<point descend>`.
30. Agent 1's `run_python` simulations reach the screen only as fixed values.
31. No way to express repeated random processes: many balls through pegs, particles, random
    walks, collisions, "run N trials and tally". 3b1b: 107 of 218 scene files (2019–2026) use
    time-step updaters (`lambda m, dt`), 688 random calls; the CLT Galton board is random bits
    per ball → path → many balls staggered → stacking in buckets.
32. Held lines freeze the picture; in 3b1b the simulation keeps running while he talks.

## Open decisions

- Example choice: Agent 1 picks (compares 3–4 candidates), or requests keep naming it?
- Simulations: built-in sim tags, a `<sim>` tag with a written rule, or both (recommended)?
- Order: free layout + 2D camera first, or simulations first? Demo before any model run.
