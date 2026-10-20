## Narration mode: no subtitles

This video is narrated: a voice speaks every beat's `vo`. **No caption is drawn** (the renderer
turns the automatic caption off), so:

- The whole stage is the picture's, bottom band included. Give the main display the room: put
  it in a `grow` box, and put numbers beside it in a `col`, not stacked under it.
- Do not put the `vo` back on screen as a `<caption>` or `<text>`. On-screen words are titles,
  names, labels and numbers only, the things a viewer needs to *see* while hearing the line.
- The picture carries what the voice says: when the line names a number, a group or a step,
  that thing is drawn, labelled or highlighted in that beat. Numbers on screen are rounded
  (`fmt="{:.2f}"`, 16.7%), never 0.042731.
- A beat the plan holds (same objects, same data as the beat before) stays exactly the same on
  screen: the line is commenting on what is already there.
- A `<collection>` of one plain crowd needs no legend: `<li count="40"></li>` (no name).
- **What the voice calls a colour is that colour on screen.** A thing named by its colour (white
  cards, dark beads) is drawn in the theme colour that looks like it: `ink` for white or light,
  `muted` for black, dark or grey. Use `c1`…`c5` only for things whose names are not colours, so
  the viewer never hears "white" while seeing green. Each group still carries its name.
- **Labels are words.** Text you write for the viewer (titles, labels, legend entries, notes) is
  plain words, `left pan`, never an id like `left_pan`. Ids and part names copied from the plan stay
  exactly as the plan wrote them: every reference to a part must match it.
- **One thing keeps one look.** An object keeps the same tag, shape and colour through every beat
  and every scene: if it is a circle in the first scene, it is still a circle in the last.
- **A move is shown as a move.** When the line takes an item from one place to another, keep both
  places on screen: the item leaves the source (its count there drops) and arrives in the
  target in that beat. Counts on screen always add up, part by part (8 and 9 left after 3 are
  taken from 10 and 10), never switching to a lumped total.
- **Few things, drawn large.** With only a handful of items on stage, make them big (raise the
  display's `size`) and centred in the `grow` box, not small in one corner of an empty stage.
- Still copy each `vo` exactly from the plan (it times the beat and is spoken).
