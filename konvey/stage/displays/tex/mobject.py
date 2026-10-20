"""``<tex>`` (manimgl): typeset with the rewrites manimgl needs. Two formulas that share enough
parts morph symbol by symbol (shared runs slide to their new places, the rest fades out and in
where it stands); unrelated formulas never blend: the old one leaves before the new one comes."""

from __future__ import annotations

from manimlib import *  # noqa: F401,F403

from ...theme import current
from ...tree import Node
from . import tex_safe

RELATED = 0.4        # share of glyphs in shared runs (2+ glyphs) over the larger formula ...
RELATED_SMALL = 0.75  # ... or over the smaller one (a formula that grows by a term)
EARLY = squish_rate_func(smooth, 0.0, 0.4)
LATE = squish_rate_func(smooth, 0.45, 1.0)


def build(node: Node, world=None) -> Mobject:
    tex = node.segments[0][0]
    mob = Tex(tex_safe(tex), font_size=int(node.attrs.get("size", 44)),
              color=current().color(node.attrs.get("color")))
    mob.content = tex
    return mob


def shared_runs(old: Mobject, new: Mobject) -> tuple[list[tuple[Mobject, Mobject]], bool]:
    """manimgl's matching runs of symbols between two formulas, and whether the two are related:
    judged by the glyphs in runs of two or more (single matches such as '=' or 'x' are common to
    any two formulas, so they say nothing)."""
    try:
        blocks = TransformMatchingStrings.matching_blocks(None, old, new, [], {})
    except Exception:  # noqa: BLE001 - a formula manimgl cannot split: treat as unrelated
        return [], False
    glyphs = lambda m: len(m.family_members_with_points())  # noqa: E731
    blocks = [(a, b) for a, b in blocks if glyphs(a) and glyphs(b)]
    n_old, n_new = glyphs(old), glyphs(new)
    if not n_old or not n_new:
        return blocks, False
    multi = sum(glyphs(a) for a, _ in blocks if glyphs(a) >= 2)
    return blocks, multi / max(n_old, n_new) >= RELATED or multi / min(n_old, n_new) >= RELATED_SMALL


def morph(old: Mobject, new: Mobject, sources=None) -> Animation:
    blocks, related = shared_runs(old, new)
    if not related:
        return AnimationGroup(FadeOut(old, rate_func=EARLY), FadeIn(new, shift=0.1 * UP, rate_func=LATE))
    anims, moved_old, moved_new = [], set(), set()
    for a, b in blocks:
        anims.append(Transform(a, b))
        moved_old |= {id(m) for m in a.family_members_with_points()}
        moved_new |= {id(m) for m in b.family_members_with_points()}
    anims += [FadeOut(m, rate_func=EARLY) for m in old.family_members_with_points() if id(m) not in moved_old]
    anims += [FadeIn(m, rate_func=LATE) for m in new.family_members_with_points() if id(m) not in moved_new]
    return AnimationGroup(*anims)
