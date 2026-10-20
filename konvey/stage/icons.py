"""Line icons for things that have a look of their own (a sock, a person, a coin, a key, a die).

The vendored Tabler set (``assets/icons/tabler``, MIT): 4905 outline icons drawn on a 24 × 24
grid with round 2 px strokes, plus 849 filled ones. ``icon(name, height, fill, stroke)`` draws
one in the theme's colours: its closed outlines are filled (a dark sock is a dark shape with a
light edge, a light one the reverse), its open strokes (a cuff, a seam) stay lines.

Pure lookups (``exists``, ``suggest``) need no manimgl; ``icon`` does.
"""

from __future__ import annotations

import difflib
import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "assets" / "icons" / "tabler"
GRID = 24.0
# A few everyday words that the set spells differently.
ALIASES = {"person": "user", "people": "users", "die": "dice", "card": "cards", "letter": "mail",
           "envelope": "mail", "house": "home", "document": "file"}


@lru_cache(maxsize=None)
def _nodes(style: str) -> dict:
    return json.loads((ROOT / f"{style}.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _tags() -> dict:
    return json.loads((ROOT / "tags.json").read_text(encoding="utf-8"))


def resolve(name: str) -> str | None:
    """The set's own name for ``name`` (an alias, any case), or None."""
    key = name.strip().lower().replace(" ", "-")
    key = ALIASES.get(key, key)
    return key if key in _nodes("outline") else None


def exists(name: str) -> bool:
    return resolve(name) is not None


def suggest(name: str, n: int = 5) -> list[str]:
    """Names close to ``name``: by spelling, then icons tagged with it."""
    key = name.strip().lower()
    names = list(_nodes("outline"))
    close = difflib.get_close_matches(key, names, n=n, cutoff=0.6)
    tagged = [k for k, tags in _tags().items() if key in tags and k not in close]
    return (close + sorted(tagged, key=len))[:n]


_CLOSED = re.compile(r"[zZ]\s*$")


def _closed(tag: str, attrs: dict) -> bool:
    if tag in ("circle", "rect", "ellipse", "polygon"):
        return True
    return tag == "path" and bool(_CLOSED.search(attrs.get("d", "")))


def _ends_meet(shape, height: float) -> bool:
    """A path that comes back to where it started (a circle drawn as two arcs) is an outline too."""
    pts = shape.get_points()
    return len(pts) > 2 and float(((pts[0] - pts[-1]) ** 2).sum()) ** 0.5 < 0.02 * height


def _svg(nodes: list) -> str:
    """One element per node, preceded by the invisible 24 × 24 frame that fixes the scale."""
    parts = ['<path d="M0 0h24v24H0z"/>']
    for tag, attrs in nodes:
        if tag == "g":
            continue
        body = " ".join(f'{k}="{v}"' for k, v in attrs.items() if k not in ("stroke", "fill", "key"))
        parts.append(f"<{tag} {body}/>")
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">{"".join(parts)}</svg>'


def icon(name: str, height: float, fill: str, stroke: str, filled: bool = False):
    """A VGroup ``height`` units tall (the 24-unit grid; the drawing itself may be smaller),
    closed outlines filled with ``fill``, every outline stroked with ``stroke``."""
    from manimlib import SVGMobject, VGroup

    key = resolve(name)
    if key is None:
        raise KeyError(name)
    style = "filled" if filled and key in _nodes("filled") else "outline"
    nodes = [n for n in _nodes(style)[key] if n[0] != "g"]
    svg = SVGMobject(svg_string=_svg(nodes), height=None)
    frame, *shapes = svg.submobjects
    k = height / max(frame.get_height(), 1e-6)
    svg.scale(k)
    width = max(1.0, 2.0 / GRID * height * 100 * 0.42)   # Tabler's 2 px of 24, in manimgl stroke units
    out = VGroup()
    shut = [style == "filled" or _closed(tag, attrs) or _ends_meet(shape, height)
            for (tag, attrs), shape in zip(nodes, shapes)]
    bodies = [s for s, c in zip(shapes, shut) if c]

    def over_body(s):   # an open line drawn on a filled body (a cuff) vs. one standing alone (shoulders)
        x, y, _ = s.get_center()
        return any(b.get_left()[0] <= x <= b.get_right()[0] and b.get_bottom()[1] <= y <= b.get_top()[1]
                   for b in bodies)

    for shape, c in zip(shapes, shut):
        # a line standing alone is part of the thing's silhouette: drawn in its colour
        shape.set_stroke(stroke if c or over_body(shape) else fill, width)
        shape.set_fill(fill, 1.0 if c else 0.0)
        out.add(shape)
    # filled shapes behind the open strokes (a cuff line stays visible over the sock's body)
    out.submobjects.sort(key=lambda s: s.get_fill_opacity() < 0.5)
    return out
