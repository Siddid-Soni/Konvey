---
genre: chart
kinds: chart, bars, number
topic_keywords: coffee, cooling, newton's law of cooling, room temperature
---
### Example: a chart scene (topic: a cup of coffee cooling)

SCENE_SPEC (abridged): beats = [
 {vo_line: "Fresh coffee at ninety degrees cools fast at first, then slower.", objects: [{id: temp, kind: chart, data: {series: {"coffee": [90, 55, 37.5, 28.8, 24.4]}, x: [0, 40]}}, {id: law, kind: tex, data: {tex: "T(t) = 20 + 70\\,e^{-kt}"}}]},
 {vo_line: "The gap to the room halves every ten minutes.", objects: [{id: temp, kind: chart, data: {series: {"coffee": [90, 55, 37.5, 28.8, 24.4], "room": [20, 20, 20, 20, 20]}, x: [0, 40]}}, {id: gap, kind: bars, data: {labels: ["0 min", "10 min", "20 min"], values: [70, 35, 17.5]}}]} ]

```html
<beats>
<beat vo="Fresh coffee at ninety degrees cools fast at first, then slower." t="2.4" shot="derive">
  <chart id="temp" series="coffee:90,55,37.5,28.8,24.4" x="0,40" y="0,100" mark="coffee:max"
         xlabel="minutes" ylabel="°C" w="8" h="5.5"></chart>
  <tex id="law">T(t) = 20 + 70\,e^{-kt}</tex>
</beat>

<beat vo="The gap to the room halves every ten minutes." t="2" shot="compare">
  <chart id="temp" series="coffee:90,55,37.5,28.8,24.4;room:20,20,20,20,20" x="0,40" y="0,100"
         colors="accent,muted" mark="x:10;x:20" xlabel="minutes" ylabel="°C" w="6" h="3.6"></chart>
  <bars id="gap" labels="0 min,10 min,20 min" values="70,35,17.5" suffix="°" highlight="1"></bars>
</beat>
</beats>
```

Why it works: the chart is drawn line by line as it enters, the engine marks the starting peak
from the data instead of a hand-placed label, and the second beat makes the claim visible two
ways at once: guide lines every ten minutes on the curve, and bars that halve. Every number is
copied from the plan. No headline: the law sits beside the curve it describes (`derive`), then gives way
to the two pictures side by side (`compare`).
