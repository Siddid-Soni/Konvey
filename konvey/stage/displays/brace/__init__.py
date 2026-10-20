"""``<brace of="id>part" label="…">``: a curly brace along one side of a thing on screen (the
group a count is about), drawn after layout. Takes no room in the layout
(``konvey.stage.attach``)."""

from __future__ import annotations

from .. import Display

DISPLAY = Display(tag="brace", order=142, shrink=None, picture=False)
