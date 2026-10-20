"""``<number>``: a readout, the value large and its label under it; the plan's ``number`` kind."""

from __future__ import annotations

from .. import Display


def _check_object(d: dict) -> list[str]:
    if not d.get("label"):
        return ["kind 'number' needs data['label'] (what the number counts); bare numbers mean nothing"]
    return []


DISPLAY = Display(tag="number", order=20, shrink=0.7, kind="number", needs=("value",), picture=False,
                  check_object=_check_object)
