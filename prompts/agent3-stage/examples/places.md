---
genre: places
kinds: places
fits: request, response, server, client, service, database, network, message, packet, protocol, api, endpoint, http, browser, backend, call, thread, worker
topic_keywords: cache hit, cache miss, read-through cache, read-through
---
### Example: things travelling between parts (topic: a read-through cache)

SCENE_SPEC (abridged): beats = [
 {vo_line: "The app needs user 7. A cache sits in front of the database.", objects: [{id: sys, kind: places, data: {parts: [app, cache, database], holds: {"cache": ["user 3"], "database": ["user 3", "user 7", "user 9"]}, items: [{"id": "req", "in": "app", "text": "get 7"}]}}]},
 {vo_line: "The request reaches the cache first. User 7 is not there: a miss.", objects: [{id: sys, kind: places, data: {parts: [app, cache, database], holds: {"cache": ["user 3"], "database": ["user 3", "user 7", "user 9"]}, items: [{"id": "req", "in": "cache", "text": "get 7"}]}}]},
 {vo_line: "On a miss the cache asks the database, which finds the row.", objects: [{id: sys, kind: places, data: {parts: [app, cache, database], holds: {"cache": ["user 3"], "database": ["user 3", "user 7", "user 9"]}, items: [{"id": "req", "in": "database", "text": "get 7"}]}}]},
 {vo_line: "The database answers with the row for user 7.", objects: [{id: sys, kind: places, data: {parts: [app, cache, database], holds: {"cache": ["user 3"], "database": ["user 3", "user 7", "user 9"]}, items: [{"id": "row", "in": "database", "text": "user 7", "lines": ["name: Ada"]}]}}]},
 {vo_line: "The row travels back, and the cache keeps a copy on the way.", objects: [{id: sys, kind: places, data: {parts: [app, cache, database], holds: {"cache": ["user 3", "user 7"], "database": ["user 3", "user 7", "user 9"]}, items: [{"id": "row", "in": "app", "text": "user 7", "lines": ["name: Ada"]}]}}]},
 {vo_line: "Ask for user 7 again: the cache already holds it, a hit.", objects: [{id: sys, kind: places, data: {parts: [app, cache, database], holds: {"cache": ["user 3", "user 7"], "database": ["user 3", "user 7", "user 9"]}, items: [{"id": "req2", "in": "cache", "from": "app", "text": "get 7"}]}}]} ]

```html
<beats>
<beat vo="The app needs user 7. A cache sits in front of the database." t="1.6" shot="full">
  <places id="sys" parts="app,cache,database" holds="cache:user 3; database:user 3|user 7|user 9" shapes="database:cylinder">
    <item id="req" in="app" text="get 7" style="pill"></item>
  </places>
</beat>

<beat vo="The request reaches the cache first. User 7 is not there: a miss." t="1.6" shot="full">
  <places id="sys" parts="app,cache,database" holds="cache:user 3; database:user 3|user 7|user 9" shapes="database:cylinder" notes="cache:miss">
    <item id="req" in="cache" text="get 7" style="pill"></item>
  </places>
</beat>

<beat vo="On a miss the cache asks the database, which finds the row." t="1.6" shot="full">
  <places id="sys" parts="app,cache,database" holds="cache:user 3; database:user 3|user 7|user 9" shapes="database:cylinder" highlight="database:user 7">
    <item id="req" in="database" text="get 7" style="pill"></item>
  </places>
</beat>

<beat vo="The database answers with the row for user 7." t="1.6" shot="full">
  <places id="sys" parts="app,cache,database" holds="cache:user 3; database:user 3|user 7|user 9" shapes="database:cylinder" highlight="database:user 7">
    <item id="row" in="database" text="user 7" lines="name: Ada" color="c2"></item>
  </places>
</beat>

<beat vo="The row travels back, and the cache keeps a copy on the way." t="1.6" shot="full">
  <places id="sys" parts="app,cache,database" holds="cache:user 3|user 7; database:user 3|user 7|user 9" shapes="database:cylinder">
    <item id="row" in="app" text="user 7" lines="name: Ada" color="c2"></item>
  </places>
</beat>

<beat vo="Ask for user 7 again: the cache already holds it, a hit." t="1.6" shot="full">
  <places id="sys" parts="app,cache,database" holds="cache:user 3|user 7; database:user 3|user 7|user 9" shapes="database:cylinder" notes="cache:hit" highlight="cache:user 7">
    <item id="req2" in="cache" from="app" text="get 7" style="pill"></item>
  </places>
</beat>
</beats>
```

Why it works: each beat's state is the plan's (`parts`, `holds`, one `<item>` per planned item
with its id, place and text), and everything else is a look chosen to read well: the database is
a `cylinder`, the request a `pill`, the answer a `card` whose line is the row's content, the
verdict a `note` above the cache, the row being read `highlight`ed. All motion comes from ids:
`req` keeps its id and its `in` moves app → cache → database, so it travels along the wires; the
database then builds `row` in place and the next beat puts the same id in the app, so the card
shrinks into a packet, runs back through the cache to the app and opens there, while the cache's
copy fades into a slot. The second request is new in its beat, so it is written in the cache with
`from="app"`: it is born in the app and sent, instead of appearing out of nowhere.
