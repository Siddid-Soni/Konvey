---
genre: drawing-queue
kinds: drawing
fits: queue, buffer, producer, consumer, thread, process, lock, semaphore, mutex, pipe, job, task, worker, channel, backpressure
topic_keywords: bounded buffer, producer-consumer, producer consumer, ring buffer, circular buffer
---
### Example: fixed slots that fill and empty (topic: a bounded buffer between two threads)

SCENE_SPEC (abridged): beats = [
 {vo_line: "Four slots sit between a producer and a consumer. A, B and C are in; D is ready.", objects: [{id: buf, kind: drawing, data: {shows: "producer box, four empty slot outlines, consumer box; A, B, C in the first three slots; D waiting in the producer; in/out arrows", labels: ["producer", "consumer", "A", "B", "C", "D"]}}]},
 {vo_line: "The producer writes D into the last free slot. Now the buffer is full.", objects: [{id: buf, kind: drawing, data: {shows: "D slides into slot 4; the in arrow wraps to slot 1"}}]},
 {vo_line: "E is ready too, but no slot is free, so the producer has to wait.", objects: [{id: buf, kind: drawing, data: {shows: "E appears dimmed in the producer", labels: ["E", "waits"]}}]},
 {vo_line: "The consumer takes A from the front, and its slot is free again.", objects: [{id: buf, kind: drawing, data: {shows: "A moves over to the consumer; slot 1 is empty; the out arrow moves to slot 2"}}]},
 {vo_line: "E goes into the slot A left: the writes wrap around to the start.", objects: [{id: buf, kind: drawing, data: {shows: "E slides into slot 1, no longer dimmed"}}]},
 {vo_line: "The consumer takes B next: items leave in the order they came in.", objects: [{id: buf, kind: drawing, data: {shows: "B moves to the consumer; the out arrow moves to slot 3"}}]} ]

