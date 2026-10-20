"""``<note on="pic" at="x,y" text="…">`` / ``<note to="id>part" text="…">``: a short note in the
nearest open space with a thin arrow to the exact point or thing it is about (3b1b's "Slope =" with
an arrow to the line); drawn after layout, takes no room (``konvey.stage.marks``)."""

from __future__ import annotations

from ... import marks
from .. import Display

_CHECK, _DRAWN = marks.plan_hooks('note', ("on", "at", "to", "text", "color", "side", "dim"), (("text",), ("at", "to")))

DISPLAY = Display(tag="note", order=147, shrink=None, picture=False, kind="note", check_object=_CHECK,
                  check_drawn=_DRAWN)
