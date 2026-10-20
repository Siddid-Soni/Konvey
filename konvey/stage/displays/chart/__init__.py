"""``<chart series="A:1,2,3;B:3,2,1" x="0,10">``: line / area chart; the plan's ``chart`` kind."""

from __future__ import annotations

from ...match import fmt_list, same_values, squash
from .. import Display


def _check_object(d: dict) -> list[str]:
    if "series" not in d:
        return []
    series = d["series"]
    lens = {len(v) for v in series.values()} if isinstance(series, dict) and series and all(
        isinstance(v, list) for v in series.values()) else set()
    if not lens:
        return ["chart data['series'] must be {name: [numbers, ...]}, e.g. {'S': [990, 900], 'I': [10, 90]}"]
    if len(lens) != 1 or min(lens) < 2:
        return ["chart series must all have the same number (>= 2) of values"]
    return []


def _series_attr(raw: str) -> dict[str, str]:
    out = {}
    for part in raw.split(";"):
        name, _, vals = part.partition(":")
        out[squash(name)] = vals
    return out


def _check_drawn(where: str, obj, leaves) -> list[str]:
    if not isinstance(obj.data.get("series"), dict):
        return []
    charts = [_series_attr(n.attrs.get("series", "")) for n in leaves if n.tag == "chart"]
    for name, vals in obj.data["series"].items():
        if not any(same_values(vals, c.get(squash(name), "")) for c in charts):
            return [f'{where}: needs <chart series="{name}:{fmt_list(vals)};…"> with series {name!r} verbatim']
    return []


DISPLAY = Display(tag="chart", order=50, enter="create", kind="chart", needs=("series",),
                  check_object=_check_object, check_drawn=_check_drawn)
