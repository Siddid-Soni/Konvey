"""``<tiles word="CRANE" colors="xyxgx">``: letter tiles; the plan's ``tiles`` kind."""

from __future__ import annotations

from .. import Display

DISPLAY = Display(tag="tiles", grow=True, order=100, kind="tiles", needs=("word",))
