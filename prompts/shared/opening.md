# The opening: the first lines the viewer hears

You write only the opening of a short math explainer video: the first 3–5 lines the narrator
says, before the video starts working on the question. Output ONLY JSON:

```json
{"explains": "<what the video will explain: the reason or method, in one sentence (never said in the opening)>",
 "drafts": {"concrete": ["<line>", "…"], "matters": ["<line>", "…"], "confusion": ["<line>", "…"]},
 "kind": "<the draft that suits this topic best: concrete | matters | confusion>",
 "why_this_kind": "<one sentence>",
 "lines": ["<the chosen draft, polished>"],
 "on_screen": "<what the viewer sees while the opening plays>"}
```

Write all three drafts, each 3–5 lines, each a real opening of its kind, then choose.

## How 3Blue1Brown opens a video

He never opens with the explanation, a summary, or a slogan about the answer. Every opening is
one of three kinds. These are his own words, from his videos:

**`concrete`: shows one concrete thing, points at what is strange about it, ends on a question.**
- "This is a 3. It's sloppily written and rendered at an extremely low resolution of 28 by 28
  pixels, but your brain has no trouble recognizing it as a 3. And I want you to take a moment
  to appreciate how crazy it is that brains can do this so effortlessly."
- "You're buying a product online, and you see three different sellers. One of them has a 100%
  positive rating, but with only 10 reviews. Another has a 96% positive rating, with 50 total
  reviews. And yet another has 93%, but with 200 reviews. Which one should you buy from?"
- "I have up on screen here a sequence of computations, and each one happens to equal pi. You
  might think this was a pattern that would go on forever. But it doesn't. At some point it
  stops."
- "Let me show you something I find completely magical. Behind this piece of glass, there
  appears to be a three-dimensional scene. But it's an illusion. In reality, all that's there
  is an empty table and a laser beam."

**`matters`: starts with what the question matters for, or what it is really about.**
- "Every year, more than 100 countries send six of their brightest teenagers to the
  International Math Olympiad… Only one of them got a perfect score. And the only thing
  standing between the next two and a perfect score was problem number two."
- "Do you know about the Putnam? It's a six-hour test with 12 questions, taken only by students
  who love math, and yet the median score is around 1 or 2."

**`confusion`: starts with a confusion, or a familiar fact nobody questions.**
- "I realized recently that I didn't really understand how a prism works, and I suspect most
  people out there don't either."
- "e to the pi i equals negative one is one of the most famous equations in math, but it's also
  one of the most confusing."
- "Eigenvectors and eigenvalues is one of those topics that a lot of students find particularly
  unintuitive. Questions like 'why are we doing this' are left floating away in an unanswered
  sea of computations."

## What makes these work

- **Something real comes first**: a digit, three sellers with their numbers, a test and its
  median score, an album cover. Never an abstract claim ("you can know things without
  looking"), never a list of counts ("five towns, seven roads, and a cost on each").
- **It points at the strange part** in plain words: "how crazy it is", "But it doesn't", "But
  it's an illusion", "and yet the median score is 1 or 2", "I didn't really understand".
- **It ends open.** The viewer is left with a question they cannot answer yet.
- **It never explains.** Write `explains` first: that is exactly what the opening must not say,
  in any wording. No method, no mechanism, no principle's name, no "always", "guaranteed",
  "certain", "must", "the trick is", no hint at the reason. A surprising *result* may be shown
  only when the video is about *why* it is true, and then the opening asks that why ("Euler
  found the answer to be pi squared over 6. What is pi doing here?").
- **It talks like a person**: "you", "I", "let me show you", short spoken sentences, each line
  at most 20 words. No hype words, no "Imagine a world where".

Choosing the kind: a puzzle or a surprising phenomenon the viewer can watch → `concrete`; a
tool or idea used everywhere, a lesson that the question is really a vehicle for, a famous hard
problem → `matters`; a formula, fact or idea everyone has met but few understand, or a common
misconception → `confusion`. A `matters` opening names real places it matters, with a concrete
detail ("used in image processing, in probability, in solving differential equations"); a
`confusion` opening names the familiar fact first, then why it is strange that nobody asks.
