"""``<relation cols="a,fluffy,blue,creature" weights="…">``: how strongly each item of one list
relates to each item of another (or of the same list); the plan's ``relation`` kind.

One picture for many topics: attention between the words of a sentence, word alignment between a
sentence and its translation, a confusion matrix, a similarity or correlation matrix,
co-occurrence counts, which word a pronoun means, a bipartite matching. Drawn the way 3Blue1Brown
draws an attention pattern: ``cols`` in a row across the top, ``rows`` (the same list when left
out) down the left, and each cell holds a dot sized by the pair's weight. ``weights`` is given one
group per column, so a column-normalised group sums to 1. ``view="links"`` shows the items
instead: with one list, arrows arc from the related items into the ``focus`` item; with two
lists, the rows sit in a second line under the columns and each pair is joined by a line as thick
as its weight. Numbers that belong to one item (an embedding, a score) are a ``<vector>`` beside
the picture, not part of it. The same items stay in place between views, so one picture morphs through the
whole story. This module is pure Python: the attribute parsing shared with the mobject, and the
plan checks."""

from __future__ import annotations

import re

from ...match import as_num, fmt_list, same_values, split_list, squash
from ...tree import BeatError
from .. import Display

MAX_ITEMS = 10         # beyond this the labels and cells are unreadably small
SUM_TOL = 0.02         # a normalised group sums to 1 within rounding (0.33 + 0.33 + 0.33)
VIEWS = ("grid", "links", "both")
NORMALIZE = ("none", "columns", "rows")
MASKS = ("none", "later")
NEG_INF = {"-inf", "−inf", "-∞", "−∞"}


def items_of(raw: str) -> list[str]:
    return [t for t in split_list(raw) if t] if raw.strip() else []


def groups_of(raw: str) -> list[list[str]]:
    """``"0.1,0.9;1,0"`` -> one list per group (a column's weights, an item's vector)."""
    if not raw.strip():
        return []
    sep = "|" if "|" in raw else ","
    return [[c.strip() for c in g.split(sep)] if g.strip() else [] for g in raw.split(";")]


def cell_num(text: str) -> float | None:
    """A weight as a number; "" (not computed yet) is None, a masked "-inf" is -inf."""
    t = text.strip().lower()
    if t in NEG_INF:
        return float("-inf")
    return as_num(t) if t else None


def item_index(spec: str, items: list[str], what: str) -> int | None:
    """``focus="creature"`` or ``focus="3"`` -> its position; a repeated item needs its index."""
    spec = spec.strip()
    if not spec:
        return None
    hits = [i for i, t in enumerate(items) if squash(t) == squash(spec)]
    if len(hits) == 1:
        return hits[0]
    if spec.isdigit() and int(spec) < len(items):
        return int(spec)
    if hits:
        raise BeatError(f'{what}="{spec}": that item appears {len(hits)} times; give its position '
                        f'(0..{len(items) - 1}) instead')
    raise BeatError(f'{what}="{spec}" is not one of the items ({", ".join(items)})')


def truthy(v) -> bool:
    return str(v).strip().lower() in ("true", "yes", "1", "on")


def norm_of(raw) -> str:
    v = str(raw or "").strip().lower()
    return {"": "none", "false": "none", "column": "columns", "row": "rows", "true": "columns"}.get(v, v)


def mask_of(raw) -> str:
    v = str(raw or "").strip().lower()
    return {"": "none", "causal": "later", "false": "none"}.get(v, v)


def masked(row: int, col: int, mask: str) -> bool:
    """``mask="later"`` (one list): a column sees only itself and the items before it."""
    return mask == "later" and row > col


def _nums(col: list) -> list[float | None]:
    return [float(c) if isinstance(c, (int, float)) and not isinstance(c, bool) else cell_num(str(c)) for c in col]


def weight_problems(cols: list[str], rows: list[str], weights: list[list], norm: str, mask: str) -> list[str]:
    """Shape (one group of len(rows) per column, or an empty group not computed yet), numbers,
    and when normalised, groups (columns) or rows that sum to 1 with masked cells at 0. Shared by
    the plan check and the renderer."""
    n, m = len(cols), len(rows)
    if len(weights) != n:
        return [f"weights has {len(weights)} groups for {n} columns: give one group per column "
                f"(its weights for all {m} rows, in order), {n} groups of {m}"]
    problems, grid = [], []
    for c, col in enumerate(weights):
        if not col or all(str(v).strip() == "" for v in col):
            grid.append(None)                          # this column is not computed yet
            continue
        if len(col) != m:
            problems.append(f'weights for "{cols[c]}" has {len(col)} numbers for {m} rows')
            grid.append(None)
            continue
        nums = _nums(col)
        bad = [v for v, x in zip(col, nums) if x is None and str(v).strip()]
        if bad:
            problems.append(f'weights for "{cols[c]}": {bad[:3]} are not numbers')
            grid.append(None)
            continue
        grid.append(nums)
        if norm == "none" or None in nums:
            continue
        hidden = [rows[r] for r, v in enumerate(nums) if masked(r, c, mask) and v != 0]
        if hidden:
            problems.append(f'weights for "{cols[c]}": with mask="later" the later items {hidden} '
                            f"must have weight 0 once normalised")
        if any(v < 0 or v > 1 for v in nums):
            problems.append(f'weights for "{cols[c]}": normalised weights lie between 0 and 1')
        elif norm == "columns" and abs(sum(nums) - 1) > SUM_TOL:
            problems.append(f'weights for "{cols[c]}" sum to {sum(nums):.3g}; with normalize="columns" '
                            f"each column sums to 1")
    if norm == "rows" and not problems and all(g is not None for g in grid):
        for r in range(m):
            s = sum(g[r] for g in grid)
            if abs(s - 1) > SUM_TOL:
                problems.append(f'row "{rows[r]}" sums to {s:.3g}; with normalize="rows" each row '
                                f"sums to 1 (fill every column)")
    return problems


