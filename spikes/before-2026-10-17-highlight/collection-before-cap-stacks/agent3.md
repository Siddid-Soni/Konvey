| `collection` | members sorted into groups, as nested lists: a population and its subgroups (1000 people, 10 sick), balls in an urn, votes, a hand of cards, a sample; the renderer lays every member out | `look` (`units` one packed block, default · `bins` a pile per group · `row` one line in order), `shape` (`dot` default, `square`, `ball`, `chip`: a tag showing a listed member's text, the default for listed members), `size` (26); children `<li>` (see below) |

**`<collection>`: write the groups, never positions.** Each group is an `<li>` with its name as
its text. `<li count="990">healthy</li>` is 990 identical members; `<li>7♥</li>` (no count, no
inner `<li>`) is one listed member showing that text. A group splits by holding `<li>`s inside
it, and their counts must add up to its own (`<li count="10">sick <li count="9">test
positive</li> <li count="1">test negative</li></li>`). On any `<li>`: `color` (c1…c5, muted;
inner lists take their group's colour), `mark` (a ring: the members the line is about), `dim`,
`strike` (crossed out: removed, ruled out).

```html
<collection id="people" look="units">
  <li count="10" color="c3">sick
    <li count="9" mark>test positive</li>
    <li count="1">test negative</li>
  </li>
  <li count="990" color="muted">healthy
    <li count="99" mark>test positive</li>
    <li count="891">test negative</li>
  </li>
</collection>
```

Members keep their identity from beat to beat (same `id`, the whole collection written again):
- a group that gets split or merged keeps its members, which turn into the new groups in place;
- a listed member is followed by its text, wherever it goes (a card moved into a suit's bin);
- to regroup counted members, give the new group `from="old group > old subgroup"`: `<li
  count="99" from="healthy > test positive">healthy</li>` inside a new `<li count="108">positive
  tests</li>` gathers exactly those 99 there; members no group takes leave the picture;
- a new `look` moves the same members into the new picture (`units` → `bins`: they fly into piles).

At most 2000 members (scale a population down: "out of 1000"). `units` fits proportions and
shares of a whole (populations of similar size that are each split, such as the patients of
two treatments, get a block each, side by side), `bins` counts side by side (votes, tallies, draws from an urn), `row` an order or a
sample drawn one by one. Never build a crowd, an urn or a hand from `<draw>` circles.
