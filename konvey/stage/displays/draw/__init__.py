"""``<draw>``: a flat diagram built from shapes in its own coordinates; the plan's ``drawing`` kind."""

from __future__ import annotations

import re

from ...match import squash
from .. import Display

SHAPES = frozenset({"rect", "circle", "polygon", "line", "label", "arc", "icon"})   # its children


def _check_object(d: dict) -> list[str]:
    if "shows" in d and any(k in d for k in ("parts", "items", "holds")):
        return ["parts/items/holds belong to kind 'system' (parts joined by wires, with items "
                "moving between them), not 'drawing'"]
    return []


def _check_drawn(where: str, obj, leaves) -> list[str]:
    if not isinstance(obj.data.get("labels"), list):
        return []
    drawn = {squash(t) for n in leaves if n.tag == "draw" for c in n.children
             for t in (c.attrs.get("text", ""), c.attrs.get("label", "")) if t}
    missing = [str(x) for x in obj.data["labels"] if squash(x) not in drawn]
    if missing:
        return [f"{where}: needs a <draw> whose shapes show the planned labels; missing {missing} "
                '(as <label text="…"> or a shape\'s label="…")']
    return []


def frame_of(n) -> tuple[float, float, float, float, float, float]:
    """``(w, h, x0, x1, y0, y1)`` of a ``<draw>``: its size on the page and the window of its own
    coordinates it shows (default 0..w and 0..h). Unreadable values read as the defaults; the
    block itself reports them."""
    def f(v, d):
        try:
            return float(v)
        except (TypeError, ValueError):
            return d
    w, h = f(n.attrs.get("w"), 8.0), f(n.attrs.get("h"), 4.0)

    def rng(key, hi):
        parts = (n.attrs.get(key) or "").split(",")
        return (f(parts[0], 0.0), f(parts[1], hi)) if len(parts) >= 2 else (0.0, hi)
    return (w, h, *rng("x", w), *rng("y", h))


_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def _extent(n) -> tuple[float, float, float, float] | None:
    """The box (x0, x1, y0, y1) the shapes cover, in the draw's own coordinates."""
    xs, ys = [], []
    for c in n.children:
        a = c.attrs
        for key in ("points", "from", "to") if c.tag in ("line", "polygon") else ():
            nums = [float(v) for v in _NUM.findall(a.get(key, ""))]
            xs += nums[0::2]
            ys += nums[1::2]
        if c.tag in ("rect", "circle", "arc", "label", "icon"):
            try:
                x, y = float(a["x"]), float(a["y"])
            except (KeyError, ValueError):
                continue
            rx = float(a.get("r") or 0) if c.tag in ("circle", "arc") else float(a.get("w") or a.get("h") or 0) / 2
            ry = float(a.get("r") or 0) if c.tag in ("circle", "arc") else float(a.get("h") or 0) / 2
            xs += [x - rx, x + rx]
            ys += [y - ry, y + ry]
    return (min(xs), max(xs), min(ys), max(ys)) if xs and ys else None


FRAME_SLACK = 0.03   # shapes may poke this fraction of the window past its edge (an arrow tip, a label)


def carry_draw_frame(beats: list, strict: bool = True) -> None:
    """A drawing keeps the frame of its first beat (``w``/``h`` on the page and its ``x``/``y``
    window), also over a scene cut (the previous scene's last beat comes first): each scene's
    beats pick their own frame, so without this the axes cross-fade at two scales and the plane
    changes size at every cut. The window only widens, once, when a beat's shapes would fall
    outside it (then the shapes shrink in place, they never jump). Never an error."""
    frames: dict[str, tuple] = {}
    for b in beats:
        for n in b.leaves().values():
            if n.tag != "draw" or not n.id:
                continue
            own = frame_of(n)
            prev = frames.get(n.id)
            if prev is None:
                frames[n.id] = own
                continue
            w, h, x0, x1, y0, y1 = prev
            ext = _extent(n)
            sx, sy = FRAME_SLACK * (x1 - x0), FRAME_SLACK * (y1 - y0)
            if ext is not None and not (ext[0] >= x0 - sx and ext[1] <= x1 + sx and ext[2] >= y0 - sy and ext[3] <= y1 + sy):
                x0, x1 = min(x0, own[2], ext[0]), max(x1, own[3], ext[1])
                y0, y1 = min(y0, own[4], ext[2]), max(y1, own[5], ext[3])
            frames[n.id] = (w, h, x0, x1, y0, y1)
            n.attrs.update(w=f"{w:g}", h=f"{h:g}", x=f"{x0:g},{x1:g}", y=f"{y0:g},{y1:g}")


_GEOMETRY = ("x", "y", "r", "w", "h", "points", "from", "to")


def _shape_key(c) -> tuple:
    """Where a shape is and what shape it is, without its id, colour or label."""
    return (c.tag, *("".join(c.attrs.get(k, "").split()) for k in _GEOMETRY))


def _adopt(prev, first) -> None:
    """Scenes are written independently: the same picture may be ``plane`` in one scene and
    ``board`` in the next (one draw each side: the same drawing), and the same x axis ``re`` and
    ``xaxis``. A shape of the previous scene takes the id of the next scene's shape it is (see
    below), so it stays put, or moves on, over the cut instead of cross-fading with a twin."""
    olds = [n for n in prev.leaves().values() if n.tag == "draw"]
    news = [n for n in first.leaves().values() if n.tag == "draw"]
    if len(olds) == 1 and len(news) == 1 and olds[0].id != news[0].id:
        olds[0].attrs["id"] = news[0].id
    by_id = {n.id: n for n in news}
    for old in olds:
        new = by_id.get(old.id)
        if new is None:
            continue
        old_ids = {c.id for c in old.children}
        free = [c for c in old.children if c.id not in {d.id for d in new.children}]
        todo = [c for c in new.children if c.id not in old_ids]   # the rest carry over by name
        text = lambda c: c.attrs.get("text") or c.attrs.get("label") or ""  # noqa: E731
        # same place and shape; else the same text; else the only one of its kind left each
        # side (the spoke of a clock that moved on during the cut), which then turns or slides
        for same in (lambda p, c: _shape_key(p) == _shape_key(c),
                     lambda p, c: p.tag == c.tag and text(p) and text(p) == text(c),
                     lambda p, c: p.tag == c.tag and sum(q.tag == c.tag for q in free) == 1
                     and sum(d.tag == c.tag for d in todo) == 1):
            for c in list(todo):
                match = next((p for p in free if same(p, c)), None)
                if match is not None:
                    free.remove(match)
                    todo.remove(c)
                    match.attrs["id"] = c.id


DISPLAY = Display(tag="draw", grow=True, order=120, children=SHAPES, steady=True, kind="drawing", needs=("shows",),
                  prepare=carry_draw_frame, adopt=_adopt, check_object=_check_object, check_drawn=_check_drawn)
