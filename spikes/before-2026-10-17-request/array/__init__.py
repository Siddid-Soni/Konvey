"""``<array values="3,8,1" pointers="i:0,j:2">``: a row of cells; the plan's ``array`` kind."""

from __future__ import annotations

from .. import Display
from ...match import same_values
from .._values import drawn_values, flat_values


def _check_object(d: dict) -> list[str]:
    values = d.get("values")
    if isinstance(values, list) and any(isinstance(v, (list, tuple, dict)) for v in values):
        # a row of cells holds one value per cell; a nested list would be flattened into extra cells
        return [f"array data['values'] {values!r} nests lists: an array is one row, one value per cell. "
                "A table is a `grid` (values row by row); a point or pair in one cell is a string, "
                'e.g. "(1, 1)"']
    index = d.get("index")
    if index is not None and index != "none" and not (isinstance(index, int) and not isinstance(index, bool)):
        return [f'array data[\'index\'] {index!r}: the first index label as a number (1 for 1..n), or "none"']
    return []


def _check_drawn(where: str, obj, leaves) -> list[str]:
    problems = drawn_values(where, obj, leaves)
    index = obj.data.get("index")
    if index is not None and not problems:
        values = flat_values(obj.data) or []
        drawn = [n for n in leaves if n.tag == "array" and same_values(values, n.attrs.get("values", ""))]
        if not any(n.attrs.get("index", "0").strip() == str(index) for n in drawn):
            problems.append(f'{where}: needs <array index="{index}"> (the plan numbers the cells from {index})')
    return problems


DISPLAY = Display(tag="array", order=60, min_size=24, kind="array", needs=("values",),
                  check_object=_check_object, check_drawn=_check_drawn)
