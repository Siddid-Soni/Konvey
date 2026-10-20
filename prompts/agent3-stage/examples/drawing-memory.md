---
genre: drawing-memory
kinds: drawing
fits: memory, address, page, frame, pointer, heap, register, virtual, physical, disk, block, cache line, allocation, segment, mapping, translation
topic_keywords: page table, virtual address, physical frame, virtual memory, page fault
---
### Example: two address spaces joined by a mapping (topic: virtual memory and page tables)

SCENE_SPEC (abridged): beats = [
 {vo_line: "A program sees four pages. Memory has five frames, and some belong to other programs.", objects: [{id: mem, kind: drawing, data: {shows: "a column of 4 virtual pages and a column of 5 physical frames; frame 2 used by another program, frame 4 free; page 2 dimmed, on disk", labels: ["page 0", "page 1", "page 2", "page 3", "free"]}}]},
 {vo_line: "A page table sends each page to a frame. Page 2 is not in memory yet.", objects: [{id: mem, kind: drawing, data: {shows: "arrows page 0 to frame 3, page 1 to frame 0, page 3 to frame 1; none from page 2"}}]},
 {vo_line: "Take byte 40 of page 1.", objects: [{id: mem, kind: drawing, data: {shows: "an address token beside page 1", labels: ["page 1 + 40"]}}]},
 {vo_line: "Page 1's arrow says frame 0, so it is byte 40 of frame 0.", objects: [{id: mem, kind: drawing, data: {shows: "the arrow from page 1 lights up; the token slides to frame 0 and its label changes", labels: ["frame 0 + 40"]}}]},
 {vo_line: "Now byte 8 of page 2: there is no arrow to follow. That is a page fault.", objects: [{id: mem, kind: drawing, data: {shows: "a new token beside page 2", labels: ["page 2 + 8", "fault"]}}]},
 {vo_line: "The system copies page 2 into the free frame 4, adds its arrow, and the access goes through.", objects: [{id: mem, kind: drawing, data: {shows: "frame 4 fills, a new arrow page 2 to frame 4, the token slides there", labels: ["frame 4 + 8"]}}]} ]

