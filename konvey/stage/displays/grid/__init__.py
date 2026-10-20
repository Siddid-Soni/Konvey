"""``<grid rows="4" cols="4" values="…" mark="2,3">``: a table of cells; the plan's ``grid`` kind.

A ``window="r,c,h,w"`` frames a block of cells (a filter over an image) and slides cell by cell
to its next place between beats; ``heat`` colours each cell by its number. ``row-labels`` and
``col-labels`` name the rows and columns (a confusion matrix, a truth table, an attention
pattern), ``cells="dots"`` draws each number as a dot sized by it, ``strike`` crosses cells out (a
mask), and ``sweep`` makes a beat's new values arrive one column (or row) at a time under a frame
named by ``op`` (normalising each column, a softmax, a running total)."""

from __future__ import annotations

from ...match import as_num, fmt_list, split_list, squash
from .. import Display
from .._values import drawn_values, flat_values


def _window(v) -> list[int] | None:
    """A planned ``window`` [r, c, h, w] (h, w default 1), or None if it is not four whole numbers."""
    if not isinstance(v, list) or len(v) not in (2, 4) or not all(isinstance(x, int) for x in v):
        return None
    return [*v, 1, 1] if len(v) == 2 else list(v)


SWEEPS = ("columns", "rows")


def struck(spec: str, rows: int, cols: int) -> set[int]:
    """``strike``: "below" (cells under the diagonal: a row later than its column, a causal
    mask), "above", or cells "r,c;r,c" -> cell indices (row * cols + col)."""
    spec = spec.strip().lower()
    if not spec:
        return set()
    if spec in ("below", "above"):
        return {r * cols + c for r in range(rows) for c in range(cols) if (r > c if spec == "below" else r < c)}
    out = set()
    for part in (p.strip() for p in spec.split(";") if p.strip()):
        try:
            r, c = (int(x) for x in part.split(","))
            assert 0 <= r < rows and 0 <= c < cols
        except (ValueError, AssertionError) as e:
            raise ValueError(f'strike "{part}": use "below", "above" or cells "row,col;row,col" inside '
                             f"the {rows}x{cols} grid") from e
        out.add(r * cols + c)
    return out


def _check_object(d: dict) -> list[str]:
    problems = []
    cells = flat_values(d)
    rows, cols = d.get("rows"), d.get("cols")
    sized = isinstance(rows, int) and isinstance(cols, int)
    for key, n in (("row_labels", rows), ("col_labels", cols)):
        labs = d.get(key)
        if labs is not None and (not isinstance(labs, list) or (sized and len(labs) != n)):
            problems.append(f"grid {key} must be a list of {n} names (one per {key[:3]})")
    if d.get("cells") not in (None, "numbers", "dots"):
        problems.append('grid cells: "dots" (a dot sized by each number) or leave it out (numbers)')
    if d.get("sweep") not in (None, *SWEEPS):
        problems.append('grid sweep: "columns" or "rows" (new values arrive one line at a time)')
    if "strike" in d:
        st = d["strike"]
        spec = st if isinstance(st, str) else ";".join(f"{a},{b}" for a, b in st) \
            if isinstance(st, list) and all(isinstance(x, list) and len(x) == 2 for x in st) else None
        if spec is None:
            problems.append('grid strike: "below", "above" or a list of [row, col] cells')
        elif sized:
            try:
                struck(spec, rows, cols)
            except ValueError as e:
                problems.append(f"grid {e}")
    if cells is not None and sized and len(cells) != rows * cols:
        problems.append(f"grid has {len(cells)} values for {rows}x{cols} cells")
    if "window" in d:
        win = _window(d["window"])
        if win is None:
            problems.append(f"grid window {d['window']!r}: use [row, col, height, width] (whole numbers)")
        elif sized and not (0 <= win[0] and 0 <= win[1] and win[2] >= 1 and win[3] >= 1
                            and win[0] + win[2] <= rows and win[1] + win[3] <= cols):
            problems.append(f"grid window {win} does not fit inside {rows}x{cols} cells")
        elif "kernel" in d:
            k = flat_values({"values": d["kernel"]})
            if k is None or len(k) != win[2] * win[3]:
                problems.append(f"grid kernel needs {win[2] * win[3]} numbers for a {win[2]}x{win[3]} window")
    elif "kernel" in d:
        problems.append("grid kernel needs a window [row, col, height, width] to sit in")
    heat = d.get("heat")
    if heat is not None and heat is not True and heat is not False and not (
            isinstance(heat, list) and len(heat) == 2 and all(as_num(x) is not None for x in heat)
            and as_num(heat[0]) < as_num(heat[1])):
        problems.append(f"grid heat {heat!r}: use true (range from the values) or [low, high]")
    return problems


