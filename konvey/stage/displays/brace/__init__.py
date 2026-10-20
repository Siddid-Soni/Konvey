"""``<brace of="id>part" label="…">``: a curly brace along one side of a thing on screen (the
group a count is about), drawn after layout. Takes no room in the layout
(``konvey.stage.attach``)."""

from __future__ import annotations

from ... import marks
from .. import Display

_CHECK, _DRAWN = marks.plan_hooks('brace', ("of", "on", "from", "to", "flip", "label", "side", "color", "dim"), (("of", "on"),))

DISPLAY = Display(tag="brace", order=142, shrink=None, picture=False, kind="brace", check_object=_CHECK,
                  check_drawn=_DRAWN)
