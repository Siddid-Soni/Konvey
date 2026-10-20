---
genre: collection
kinds: collection
fits: out of, population, group, groups, share, proportion, sample, draw, drawn, urn, count, counted, tally, votes, members, split
topic_keywords: club vote, class vote, show of hands
---
### Example: a vote counted, then the yes votes split by year (topic: a club vote)

SCENE_SPEC (abridged): beats = [
 {vo_line: "Forty members vote on the new rule.", objects: [{id: votes, kind: collection, data: {groups: [{name: "yes", count: 24, color: "c2"}, {name: "no", count: 16, color: "c3"}]}}]},
 {vo_line: "Pile them up... twenty-four yes, sixteen no.", objects: [{id: votes, kind: collection, data: {look: "bins", groups: [...same...]}}]},
 {vo_line: "But look who said yes. Eighteen of them joined this year!", objects: [{id: votes, kind: collection, data: {look: "bins", groups: [{name: "yes", count: 24, groups: [{name: "new members", count: 18, mark: true}, {name: "old members", count: 6}]}, {name: "no", count: 16}]}}]} ]

```html
<beats>
<beat vo="Forty members vote on the new rule." t="2.0" shot="full">
  <collection id="votes" look="units" shape="square">
    <li count="24" color="c2">yes</li>
    <li count="16" color="c3">no</li>
  </collection>
</beat>

<beat vo="Pile them up... twenty-four yes, sixteen no." t="2.2" shot="full">
  <collection id="votes" look="bins" shape="square">
    <li count="24" color="c2">yes</li>
    <li count="16" color="c3">no</li>
  </collection>
</beat>

<beat vo="But look who said yes. Eighteen of them joined this year!" t="2.0" shot="full">
  <collection id="votes" look="bins" shape="square">
    <li count="24" color="c2">yes
      <li count="18" mark>new members</li>
      <li count="6">old members</li>
    </li>
    <li count="16" color="c3">no</li>
  </collection>
</beat>
</beats>
```