def list_problems(cols: list[str], rows: list[str], mask: str, view: str) -> list[str]:
    problems = []
    for what, items in (("cols", cols), ("rows", rows)):
        if not 1 <= len(items) <= MAX_ITEMS:
            problems.append(f"{what} has {len(items)} items; use 1 to {MAX_ITEMS} (a short list)")
    if len(cols) + (len(rows) if rows is not cols else 0) < 2:
        problems.append("a relation needs at least two items")
    if mask not in MASKS:
        problems.append(f'mask "{mask}": use "later" (an item sees only itself and earlier items) or leave it out')
    elif mask == "later" and rows is not cols:
        problems.append('mask="later" needs one list (leave rows out)')
    if view not in VIEWS:
        problems.append(f'view "{view}": use one of {", ".join(VIEWS)}')
    elif view == "both" and rows is not cols:
        problems.append('view="both" needs one list (leave rows out); with two lists use "grid" or "links"')
    return problems


# --- the plan --------------------------------------------------------------------------------
def _plan_list(d: dict, key: str) -> list[str] | None:
    v = d.get(key)
    if isinstance(v, list) and v and all(isinstance(t, (str, int, float)) for t in v):
        return [str(t) for t in v]
    return None


def plan_lists(d: dict) -> tuple[list[str] | None, list[str] | None]:
    cols = _plan_list(d, "cols")
    rows = _plan_list(d, "rows") if d.get("rows") is not None else cols
    return cols, rows


def _plan_weights(d: dict) -> list[list] | None:
    w = d.get("weights")
    if isinstance(w, list) and all(isinstance(g, list) for g in w):
        return [["" if v is None else v for v in g] for g in w]
    return None


def _check_object(d: dict) -> list[str]:
    cols, rows = plan_lists(d)
    if cols is None:
        return ['relation cols must be a list of items ["a", "fluffy", "blue", "creature"]']
    if rows is None:
        return ['relation rows must be a list of items (or leave it out: the rows are the cols)']
    if d.get("rows") is not None and [squash(t) for t in rows] == [squash(t) for t in cols]:
        rows = cols
    mask, norm, view = mask_of(d.get("mask")), norm_of(d.get("normalize")), d.get("view", "grid")
    problems = [f"relation {p}" for p in list_problems(cols, rows, mask, view)]
    if norm not in NORMALIZE:
        problems.append(f'relation normalize {d.get("normalize")!r}: use "columns" or "rows"')
    if "weights" in d:
        w = _plan_weights(d)
        if w is None:
            problems.append("relation weights: a list with one list per column (its weight for every "
                            "row), e.g. [[1, 0], [0.3, 0.7]]")
        elif not problems:
            problems += [f"relation {p}" for p in weight_problems(cols, rows, w, norm, mask)]
    for key, items in (("focus", cols), ("focus_row", rows)):
        if key in d and squash(d[key]) not in {squash(t) for t in items} and not (
                isinstance(d[key], int) and 0 <= d[key] < len(items)):
            problems.append(f"relation {key} {d[key]!r} is not one of the {'cols' if key == 'focus' else 'rows'}")
    return problems


def _same_list(a: list[str], raw: str) -> bool:
    return [squash(t) for t in items_of(raw)] == [squash(t) for t in a]


