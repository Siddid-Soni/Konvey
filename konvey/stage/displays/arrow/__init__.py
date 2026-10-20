"""``<arrow from="a" to="b>part">``: an arrow from one thing on screen to another (a member to
the bin it goes to, a label to the cell it names), drawn after layout between the parts'
edges. Takes no room in the layout (``konvey.stage.attach``)."""

from __future__ import annotations

from .. import Display

DISPLAY = Display(tag="arrow", order=140, shrink=None, picture=False)
