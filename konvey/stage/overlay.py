"""Overlay leaves -> Manim mobjects at natural size (spec §6.2), fit (§6.4).

Text tags (h1–h3, text, caption) are drawn here; every other leaf is a display
(``konvey/stage/displays/<name>/mobject.py``)."""

from __future__ import annotations

import textwrap

from manimlib import *  # noqa: F401,F403

from . import displays
from .layout import Box
from .parse import BeatError, Node
from .theme import current

FONT_SIZE = {"h1": 64, "h2": 46, "h3": 34, "text": 30, "caption": 28}
HEADINGS = ("h1", "h2", "h3")
WRAP = {"caption": 64, "text": 48}


class KineticText(VGroup):
    """Text whose glyphs are also grouped per word, for word-level animation."""

    def __init__(self, node: Node):
        size = int(node.attrs.get("size", FONT_SIZE[node.tag]))
        raw = "".join(s for s, _ in node.segments).strip()
        width = int(node.attrs.get("wrap", WRAP.get(node.tag, 0)))
        lines = [textwrap.fill(part, width) if width else part for part in raw.split("\n")]
        content = "\n".join(line.strip() for line in "\n".join(lines).split("\n"))
        th = current()
        pill = node.tag == "caption" and th.caption == "pill"
        emph = {s.strip(): th.accent for s, e in node.segments if e and s.strip()}
        color = th.color(node.attrs.get("color"), "muted" if pill else "ink")
        heading = node.tag in HEADINGS
        text = Text(content, font=th.heading_font if heading else th.body_font, font_size=size,
                    weight=th.heading_weight if heading else NORMAL,
                    t2c=emph, fill_color=color, lsh=1.3)   # Text ignores color= in 1.7.2
        super().__init__(*text.submobjects)
        self.content = content
        self.tag = node.tag
        # motion.py rebuilds single words (a counting number) in exactly this style
        self.style = dict(font=th.heading_font if heading else th.body_font, font_size=size,
                          weight=th.heading_weight if heading else NORMAL)
        self.emph_words = {w for phrase in emph for w in phrase.split()}
        self.words, self.word_strings = VGroup(), []
        i = 0
        for word in content.split():
            n = len(word)
            self.words.add(VGroup(*self.submobjects[i:i + n]))
            self.word_strings.append(word)
            i += n
        self.backing = None
        if pill:
            # Captions sit over 3D content: give them a dark band so they stay readable.
            band = RoundedRectangle(width=self.get_width() + 0.5, height=self.get_height() + 0.3,
                                    corner_radius=0.12, fill_color=th.panel_fill, fill_opacity=0.78,
                                    stroke_width=0).move_to(self)
            self.backing = band
            self.add_to_back(band)


def build_leaf(node: Node, world) -> Mobject:
    build = displays.hook(node.tag, "build")
    if build is None:
        if node.tag not in FONT_SIZE:
            raise BeatError(f"<{node.tag} id={node.id}> is not a leaf this renderer can draw")
        return KineticText(node)
    mob = build(node, world)
    mob.tag = node.tag   # motion and scene look up the display's hooks by it
    return mob


def build_card(node: Node, box: Box) -> Mobject:
    th = current()
    drawn = th.cards or "panel" in node.attrs.get("class", "").split()
    card = RoundedRectangle(width=box.w, height=box.h, corner_radius=0.18,
                            fill_color=th.panel_fill, fill_opacity=0.82 if drawn else 0,
                            stroke_color=th.panel_stroke, stroke_width=1.5 if drawn else 0)
    card.move_to([box.x, box.y, 0])
    card.content = "card"
    return card


def fit(mob: Mobject, box: Box, grow: bool = False) -> Mobject:
    """Uniformly scale down into the box (and up into it with ``grow``: the layout enlarged the
    box of a lone picture), then centre it there."""
    k = min(box.w / max(mob.get_width(), 1e-6), box.h / max(mob.get_height(), 1e-6))
    if k < 1 - 1e-4 or (grow and k > 1 + 1e-3):
        mob.scale(k)
    mob.move_to([box.x, box.y, 0])
    return mob
