---
genre: drawing-stack
kinds: drawing
fits: stack, push, pop, undo, call stack, plate, pile, last in
topic_keywords: push and pop, lifo, last in first out, stack data structure
---
### Example: a diagram built from shapes (topic: a stack, push and pop)

SCENE_SPEC (abridged): beats = [
 {vo_line: "A stack holds 4 and 9; only the top one can be reached.", objects: [{id: stack, kind: drawing, data: {shows: "plates 4 and 9 stacked in a holder, 4 at the bottom, an arrow at the top", labels: [4, 9]}}]},
 {vo_line: "Push 7: it lands on top of 9.", objects: [{id: stack, kind: drawing, data: {shows: "7 added on top", labels: [4, 9, 7]}}]},
 {vo_line: "Pop takes the top again, so 7 leaves first.", objects: [{id: stack, kind: drawing, data: {shows: "7 lifted off the top", labels: [4, 9]}}]} ]

```html
<beats>
<beat vo="A stack holds 4 and 9; only the top one can be reached." t="1.6" shot="full">
  <draw id="stack" w="6" h="4.2" x="0,6" y="0,7">
    <line id="walls" points="1.5,6; 1.5,0.3; 4.5,0.3; 4.5,6" color="muted"></line>
    <rect id="p4" x="3" y="0.8" w="2.6" h="0.8" round="0.15" color="c1" label="4"></rect>
    <rect id="p9" x="3" y="1.7" w="2.6" h="0.8" round="0.15" color="c2" label="9"></rect>
    <line id="top" from="5.9,1.7" to="4.8,1.7" arrow="true" color="accent"></line>
    <label id="toptxt" x="5.4" y="2.3" text="top" color="accent"></label>
  </draw>
</beat>

<beat vo="Push 7: it lands on top of 9." t="1.6" shot="full">
  <draw id="stack" w="6" h="4.2" x="0,6" y="0,7">
    <line id="walls" points="1.5,6; 1.5,0.3; 4.5,0.3; 4.5,6" color="muted"></line>
    <rect id="p4" x="3" y="0.8" w="2.6" h="0.8" round="0.15" color="c1" label="4"></rect>
    <rect id="p9" x="3" y="1.7" w="2.6" h="0.8" round="0.15" color="c2" label="9"></rect>
    <rect id="p7" x="3" y="2.6" w="2.6" h="0.8" round="0.15" color="c3" label="7"></rect>
    <line id="top" from="5.9,2.6" to="4.8,2.6" arrow="true" color="accent"></line>
    <label id="toptxt" x="5.4" y="3.2" text="top" color="accent"></label>
  </draw>
</beat>

<beat vo="Pop takes the top again, so 7 leaves first." t="1.6" shot="full">
  <draw id="stack" w="6" h="4.2" x="0,6" y="0,7">
    <line id="walls" points="1.5,6; 1.5,0.3; 4.5,0.3; 4.5,6" color="muted"></line>
    <rect id="p4" x="3" y="0.8" w="2.6" h="0.8" round="0.15" color="c1" label="4"></rect>
    <rect id="p9" x="3" y="1.7" w="2.6" h="0.8" round="0.15" color="c2" label="9"></rect>
    <line id="top" from="5.9,1.7" to="4.8,1.7" arrow="true" color="accent"></line>
    <label id="toptxt" x="5.4" y="2.3" text="top" color="accent"></label>
    <rect id="p7" x="5.6" y="6.4" w="2.6" h="0.8" round="0.15" color="c3" fill="0.3" label="7"></rect>
  </draw>
</beat>
</beats>
```

Why it works: no tag draws a stack, so the picture is built from `<draw>` shapes, and it looks
like the thing itself: a holder, plates sitting on each other, an arrow at the top. Each plate
keeps its id in every beat, so a push is one plate dropping into place, the arrow glides up
with the top, and the pop slides the same plate up and out (dimmed with `fill`) instead of
redrawing the stack. Coordinates are chosen so plates rest exactly on the one below (height
0.8, spacing 0.9), and the canvas keeps the same `w`/`h`/`x`/`y` in every beat.
