"""``<ring of="id>part">``: a rounded outline around one thing on screen (the group the line is
about), drawn after layout. Takes no room in the layout (``konvey.stage.attach``)."""

from __future__ import annotations

from .. import Display

DISPLAY = Display(tag="ring", order=141, shrink=None, picture=False)
