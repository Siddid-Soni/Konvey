"""``<number>``: a readout, the value large and its label under it (manimgl). A new value never
morphs glyph into glyph: a number with the same unit counts to its new value, anything else
slides out upwards while the new value slides in from below; an unchanged label stays put."""

from __future__ import annotations

from manimlib import *  # noqa: F401,F403

from ...tree import BeatError, Node
from ...theme import current
from ..base import _label, Block

MAX_STEPS = 12                                   # frames a count runs through at most
EARLY = squish_rate_func(smooth, 0.0, 0.45)      # the old value leaves first ...
LATE = squish_rate_func(smooth, 0.4, 1.0)        # ... the new one arrives after it


class NumberBlock(Block):
    """``<number value="13" label="moves">``: a readout, the value large with its label under it
    (the plan's `number` kind)."""

    tag = "number"

    def __init__(self, node: Node):
        th = current()
        value = node.attrs.get("value", "").strip()
        if not value:
            raise BeatError(f'<number id={node.id}> needs value="…"')
        size = self.size = float(node.attrs.get("size", 56))
        unit = node.attrs.get("unit", "").strip()
        self.text = value + (f" {unit}" if unit else "")
        self.color = th.color(node.attrs.get("color"), "ink")
        self.value = _label(self.text, size, self.color)
        parts = [self.value]
        self.label = None
        self.label_text = node.attrs.get("label", "").strip()
        if self.label_text:
            self.label = _label(self.label_text, 0.45 * size, th.muted).next_to(self.value, DOWN, buff=0.12)
            parts.append(self.label)
        super().__init__(*parts)
        self.set_content(node, "value", "label", "unit")


def build(node: Node, world=None) -> NumberBlock:
    return NumberBlock(node)


def _count(old: NumberBlock, new: NumberBlock, a, b) -> Animation:
    """The value ticks from the old number to the new one in place (riding along if the readout
    moves), in the readout's own font; the last frame is the new value exactly."""
    pre, va, post, dec_a, commas = a
    _, vb, _, dec_b, commas_b = b
    dec, fmt = max(dec_a, dec_b), ("," if commas or commas_b else "")
    steps = int(min(MAX_STEPS, max(1, abs(vb - va) if dec == 0 else MAX_STEPS)))
    frames = [_label(f"{pre}{va + (vb - va) * k / steps:{fmt}.{dec}f}{post}" if k < steps else new.text,
                     new.size, new.color) for k in range(steps + 1)]
    ref = frames[-1].get_height() or 1.0
    h0, h1 = old.value.get_height() / ref, new.value.get_height() / ref
    c0, c1 = old.value.get_center(), new.value.get_center()
    shown = frames[0].copy().fix_in_frame()

    def tick(m, t):
        t = smooth(t)   # UpdateFromAlphaFunc ignores rate_func in manimgl: time it here
        f = frames[min(steps, int(t * (steps + 1)))].copy().fix_in_frame()
        f.scale(interpolate(h0, h1, t)).move_to(interpolate(c0, c1, t))
        m.become(f)

    old.value.set_opacity(0)   # the counter takes over from the first frame
    return UpdateFromAlphaFunc(shown, tick, remover=True)


def _parse(text: str):
    """'45 deg' -> ('', 45.0, ' deg', 0, False); None if not a number (see motion._num)."""
    from ...motion import _num   # manimgl side, like this module

    return _num(text)


def morph(old: NumberBlock, new: NumberBlock, sources=None) -> Animation:
    anims = []
    if old.text == new.text:
        anims.append(Transform(old.value, new.value))
    else:
        a, b = _parse(old.text), _parse(new.text)
        if a and b and (a[0], a[2]) == (b[0], b[2]):
            anims.append(_count(old, new, a, b))
        else:   # a different kind of value: out upwards, then the new one in from below
            d = 0.6 * max(old.value.get_height(), new.value.get_height()) * UP
            anims += [FadeOut(old.value, shift=d, rate_func=EARLY), FadeIn(new.value, shift=d, rate_func=LATE)]
    if old.label is not None and new.label is not None and old.label_text == new.label_text:
        anims.append(Transform(old.label, new.label))
    else:
        anims += [FadeOut(m, rate_func=EARLY) for m in (old.label,) if m is not None]
        anims += [FadeIn(m, rate_func=LATE) for m in (new.label,) if m is not None]
    return AnimationGroup(*anims)
