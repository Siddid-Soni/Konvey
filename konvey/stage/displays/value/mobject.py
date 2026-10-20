"""``<value>`` (manimgl): ``label  1.23`` whose number follows a world quantity every frame. A live
number rebuilds its glyphs each frame, so it fades by opacity and moves by its label."""

from __future__ import annotations

from manimlib import *  # noqa: F401,F403

from ...theme import current
from ...tree import BeatError, Node

FONT_SIZE = 30


class Value(VGroup):
    """``label  1.23`` bound to a world quantity; the number updates every frame."""

    tag = "value"

    def __init__(self, node: Node, world):
        size = int(node.attrs.get("size", FONT_SIZE))
        digits = self.digits = int(node.attrs.get("digits", 2))
        th = current()
        self.label = Text(node.attrs.get("label", ""), font=th.body_font, font_size=size,
                          fill_color=th.muted)
        self.number = DecimalNumber(8888 if digits == 0 else 8.88, num_decimal_places=digits,
                                    font_size=size * 1.15, color=th.color(node.attrs.get("color"), "accent"),
                                    group_with_commas=False)
        super().__init__(self.label, self.number)
        self.arrange(RIGHT, buff=0.25, aligned_edge=DOWN)
        # Number size and gap are kept relative to the label, so moves/scales carry over.
        self._ratio = self.number.get_height() / self.label.get_height()
        self._gap = 0.25 / self.label.get_height()
        if not node.attrs.get("bind"):
            raise BeatError(f'<value id={node.id}> needs bind="…" (a live world value such as '
                            '"shadowId.area"); for a fixed number use <text> with the number')
        self.bind = node.attrs["bind"]
        self.content = self.bind
        self.world = world
        self.number.add_updater(self._update)

    def _update(self, number):
        h = self.label.get_height()
        # manimgl truncates (9.99999 shows "9" at 0 decimals), so round first.
        number.set_value(round(float(self.world.values.get(self.bind, 0.0)), self.digits))
        number.set_height(h * self._ratio)
        number.next_to(self.label, RIGHT, buff=self._gap * h, aligned_edge=DOWN)


def build(node: Node, world) -> Value:
    return Value(node, world)


def _fade_number(number, fade_in: bool, run_time: float = 0.5) -> Animation:
    """A live number rebuilds its glyphs every frame, so fade it by opacity, not Transform."""
    return UpdateFromAlphaFunc(number, lambda m, a: m.set_opacity(a if fade_in else 1 - a),
                               run_time=run_time)


def enter(node: Node, mob: Value, run_time: float) -> Animation:
    return AnimationGroup(FadeIn(mob.label, shift=0.25 * UP), _fade_number(mob.number, True),
                          run_time=min(run_time, 1.0))


def exit(node: Node, mob: Value) -> Animation:
    return AnimationGroup(FadeOut(mob.label, shift=0.2 * UP), _fade_number(mob.number, False))


def move(old: Value, new: Value) -> Animation:
    # the number follows its label
    return Transform(old.label, new.label)


def _fade(m: Mobject, fade_in: bool, start: float, end: float) -> Animation:
    """Opacity over part of the transition (a live number rebuilds its glyphs every frame)."""
    timing = squish_rate_func(smooth, start, end)   # UpdateFromAlphaFunc ignores rate_func: time it here
    return UpdateFromAlphaFunc(m, lambda x, a: x.set_opacity(timing(a) if fade_in else 1 - timing(a)))


def morph(old: Value, new: Value, sources=None) -> Animation:
    """Same quantity, same label: the label moves and the number follows. Otherwise the old
    readout fades first and the new one after, never two labels blended into each other."""
    if old.bind == new.bind and old.label.text == new.label.text:
        return Transform(old.label, new.label)
    return AnimationGroup(_fade(old.label, False, 0.0, 0.4), _fade(old.number, False, 0.0, 0.4),
                          _fade(new.label, True, 0.45, 1.0), _fade(new.number, True, 0.45, 1.0))


def emphasis_target(kind: str, mob: Value) -> Mobject:
    return mob if kind in ("flash", "circle") else mob.label
