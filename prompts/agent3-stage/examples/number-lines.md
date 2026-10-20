---
genre: number-lines
kinds: numberline, brace, note, tex
fits: number line, input, output, slider, value, step, steps, scale, convert, conversion, function, maps, sends, nudge, small change, range, interval, where does, lands
topic_keywords: celsius, fahrenheit, temperature, degrees
---
### Example: a value carried through steps on stacked number lines (topic: Celsius to Fahrenheit)

SCENE_SPEC (abridged): beats = [
 {vo_line: "Twenty degrees Celsius: first multiply by one point eight, then add thirty two.", objects: [{id: c, kind: numberline, data: {x: [0, 40], markers: {"C": 20}}}, {id: m, kind: numberline, data: {x: [0, 72], markers: {"1.8C": 36}}}, {id: f, kind: numberline, data: {x: [32, 104], markers: {"F": 68}}}]},
 {vo_line: "Warm it by five degrees, and Fahrenheit moves by nine.", objects: [{id: c, kind: numberline, data: {x: [0, 40], markers: {"C": 25}}}, {id: m, kind: numberline, data: {x: [0, 72], markers: {"1.8C": 45}}}, {id: f, kind: numberline, data: {x: [32, 104], markers: {"F": 77}}}, {id: dc, kind: brace, data: {on: c, from: [20, 0], to: [25, 0], label: "5"}}, {id: df, kind: brace, data: {on: f, from: [68, 0], to: [77, 0], label: "9"}}]},
 {vo_line: "So every Celsius degree is worth one point eight of Fahrenheit's.", objects: [{id: law, kind: tex, data: {tex: "F = 1.8\\,C + 32"}}, {id: per, kind: note, data: {text: "1.8 per degree", to: "law>1.8"}}]} ]

```html
<beats>
<beat vo="Twenty degrees Celsius: first multiply by one point eight, then add thirty two." t="2" style="padding: 0.75u 0.8u; gap: 0.35u">
  <div class="row center" style="height: 1.3u"></div>
  <div class="grow col center" style="gap: 0.7u; padding-right: 2u">
    <numberline id="c" x="0,40" markers="C: 20"></numberline>
    <numberline id="m" x="0,72" markers="1.8C: 36"></numberline>
    <numberline id="f" x="32,104" markers="F: 68"></numberline>
  </div>
  <arrow id="s1" from="c>x=42" to="m>x=76" label="\times 1.8"></arrow>
  <arrow id="s2" from="m>x=76" to="f>x=108" label="+32"></arrow>
</beat>

<beat vo="Warm it by five degrees, and Fahrenheit moves by nine." t="2.2" style="padding: 0.75u 0.8u; gap: 0.35u">
  <div class="row center" style="height: 1.3u"></div>
  <div class="grow col center" style="gap: 0.7u; padding-right: 2u">
    <numberline id="c" x="0,40" markers="C: 25"></numberline>
    <numberline id="m" x="0,72" markers="1.8C: 45"></numberline>
    <numberline id="f" x="32,104" markers="F: 77"></numberline>
  </div>
  <arrow id="s1" from="c>x=42" to="m>x=76" label="\times 1.8"></arrow>
  <arrow id="s2" from="m>x=76" to="f>x=108" label="+32"></arrow>
  <brace id="dc" on="c" from="20,0" to="25,0" label="5"></brace>
  <brace id="df" on="f" from="68,0" to="77,0" label="9"></brace>
</beat>

<beat vo="So every Celsius degree is worth one point eight of Fahrenheit's." t="2" style="padding: 0.75u 0.8u; gap: 0.35u">
  <div class="row center" style="height: 1.3u"><tex id="law" size="56">F = 1.8\,C + 32</tex></div>
  <div class="grow col center" style="gap: 0.7u; padding-right: 2u">
    <numberline id="c" x="0,40" markers="C: 25"></numberline>
    <numberline id="m" x="0,72" markers="1.8C: 45"></numberline>
    <numberline id="f" x="32,104" markers="F: 77"></numberline>
  </div>
  <arrow id="s1" from="c>x=42" to="m>x=76" label="\times 1.8"></arrow>
  <arrow id="s2" from="m>x=76" to="f>x=108" label="+32"></arrow>
  <brace id="dc" on="c" from="20,0" to="25,0" label="5" dim="true"></brace>
  <brace id="df" on="f" from="68,0" to="77,0" label="9"></brace>
  <note id="per" to="law>1.8" text="1.8 per degree"></note>
</beat>
</beats>
```

Why it works: each step is its own line, stacked, so the eye follows the value down; the markers
keep their names and only their values change, so a new input slides all three at once. The step
arrows sit just past the lines' right ends (`x=42` on a line that ends at 40), in the room the
padding leaves, so they never cross a number. The braces show the change on both ends at once,
and the note points at the one symbol the line is about.
