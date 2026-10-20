---
genre: places-jump
kinds: places
fits: move, moves, transfer, pay, deal, dealt, drop, bucket, buckets, account, accounts, hand, hands, container, sort into, distribute, pass to
topic_keywords: bucket sort, buckets by tens, scatter into buckets
---
### Example: values dropped into buckets (topic: bucket sort by tens)

SCENE_SPEC (abridged): beats = [
 {vo_line: "Start with the values in the input list.", objects: [{id: bk, kind: places, data: {parts: ["input", "0-9", "10-19", "20-29"], links: "none", holds: {"input": ["23", "7", "15"]}}}]},
 {vo_line: "23 goes into the twenties bucket.", objects: [{id: bk, kind: places, data: {parts: [...], links: "none", holds: {"input": ["7", "15"], "20-29": ["23"]}}}]},
 {vo_line: "7 and 15 go to theirs.", objects: [{id: bk, kind: places, data: {parts: [...], links: "none", holds: {"0-9": ["7"], "10-19": ["15"], "20-29": ["23"]}}}]} ]

```html
<beats>
<beat vo="Start with the values in the input list." t="2.0" shot="full">
  <places id="bk" parts="input,0-9,10-19,20-29" links="none" shapes="0-9:bin;10-19:bin;20-29:bin" holds="input:23|7|15"></places>
</beat>

<beat vo="23 goes into the twenties bucket." t="2.2" shot="full">
  <places id="bk" parts="input,0-9,10-19,20-29" links="none" shapes="0-9:bin;10-19:bin;20-29:bin" holds="input:7|15; 20-29:23" highlight="20-29:23"></places>
</beat>

<beat vo="7 and 15 go to theirs." t="2.4" shot="full">
  <places id="bk" parts="input,0-9,10-19,20-29" links="none" shapes="0-9:bin;10-19:bin;20-29:bin" holds="0-9:7; 10-19:15; 20-29:23"></places>
</beat>
</beats>
```

Why it works: nothing physical joins the input and the buckets, so `links="none"` draws no wires
and a value that changes place jumps across in an arc; a held value that leaves one place and
appears in another is the same value moving (no item ids needed for plain contents). `bin` draws
the buckets as open containers. The same picture tells money moving between accounts, cards dealt
to players, or anything handed from place to place: name the places, list what each holds, and
change it beat by beat.
