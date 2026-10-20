"""Plan checks shared by the displays that draw a list of planned values (pure Python)."""

from __future__ import annotations

from ..match import fmt_list, same_values


def flat_values(d: dict) -> list | None:
    """The plan's ``values`` in order (a grid given row by row is read row after row)."""
    values = d.get("values")
    if not isinstance(values, list):
        return None
    if values and all(isinstance(r, list) for r in values):
        values = [c for r in values for c in r]
    return values


def drawn_values(where: str, obj, leaves) -> list[str]:
    """``values`` must be drawn verbatim, in order, by a leaf of the display's own tag."""
    values = flat_values(obj.data)
    if values is None:
        return []
    if not any(same_values(values, n.attrs.get("values", "")) for n in leaves if n.tag == obj.kind):
        return [f'{where}: needs <{obj.kind} values="{fmt_list(values)}"> (the planned values, in order)']
    return []
