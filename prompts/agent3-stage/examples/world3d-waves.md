---
genre: world3d-waves
kinds: waves, particles, paths
fits: wave, ripple, interference, oscillation, vibration, crest, trough, standing wave, orbit, attract, repel
topic_keywords: pond, stone, stones, splash
---
### Example: a field that changes in time (topic: ripples from two stones dropped in a pond)

SCENE_SPEC (abridged): beats = [
 {vo_line: "Drop one stone in a still pond.", objects: [{id: pond, kind: waves, data: {sources: [[0, 0]], wavelength: 0.9, until: 6}}]},
 {vo_line: "Drop two side by side. Where their rings cross, the water rises higher, or stays flat.", objects: [{id: pond, kind: waves, data: {sources: [[-1.2, 0], [1.2, 0]], until: 16}}]},
 {vo_line: "Ask only how hard each spot shakes, and calm lanes fan out between the stones.", objects: [{id: pond, kind: waves, data: {sources: [[-1.2, 0], [1.2, 0]], show: intensity, until: 22}}]} ]

```html
<beats>
<beat vo="Drop one stone in a still pond." shot="full">
  <world>
    <waves id="pond" sources="0,0" wavelength="0.9" size="9" t="6"></waves>
  </world>
  <camera theta="0" phi="55"></camera>
</beat>

<beat vo="Drop two side by side. Where their rings cross, the water rises higher, or stays flat." shot="full">
  <world>
    <waves id="pond" sources="-1.2,0; 1.2,0" wavelength="0.9" size="9" lift="0.4" t="16"></waves>
  </world>
  <camera theta="30" phi="62"></camera>
</beat>

<beat vo="Ask only how hard each spot shakes, and calm lanes fan out between the stones." shot="full">
  <world>
    <waves id="pond" sources="-1.2,0; 1.2,0" wavelength="0.9" size="9" show="intensity" t="22"></waves>
  </world>
  <camera theta="0" phi="0"></camera>
</beat>
</beats>
```

Why it works: one `<waves>` id carries the whole scene and its clock (`t`) only grows, so the rings
keep travelling through every line. The second source slides in from the first; `lift` raises
the sheet into heights for the line about water rising, and the camera comes down top-down for
the pattern of lanes, which is flat by nature. Nothing is drawn by hand: the engine sums the waves.