def _check_drawn(where: str, obj, leaves) -> list[str]:
    d = obj.data
    cols, rows = plan_lists(d)
    mine = [n for n in leaves if n.tag == "relation"]
    if not cols:
        return []
    if not mine:
        return [f'{where}: needs <relation cols="{fmt_list(cols)}"> (the planned items)']
    same = [n for n in mine if _same_list(cols, n.attrs.get("cols", ""))]
    if not same:
        return [f'{where}: needs <relation cols="{fmt_list(cols)}"> (the planned items, in order)']
    problems = []
    if d.get("rows") is not None and rows != cols:
        if not any(_same_list(rows, n.attrs.get("rows", "") or n.attrs.get("cols", "")) for n in same):
            problems.append(f'{where}: needs <relation rows="{fmt_list(rows)}"> (the planned rows, in order)')
    w = _plan_weights(d)
    if w is not None:
        want = ";".join(fmt_list(g) for g in w)
        flat = [v for g in w for v in g]
        if not any(same_values(flat, n.attrs.get("weights", "")) and len(groups_of(n.attrs.get("weights", ""))) == len(w)
                   for n in same):
            problems.append(f'{where}: needs <relation weights="{want}"> (the planned weights, one group per column)')
    if norm_of(d.get("normalize")) != "none" and not any(
            norm_of(n.attrs.get("normalize")) == norm_of(d.get("normalize")) for n in same):
        problems.append(f'{where}: needs <relation normalize="{norm_of(d.get("normalize"))}">')
    if d.get("numbers") and not any(truthy(n.attrs.get("numbers", "")) for n in same):
        problems.append(f'{where}: needs <relation numbers="true">')
    if mask_of(d.get("mask")) == "later" and not any(mask_of(n.attrs.get("mask")) == "later" for n in same):
        problems.append(f'{where}: needs <relation mask="later">')
    for key, attr in (("focus", "focus"), ("focus_row", "focus-row"), ("view", "view")):
        if key in d and not any(squash(n.attrs.get(attr, "grid" if key == "view" else "")) == squash(d[key])
                                for n in same):
            problems.append(f'{where}: needs <relation {attr}="{d[key]}">')
    return problems


# --- one picture for the scene ---------------------------------------------------------------
def view_of(attrs: dict) -> str:
    v = attrs.get("view", "").strip().lower()
    if v:
        return v
    return "grid" if attrs.get("weights", "").strip() else "links"


def two_lists(attrs: dict) -> bool:
    rows = attrs.get("rows", "").strip()
    return bool(rows) and [squash(t) for t in items_of(rows)] != [squash(t) for t in items_of(attrs.get("cols", ""))]


def _arrows(n) -> bool:
    """One list, links view, a focus and weights: arcs into the focus item."""
    return (not two_lists(n.attrs) and view_of(n.attrs) in ("links", "both")
            and bool(n.attrs.get("focus", "").strip()) and bool(n.attrs.get("weights", "").strip()))


def arc_span(n) -> int:
    """How many items the longest arc into the focus crosses (0: no arcs), so the room kept
    above the items fits the arcs the scene draws, not the longest arc it could."""
    if not _arrows(n):
        return 0
    cols = items_of(n.attrs.get("cols", ""))
    try:
        f = item_index(n.attrs.get("focus", ""), cols, "focus")
    except BeatError:
        return 0
    groups = groups_of(n.attrs.get("weights", ""))
    col = groups[f] if f is not None and f < len(groups) else []
    nums = [cell_num(v) for v in col]
    top = max((abs(v) for v in nums if v is not None and v != float("-inf")), default=0) or 1
    normed = norm_of(n.attrs.get("normalize")) != "none"
    mask = mask_of(n.attrs.get("mask"))
    far = [abs(j - f) for j, v in enumerate(nums) if j != f and v is not None and v != float("-inf")
           and not masked(j, f, mask) and (v if normed else v / top) >= 0.04]
    return max(far, default=0)


def _reserve_room(beats: list, strict: bool = True) -> None:
    """Every beat of one ``<relation id>`` is laid out on one canvas: the room for the grid, the
    row labels, the arcs or the second line of items that any beat of the scene shows is kept in all of them (``_room``), so the items never move while the picture
    changes under them. Raw weights share one scale (``_scale``), so a dot keeps its size until
    its own number changes."""
    nodes: dict[str, list] = {}
    for b in beats:
        for n in b.leaves().values():
            if n.tag == "relation" and n.id:
                nodes.setdefault(n.id, []).append(n)
    for ns in nodes.values():
        grid = any(view_of(n.attrs) in ("grid", "both") for n in ns)
        arcs = max((arc_span(n) for n in ns), default=0)
        links2 = any(two_lists(n.attrs) and view_of(n.attrs) == "links" for n in ns)
        rows = max((len(items_of(n.attrs.get("rows", "") or n.attrs.get("cols", ""))) for n in ns), default=0)
        cols = max((len(items_of(n.attrs.get("cols", ""))) for n in ns), default=0)
        raw = [abs(v) for n in ns if norm_of(n.attrs.get("normalize")) == "none"
               for g in groups_of(n.attrs.get("weights", "")) for v in map(cell_num, g)
               if v is not None and v != float("-inf")]
        room = f"grid={int(grid)};arcs={arcs};links2={int(links2)};rows={rows};cols={cols}"
        for n in ns:
            n.attrs["_room"] = room
            n.attrs["_scale"] = f"{max(raw, default=1.0) or 1.0:g}"


ROOM_RE = re.compile(r"(\w+)=(\d+)")


def room_of(raw: str) -> dict[str, int]:
    return {k: int(v) for k, v in ROOM_RE.findall(raw)}


DISPLAY = Display(tag="relation", order=82, steady=True, grow=2.0, shrink=0.5, min_size=22,
                  kind="relation", needs=("cols",), prepare=_reserve_room,
                  check_object=_check_object, check_drawn=_check_drawn)
