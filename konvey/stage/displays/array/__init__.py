"""``<array values="3,8,1" pointers="i:0,j:2">``: a row of cells; the plan's ``array`` kind.
``linked`` draws each cell pointing to the next; ``chains`` hangs a short list below a cell."""

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
    chains = d.get("chains")
    if chains is not None:
        n = len(values) if isinstance(values, list) else 0
        if not isinstance(chains, dict):
            return [f"array data['chains'] {chains!r}: a dict, cell index -> the list below it, "
                    'e.g. {"3": ["cat", "fox"]}']
        for k, items in chains.items():
            if not str(k).strip().isdigit() or not 0 <= int(k) < n:
                return [f"array data['chains'] key {k!r}: a cell index 0..{n - 1}"]
            if not isinstance(items, list) or any(isinstance(x, (list, dict)) for x in items):
                return [f"array data['chains'][{k!r}] {items!r}: a list of plain items, first to last"]
    return []


def plan_chains(d: dict) -> dict[int, list[str]]:
    return {int(k): [str(x).strip() for x in v] for k, v in (d.get("chains") or {}).items() if v}


def drawn_chains(raw: str) -> dict[int, list[str]]:
    out = {}
    for part in (p.strip() for p in raw.split(";") if p.strip()):
        at, _, items = part.partition(":")
        if at.strip().isdigit():
            out[int(at)] = [x.strip() for x in items.split(">") if x.strip()]
    return {k: v for k, v in out.items() if v}


def _check_drawn(where: str, obj, leaves) -> list[str]:
    problems = drawn_values(where, obj, leaves)
    want = plan_chains(obj.data)
    if want and not problems:
        values = flat_values(obj.data) or []
        drawn = [n for n in leaves if n.tag == "array" and same_values(values, n.attrs.get("values", ""))]
        if not any(drawn_chains(n.attrs.get("chains", "")) == want for n in drawn):
            spec = ";".join(f"{k}:{'>'.join(v)}" for k, v in sorted(want.items()))
            problems.append(f'{where}: needs <array chains="{spec}"> (the planned lists below the cells)')
    index = obj.data.get("index")
    if index is not None and not problems:
        values = flat_values(obj.data) or []
        drawn = [n for n in leaves if n.tag == "array" and same_values(values, n.attrs.get("values", ""))]
        if not any(n.attrs.get("index", "0").strip() == str(index) for n in drawn):
            problems.append(f'{where}: needs <array index="{index}"> (the plan numbers the cells from {index})')
    return problems


DISPLAY = Display(tag="array", order=60, min_size=24, kind="array", needs=("values",),
                  check_object=_check_object, check_drawn=_check_drawn)
