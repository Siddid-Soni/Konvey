| `collection` | members sorted into groups, as nested lists: a population and its subgroups (1000 people, 40 left-handed), balls in an urn, votes, a hand of cards, a sample, items piled in columns; the renderer lays every member out | `look` (`units` one packed block, default · `bins` a pile per group · `row` one line in order · `stacks` a post per group, its members piled on it), `shape` (`dot` default, `square`, `ball`, `chip`: a tag showing a listed member's text, the default for listed members, `slab`: a flat bar as wide as the member's `size`, the default for `stacks`), `size` (26); children `<li>` (see below) |

**`<collection>`: write the groups, never positions.** Each group is an `<li>` with its name as
its text. `<li count="960">right-handed</li>` is 960 identical members; `<li>7♥</li>` (no count,
no inner `<li>`) is one listed member showing that text. A group splits by holding `<li>`s inside
it, and their counts must add up to its own (`<li count="40">left-handed <li count="30">plays
chess</li> <li count="10">does not</li></li>`). On any `<li>`: `color` (c1…c5, muted; inner
lists take their group's colour), `mark` (their outline lit: the members the line is about), `dim`,
`strike` (crossed out: removed, ruled out).

```html
<collection id="people" look="units">
  <li count="40" color="c3">left-handed
    <li count="30" mark>plays chess</li>
    <li count="10">does not</li>
  </li>
  <li count="960" color="muted">right-handed
    <li count="96" mark>plays chess</li>
    <li count="864">does not</li>
  </li>
</collection>
```

Members keep their identity from beat to beat (same `id`, the whole collection written again):
- a group that gets split or merged keeps its members, which turn into the new groups in place;
- a listed member is followed by its text, wherever it goes (a card moved into a suit's bin);
- to regroup counted members, give the new group `from="old group > old subgroup"`: `<li
  count="96" from="right-handed > plays chess">right-handed</li>` inside a new `<li
  count="126">chess players</li>` gathers exactly those 96 there; members no group takes leave
  the picture;
- a new `look` moves the same members into the new picture (`units` → `bins`: they fly into piles).

At most 2000 members (scale a population down: "out of 1000"). `units` fits proportions and
shares of a whole (populations of similar size that are each split, such as the patients of
two treatments, get a block each, side by side), `bins` counts side by side (votes, tallies, draws from an urn), `row` an order or a
sample drawn one by one. Never build a crowd, an urn or a hand from `<draw>` circles.

**`look="stacks"`: things piled on posts**, one post per group, its listed members piled from the
bottom up in the order written: plates in piles, coins in columns, a stack that is pushed and
popped, cards dealt into piles. Give each member `size` (its width, relative to the
largest) and a short text, and write an empty post as `<li count="0">name</li>`. Move a member
to another post by writing it in that group in the next beat: it lifts off, travels above the
posts and drops onto its new pile. The posts and the members' thickness stay the same in every
beat, so only what moved changes.

```html
<collection id="piles" look="stacks">
  <li>left <li size="4">4</li><li size="2">2</li></li>
  <li>right <li size="3">3</li><li size="1">1</li></li>
  <li count="0">spare</li>
</collection>
```