def strike_spec(st) -> str:
    return st if isinstance(st, str) else ";".join(f"{a},{b}" for a, b in st)


def _check_drawn(where: str, obj, leaves) -> list[str]:
    problems = drawn_values(where, obj, leaves)
    win = _window(obj.data.get("window"))
    if win is not None:
        want = ",".join(map(str, win))
        drawn = {"".join(n.attrs.get("window", "").split()) for n in leaves if n.tag == "grid"}
        # "r,c" alone is a 1x1 window
        drawn |= {w + ",1,1" for w in drawn if w.count(",") == 1}
        if want not in drawn:
            problems.append(f'{where}: needs <grid window="{want}"> (the planned window: row,col,height,width)')
    grids = [n for n in leaves if n.tag == "grid"]
    d = obj.data
    for key, attr in (("row_labels", "row-labels"), ("col_labels", "col-labels")):
        if isinstance(d.get(key), list):
            want = [squash(x) for x in d[key]]
            if not any([squash(x) for x in split_list(n.attrs.get(attr, ""))] == want for n in grids):
                problems.append(f'{where}: needs <grid {attr}="{fmt_list(d[key])}"> (the planned names, in order)')
    for key in ("cells", "sweep"):
        if d.get(key) and not any(n.attrs.get(key, "").strip().lower() == d[key] for n in grids):
            problems.append(f'{where}: needs <grid {key}="{d[key]}">')
    if d.get("strike") and not any(squash(n.attrs.get("strike", "")) == squash(strike_spec(d["strike"])) for n in grids):
        problems.append(f'{where}: needs <grid strike="{strike_spec(d["strike"])}">')
    return problems


def _heat_range(beats: list, strict: bool = True) -> None:
    """``heat="true"`` takes one range for the grid's whole scene (every beat's numbers), so a
    cell keeps its colour while the rest of a feature map fills in; ``cells="dots"`` likewise
    takes one size scale (the largest number of the scene), so a dot keeps its size until its own
    number changes. Labels and dots widen the columns: every beat keeps the widest."""
    seen: dict[str, list[float]] = {}
    grids = [n for b in beats for n in b.leaves().values() if n.tag == "grid" and n.id]
    dots: dict[str, list[float]] = {}
    for n in grids:
        if n.attrs.get("cells", "").strip().lower() == "dots":
            dots.setdefault(n.id, []).extend(abs(x) for x in map(as_num, split_list(n.attrs.get("values", ""), rows=True))
                                             if x is not None)
    for n in grids:
        if dots.get(n.id):
            n.attrs["_dotmax"] = f"{max(dots[n.id]) or 1:g}"
    for n in grids:
        if n.attrs.get("heat", "").strip().lower() in ("true", "auto", "yes", "1"):
            raw = n.attrs.get("values", "")
            seen.setdefault(n.id, []).extend(x for x in map(as_num, split_list(raw, rows=True)) if x is not None)
    for n in grids:
        nums = seen.get(n.id)
        if nums and n.attrs.get("heat", "").strip().lower() in ("true", "auto", "yes", "1"):
            n.attrs["_heat"] = f"{min(nums)},{max(nums)}"


# a big board may scale to 50% to fit beside another grid (a 5x5 image next to its filter)
DISPLAY = Display(tag="grid", order=70, shrink=0.5, grow=True, kind="grid", needs=("rows", "cols"), prepare=_heat_range,
                  check_object=_check_object, check_drawn=_check_drawn)
