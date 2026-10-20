"""``<vector values="0.9,-0.4,0.2">``: a list of numbers in square brackets, a column (or a row);
the plan's ``vector`` kind.

One building block for any topic: a word's embedding, a state, a gradient, a velocity, a
probability distribution, a matrix-times-vector result, a point's coordinates. It stands on its
own or beside any other picture; a changed entry takes its new number from a cell that is being
looked at elsewhere (``sources``), so values flow into it from a grid, an array or another vector.
Pure Python: the plan checks."""

from __future__ import annotations

from ...match import split_list
from .. import Display
from .._values import drawn_values

MAX_ENTRIES = 8


def entries_of(raw: str) -> list[str]:
    return split_list(raw) if raw.strip() else []


def _check_object(d: dict) -> list[str]:
    vals = d.get("values")
    if not isinstance(vals, list) or not vals or any(isinstance(v, (list, dict)) for v in vals):
        return ['vector values must be a flat list of numbers [0.9, -0.4, 0.2] (a matrix is a "grid" or "tex")']
    problems = []
    if len(vals) > MAX_ENTRIES:
        problems.append(f"vector has {len(vals)} entries; at most {MAX_ENTRIES} stay readable (show a few, then '…')")
    hl = d.get("highlight", [])
    if not isinstance(hl, list) or any(not isinstance(i, int) or not 0 <= i < len(vals) for i in hl):
        problems.append(f"vector highlight must list entry positions 0..{len(vals) - 1}")
    if d.get("orient", "column") not in ("column", "row"):
        problems.append('vector orient: "column" (default) or "row"')
    return problems


DISPLAY = Display(tag="vector", order=24, shrink=0.6, min_size=20, kind="vector", needs=("values",),
                  check_object=_check_object, check_drawn=drawn_values)
