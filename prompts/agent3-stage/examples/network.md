---
genre: network
kinds: graph
topic_keywords: breadth-first, breadth first, bfs, hops, fewest hops, frontier
---
### Example: a network that changes step by step (topic: breadth-first search, counting hops)

SCENE_SPEC (abridged): beats = [
 {vo_line: "Six rooms joined by doors. How many doors from room A to each of the others?", objects: [{id: rooms, kind: graph, data: {nodes: [A, B, C, D, E, F], edges: [[A, B], [A, C], [B, D], [C, D], [D, E], [C, F]]}}]},
 {vo_line: "Start at A: zero doors. Its neighbours B and C are one door away.", objects: [{id: rooms, kind: graph, data: {highlight: [A], values: {A: 0, B: 1, C: 1}}}]},
 {vo_line: "From B and C we reach D and F: two doors.", objects: [{id: rooms, kind: graph, data: {highlight: [A, B, C], values: {A: 0, B: 1, C: 1, D: 2, F: 2}}}]},
 {vo_line: "E is behind D, so three doors, and that is the whole house.", objects: [{id: rooms, kind: graph, data: {path: [A, C, D, E], values: {A: 0, B: 1, C: 1, D: 2, E: 3, F: 2}}}]} ]

```html
<beats>
<beat vo="Six rooms joined by doors. How many doors from room A to each of the others?" t="1.8" shot="full">
  <graph id="rooms" nodes="A:0,0;B:2,1.2;C:2,-1.2;D:4,0;E:6,0;F:4,-2" edges="A-B;A-C;B-D;C-D;D-E;C-F" w="7" h="3.6"></graph>
</beat>

<beat vo="Start at A: zero doors. Its neighbours B and C are one door away." t="1.6" shot="full">
  <graph id="rooms" nodes="A:0,0;B:2,1.2;C:2,-1.2;D:4,0;E:6,0;F:4,-2" edges="A-B;A-C;B-D;C-D;D-E;C-F" w="7" h="3.6" highlight="A" values="A:0;B:1;C:1"></graph>
</beat>

<beat vo="From B and C we reach D and F: two doors." t="1.6" shot="full">
  <graph id="rooms" nodes="A:0,0;B:2,1.2;C:2,-1.2;D:4,0;E:6,0;F:4,-2" edges="A-B;A-C;B-D;C-D;D-E;C-F" w="7" h="3.6" highlight="A,B,C" values="A:0;B:1;C:1;D:2;F:2"></graph>
</beat>

<beat vo="E is behind D, so three doors, and that is the whole house." t="1.6" shot="full">
  <graph id="rooms" nodes="A:0,0;B:2,1.2;C:2,-1.2;D:4,0;E:6,0;F:4,-2" edges="A-B;A-C;B-D;C-D;D-E;C-F" w="7" h="3.6" highlight="A,B,C,D,E,F" path="A-C-D-E" values="A:0;B:1;C:1;D:2;E:3;F:2"></graph>
</beat>
</beats>
```

Why it works: one `graph` id with the same `nodes` and `edges` in every beat, so nothing is
redrawn: each step only adds to `highlight` and `values`, and the graph re-colours in place
while the numbers appear beside their nodes. The positions are chosen so the layers read left to
right (A, then B and C, then D and F, then E). The last beat lights one route with `path`. No
headline: the narration names each step, and the picture shows it.
