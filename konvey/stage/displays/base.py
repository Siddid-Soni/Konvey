"""Shared pieces of the display mobjects (manimgl): cell/label builders, list attributes,
number formatting, and the default part-by-part morph."""

from __future__ import annotations

import re

import json

from manimlib import *  # noqa: F401,F403

from ..theme import current
from ..match import split_list
from ..tree import BeatError, Node

CELL = 0.9
# Every display highlights the same way (3b1b): the shape keeps its own fill and colour and its
# own outline is drawn in the accent at this width; never a solid accent fill or a frame around it.
LIT_W = 3.5


def lit_color(node: Node) -> str:
    """The highlight colour for this element: its own ``lit-color`` (a theme colour, or a hex),
    else the video's (theme ``lit``: the accent unless chosen)."""
    th = current()
    v = node.attrs.get("lit-color", "").strip()
    if not v:
        return th.lit
    try:
        return v if v.startswith("#") and len(v) in (4, 7) else th.color(v)
    except ValueError as e:
        raise BeatError(f'<{node.tag} id={node.id}> lit-color="{v}": {e}') from None
MAX_CELL = 3.0   # a cell widens for its text up to this (a log record "1 T1 A 100->70"), then the text shrinks


def cell_width(texts, size: float, least: float) -> float:
    """The width a row of cells needs so each text reads at its size (at least ``least``)."""
    widest = max((_label(t, size, "#ffffff").get_width() for t in texts if str(t).strip()), default=0.0)
    return min(MAX_CELL, max(least, widest / 0.85 + 0.1))


def data_list(node: Node, key: str, required: bool = True) -> list:
    raw = node.attrs.get(key, "").strip()
    if not raw:
        if required:
            raise BeatError(f"<{node.tag} id={node.id}> needs {key}=")
        return []
    if raw.startswith("["):
        return json.loads(raw)
    return split_list(raw)


def index_set(spec: str, n: int, what: str = "index") -> set[int]:
    """``"0-3,5"`` -> {0, 1, 2, 3, 5}; every index must be < n."""
    out: set[int] = set()
    for part in (p.strip() for p in spec.split(",") if p.strip()):
        try:
            a, _, b = part.partition("-")
            lo, hi = int(a), int(b or a)
        except ValueError as e:
            raise BeatError(f'{what} "{part}": use numbers or ranges like "0-3"') from e
        if not (0 <= lo <= hi < n):
            raise BeatError(f'{what} "{part}" is outside 0..{n - 1}')
        out.update(range(lo, hi + 1))
    return out


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError) as e:
        raise BeatError(f"{v!r} is not a number") from e


_SUP = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")
_E = re.compile(r"(-?\d+(?:\.\d+)?)[eE]([+-]?\d+)")


def times_ten(text: str) -> str:
    """``9.66e-08`` -> ``9.66×10⁻⁸``: a program's e-notation, written the way a person would."""
    return _E.sub(lambda m: f"{m.group(1)}×10{str(int(m.group(2))).translate(_SUP)}", text)


def tidy_number(text: str) -> str:
    """A cell's value as a person writes it: ``0.0013888889`` -> ``0.001389`` (four significant
    figures), ``2.16e-05`` -> ``2.16×10⁻⁵``; words, fractions and short numbers stay as given."""
    t = str(text).strip()
    try:
        v = float(t)
    except ValueError:
        return times_ten(t)
    digits = len(re.sub(r"[^0-9]", "", t.split("e")[0].split("E")[0]).lstrip("0"))
    if "e" not in t.lower() and (digits <= 5 or v.is_integer()):   # counts stay exact
        return t
    if v != 0 and abs(v) < 1e-4:
        return times_ten(f"{v:.3g}")
    out = f"{v:.4g}"
    return times_ten(out) if "e" in out else out


def _fmt(v: float, fmt: str | None) -> str:
    """Default: 1,048,576 / 12,742 / 0.53 / 2.5 / 9.66×10⁻⁸ — never e-notation on screen."""
    if fmt is None:
        if abs(v) >= 1000 or float(v).is_integer():
            return f"{v:,.0f}"
        return f"{v:.3g}" if abs(v) >= 0.001 else times_ten(f"{v:.2e}")
    try:
        return times_ten(fmt.format(v))
    except (ValueError, IndexError) as e:
        raise BeatError(f'fmt="{fmt}" is not a format like "{{:.3g}}"') from e


UNKNOWN = {"none", "null", "nan", "undefined"}   # a program's "no value yet", shown as "?"


def _label(text: str, size: float, color: str) -> Mobject:
    """Plain text; text with LaTeX commands (``\\cos\\theta`` in a matrix cell) is typeset."""
    text = "?" if str(text).strip().lower() in UNKNOWN else str(text)
    if text.strip().lower() in ("inf", "infinity", "-inf", "-infinity"):   # a program's infinity
        text = "-\u221e" if text.strip().startswith("-") else "\u221e"
    if "\\" in text:
        tex = text.strip().strip("$")
        try:
            return Tex(tex, font_size=size * 1.25).set_fill(color, 1)
        except Exception as e:  # noqa: BLE001 - LaTeX errors come back to Agent 3 by name
            raise BeatError(f"{text!r} is not valid LaTeX: {str(e).strip()[:120]}") from e
    return Text(text, font=current().body_font, font_size=size, fill_color=color)


class Block(VGroup):
    def set_content(self, node: Node, *keys: str):
        # lit-color (any display) is content too: changing only it redraws the highlight
        self.content = json.dumps([node.tag, *(node.attrs.get(k) for k in (*keys, "lit-color"))])


def _own_layer(item: Mobject, k: int) -> None:
    """manimgl draws consecutive VMobjects with the same shader in one batch: every fill of
    the batch first, then every stroke, so a post drawn as a line lands on top of boxes drawn
    after it. A uniform that differs by an invisible amount gives each shape its own batch,
    and shapes then paint in order."""
    for m in item.get_family():
        if "anti_alias_width" in m.uniforms:
            m.uniforms["anti_alias_width"] = float(m.uniforms["anti_alias_width"]) + 1e-4 * (k + 1)


HOP = PI / 2   # arc for an array item that jumps over two or more neighbours


def _swap(a: Mobject, b: Mobject) -> Animation:
    """Replace one label with another in place; either may be empty (no label)."""
    full_a, full_b = bool(a.get_family()[-1].has_points()), bool(b.get_family()[-1].has_points())
    if full_a and full_b:
        return FadeTransform(a, b)
    if full_b:
        return FadeIn(b, scale=0.6)
    if full_a:
        return FadeOut(a, scale=0.6)
    return Animation(Mobject())


def _parts(old: Mobject, new: Mobject) -> Animation:
    """Same structure: morph part by part; different structure: cross-fade in place."""
    a, b = old.submobjects, new.submobjects
    if not a and not b:
        return Transform(old, new)
    if len(a) == len(b) and a:
        if old.has_points() or new.has_points():
            # A part that is drawn itself and has parts (an axis line with its ticks): animating
            # only the children makes the scene drop the parent, so the line vanishes mid-morph.
            return Transform(old, new)
        return AnimationGroup(*(_parts(x, y) for x, y in zip(a, b)))
    return FadeTransform(old, new)
