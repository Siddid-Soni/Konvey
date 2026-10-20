"""Shots: the renderer composes a beat, so Agent 3 picks a composition instead of writing divs.

``<beat shot="derive">`` followed by the beat's elements in reading order, with no containers.
The elements are sorted into the picture (displays, or the 3D world) and the words (headings,
text, tex, numbers, readouts), then laid out by the shot's recipe:

- ``full``     the picture takes the whole stage; words (if any) in one line under it
- ``question`` one large line across the top (the first text/heading), the picture under it
- ``derive``   the picture on the left, the words stacked on the right (an equation built
               beside the thing it comes from)
- ``compare``  the pictures side by side, the same size, words under them
- ``title``    the words alone, large and centred (a chapter change or a payoff line)

A word with ``inline`` (an operator: ``<tex id="times" inline>\times</tex>``) stays in the
picture row between the pictures it was written between: a matrix × a vector, a set = a set.

Attached leaves (``of=``, ``<arrow>``, ``<ring>``, ``<brace>``) stay as they are: they sit on
their parts. A beat without ``shot`` keeps the HTML it was written with.
"""

from __future__ import annotations

from . import displays
from .tree import BeatError, Node

SHOTS = ("full", "question", "derive", "compare", "title")
WORDS = {"h1", "h2", "h3", "text", "tex", "number", "value"}
PAD = "padding: 0.75u 0.8u; gap: 0.35u"
QUESTION_SIZE = "48"
TITLE_SIZE = {"h1": "64", "h2": "56", "h3": "46", "text": "46"}


def _div(cls: str, style: str = "", children=(), ident: str | None = None) -> Node:
    attrs = {"class": cls}
    if style:
        attrs["style"] = style
    if ident:
        attrs["id"] = ident
    return Node("div", attrs, children=list(children))


def _leaves(overlay: list[Node], leaf_tags) -> list[Node]:
    """The beat's leaves in reading order, out of whatever containers were written around them."""
    out = []
    for root in overlay:
        for n in root.walk():
            if n.tag in leaf_tags:
                out.append(n)
    return out


def _regions(overlay: list[Node]) -> tuple[list[Node], list[Node]]:
    """(other areas of a larger page, the rest): a container written at the top of the beat with
    an id is a region the camera can travel to; it keeps its own layout."""
    regions = [n for n in overlay if n.tag in ("div", "section") and n.id]
    return regions, [n for n in overlay if n not in regions]


# marks drawn on other elements' parts (arrow, ring, brace): neither a picture nor words
MARKS = {d.tag for d in displays.all_displays() if not d.picture} - WORDS


def _attached(n: Node) -> bool:
    return "of" in n.attrs or n.tag in MARKS


def compose(attrs: dict, overlay: list[Node], has_world: bool, leaf_tags, index: int) -> list[Node]:
    """The beat's overlay rebuilt as ``shot`` lays it out."""
    shot = attrs.get("shot", "").strip()
    if shot not in SHOTS:
        raise BeatError(f'beat {index} shot="{shot}": use one of {", ".join(SHOTS)}')
    from .view import page_size

    regions, overlay = _regions(overlay)
    leaves = _leaves(overlay, leaf_tags)
    pinned = [n for n in leaves if _attached(n)]
    loose = [n for n in leaves if not _attached(n) and n.tag != "caption"]
    captions = [n for n in leaves if n.tag == "caption"]
    # ``inline`` words (an operator: ×, =, +) stay in the picture row, between the pictures
    # they were written between
    inline = lambda n: n.tag in WORDS and "inline" in n.attrs  # noqa: E731
    words = [n for n in loose if n.tag in WORDS and not inline(n)]
    # each picture in a box that fills its share of the row in both directions, so the layout
    # sees the room it may grow into
    pictures = [_div("grow center", "align-self: stretch", [n]) if not inline(n) else _div("center", "flex: none", [n])
                for n in loose if n.tag not in WORDS or inline(n)]
    n_pictures = sum(1 for n in loose if n.tag not in WORDS)
    formula = any(inline(n) for n in loose)
    if formula:
        # pictures with operators between them read as one formula (a matrix × a vector): packed
        # together, and grown as one (layout measures the row's room)
        for w in pictures:
            w.attrs["class"], w.attrs["style"] = "center", "flex: none"
            for n in w.children:
                if n.tag not in WORDS:
                    n.attrs["_grow"] = "1"
                    n.attrs["_formula"] = "1"   # a term of a written-out formula (names go under it)
    elif n_pictures > 1:   # side by side: each as wide as its picture needs, not an equal share
        for w in pictures:
            if "grow" in w.attrs["class"]:
                w.attrs["style"] += "; flex: 1 1 auto"
    row_cls = "grow row center formula" if formula else "grow row center"
    row_gap = "0.45u" if formula else None
    if has_world:   # the 3D world gets the picture's place (the camera frames it there)
        pictures.insert(0, _div("grow", ident="view"))
    pw, ph = page_size(attrs)
    attrs.setdefault("style", PAD if (pw, ph) == (1.0, 1.0) and not regions else "padding: 0")

    def line(ns, gap="0.6u"):
        return _div("row center", f"gap: {gap}", ns)

    if shot == "title":
        if n_pictures or has_world:
            raise BeatError(f'beat {index} shot="title" shows words only; put the picture in a '
                            'beat of its own (shot="full")')
        for n in words:
            n.attrs.setdefault("size", TITLE_SIZE.get(n.tag, n.attrs.get("size", "")) or "60")
        body = [_div("grow col center", "gap: 0.4u", words)]
    elif not n_pictures and not has_world:
        raise BeatError(f'beat {index} shot="{shot}" needs a picture (a display or a <world>); '
                        'for words alone use shot="title"')
    elif shot == "full":
        body = [_div(row_cls, f"gap: {row_gap or '1u'}", pictures)] + ([line(words)] if words else [])
    elif shot == "question":
        if not words:
            raise BeatError(f'beat {index} shot="question" needs the question as its first '
                            '<text> or heading')
        q, rest = words[0], words[1:]
        q.attrs.setdefault("size", QUESTION_SIZE)
        body = [line([q]), _div(row_cls, f"gap: {row_gap or '1u'}", pictures)] + ([line(rest)] if rest else [])
    elif shot == "derive":
        body = [_div("grow row center", "gap: 0.9u", [
            _div(row_cls, f"gap: {row_gap or '0.6u'}; flex: 3 1 0; align-self: stretch", pictures),
            _div("col center", "gap: 0.45u; flex: 2 1 0; align-self: stretch", words),
        ])]
    else:   # compare
        if n_pictures + has_world < 2:
            raise BeatError(f'beat {index} shot="compare" needs two pictures side by side')

        body = [_div(row_cls, f"gap: {row_gap or '1.2u'}", pictures)] + ([line(words)] if words else [])
    if (pw, ph) != (1.0, 1.0) or regions:
        # the shot fills the home frame; the regions lie beyond it (right on a wide page, below
        # on a tall one), where view= takes the camera
        home = _div("col", f"width: 14.22u; height: 8u; flex: none; {PAD}", body)
        body = [_div("row" if pw > 1 else "col", "flex: none", [home, *regions])]
    return body + pinned + captions
