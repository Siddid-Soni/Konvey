"""``<bars labels="a,b" values="5,-6">``: bars from a zero baseline; the plan's ``bars`` kind."""

from __future__ import annotations

from .. import Display
from .._values import drawn_values


def _check_object(d: dict) -> list[str]:
    if isinstance(d.get("labels"), list) and isinstance(d.get("values"), list) and len(d["labels"]) != len(d["values"]):
        return ["bars data['labels'] and data['values'] differ in length"]
    return []


DISPLAY = Display(tag="bars", grow=True, order=40, min_size=24, kind="bars", needs=("labels", "values"),
                  check_object=_check_object, check_drawn=drawn_values)
