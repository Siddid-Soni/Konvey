"""Comparing what the plan says with what a beat draws (pure Python; used by the checker and by
each display's own checks)."""

from __future__ import annotations

import html as _html
import re


def squash(text) -> str:
    return "".join(str(text).split()).lower()


def as_num(v) -> float | None:
    if isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def list_sep(raw: str) -> str:
    """A list attribute is split on "|" when it has one (a value may then hold a comma:
    "T1|committed, kept"), otherwise on ","."""
    return "|" if "|" in raw else ","


def split_list(raw: str, rows: bool = False) -> list[str]:
    """The items of a list attribute; ``rows``: ";" also ends an item (a grid row by row)."""
    sep = re.escape(list_sep(raw)) + (";" if rows else "")
    return [t.strip() for t in re.split(f"[{sep}]", raw)]


UNKNOWN = {"none", "null", "nan", "undefined", "?"}   # a program's "no value yet"; drawn as "?"


def cell_text(v) -> str:
    """A planned value as a beat writes it: a planned null (an unknown cell) is "?"."""
    if v is None or str(v).strip().lower() in UNKNOWN:
        return "?"
    return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)


def _same(want, got: str) -> bool:
    if want == "?":
        return got.strip().lower() in UNKNOWN or not got.strip()
    a, b = as_num(want), as_num(got)
    if a is not None and b is not None:
        return abs(a - b) <= 1e-6 * max(1.0, abs(a))
    return squash(want) == squash(got)


def same_values(planned: list, attr: str) -> bool:
    """The attribute lists the planned values in order: numbers compared as numbers
    (1048576 == 1.048576e6), anything else as text; a planned null matches "?" or an empty cell."""
    planned = [cell_text(v) for v in planned]
    cells = split_list(attr, rows=True)
    if len(cells) == len(planned) and all(_same(w, g) for w, g in zip(planned, cells)):
        return True
    # blank cells (a table's corner) draw as nothing: compare without them
    drawn = [t for t in cells if t]
    planned = [v for v in planned if v.strip()]
    return len(drawn) == len(planned) and all(_same(w, g) for w, g in zip(planned, drawn))


def fmt_list(values: list) -> str:
    cells = [cell_text(v) for v in values]
    sep = "|" if any("," in c for c in cells) else ","   # a value with a comma: "|" between
    return sep.join(cells)


_ATTR_RE = re.compile(r'([A-Za-z_][\w-]*)\s*=\s*"([^"]*)"')


def attrs_of(src: str) -> dict[str, str]:
    """``a="1" b="x"`` (a tag's source) -> {"a": "1", "b": "x"}."""
    return {k: _html.unescape(v) for k, v in _ATTR_RE.findall(src)}


def attr_src(attrs: dict[str, str]) -> str:
    return " ".join(f'{k}="{_html.escape(str(v), quote=True)}"' for k, v in attrs.items())
