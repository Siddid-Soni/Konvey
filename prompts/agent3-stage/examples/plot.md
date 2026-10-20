---
genre: plot
kinds: plot, tex
fits: function, graph, curve, approximation, polynomial, series, term, harmonic, partial sum, supply, demand, equilibrium, decay, exponential, rate, f(x), y =
topic_keywords: drug, dose, bloodstream, half-life, half life
---
### Example: function graphs that change in place (topic: a drug dose fading from the blood)

SCENE_SPEC (abridged): beats = [
 {vo_line: "One dose starts at 100 and halves every two hours.", objects: [{id: level, kind: plot, data: {fns: {"one dose": "100*0.5^(x/2)"}, x: [0, 12], y: [0, 160], points: {"half": [2, 50]}}}, {id: law, kind: tex, data: {tex: "c(t) = 100 \\cdot 2^{-t/2}"}}]},
 {vo_line: "Two more hours, and a quarter is left.", objects: [{id: level, kind: plot, data: {fns: {"one dose": "100*0.5^(x/2)"}, x: [0, 12], y: [0, 160], points: {"quarter": [4, 25]}}}]},
 {vo_line: "A second dose at hour six lands on what is left of the first.", objects: [{id: level, kind: plot, data: {fns: {"two doses": "100*0.5^(x/2) + 100*0.5^((x-6)/2)*(sign(x-6)+1)/2"}, x: [0, 12], y: [0, 160]}}]} ]

```html
<beats>
<beat vo="One dose starts at 100 and halves every two hours." t="2" shot="derive">
  <tex id="law">c(t) = 100 \cdot 2^{-t/2}</tex>
  <plot id="level" fn="one dose: 100*0.5^(x/2)" x="0,12" y="0,160" color="c1"
        points="half: 2,one dose" mark="x=2: 2 h" xlabel="hours" ylabel="mg/L" w="8" h="5.5"></plot>
</beat>

<beat vo="Two more hours, and a quarter is left." t="1.6" shot="derive">
  <tex id="law">c(t) = 100 \cdot 2^{-t/2}</tex>
  <plot id="level" fn="one dose: 100*0.5^(x/2)" x="0,12" y="0,160" color="c1"
        points="quarter: 4,one dose" mark="x=4: 4 h" xlabel="hours" ylabel="mg/L" w="8" h="5.5"></plot>
</beat>

<beat vo="A second dose at hour six lands on what is left of the first." t="2" shot="derive">
  <tex id="law">c(t) = 100 \cdot 2^{-t/2}</tex>
  <plot id="level" fn="two doses: 100*0.5^(x/2) + 100*0.5^((x-6)/2)*(sign(x-6)+1)/2" x="0,12" y="0,160"
        color="c1" mark="x=6: second dose" xlabel="hours" ylabel="mg/L" w="8" h="5.5"></plot>
</beat>
</beats>
```

Why it works: the curve is written as its formula, so it is exact and smooth; the axes and
ticks come from `x`/`y`. The point and the dashed mark slide from hour 2 to hour 4 along the
curve instead of being redrawn, and the second dose bends the same curve (same id, new `fn`):
the engine shows the jump at hour six as a clean step, never a hand-drawn line. The law stays
beside the graph it describes (`derive`) in every beat.
