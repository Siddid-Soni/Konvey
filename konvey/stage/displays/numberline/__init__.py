"""``<numberline x="0,3" markers="x: 1.5">``: a number line with numbered ticks, small ticks between
them, and named markers (a triangle with its name) that slide when their value changes: a value
being varied, an input and its output on stacked lines, where a number sits among others. Has
coordinates (``x,0`` on the line), so marks (``<dots>``, ``<brace on>``, ``<note on>``) go on it."""

from __future__ import annotations

from ... import marks
from .. import Display

_CHECK, _DRAWN = marks.plan_hooks("numberline", ("x", "markers", "step", "colors", "numbers"), (("x",),))

DISPLAY = Display(tag="numberline", order=86, steady=True, shrink=0.7, kind="numberline",
                  check_object=_CHECK, check_drawn=_DRAWN)