```html
<beats>
<beat vo="A program sees four pages. Memory has five frames, and some belong to other programs." t="1.6" shot="full">
  <draw id="mem" w="13" h="5.2" x="0,21" y="0,8.4" size="30">
    <label id="vhead" x="5" y="7.75" text="virtual pages" color="muted"></label>
    <label id="phead" x="15.5" y="7.75" text="physical frames" color="muted"></label>
    <rect id="page0" x="5" y="6.2" w="3" h="1" color="c1" label="page 0"></rect>
    <rect id="page1" x="5" y="5.0" w="3" h="1" color="c1" label="page 1"></rect>
    <rect id="page2" x="5" y="3.8" w="3" h="1" color="c1" fill="0.3" label="page 2"></rect>
    <rect id="page3" x="5" y="2.6" w="3" h="1" color="c1" label="page 3"></rect>
    <rect id="frame0" x="15.5" y="6.8" w="3" h="1" color="c1" label="frame 0"></rect>
    <rect id="frame1" x="15.5" y="5.6" w="3" h="1" color="c1" label="frame 1"></rect>
    <rect id="frame2" x="15.5" y="4.4" w="3" h="1" color="muted" fill="0.5" label="other"></rect>
    <rect id="frame3" x="15.5" y="3.2" w="3" h="1" color="c1" label="frame 3"></rect>
    <rect id="frame4" x="15.5" y="2.0" w="3" h="1" color="muted" fill="none" label="free"></rect>
    <label id="note" x="1.7" y="3.8" text="on disk" color="muted"></label>
  </draw>
</beat>

<beat vo="A page table sends each page to a frame. Page 2 is not in memory yet." t="1.6" shot="full">
  <draw id="mem" w="13" h="5.2" x="0,21" y="0,8.4" size="30">
    <label id="vhead" x="5" y="7.75" text="virtual pages" color="muted"></label>
    <label id="phead" x="15.5" y="7.75" text="physical frames" color="muted"></label>
    <rect id="page0" x="5" y="6.2" w="3" h="1" color="c1" label="page 0"></rect>
    <rect id="page1" x="5" y="5.0" w="3" h="1" color="c1" label="page 1"></rect>
    <rect id="page2" x="5" y="3.8" w="3" h="1" color="c1" fill="0.3" label="page 2"></rect>
    <rect id="page3" x="5" y="2.6" w="3" h="1" color="c1" label="page 3"></rect>
    <rect id="frame0" x="15.5" y="6.8" w="3" h="1" color="c1" label="frame 0"></rect>
    <rect id="frame1" x="15.5" y="5.6" w="3" h="1" color="c1" label="frame 1"></rect>
    <rect id="frame2" x="15.5" y="4.4" w="3" h="1" color="muted" fill="0.5" label="other"></rect>
    <rect id="frame3" x="15.5" y="3.2" w="3" h="1" color="c1" label="frame 3"></rect>
    <rect id="frame4" x="15.5" y="2.0" w="3" h="1" color="muted" fill="none" label="free"></rect>
    <line id="map0" from="6.6,6.2" to="13.9,3.2" arrow="true" color="muted" width="2"></line>
    <line id="map1" from="6.6,5.0" to="13.9,6.8" arrow="true" color="muted" width="2"></line>
    <line id="map3" from="6.6,2.6" to="13.9,5.6" arrow="true" color="muted" width="2"></line>
    <label id="note" x="1.7" y="3.8" text="on disk" color="muted"></label>
  </draw>
</beat>

<beat vo="Take byte 40 of page 1." t="1.6" shot="full">
  <draw id="mem" w="13" h="5.2" x="0,21" y="0,8.4" size="30">
    <label id="vhead" x="5" y="7.75" text="virtual pages" color="muted"></label>
    <label id="phead" x="15.5" y="7.75" text="physical frames" color="muted"></label>
    <rect id="page0" x="5" y="6.2" w="3" h="1" color="c1" label="page 0"></rect>
    <rect id="page1" x="5" y="5.0" w="3" h="1" color="c1" label="page 1"></rect>
    <rect id="page2" x="5" y="3.8" w="3" h="1" color="c1" fill="0.3" label="page 2"></rect>
    <rect id="page3" x="5" y="2.6" w="3" h="1" color="c1" label="page 3"></rect>
    <rect id="frame0" x="15.5" y="6.8" w="3" h="1" color="c1" label="frame 0"></rect>
    <rect id="frame1" x="15.5" y="5.6" w="3" h="1" color="c1" label="frame 1"></rect>
    <rect id="frame2" x="15.5" y="4.4" w="3" h="1" color="muted" fill="0.5" label="other"></rect>
    <rect id="frame3" x="15.5" y="3.2" w="3" h="1" color="c1" label="frame 3"></rect>
    <rect id="frame4" x="15.5" y="2.0" w="3" h="1" color="muted" fill="none" label="free"></rect>
    <line id="map0" from="6.6,6.2" to="13.9,3.2" arrow="true" color="muted" width="2"></line>
    <line id="map1" from="6.6,5.0" to="13.9,6.8" arrow="true" color="muted" width="2"></line>
    <line id="map3" from="6.6,2.6" to="13.9,5.6" arrow="true" color="muted" width="2"></line>
    <label id="note" x="1.7" y="3.8" text="on disk" color="muted"></label>
    <rect id="addr" x="1.7" y="5.0" w="2.9" h="0.8" round="0.35" color="accent" z="1" move="slide" label="page 1 + 40"></rect>
  </draw>
</beat>

<beat vo="Page 1's arrow says frame 0, so it is byte 40 of frame 0." t="1.6" shot="full">
  <draw id="mem" w="13" h="5.2" x="0,21" y="0,8.4" size="30">
    <label id="vhead" x="5" y="7.75" text="virtual pages" color="muted"></label>
    <label id="phead" x="15.5" y="7.75" text="physical frames" color="muted"></label>
    <rect id="page0" x="5" y="6.2" w="3" h="1" color="c1" label="page 0"></rect>
    <rect id="page1" x="5" y="5.0" w="3" h="1" color="c1" label="page 1"></rect>
    <rect id="page2" x="5" y="3.8" w="3" h="1" color="c1" fill="0.3" label="page 2"></rect>
    <rect id="page3" x="5" y="2.6" w="3" h="1" color="c1" label="page 3"></rect>
    <rect id="frame0" x="15.5" y="6.8" w="3" h="1" color="c1" label="frame 0"></rect>
    <rect id="frame1" x="15.5" y="5.6" w="3" h="1" color="c1" label="frame 1"></rect>
    <rect id="frame2" x="15.5" y="4.4" w="3" h="1" color="muted" fill="0.5" label="other"></rect>
    <rect id="frame3" x="15.5" y="3.2" w="3" h="1" color="c1" label="frame 3"></rect>
    <rect id="frame4" x="15.5" y="2.0" w="3" h="1" color="muted" fill="none" label="free"></rect>
    <line id="map0" from="6.6,6.2" to="13.9,3.2" arrow="true" color="muted" width="2"></line>
    <line id="map1" from="6.6,5.0" to="13.9,6.8" arrow="true" color="accent" width="4"></line>
    <line id="map3" from="6.6,2.6" to="13.9,5.6" arrow="true" color="muted" width="2"></line>
    <label id="note" x="1.7" y="3.8" text="on disk" color="muted"></label>
    <rect id="addr" x="18.9" y="6.8" w="2.9" h="0.8" round="0.35" color="accent" z="1" move="slide" label="frame 0 + 40"></rect>
  </draw>
</beat>

<beat vo="Now byte 8 of page 2: there is no arrow to follow. That is a page fault." t="1.6" shot="full">
  <draw id="mem" w="13" h="5.2" x="0,21" y="0,8.4" size="30">
    <label id="vhead" x="5" y="7.75" text="virtual pages" color="muted"></label>
    <label id="phead" x="15.5" y="7.75" text="physical frames" color="muted"></label>
    <rect id="page0" x="5" y="6.2" w="3" h="1" color="c1" label="page 0"></rect>
    <rect id="page1" x="5" y="5.0" w="3" h="1" color="c1" label="page 1"></rect>
    <rect id="page2" x="5" y="3.8" w="3" h="1" color="c1" fill="0.3" label="page 2"></rect>
    <rect id="page3" x="5" y="2.6" w="3" h="1" color="c1" label="page 3"></rect>
    <rect id="frame0" x="15.5" y="6.8" w="3" h="1" color="c1" label="frame 0"></rect>
    <rect id="frame1" x="15.5" y="5.6" w="3" h="1" color="c1" label="frame 1"></rect>
    <rect id="frame2" x="15.5" y="4.4" w="3" h="1" color="muted" fill="0.5" label="other"></rect>
    <rect id="frame3" x="15.5" y="3.2" w="3" h="1" color="c1" label="frame 3"></rect>
    <rect id="frame4" x="15.5" y="2.0" w="3" h="1" color="muted" fill="none" label="free"></rect>
    <line id="map0" from="6.6,6.2" to="13.9,3.2" arrow="true" color="muted" width="2"></line>
    <line id="map1" from="6.6,5.0" to="13.9,6.8" arrow="true" color="muted" width="2"></line>
    <line id="map3" from="6.6,2.6" to="13.9,5.6" arrow="true" color="muted" width="2"></line>
    <label id="note" x="1.7" y="3.8" text="fault" color="accent"></label>
    <rect id="addr2" x="1.7" y="4.55" w="2.9" h="0.8" round="0.35" color="accent" z="1" move="slide" label="page 2 + 8"></rect>
  </draw>
</beat>

<beat vo="The system copies page 2 into the free frame 4, adds its arrow, and the access goes through." t="1.6" shot="full">
  <draw id="mem" w="13" h="5.2" x="0,21" y="0,8.4" size="30">
    <label id="vhead" x="5" y="7.75" text="virtual pages" color="muted"></label>
    <label id="phead" x="15.5" y="7.75" text="physical frames" color="muted"></label>
    <rect id="page0" x="5" y="6.2" w="3" h="1" color="c1" label="page 0"></rect>
    <rect id="page1" x="5" y="5.0" w="3" h="1" color="c1" label="page 1"></rect>
    <rect id="page2" x="5" y="3.8" w="3" h="1" color="c1" label="page 2"></rect>
    <rect id="page3" x="5" y="2.6" w="3" h="1" color="c1" label="page 3"></rect>
    <rect id="frame0" x="15.5" y="6.8" w="3" h="1" color="c1" label="frame 0"></rect>
    <rect id="frame1" x="15.5" y="5.6" w="3" h="1" color="c1" label="frame 1"></rect>
    <rect id="frame2" x="15.5" y="4.4" w="3" h="1" color="muted" fill="0.5" label="other"></rect>
    <rect id="frame3" x="15.5" y="3.2" w="3" h="1" color="c1" label="frame 3"></rect>
    <rect id="frame4" x="15.5" y="2.0" w="3" h="1" color="c1" label="frame 4"></rect>
    <line id="map0" from="6.6,6.2" to="13.9,3.2" arrow="true" color="muted" width="2"></line>
    <line id="map1" from="6.6,5.0" to="13.9,6.8" arrow="true" color="muted" width="2"></line>
    <line id="map3" from="6.6,2.6" to="13.9,5.6" arrow="true" color="muted" width="2"></line>
    <line id="map2" from="6.6,3.8" to="13.9,2.0" arrow="true" color="accent" width="4"></line>
    <rect id="addr2" x="18.9" y="2.0" w="2.9" h="0.8" round="0.35" color="accent" z="1" move="slide" label="frame 4 + 8"></rect>
  </draw>
</beat>
</beats>
```

Why it works: the two sides of the mapping are two columns of the same-sized blocks, and the
mapping itself is arrows between them, so a lookup is following an arrow. Ownership is colour
and fill (ours, someone else's, `fill="none"` for free), so a free slot being taken is visible.
The address is a token that keeps its id while it slides from one side to the other
(`move="slide"`) and its label changes from the page form to the frame form, which is the whole
point of the translation. The arrow being used turns `accent` and thicker; a missing arrow is
shown by its absence plus a word ("fault"), and the fix is the new arrow fading in. A second
address gets a new id instead of flying back across the picture.
