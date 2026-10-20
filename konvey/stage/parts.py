"""Parts of every display, by name: what ``id>part`` means after the ``>``.

Rings, braces, arrows, labels (``of=``), ``focus``, the camera (``view``) and ``<tex from>`` all
name a part the same way. A display may define its own ``part(name)`` (the collection's groups);
otherwise the part is found here from the display's own structure:

| display | parts |
|---|---|
| array, vector | ``3`` (index), ``2-5`` (a run of cells), or a cell's own text (``7``, ``"b"``) |
| grid | ``2,3`` (row, column from 0), ``row 2``, ``col 3``, or a row or column heading |
| graph | a node's name (``A``), an edge ``A-B`` |
| places | a place's name, an item's id or text, a held thing (``5`` or ``store:5``) |
| draw | a shape's id |
| bars | a bar's label |
| plot | ``x=2`` (the point on the first curve there; a drawn point at that x if there is one), ``x=2 on g`` (on the curve named g), a curve's name, a point's name (``P``) |
| scatter | a point's label |
| chart | a series' name |
| plane | a vector's or point's name (its tip, where the matrix sends it) |
| tex | a run of the formula (``x^2``: its first occurrence; ``x^2#2`` the second) |
| text, headings | a word or phrase |

Returns ``None`` when the display has no such part (``attach.resolve`` names the error).
"""

from __future__ import annotations

import re

from manimlib import Dot, Mobject, VGroup

_RANGE = re.compile(r"^(\d+)\s*-\s*(\d+)$")
_CELL = re.compile(r"^(\d+)\s*,\s*(\d+)$")


def _norm(s: str) -> str:
    """Compared loosely: case, and spaces around punctuation (``1,000:1`` = ``1,000 : 1``)."""
    s = " ".join(str(s).strip().strip('"').split()).lower()
    return re.sub(r"\s*([^\w\s])\s*", r"\1", s)


def _indexed(cells, texts, name: str):
    """A cell by index, a run ``a-b`` (inclusive), or the first cell showing that text."""
    n = name.strip()
    if n.isdigit() and int(n) < len(cells):
        return cells[int(n)]
    m = _RANGE.match(n)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if a <= b < len(cells):
            return VGroup(*cells[a:b + 1])
    key = _norm(n)
    for cell, t in zip(cells, texts or []):
        if _norm(t) == key:
            return cell
    return None


def _array(mob, name):
    return _indexed(list(mob.cells), getattr(mob, "values", None), name)


def _vector(mob, name):
    texts = [getattr(e, "label_text", "") for e in mob.entries]
    return _indexed(list(mob.entries), texts, name)


def _grid(mob, name):
    rows, cols = mob.shape
    n = name.strip()
    m = _CELL.match(n)
    if m:
        r, c = int(m.group(1)), int(m.group(2))
        return mob.cells[r * cols + c] if r < rows and c < cols else None
    word, _, k = n.partition(" ")
    if word in ("row", "col") and k.strip().isdigit():
        k = int(k)
        if word == "row" and k < rows:
            return VGroup(*mob.cells[k * cols:(k + 1) * cols])
        if word == "col" and k < cols:
            return VGroup(*mob.cells[k::cols])
    key = _norm(n)
    for i, t in enumerate(getattr(mob, "col_text", []) or []):
        if _norm(t) == key:
            return VGroup(*mob.cells[i::cols])
    for i, t in enumerate(getattr(mob, "row_text", []) or []):
        if _norm(t) == key:
            return VGroup(*mob.cells[i * cols:(i + 1) * cols])
    return None


def _graph(mob, name):
    key = name.strip()
    names = list(mob.names)
    if key in names:
        return mob.nodes[names.index(key)]
    for sep in ("-", ">", "→"):
        a, s, b = key.partition(sep)
        if s:
            a, b = a.strip(), b.strip()
            for i, (u, v) in enumerate(mob.edge_keys):
                if (u, v) == (a, b) or (sep == "-" and (v, u) == (a, b)):
                    return mob.edges[i]
    return None


def _places(mob, name):
    key = name.strip()
    if key in getattr(mob, "items", {}):
        return mob.items[key]
    for i, info in getattr(mob, "item_info", {}).items():   # an item by the text it shows
        if _norm(info.get("text", "")) == _norm(key):
            return mob.items[i]
    for (place, text, _), slot in getattr(mob, "slots", {}).items():   # held contents: "5" or "store:5"
        if _norm(key) in (_norm(text), _norm(f"{place}:{text}")):
            return slot
    for p, shape in getattr(mob, "box_of", {}).items():
        if _norm(p) == _norm(key):
            for box in mob.boxes:   # the box with its name
                if box[0] is shape or shape in box[0].get_family():
                    return box
            return shape
    return None


