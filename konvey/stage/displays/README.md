# Displays

One folder per overlay tag that is not plain text (`<array>`, `<places>`, `<graph>`, …). The
registry in `__init__.py` finds every folder on import, so **adding a display = adding a
folder**; the parser, layout, scene, motion, checker, validators and both agent prompts pick
it up.

```
displays/<name>/
  __init__.py   DISPLAY = Display(...)   pure Python: parser, checker, planner load it
  mobject.py    build(node, world) + optional motion hooks   (manimgl, render only)
  agent3.md     Agent 3 docs: first line = tag-table row; after a blank line = a section
  plan.md       optional: Agent 2's row in the object-kinds table
```

## A new display, step by step (`<timeline>` as the example)

1. `timeline/__init__.py`

   ```python
   from .. import Display

   def _check_object(d):            # the plan's data for one object
       return [] if isinstance(d.get("events"), list) else ["timeline data['events'] must be a list"]

   DISPLAY = Display(tag="timeline", order=130, steady=True,
                     kind="timeline", needs=("events",), check_object=_check_object)
   ```

2. `timeline/mobject.py`

   ```python
   from manimlib import *
   from ..base import Block, data_list, _label

   class TimelineBlock(Block):
       tag = "timeline"
       def __init__(self, node):
           super().__init__()
           ...                               # build at natural size, in overlay units
           self.set_content(node, "events")  # same content next beat -> it just moves

   def build(node, world=None):
       return TimelineBlock(node)

   def morph(old, new, sources=None):        # optional: same id, new content
       ...                                   # return an Animation, or None for the default
   ```

3. `timeline/agent3.md`: one table row `| \`timeline\` | … | attributes |`, optionally a
   blank line and a section with details. `timeline/plan.md`: one row of the kinds table.
   A bare `{{plan_kinds}}` in `prompts/agent2-stage/plan.md` places rows not named elsewhere.
4. Add a genre example in `prompts/agent3-stage/examples/` whose `kinds:` names the new kind.
5. Tests: a block test in `tests/test_blocks.py` and a hand-written beat file rendered and
   shown before any model run.

## `Display` fields

| field | what it does |
|---|---|
| `tag`, `order` | the tag; its place in Agent 3's table |
| `raw` | inner text kept verbatim (LaTeX) |
| `aliases` | old tag/kind names still read as this display (`<system>` → `<places>`) |
| `children` | child tags allowed inside (`<item>` in `<places>`) |
| `shrink` | may scale down to this fraction to fit the page (`None`: never) |
| `steady` | one scale and one place for the whole scene |
| `min_size` | smallest readable `size=` |
| `enter` | default enter animation (`animations.ENTERS`) |
| `prepare(beats, strict)` | scene-wide normalising before layout (places keep their look) |
| `adopt(prev, first)` | carry an element over a scene cut |
| `kind`, `needs`, `picture` | plan object kind, required data keys, counts as the beat's visual |
| `check_object(data)` | problems with one planned object |
| `check_plan(plan)` | problems across beats of the plan |
| `check_drawn(where, obj, leaves)` | the beat HTML draws the planned data verbatim |
| `check_scene(scene, beats)` | problems across the scene's beats |
| `apply_plan(body, obj)` | copy planned state into Agent 3's tag |

## `mobject.py` hooks (all optional except `build`)

| hook | default |
|---|---|
| `build(node, world)` | — |
| `morph(old, new, sources)` | part by part (`base._parts`) |
| `sources(new, old)` | none: `[(value, live mobject)]` a changing label flies out of |
| `enter(node, mob, t)` / `exit(node, mob)` | the named animation in `enter=` / `exit=` |
| `move(old, new)` | `Transform` |
| `emphasis_target(kind, mob)` | the whole mobject |

Named animations for every display (`enter="write"`, `exit="shrink"`, `emphasize="flash"`) are
in `konvey/stage/animations.py`; a new one is a single `@enter("name")` function there.
