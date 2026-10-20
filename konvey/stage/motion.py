"""In-place motion between two beats for an element that keeps its id but changes content.

The scene used to treat "same id, new content" as exit + re-enter, which made every step of a
worked example look like a slide change. Here the old element turns into the new one instead.
Each display brings its own ``morph`` (``konvey/stage/displays/<name>/mobject.py``): array cells
slide by value, grid cells cross-fade, a system sends packets along its wires, a drawing's
shapes slide or hop, tex is matched symbol by symbol. Displays without one (charts, bars,
plots, tiles) morph part by part. Text is handled here and never shuffled word by word: a
changed number flies out of the cell that shows it, or counts to its new value; subtitles swap
quickly; headings are written on; other labels fade-transform (see ``_text``).

``morph(old, new)`` returns one animation that mutates ``old`` into the look of ``new``; the
caller then swaps ``old`` for ``new`` in the scene.
"""

from __future__ import annotations

import re

from manimlib import *  # noqa: F401,F403

from . import displays
from .displays.base import _parts
from .overlay import KineticText


def morph(old: Mobject, new: Mobject, sources: dict | None = None) -> Animation:
    """``sources`` (``picture_sources``): numbers the picture points at -> the cell showing
    it; a label that changes to that number takes it from there."""
    tag = getattr(new, "tag", None)
    own = displays.hook(tag, "morph") if getattr(old, "tag", None) == tag else None
    if own is not None:
        anim = own(old, new, sources)
        if anim is not None:
            return anim
    if isinstance(old, KineticText) and isinstance(new, KineticText):
        return _text(old, new, sources)
    return _parts(old, new)


def picture_sources(mobs: dict, on_screen: dict) -> dict:
    """Numbers the picture is pointing at -> the cell text showing it, live (the old cell while
    it is still moving there). Only cells that are looked at count (each display's ``sources``:
    under a pointer, a grid's marked cell, an array item that just hopped to a new place). A
    label that changes to one of these numbers takes it from that cell; a coincidental match
    elsewhere does not."""
    out: dict[float, Mobject] = {}
    for i, m in mobs.items():
        looked = displays.hook(getattr(m, "tag", None), "sources")
        for v, live in (looked(m, on_screen.get(i)) if looked else []):
            n = _num(str(v))
            if n is not None:
                out.setdefault(n[1], live)
    return out


_NUM = re.compile(r"^([^\d\-+]*?)([-+]?\d[\d,]*(?:\.\d+)?)(\D*)$")
MAX_COUNT_STEPS = 12
LATE = squish_rate_func(smooth, 0.45, 1.0)   # after the picture has moved: read the new value off it
QUICK = squish_rate_func(smooth, 0.0, 0.18)  # subtitles swap like film subtitles, no travel


def _num(word: str):
    """'1,048,576' -> (prefix, 1048576.0, suffix, decimals, commas); None if not a number."""
    m = _NUM.match(word)
    if not m:
        return None
    pre, digits, post = m.groups()
    dec = len(digits.split(".")[1]) if "." in digits else 0
    return pre, float(digits.replace(",", "")), post, dec, "," in digits


def _text(old: KineticText, new: KineticText, sources: dict | None = None) -> Animation:
    """How 3Blue1Brown changes text, never by shuffling words:
    - a number that is also on screen in the picture (a cell, a bar) flies out of it into the
      label, once the picture has moved (TransformFromCopy);
    - any other changed number counts to its new value; the rest of the label stays still;
    - subtitles swap quickly in place, headings are written on, other labels fade-transform."""
    a, b = old.word_strings, new.word_strings
    # Old and new wording are never on screen together: the old goes first, the picture
    # moves, then the new wording arrives where it will stay.
    if new.tag == "caption":
        return AnimationGroup(FadeOut(old, rate_func=QUICK), FadeIn(new, rate_func=LATE))
    if old.backing is None and new.backing is None and len(a) == len(b):
        diff = [k for k, (u, v) in enumerate(zip(a, b)) if u != v]
        # a number that keeps its prefix and suffix ("6 socks" -> "7 socks"); "6" -> "n+1" is a
        # new word, not the number +1 with an "n" in front
        same_frame = lambda u, v: _num(u) and _num(v) and (_num(u)[0], _num(u)[2]) == (_num(v)[0], _num(v)[2])  # noqa: E731
        if diff and all(same_frame(a[k], b[k]) for k in diff):
            anims = [Transform(old.words[k], new.words[k]) for k in range(len(a)) if k not in diff]
            for k in diff:
                src = (sources or {}).get(_num(b[k])[1])
                if src is not None:
                    anims += [FadeOut(old.words[k], rate_func=QUICK), _fly(src, new.words[k])]
                else:
                    anims += _count(old, new, k, a[k], b[k])
            return AnimationGroup(*anims)
    if new.tag in ("h1", "h2", "h3"):
        return AnimationGroup(FadeOut(old, rate_func=QUICK), Write(new, rate_func=LATE))
    return AnimationGroup(FadeOut(old, rate_func=QUICK),
                          FadeIn(new, shift=0.08 * UP, lag_ratio=0.03, rate_func=LATE))


def _fly(src: Mobject, target: Mobject) -> Animation:
    """A copy of the number leaves the cell (wherever that cell is right now) once the
    picture has mostly moved, and lands in the label, resizing on the way. Invisible before."""
    timing = squish_rate_func(smooth, 0.55, 1.0)

    def upd(m, t):
        a = timing(t)   # UpdateFromAlphaFunc ignores rate_func in manimgl: time it here
        if a <= 0:
            m.set_opacity(0)
            return
        f = target.copy()
        f.scale(interpolate(_height(src) / max(_height(target), 1e-6), 1.0, a))
        f.move_to(interpolate(_center(src), _center(target), a))
        m.become(f)

    return UpdateFromAlphaFunc(target.copy().set_opacity(0), upd, remover=True)


