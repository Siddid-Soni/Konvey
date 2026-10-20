"""Overlay leaves -> Manim mobjects at natural size (spec §6.2), fit (§6.4)."""

from __future__ import annotations

import textwrap

from manimlib import *  # noqa: F401,F403

from .layout import Box
from .parse import Node

FONT = "Noto Sans"
ACCENT = "#facc15"
INK = "#e5e7eb"
MUTED = "#9ca3af"
CARD_FILL = "#111827"
CARD_STROKE = "#374151"

FONT_SIZE = {"h1": 64, "h2": 46, "h3": 34, "text": 30, "caption": 28, "value": 30}
WEIGHT = {"h1": BOLD, "h2": BOLD, "h3": BOLD}
WRAP = {"caption": 64, "text": 48}


class KineticText(VGroup):
    """Text whose glyphs are also grouped per word, for word-level animation."""

    def __init__(self, node: Node):
        size = int(node.attrs.get("size", FONT_SIZE[node.tag]))
        raw = "".join(s for s, _ in node.segments).strip()
        width = int(node.attrs.get("wrap", WRAP.get(node.tag, 0)))
        lines = [textwrap.fill(part, width) if width else part for part in raw.split("\n")]
        content = "\n".join(line.strip() for line in "\n".join(lines).split("\n"))
        emph = {s.strip(): ACCENT for s, e in node.segments if e and s.strip()}
        color = node.attrs.get("color", MUTED if node.tag == "caption" else INK)
        text = Text(content, font=FONT, font_size=size, weight=WEIGHT.get(node.tag, NORMAL),
                    t2c=emph, color=color, lsh=1.3)
        super().__init__(*text.submobjects)
        self.content = content
        self.emph_words = {w for phrase in emph for w in phrase.split()}
        self.words, self.word_strings = VGroup(), []
        i = 0
        for word in content.split():
            n = len(word)
            self.words.add(VGroup(*self.submobjects[i:i + n]))
            self.word_strings.append(word)
            i += n


class Value(VGroup):
    """``label  1.23`` bound to a world quantity; the number updates every frame."""

    def __init__(self, node: Node, world):
        size = int(node.attrs.get("size", FONT_SIZE["value"]))
        digits = int(node.attrs.get("digits", 2))
        self.label = Text(node.attrs.get("label", ""), font=FONT, font_size=size, color=MUTED)
        self.number = DecimalNumber(8888 if digits == 0 else 8.88, num_decimal_places=digits,
                                    font_size=size * 1.15, color=ACCENT,
                                    group_with_commas=False)
        super().__init__(self.label, self.number)
        self.arrange(RIGHT, buff=0.25, aligned_edge=DOWN)
        # Number size and gap are kept relative to the label, so moves/scales carry over.
        self._ratio = self.number.get_height() / self.label.get_height()
        self._gap = 0.25 / self.label.get_height()
        self.bind = node.attrs["bind"]
        self.content = self.bind
        self.world = world
        self.number.add_updater(self._update)

    def _update(self, number):
        h = self.label.get_height()
        number.set_value(self.world.values.get(self.bind, 0.0))
        number.set_height(h * self._ratio)
        number.next_to(self.label, RIGHT, buff=self._gap * h, aligned_edge=DOWN)


def build_leaf(node: Node, world) -> Mobject:
    if node.tag == "tex":
        tex = node.segments[0][0]
        size = int(node.attrs.get("size", 44))
        mob = Tex(tex, font_size=size, color=node.attrs.get("color", INK))
        mob.content = tex
        return mob
    if node.tag == "value":
        return Value(node, world)
    return KineticText(node)


def build_card(node: Node, box: Box) -> Mobject:
    card = RoundedRectangle(width=box.w, height=box.h, corner_radius=0.18,
                            fill_color=CARD_FILL, fill_opacity=0.82,
                            stroke_color=CARD_STROKE, stroke_width=1.5)
    card.move_to([box.x, box.y, 0])
    card.content = "card"
    return card


def fit(mob: Mobject, box: Box) -> Mobject:
    """Uniformly scale down (never up) into the box, then centre it there."""
    if mob.get_width() > box.w + 1e-3 or mob.get_height() > box.h + 1e-3:
        mob.scale(min(box.w / mob.get_width(), box.h / mob.get_height()))
    mob.move_to([box.x, box.y, 0])
    return mob