def _draw(mob, name):
    return mob.items.get(name.strip())


def _bars(mob, name):
    """A bar with its name under it and its value over it: framing a bar shows what it is."""
    whole = [VGroup(b, lab, val) for b, lab, val in zip(mob.bars, mob.labels, mob.value_labels)]
    return _indexed(whole, mob.label_text, name)


def _plot(mob, name):
    from .displays.plot.mobject import Frame

    n = name.strip()
    curves = mob.spec.curves
    pts = list(getattr(mob.spec, "points", ()))
    dots = getattr(mob, "dots", [])
    for (label, x, _), dot in zip(pts, dots):   # a named point (``P``) is its dot
        if _norm(label) == _norm(n):
            return dot
    if n.startswith("x="):
        at, _, on = n[2:].partition(" on ")
        try:
            x = float(at)
        except ValueError:
            return None
        k = 0
        if on.strip():
            labels = [_norm(getattr(c, "label", "")) for c in curves]
            if _norm(on) not in labels:
                return None
            k = labels.index(_norm(on))
        if not curves:
            return None
        fr = Frame.of(mob)
        if not fr.inside(x, fr.y[0]) and not (fr.x[0] <= x <= fr.x[1]):
            return None
        if not on.strip():   # a point already drawn there is that part (focus keeps it lit)
            for (_, px, _), dot in zip(pts, dots):
                if abs(px - x) < 1e-9:
                    return dot
        y = float(curves[k].f(x))
        return Dot(fr.p(x, y), radius=0.06).set_opacity(0)
    for c, vm in zip(curves, mob.lines):
        if _norm(getattr(c, "label", "")) == _norm(n):
            return vm
    return None


def _chart(mob, name):
    return _indexed(list(mob.lines), mob.series_names, name)


def _plane(mob, name):
    """A vector or point by name: a point at its tip, where the matrix (if any) sends it."""
    sp = mob.spec
    for item in [*sp.vectors, *sp.points]:
        if _norm(item.name) == _norm(name):
            x0, x1, y0, y1, _ = sp.rng
            m = sp.m
            px = m[0, 0] * item.xy[0] + m[0, 1] * item.xy[1]
            py = m[1, 0] * item.xy[0] + m[1, 1] * item.xy[1]
            k = mob.view.get_width() / (x1 - x0)   # screen units per plane unit, as laid out
            c = mob.view.get_center()
            return Dot([c[0] + (px - (x0 + x1) / 2) * k, c[1] + (py - (y0 + y1) / 2) * k, 0],
                       radius=0.06).set_opacity(0)
    return None


def _scatter(mob, name):
    return _indexed(list(mob.points), getattr(mob, "name_text", None), name)


def occurrence(mob, name: str):
    """One occurrence of a run of a formula: the first (``1`` in "1 + 15" is the lone 1, not the
    1 inside 15), or the k-th with ``sym#k``. None when the formula has no such run."""
    sym, _, k = name.strip().rpartition("#") if "#" in name else (name.strip(), "", "1")
    try:
        i = int(k) - 1
        found = mob.select_parts(sym.strip())
        if not 0 <= i < len(found):
            return None
        part = mob.select_part(sym.strip(), i)
    except Exception:  # noqa: BLE001 - a run manimgl cannot split out
        return None
    return part if part.family_members_with_points() else None


def _tex(mob, name):
    return occurrence(mob, name)


def _text(mob, name):
    words = [_norm(w).strip(".,;:!?") for w in mob.word_strings]
    want = [_norm(w).strip(".,;:!?") for w in name.split()]
    for i in range(len(words) - len(want) + 1):
        if words[i:i + len(want)] == want:
            return VGroup(*mob.words[i:i + len(want)])
    return None


FINDERS = {"array": _array, "vector": _vector, "grid": _grid, "graph": _graph, "places": _places,
           "draw": _draw, "bars": _bars, "plot": _plot, "scatter": _scatter, "tex": _tex,
           "chart": _chart, "plane": _plane}


def find(mob: Mobject, name: str) -> Mobject | None:
    own = getattr(mob, "part", None)
    if own is not None:
        return own(name)
    tag = getattr(mob, "tag", None)
    if tag in FINDERS:
        try:
            return FINDERS[tag](mob, name)
        except (AttributeError, IndexError, KeyError):
            return None
    if hasattr(mob, "word_strings"):
        return _text(mob, name)
    return None