def _center(m: Mobject) -> np.ndarray:
    pts = m.get_all_points()
    return (pts.min(axis=0) + pts.max(axis=0)) / 2 if len(pts) else m.get_center()


def _height(m: Mobject) -> float:
    pts = m.get_all_points()
    return float(np.ptp(pts[:, 1])) if len(pts) else m.get_height()


def _dl(m: Mobject) -> np.ndarray:
    """Down-left corner from the actual points (the cached bounding box lags behind a
    mobject that a running Transform is moving)."""
    pts = m.get_all_points()
    return np.array([pts[:, 0].min(), pts[:, 1].min(), 0.0]) if len(pts) else m.get_corner(DL)


def _count(old: KineticText, new: KineticText, k: int, a: str, b: str) -> list[Animation]:
    """Word k ticks through its values from a to b, in the label's own font and colour. It
    rides along with its neighbouring word, which may still be sliding to its new place."""
    _, va, _, _, _ = _num(a)
    pre, vb, post, dec, commas = _num(b)
    target = new.words[k]
    span = abs(vb - va)
    steps = int(min(MAX_COUNT_STEPS, max(1, span if dec == 0 else MAX_COUNT_STEPS)))
    color = target[0].get_fill_color() if len(target) else WHITE
    ref = Text(b, fill_color=color, **new.style)
    scale = target.get_height() / max(ref.get_height(), 1e-6)
    frames = []
    for n in range(0, steps + 1):   # from the old value, so nothing jumps at the start
        v = va + (vb - va) * n / steps
        body = f"{v:,.{dec}f}" if commas else f"{v:.{dec}f}"
        frames.append(Text(f"{pre}{body}{post}", fill_color=color, **new.style).scale(scale).fix_in_frame())
    # anchor: the word before (or after) this one, as it moves from its old place to its new one
    nb = k - 1 if k > 0 else k + 1
    if not 0 <= nb < len(new.words):
        anchor_old, anchor_new = old.words[k], target
    else:
        anchor_old, anchor_new = old.words[nb], new.words[nb]
    offset = _dl(target) - _dl(anchor_new)
    shown = frames[0].copy()

    def tick(m, t):
        alpha = LATE(t)   # UpdateFromAlphaFunc ignores rate_func in manimgl: time it here
        # place a fresh copy first, then take its points (measuring m after become() reads a
        # stale bounding box and the number drifts across the screen)
        f = frames[min(steps, int(alpha * (steps + 1)))].copy()
        f.shift(_dl(anchor_old) + offset - _dl(f))
        m.become(f)

    old.words[k].set_opacity(0)   # the counter takes over from the first frame
    return [UpdateFromAlphaFunc(shown, tick, remover=True)]


def assemble(node, tex: Mobject, resolve) -> Animation:
    """``<tex from="2: bins>left; 3: hand">``: each listed symbol is a copy of the picture part it
    stands for, flying out of it and turning into the symbol (3b1b's TransformFromCopy); the rest
    of the formula fades in around them as they land. Only copies move: the formula itself stays
    hidden until the end and is then shown whole, so its glyphs are never rebuilt."""
    from .tree import BeatError

    pairs = [p.partition(":") for p in node.attrs["from"].split(";") if p.strip()]
    whole = tex.copy()
    flying, taken = [], set()
    for sym, colon, ref in pairs:
        sym, ref = sym.strip(), ref.strip()
        if not colon or not sym or not ref:
            raise BeatError(f'<tex id={node.id}> from="{node.attrs["from"]}": write "symbol: part; '
                            'symbol: part", e.g. from="2: bins; 3: hand"')
        from .parts import occurrence

        target = occurrence(whole, sym) or VGroup()   # its first occurrence ("sym#2": the second)
        glyphs = target.family_members_with_points()
        if not glyphs:
            raise BeatError(f'<tex id={node.id}> from=: "{sym}" is not in the formula {node.text!r}')
        flying.append((resolve(ref), VGroup(*glyphs).copy()))
        taken |= {id(m) for m in glyphs}
    rest = VGroup(*(m for m in whole.family_members_with_points() if id(m) not in taken)).copy()
    tex.set_opacity(0)
    move = squish_rate_func(smooth, 0.05, 0.7)
    appear = squish_rate_func(smooth, 0.45, 0.8)

    def upd(m, t):
        if t >= 1:
            tex.become(whole)
            m.become(VGroup())
            return
        a = move(t)
        frames = [_faded(rest, appear(t))]
        for src, sym in flying:
            piece = _faded(src, 1 - a)
            piece.scale(interpolate(1.0, _height(sym) / max(_height(piece), 1e-6), a))
            piece.move_to(interpolate(_center(src), _center(sym), a))
            frames += [piece, _faded(sym, a).move_to(piece)]
        m.become(VGroup(*frames))

    return UpdateFromAlphaFunc(VGroup(), upd, remover=True)


def _faded(m: Mobject, k: float) -> Mobject:
    """A copy with every part's opacity scaled by k: parts kept invisible (a backing box, a
    strike line not in use) stay invisible, which ``set_opacity`` would reveal."""
    out = m.copy()
    for sm in out.get_family():
        if sm.has_points():
            for key in ("fill_rgba", "stroke_rgba"):
                if key in sm.data.dtype.names:
                    sm.data[key][:, 3] *= k
    return out
