"""``<angle on="pic" at="hits.3" from="hits.2" to="0,0" label="θ">``: the angle at a corner
between two lines, a small arc with its name; a mark drawn after layout
(``konvey.stage.marks``)."""

from __future__ import annotations

from ... import marks
from .. import Display

_CHECK, _DRAWN = marks.plan_hooks('angle', ("on", "at", "from", "to", "label", "color", "dim", "radius"), (("on",), ("at",), ("from",), ("to",)))

DISPLAY = Display(tag="angle", order=146, shrink=None, picture=False, kind="angle_mark", check_object=_CHECK,
                  check_drawn=_DRAWN)
