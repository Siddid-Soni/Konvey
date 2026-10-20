"""Named animations for overlay leaves: ``enter=``, ``exit=`` and ``emphasize=`` (manimgl).

Each name is one decorated function; adding an animation is adding one here::

    @enter("spin")
    def _spin(mob, run_time):
        return SpinInFromNothing(mob, run_time=run_time)

A function may return None when it does not apply to that mobject (``kinetic`` on a chart); the
leaf then fades. A display can override the whole choice with ``enter``/``exit`` hooks in its
``mobject.py`` (a live ``<value>`` fades its number by opacity), and picks its default with
``Display(enter=...)``. Changes of content between beats are not here: see ``motion.py``.
"""

from __future__ import annotations

from typing import Callable

from manimlib import *  # noqa: F401,F403

from . import displays
from . import theme as themes
from .overlay import KineticText

ENTERS: dict[str, Callable] = {}
EXITS: dict[str, Callable] = {}
EMPHASES: dict[str, Callable] = {}


def _register(table: dict, name: str):
    def deco(fn):
        table[name] = fn
        return fn
    return deco


def enter(name: str):
    return _register(ENTERS, name)


def exit_(name: str):
    return _register(EXITS, name)


def emphasis(name: str):
    return _register(EMPHASES, name)


# --- kinetic typography ----------------------------------------------------
def kinetic_in(mob: KineticText, run_time: float) -> Animation:
    anims = []
    for word, s in zip(mob.words, mob.word_strings):
        hot = s.strip(".,?!:;—") in mob.emph_words
        anims.append(Succession(
            FadeIn(word, shift=0.35 * UP, scale=1.6 if hot else 1.25, run_time=0.5),
            *( [Indicate(word, scale_factor=1.15, color=themes.current().accent, run_time=0.4)] if hot else []),
        ))
    words = LaggedStart(*anims, lag_ratio=min(0.35, 2.5 / max(len(anims), 1)), run_time=run_time)
    if mob.backing is None:
        return words
    return AnimationGroup(FadeIn(mob.backing, run_time=0.4), words, run_time=run_time)


def kinetic_out(mob: KineticText) -> Animation:
    words = LaggedStart(*(FadeOut(w, shift=0.4 * UP, scale=0.8) for w in mob.words),
                        lag_ratio=0.05, run_time=0.6)
    if mob.backing is None:
        return words
    return AnimationGroup(words, FadeOut(mob.backing), run_time=0.6)


# --- enter ------------------------------------------------------------------
@enter("kinetic")
def _kinetic(mob, run_time):
    return kinetic_in(mob, run_time) if isinstance(mob, KineticText) else None


@enter("create")
def _create(mob, run_time):
    if not hasattr(mob, "lines"):
        return None
    # Axes fade in, then each series is drawn left to right.
    rest = [m for m in mob.submobjects if m is not mob.lines]
    # AnimationGroup (not Succession) begins both at once, so the lines start hidden.
    return AnimationGroup(FadeIn(Group(*rest), run_time=0.5),
                          ShowCreation(mob.lines, lag_ratio=0.15, run_time=max(0.8, run_time - 0.5)),
                          lag_ratio=0.4)


@enter("write")
def _write(mob, run_time):
    return Write(mob, run_time=run_time)


@enter("grow")
def _grow(mob, run_time):
    return GrowFromCenter(mob, run_time=run_time)


@enter("draw")
def _draw(mob, run_time):
    return DrawBorderThenFill(mob, run_time=run_time)


@enter("fade")
def _fade_in(mob, run_time):
    return FadeIn(mob, shift=0.25 * UP, run_time=run_time)


# --- exit -------------------------------------------------------------------
@exit_("kinetic")
def _kinetic_out(mob):
    return kinetic_out(mob) if isinstance(mob, KineticText) else None


@exit_("shrink")
def _shrink(mob):
    return ShrinkToCenter(mob, run_time=0.5)


@exit_("fade")
def _fade_out(mob):
    return FadeOut(mob, shift=0.2 * UP, run_time=0.5)


# --- emphasis (played once, after the beat's transition) ----------------------------
# Overlay leaves are fixed in frame, so the rectangles around them must be too
# (otherwise a 3D camera moves them away from what they surround).
@emphasis("flash")
def _flash(mob):
    anim = FlashAround(mob, color=themes.current().accent, time_width=0.6, run_time=1.2)
    anim.mobject.fix_in_frame()
    return anim


@emphasis("circle")
def _circle(mob):
    rect = SurroundingRectangle(mob, buff=0.15).set_stroke(themes.current().accent, 3).fix_in_frame()
    return ShowCreationThenFadeOut(rect, run_time=1.4)


@emphasis("indicate")
def _indicate(mob):
    return Indicate(mob, color=themes.current().accent, scale_factor=1.12)


# --- what the scene calls ---------------------------------------------------------
def _default(node) -> str:
    d = displays.get(node.tag)
    return (d.enter if d and d.enter else None) or ("kinetic" if node.tag not in displays.tags() else "fade")


def enter_anim(node, mob, run_time) -> Animation:
    own = displays.hook(node.tag, "enter")
    if own is not None:
        return own(node, mob, run_time)
    fn = ENTERS.get(node.attrs.get("enter") or _default(node))
    return (fn(mob, run_time) if fn else None) or _fade_in(mob, run_time)


def exit_anim(node, mob) -> Animation:
    own = displays.hook(node.tag, "exit")
    if own is not None:
        return own(node, mob)
    fn = EXITS.get(node.attrs.get("exit", "kinetic" if isinstance(mob, KineticText) else "fade"))
    return (fn(mob) if fn else None) or _fade_out(mob)


def emphasize_anim(kind: str, mob, tag: str | None = None) -> Animation:
    target = displays.hook(tag, "emphasis_target")
    if target is not None:
        mob = target(kind, mob)
    return EMPHASES.get(kind, _indicate)(mob)
