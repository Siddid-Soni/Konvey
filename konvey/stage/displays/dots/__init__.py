"""``<dots on="pic" at="1,0; 0.5,-0.8">``: points of a picture, in its own coordinates (a
mark, drawn after layout; ``konvey.stage.marks``). Other marks name them ``id.k``."""

from __future__ import annotations

from ... import marks
from .. import Display

_CHECK, _DRAWN = marks.plan_hooks('dots', ("on", "at", "labels", "numbered", "color", "dim", "size"), (("on",), ("at",)))

DISPLAY = Display(tag="dots", order=143, shrink=None, picture=False, kind="dots", check_object=_CHECK,
                  check_drawn=_DRAWN)
