---
genre: diagram
kinds: text, shape, arrow, custom
topic_keywords: caesar, cipher, shift cipher, encrypt, decrypt, alphabet
---
### Example: a diagram scene (topic: the Caesar shift cipher)

SCENE_SPEC (abridged): beats = [
 {vo_line: "Every letter moves three places down the alphabet.", objects: [{id: rule, kind: tex, data: {tex: "c = p + 3"}}, {id: plain, kind: array, data: {values: ["A", "B", "C", "D", "E", "F"]}}, {id: coded, kind: array, data: {values: ["D", "E", "F", "G", "H", "I"]}}]},
 {vo_line: "Near the end it wraps around, so X becomes A.", objects: [{id: rule, kind: tex, data: {tex: "c = (p + 3) \\bmod 26"}}, {id: plain_end, kind: array, data: {values: ["U", "V", "W", "X", "Y", "Z"]}}, {id: coded_end, kind: array, data: {values: ["X", "Y", "Z", "A", "B", "C"]}}]} ]

```html
<beats>
<beat vo="Every letter moves three places down the alphabet." t="2" style="padding: 0.5u 0.6u; gap: 0.2u">
  <tex id="rule">c = p + 3</tex>
  <div class="grow col center" style="gap: 0.35u">
    <div class="row center" style="gap: 0.4u">
      <text id="plain_label" color="muted">plain</text>
      <array id="plain" values="A,B,C,D,E,F" index="none" highlight="0"></array>
    </div>
    <div class="row center" style="gap: 0.4u">
      <text id="coded_label" color="muted">coded</text>
      <array id="coded" values="D,E,F,G,H,I" index="none" highlight="0"></array>
    </div>
  </div>
</beat>

<beat vo="Near the end it wraps around, so X becomes A." t="2.2" style="padding: 0.5u 0.6u; gap: 0.2u">
  <tex id="rule" morph="match">c = (p + 3) \bmod 26</tex>
  <div class="grow col center" style="gap: 0.35u">
    <div class="row center" style="gap: 0.4u">
      <text id="plain_label" color="muted">plain</text>
      <array id="plain_end" values="U,V,W,X,Y,Z" index="none" highlight="3"></array>
    </div>
    <div class="row center" style="gap: 0.4u">
      <text id="coded_label" color="muted">coded</text>
      <array id="coded_end" values="X,Y,Z,A,B,C" index="none" highlight="3" emphasize="flash"></array>
    </div>
  </div>
  <text id="note">The alphabet is a <em>circle</em>, not a line.</text>
</beat>
</beats>
```

Why it works: no shot stacks two rows in line with each other, so this screen is written as
HTML (a column of two rows): the exception, not the rule. Two aligned rows make the mapping
visible without arrows; the highlight sits on
the same column in both rows, so the eye reads "this becomes that"; the rule morphs when it
gains the wrap-around; one short line of text with `<em>` names the idea to remember.