```html
<beats>
<beat vo="Four slots sit between a producer and a consumer. A, B and C are in; D is ready." t="1.6" shot="full">
  <draw id="buf" w="13" h="5.2" x="0,20" y="0,8" size="30">
    <rect id="prod" x="2.5" y="4" w="3.6" h="3.2" round="0.3" color="c1" fill="0.12"></rect>
    <rect id="cons" x="17.5" y="4" w="3.6" h="3.2" round="0.3" color="c3" fill="0.12"></rect>
    <label id="prodname" x="2.5" y="1.6" text="producer" color="muted"></label>
    <label id="consname" x="17.5" y="1.6" text="consumer" color="muted"></label>
    <rect id="slot0" x="6.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <rect id="slot1" x="8.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <rect id="slot2" x="10.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <rect id="slot3" x="12.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <line id="in" from="12.9,6.6" to="12.9,5.1" arrow="true" color="c1" move="slide"></line>
    <label id="inname" x="12.9" y="7.2" text="in" color="c1" move="slide"></label>
    <line id="out" from="6.9,1.2" to="6.9,2.9" arrow="true" color="c3" move="slide"></line>
    <label id="outname" x="6.9" y="0.6" text="out" color="c3" move="slide"></label>
    <rect id="a" x="6.9" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="A"></rect>
    <rect id="b" x="8.9" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="B"></rect>
    <rect id="c" x="10.9" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="C"></rect>
    <rect id="d" x="2.5" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="D"></rect>
  </draw>
</beat>

<beat vo="The producer writes D into the last free slot. Now the buffer is full." t="1.6" shot="full">
  <draw id="buf" w="13" h="5.2" x="0,20" y="0,8" size="30">
    <rect id="prod" x="2.5" y="4" w="3.6" h="3.2" round="0.3" color="c1" fill="0.12"></rect>
    <rect id="cons" x="17.5" y="4" w="3.6" h="3.2" round="0.3" color="c3" fill="0.12"></rect>
    <label id="prodname" x="2.5" y="1.6" text="producer" color="muted"></label>
    <label id="consname" x="17.5" y="1.6" text="consumer" color="muted"></label>
    <rect id="slot0" x="6.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <rect id="slot1" x="8.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <rect id="slot2" x="10.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <rect id="slot3" x="12.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <line id="in" from="6.9,6.6" to="6.9,5.1" arrow="true" color="c1" move="slide"></line>
    <label id="inname" x="6.9" y="7.2" text="in" color="c1" move="slide"></label>
    <line id="out" from="6.9,1.2" to="6.9,2.9" arrow="true" color="c3" move="slide"></line>
    <label id="outname" x="6.9" y="0.6" text="out" color="c3" move="slide"></label>
    <rect id="a" x="6.9" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="A"></rect>
    <rect id="b" x="8.9" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="B"></rect>
    <rect id="c" x="10.9" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="C"></rect>
    <rect id="d" x="12.9" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="D" move="slide"></rect>
  </draw>
</beat>

<beat vo="E is ready too, but no slot is free, so the producer has to wait." t="1.6" shot="full">
  <draw id="buf" w="13" h="5.2" x="0,20" y="0,8" size="30">
    <rect id="prod" x="2.5" y="4" w="3.6" h="3.2" round="0.3" color="c1" fill="0.12"></rect>
    <rect id="cons" x="17.5" y="4" w="3.6" h="3.2" round="0.3" color="c3" fill="0.12"></rect>
    <label id="prodname" x="2.5" y="1.6" text="producer" color="muted"></label>
    <label id="consname" x="17.5" y="1.6" text="consumer" color="muted"></label>
    <rect id="slot0" x="6.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <rect id="slot1" x="8.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <rect id="slot2" x="10.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <rect id="slot3" x="12.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <line id="in" from="6.9,6.6" to="6.9,5.1" arrow="true" color="c1" move="slide"></line>
    <label id="inname" x="6.9" y="7.2" text="in" color="c1" move="slide"></label>
    <line id="out" from="6.9,1.2" to="6.9,2.9" arrow="true" color="c3" move="slide"></line>
    <label id="outname" x="6.9" y="0.6" text="out" color="c3" move="slide"></label>
    <rect id="a" x="6.9" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="A"></rect>
    <rect id="b" x="8.9" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="B"></rect>
    <rect id="c" x="10.9" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="C"></rect>
    <rect id="d" x="12.9" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="D"></rect>
    <rect id="e" x="2.5" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="E" fill="0.3"></rect>
    <label id="wait" x="2.5" y="6.4" text="waits" color="accent"></label>
  </draw>
</beat>

<beat vo="The consumer takes A from the front, and its slot is free again." t="1.6" shot="full">
  <draw id="buf" w="13" h="5.2" x="0,20" y="0,8" size="30">
    <rect id="prod" x="2.5" y="4" w="3.6" h="3.2" round="0.3" color="c1" fill="0.12"></rect>
    <rect id="cons" x="17.5" y="4" w="3.6" h="3.2" round="0.3" color="c3" fill="0.12"></rect>
    <label id="prodname" x="2.5" y="1.6" text="producer" color="muted"></label>
    <label id="consname" x="17.5" y="1.6" text="consumer" color="muted"></label>
    <rect id="slot0" x="6.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <rect id="slot1" x="8.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <rect id="slot2" x="10.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <rect id="slot3" x="12.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <line id="in" from="6.9,6.6" to="6.9,5.1" arrow="true" color="c1" move="slide"></line>
    <label id="inname" x="6.9" y="7.2" text="in" color="c1" move="slide"></label>
    <line id="out" from="8.9,1.2" to="8.9,2.9" arrow="true" color="c3" move="slide"></line>
    <label id="outname" x="8.9" y="0.6" text="out" color="c3" move="slide"></label>
    <rect id="a" x="17.5" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="A" move="hop"></rect>
    <rect id="b" x="8.9" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="B"></rect>
    <rect id="c" x="10.9" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="C"></rect>
    <rect id="d" x="12.9" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="D"></rect>
    <rect id="e" x="2.5" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="E" fill="0.3"></rect>
    <label id="wait" x="2.5" y="6.4" text="waits" color="accent"></label>
  </draw>
</beat>

<beat vo="E goes into the slot A left: the writes wrap around to the start." t="1.6" shot="full">
  <draw id="buf" w="13" h="5.2" x="0,20" y="0,8" size="30">
    <rect id="prod" x="2.5" y="4" w="3.6" h="3.2" round="0.3" color="c1" fill="0.12"></rect>
    <rect id="cons" x="17.5" y="4" w="3.6" h="3.2" round="0.3" color="c3" fill="0.12"></rect>
    <label id="prodname" x="2.5" y="1.6" text="producer" color="muted"></label>
    <label id="consname" x="17.5" y="1.6" text="consumer" color="muted"></label>
    <rect id="slot0" x="6.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <rect id="slot1" x="8.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <rect id="slot2" x="10.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <rect id="slot3" x="12.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <line id="in" from="8.9,6.6" to="8.9,5.1" arrow="true" color="c1" move="slide"></line>
    <label id="inname" x="8.9" y="7.2" text="in" color="c1" move="slide"></label>
    <line id="out" from="8.9,1.2" to="8.9,2.9" arrow="true" color="c3" move="slide"></line>
    <label id="outname" x="8.9" y="0.6" text="out" color="c3" move="slide"></label>
    <rect id="b" x="8.9" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="B"></rect>
    <rect id="c" x="10.9" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="C"></rect>
    <rect id="d" x="12.9" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="D"></rect>
    <rect id="e" x="6.9" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="E" move="slide"></rect>
  </draw>
</beat>

<beat vo="The consumer takes B next: items leave in the order they came in." t="1.6" shot="full">
  <draw id="buf" w="13" h="5.2" x="0,20" y="0,8" size="30">
    <rect id="prod" x="2.5" y="4" w="3.6" h="3.2" round="0.3" color="c1" fill="0.12"></rect>
    <rect id="cons" x="17.5" y="4" w="3.6" h="3.2" round="0.3" color="c3" fill="0.12"></rect>
    <label id="prodname" x="2.5" y="1.6" text="producer" color="muted"></label>
    <label id="consname" x="17.5" y="1.6" text="consumer" color="muted"></label>
    <rect id="slot0" x="6.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <rect id="slot1" x="8.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <rect id="slot2" x="10.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <rect id="slot3" x="12.9" y="4" w="1.8" h="1.8" color="muted" fill="none"></rect>
    <line id="in" from="8.9,6.6" to="8.9,5.1" arrow="true" color="c1" move="slide"></line>
    <label id="inname" x="8.9" y="7.2" text="in" color="c1" move="slide"></label>
    <line id="out" from="10.9,1.2" to="10.9,2.9" arrow="true" color="c3" move="slide"></line>
    <label id="outname" x="10.9" y="0.6" text="out" color="c3" move="slide"></label>
    <rect id="b" x="17.5" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="B" move="hop"></rect>
    <rect id="c" x="10.9" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="C"></rect>
    <rect id="d" x="12.9" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="D"></rect>
    <rect id="e" x="6.9" y="4" w="1.5" h="1.5" round="0.2" color="c2" z="1" label="E"></rect>
  </draw>
</beat>
</beats>
```

Why it works: the slots are outlines that never move (`fill="none"`), and the items are separate
shapes that keep their ids, so filling, waiting and taking are items moving between places that
stay put. An item that cannot go anywhere yet stays where it is, dimmed (`fill="0.3"`) with a
word saying why, and lights up when it finally moves. Moves along the row use `move="slide"`;
an item that leaves past the others uses `move="hop"` so it arcs over them instead of sliding
through them. The in/out arrows are shapes too, sliding to the slot they point at, which shows
the wrap-around without a word of explanation.
