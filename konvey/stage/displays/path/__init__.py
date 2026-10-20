"""``<path on="pic" through="hits.1-4">``: a line through points of a picture (a segment, a
broken path, a closed shaded region, a line extended across the picture), drawn after layout
(``konvey.stage.marks``)."""

from __future__ import annotations

from ... import marks
from .. import Display

_CHECK, _DRAWN = marks.plan_hooks('path', ("on", "through", "closed", "fill", "extend", "dashed", "around", "label", "color", "dim", "width"), (("on",), ("through",)))

DISPLAY = Display(tag="path", order=144, shrink=None, picture=False, kind="path", check_object=_CHECK,
                  check_drawn=_DRAWN)
