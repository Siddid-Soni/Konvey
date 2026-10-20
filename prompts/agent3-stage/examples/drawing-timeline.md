---
genre: drawing-timeline
kinds: drawing
fits: schedule, scheduler, scheduling, cpu, core, process, thread, time, timeline, task, interrupt, deadline, latency, gantt, turn, waiting time
topic_keywords: round robin, round-robin, time slice, quantum
---
### Example: work laid out on a time axis (topic: round-robin CPU scheduling)

SCENE_SPEC (abridged): beats = [
 {vo_line: "Three processes share one CPU. Each turn lasts at most 2 time units.", objects: [{id: cpu, kind: drawing, data: {shows: "three empty rows P1, P2, P3 on a time axis 0 to 10, work left 3, 5, 2, a dashed now line at 0", labels: ["P1", "P2", "P3", 3, 5, 2]}}]},
 {vo_line: "P1 runs first for its full 2 units, then goes to the back of the line.", objects: [{id: cpu, kind: drawing, data: {shows: "a block 0-2 in P1's row; now moves to 2; P1 has 1 left"}}]},
 {vo_line: "P2 gets 2 units, then P3 gets 2 and is finished.", objects: [{id: cpu, kind: drawing, data: {shows: "blocks 2-4 for P2 and 4-6 for P3; now at 6", labels: ["done"]}}]},
 {vo_line: "P1 needs only 1 more unit, so its turn ends early and it is done.", objects: [{id: cpu, kind: drawing, data: {shows: "a short block 6-7 for P1; now at 7"}}]},
 {vo_line: "Only P2 is left, so it runs turn after turn until time 10.", objects: [{id: cpu, kind: drawing, data: {shows: "P2 blocks 7-9 and 9-10; now at 10"}}]} ]

