---
genre: network
kinds: graph
topic_keywords: sales tax, price change, receipt, bill total
fits: forward, backward, chain rule, derivative, layer, unit, attention, signal, propagate
---
### Example: values flowing forward and back along edges (topic: how a price change reaches the bill)

SCENE_SPEC (abridged): beats = [
 {vo_line: "A price goes through tax, then times three items.", objects: [{id: bill, kind: graph, data: {nodes: [price, taxed, total], edges: [[price, taxed, "×1.2"], [taxed, total, "×3"]], values: {price: 10}}}]},
 {vo_line: "Forward: 10 becomes 12 after tax, and 36 for three.", objects: [{id: bill, kind: graph, data: {values: {price: 10, taxed: 12, total: 36}, flow: [price, taxed, total]}}]},
 {vo_line: "Backward: one more on taxed adds 3 to the total; one more on price adds 1.2 times 3, that is 3.6.", objects: [{id: bill, kind: graph, data: {edge_values: {"taxed-total": 3, "price-taxed": 3.6}, flow: [total, taxed, price], highlight: [price]}}]} ]

```html
<beats>
<beat vo="A price goes through tax, then times three items." t="1.6" shot="full">
  <graph id="bill" nodes="price:0,0;taxed:3,0;total:6,0" edges="price>taxed:×1.2;taxed>total:×3" values="price:10" w="9" h="2" size="36"></graph>
</beat>

<beat vo="Forward: 10 becomes 12 after tax, and 36 for three." t="3" shot="full">
  <graph id="bill" nodes="price:0,0;taxed:3,0;total:6,0" edges="price>taxed:×1.2;taxed>total:×3" values="price:10;taxed:12;total:36" flow="price>taxed>total" highlight="total" w="9" h="2" size="36"></graph>
</beat>

<beat vo="Backward: one more on taxed adds 3 to the total; one more on price adds 1.2 times 3, that is 3.6." t="3" shot="full">
  <graph id="bill" nodes="price:0,0;taxed:3,0;total:6,0" edges="price>taxed:×1.2;taxed>total:×3" values="price:10;taxed:12;total:36" edge-values="taxed-total:3;price-taxed:3.6" flow="total>taxed>price" highlight="price" w="9" h="2" size="36"></graph>
</beat>
</beats>
```

Why it works: one graph id with the same `nodes` and `edges` throughout. Beat 2's new `flow`
sends a dot from price to taxed to total, and each new value appears as the dot arrives, so the
numbers are seen to travel forward. Beat 3 sends a dot back the other way (against the arrows):
it carries each new `edge-values` number and drops it on its edge, so what flows back is visible
edge by edge. The edge weights stay above the edges, the carried numbers below.
