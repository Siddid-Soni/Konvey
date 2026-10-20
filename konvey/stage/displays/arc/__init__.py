"""``<arc on="pic" center="0,0" from="hits.2" to="hits.4">``: the arc of a circle about a
centre from one point round to another, or the filled wedge (``fill``); a mark drawn after
layout (``konvey.stage.marks``)."""

from __future__ import annotations

from ... import marks
from .. import Display

_CHECK, _DRAWN = marks.plan_hooks('arc', ("on", "center", "from", "to", "dir", "fill", "label", "color", "dim"), (("on",), ("center",), ("from",), ("to",)))

DISPLAY = Display(tag="arc", order=145, shrink=None, picture=False, kind="arc", check_object=_CHECK,
                  check_drawn=_DRAWN)
