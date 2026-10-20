"""``<value bind="shadow.area">``: a live number bound to the 3D world (no plan kind of its own)."""

from __future__ import annotations

from .. import Display

DISPLAY = Display(tag="value", order=30, shrink=None, min_size=24)