```html
<beats>
<beat vo="Three processes share one CPU. Each turn lasts at most 2 time units." t="1.6" shot="full">
  <draw id="cpu" w="13" h="5.2" x="-3,11" y="0,7" size="30">
    <label id="name1" x="-2.3" y="5.0" text="P1" color="c1"></label>
    <line id="lane1" from="0,5.0" to="10.4,5.0" color="muted" width="1"></line>
    <label id="name2" x="-2.3" y="3.8" text="P2" color="c2"></label>
    <line id="lane2" from="0,3.8" to="10.4,3.8" color="muted" width="1"></line>
    <label id="name3" x="-2.3" y="2.6" text="P3" color="c3"></label>
    <line id="lane3" from="0,2.6" to="10.4,2.6" color="muted" width="1"></line>
    <label id="lefthead" x="-1.0" y="6.2" text="left" color="muted"></label>
    <label id="left1" x="-1.0" y="5.0" text="3" color="ink"></label>
    <label id="left2" x="-1.0" y="3.8" text="5" color="ink"></label>
    <label id="left3" x="-1.0" y="2.6" text="2" color="ink"></label>
    <line id="axis" from="0,1.6" to="10.6,1.6" arrow="true" color="muted" width="2"></line>
    <label id="t0" x="0" y="1.0" text="0" color="muted"></label>
    <label id="t2" x="2" y="1.0" text="2" color="muted"></label>
    <label id="t4" x="4" y="1.0" text="4" color="muted"></label>
    <label id="t6" x="6" y="1.0" text="6" color="muted"></label>
    <label id="t8" x="8" y="1.0" text="8" color="muted"></label>
    <label id="t10" x="10" y="1.0" text="10" color="muted"></label>
    <line id="now" from="0,6.0" to="0,1.6" dashed="true" color="accent" width="3" z="1" move="slide"></line>
    <label id="nowname" x="0" y="6.5" text="now" color="accent" move="slide"></label>
  </draw>
</beat>

<beat vo="P1 runs first for its full 2 units, then goes to the back of the line." t="1.6" shot="full">
  <draw id="cpu" w="13" h="5.2" x="-3,11" y="0,7" size="30">
    <label id="name1" x="-2.3" y="5.0" text="P1" color="c1"></label>
    <line id="lane1" from="0,5.0" to="10.4,5.0" color="muted" width="1"></line>
    <label id="name2" x="-2.3" y="3.8" text="P2" color="c2"></label>
    <line id="lane2" from="0,3.8" to="10.4,3.8" color="muted" width="1"></line>
    <label id="name3" x="-2.3" y="2.6" text="P3" color="c3"></label>
    <line id="lane3" from="0,2.6" to="10.4,2.6" color="muted" width="1"></line>
    <label id="lefthead" x="-1.0" y="6.2" text="left" color="muted"></label>
    <label id="left1" x="-1.0" y="5.0" text="1" color="ink"></label>
    <label id="left2" x="-1.0" y="3.8" text="5" color="ink"></label>
    <label id="left3" x="-1.0" y="2.6" text="2" color="ink"></label>
    <line id="axis" from="0,1.6" to="10.6,1.6" arrow="true" color="muted" width="2"></line>
    <label id="t0" x="0" y="1.0" text="0" color="muted"></label>
    <label id="t2" x="2" y="1.0" text="2" color="muted"></label>
    <label id="t4" x="4" y="1.0" text="4" color="muted"></label>
    <label id="t6" x="6" y="1.0" text="6" color="muted"></label>
    <label id="t8" x="8" y="1.0" text="8" color="muted"></label>
    <label id="t10" x="10" y="1.0" text="10" color="muted"></label>
    <rect id="b1" x="1" y="5.0" w="1.9" h="0.8" color="c1"></rect>
    <line id="now" from="2,6.0" to="2,1.6" dashed="true" color="accent" width="3" z="1" move="slide"></line>
    <label id="nowname" x="2" y="6.5" text="now" color="accent" move="slide"></label>
  </draw>
</beat>

<beat vo="P2 gets 2 units, then P3 gets 2 and is finished." t="1.6" shot="full">
  <draw id="cpu" w="13" h="5.2" x="-3,11" y="0,7" size="30">
    <label id="name1" x="-2.3" y="5.0" text="P1" color="c1"></label>
    <line id="lane1" from="0,5.0" to="10.4,5.0" color="muted" width="1"></line>
    <label id="name2" x="-2.3" y="3.8" text="P2" color="c2"></label>
    <line id="lane2" from="0,3.8" to="10.4,3.8" color="muted" width="1"></line>
    <label id="name3" x="-2.3" y="2.6" text="P3" color="c3"></label>
    <line id="lane3" from="0,2.6" to="10.4,2.6" color="muted" width="1"></line>
    <label id="lefthead" x="-1.0" y="6.2" text="left" color="muted"></label>
    <label id="left1" x="-1.0" y="5.0" text="1" color="ink"></label>
    <label id="left2" x="-1.0" y="3.8" text="3" color="ink"></label>
    <label id="left3" x="-1.0" y="2.6" text="done" color="muted"></label>
    <line id="axis" from="0,1.6" to="10.6,1.6" arrow="true" color="muted" width="2"></line>
    <label id="t0" x="0" y="1.0" text="0" color="muted"></label>
    <label id="t2" x="2" y="1.0" text="2" color="muted"></label>
    <label id="t4" x="4" y="1.0" text="4" color="muted"></label>
    <label id="t6" x="6" y="1.0" text="6" color="muted"></label>
    <label id="t8" x="8" y="1.0" text="8" color="muted"></label>
    <label id="t10" x="10" y="1.0" text="10" color="muted"></label>
    <rect id="b1" x="1" y="5.0" w="1.9" h="0.8" color="c1"></rect>
    <rect id="b2" x="3" y="3.8" w="1.9" h="0.8" color="c2"></rect>
    <rect id="b3" x="5" y="2.6" w="1.9" h="0.8" color="c3"></rect>
    <line id="now" from="6,6.0" to="6,1.6" dashed="true" color="accent" width="3" z="1" move="slide"></line>
    <label id="nowname" x="6" y="6.5" text="now" color="accent" move="slide"></label>
  </draw>
</beat>

<beat vo="P1 needs only 1 more unit, so its turn ends early and it is done." t="1.6" shot="full">
  <draw id="cpu" w="13" h="5.2" x="-3,11" y="0,7" size="30">
    <label id="name1" x="-2.3" y="5.0" text="P1" color="c1"></label>
    <line id="lane1" from="0,5.0" to="10.4,5.0" color="muted" width="1"></line>
    <label id="name2" x="-2.3" y="3.8" text="P2" color="c2"></label>
    <line id="lane2" from="0,3.8" to="10.4,3.8" color="muted" width="1"></line>
    <label id="name3" x="-2.3" y="2.6" text="P3" color="c3"></label>
    <line id="lane3" from="0,2.6" to="10.4,2.6" color="muted" width="1"></line>
    <label id="lefthead" x="-1.0" y="6.2" text="left" color="muted"></label>
    <label id="left1" x="-1.0" y="5.0" text="done" color="muted"></label>
    <label id="left2" x="-1.0" y="3.8" text="3" color="ink"></label>
    <label id="left3" x="-1.0" y="2.6" text="done" color="muted"></label>
    <line id="axis" from="0,1.6" to="10.6,1.6" arrow="true" color="muted" width="2"></line>
    <label id="t0" x="0" y="1.0" text="0" color="muted"></label>
    <label id="t2" x="2" y="1.0" text="2" color="muted"></label>
    <label id="t4" x="4" y="1.0" text="4" color="muted"></label>
    <label id="t6" x="6" y="1.0" text="6" color="muted"></label>
    <label id="t8" x="8" y="1.0" text="8" color="muted"></label>
    <label id="t10" x="10" y="1.0" text="10" color="muted"></label>
    <rect id="b1" x="1" y="5.0" w="1.9" h="0.8" color="c1"></rect>
    <rect id="b2" x="3" y="3.8" w="1.9" h="0.8" color="c2"></rect>
    <rect id="b3" x="5" y="2.6" w="1.9" h="0.8" color="c3"></rect>
    <rect id="b4" x="6.5" y="5.0" w="0.9" h="0.8" color="c1"></rect>
    <line id="now" from="7,6.0" to="7,1.6" dashed="true" color="accent" width="3" z="1" move="slide"></line>
    <label id="nowname" x="7" y="6.5" text="now" color="accent" move="slide"></label>
  </draw>
</beat>

<beat vo="Only P2 is left, so it runs turn after turn until time 10." t="1.6" shot="full">
  <draw id="cpu" w="13" h="5.2" x="-3,11" y="0,7" size="30">
    <label id="name1" x="-2.3" y="5.0" text="P1" color="c1"></label>
    <line id="lane1" from="0,5.0" to="10.4,5.0" color="muted" width="1"></line>
    <label id="name2" x="-2.3" y="3.8" text="P2" color="c2"></label>
    <line id="lane2" from="0,3.8" to="10.4,3.8" color="muted" width="1"></line>
    <label id="name3" x="-2.3" y="2.6" text="P3" color="c3"></label>
    <line id="lane3" from="0,2.6" to="10.4,2.6" color="muted" width="1"></line>
    <label id="lefthead" x="-1.0" y="6.2" text="left" color="muted"></label>
    <label id="left1" x="-1.0" y="5.0" text="done" color="muted"></label>
    <label id="left2" x="-1.0" y="3.8" text="done" color="muted"></label>
    <label id="left3" x="-1.0" y="2.6" text="done" color="muted"></label>
    <line id="axis" from="0,1.6" to="10.6,1.6" arrow="true" color="muted" width="2"></line>
    <label id="t0" x="0" y="1.0" text="0" color="muted"></label>
    <label id="t2" x="2" y="1.0" text="2" color="muted"></label>
    <label id="t4" x="4" y="1.0" text="4" color="muted"></label>
    <label id="t6" x="6" y="1.0" text="6" color="muted"></label>
    <label id="t8" x="8" y="1.0" text="8" color="muted"></label>
    <label id="t10" x="10" y="1.0" text="10" color="muted"></label>
    <rect id="b1" x="1" y="5.0" w="1.9" h="0.8" color="c1"></rect>
    <rect id="b2" x="3" y="3.8" w="1.9" h="0.8" color="c2"></rect>
    <rect id="b3" x="5" y="2.6" w="1.9" h="0.8" color="c3"></rect>
    <rect id="b4" x="6.5" y="5.0" w="0.9" h="0.8" color="c1"></rect>
    <rect id="b5" x="8" y="3.8" w="1.9" h="0.8" color="c2"></rect>
    <rect id="b6" x="9.5" y="3.8" w="0.9" h="0.8" color="c2"></rect>
    <line id="now" from="10,6.0" to="10,1.6" dashed="true" color="accent" width="3" z="1" move="slide"></line>
    <label id="nowname" x="10" y="6.5" text="now" color="accent" move="slide"></label>
  </draw>
</beat>
</beats>
```

Why it works: one row per process and one shared time axis, so who ran when is read straight
off the picture. The canvas range starts below zero (`x="-3,11"`) so the row names and the
work-left column sit left of time 0 in the same coordinates. Each beat adds the blocks that ran
since the last one (new ids fade in where they belong) and slides the dashed `now` line to the
current time; `move="slide"` keeps it gliding along the axis even when it jumps 4 units. The
work left per process is a label that changes in place, ending in "done". Every block's width is
its real duration, with a small gap so back-to-back turns stay apart.
