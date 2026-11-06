"""``<tex>`` (manimgl): typeset with the rewrites manimgl needs. Two formulas that share enough
parts morph symbol by symbol (shared runs slide to their new places, the rest fades out and in
where it stands); unrelated formulas never blend: the old one leaves before the new one comes.

``follow="plot id"`` with stages between ``||`` (``P = 1 || P = 1 + x || P = 1 + x + x^2``):
the formula changes on the same beats as that plot's steps, while the line is spoken (3b1b's
formula gains its term as the curve bends). ``paint="P: accent; \\cos x: c1"`` colours those
parts, so a term wears its curve's colour."""

from __future__ import annotations

from manimlib import *  # noqa: F401,F403

from ...theme import current
from ...tree import BeatError, Node
from . import tex_safe

RELATED = 0.4        # share of glyphs in shared runs (2+ glyphs) over the larger formula ...
RELATED_SMALL = 0.75  # ... or over the smaller one (a formula that grows by a term)
EARLY = squish_rate_func(smooth, 0.0, 0.4)
LATE = squish_rate_func(smooth, 0.45, 1.0)


def stages(node: Node) -> list[str]:
    tex = node.segments[0][0]
    if not node.attrs.get("follow", "").strip():
        return [tex]
    # "\|\|" is how the docs' markdown tables spell the separator, and models copy it as it is written
    return [t.strip() for t in tex.replace(r"\|\|", "||").split("||") if t.strip()] or [tex]


def paint(node: Node) -> dict[str, str]:
    """``paint="P(x): accent; \\cos x: c1"`` -> {tex: colour}."""
    th, out = current(), {}
    for part in (p.strip() for p in node.attrs.get("paint", "").split(";") if p.strip()):
        key, sep, col = part.rpartition(":")
        if not sep or not key.strip():
            raise BeatError(f'<tex id={node.id}> paint="{node.attrs["paint"]}": use "part: colour; part: colour"')
        try:
            out[key.strip()] = th.color(col.strip())
        except ValueError as e:
            raise BeatError(f"<tex id={node.id}> paint: {e}") from e
    return out


def _typeset(node: Node, tex: str) -> Mobject:
    colors = paint(node)
    mob = Tex(tex_safe(tex), font_size=int(node.attrs.get("size", 44)),
              color=current().color(node.attrs.get("color")),
              t2c={k: v for k, v in colors.items() if k in tex})
    mob.content = tex
    return mob


def build(node: Node, world=None) -> Mobject:
    st = stages(node)
    mob = _typeset(node, st[0])
    if len(st) > 1:   # the layout keeps room for the longest stage; it starts at the room's left
        sizes = [(m.get_width(), m.get_height()) for m in (_typeset(node, t) for t in st[1:])]
        mob.room = (max([mob.get_width(), *(w for w, _ in sizes)]), max([mob.get_height(), *(h for _, h in sizes)]))
        mob.room_h0 = mob.get_height()
    return mob


def live(node: Node, mob: Mobject, hold: float, nodes: dict) -> Animation | None:
    """The formula's stages on the beats of the plot it follows (``plot.mobject.schedule``)."""
    from ..plot.mobject import schedule, steps_of

    st = stages(node)
    target = nodes.get(node.attrs.get("follow", "").strip().lstrip("#"))
    if len(st) < 2 or getattr(mob, "played", False):
        return None
    mob.played = True
    try:
        steps, slide = steps_of(target.attrs) if target is not None and target.tag == "plot" else (len(st) - 1, False)
    except BeatError:
        steps, slide = len(st) - 1, False
    if steps == 0:   # the plot has no steps this beat: the formula steps through on its own
        steps, slide = len(st) - 1, False
    times, _ = schedule(steps, slide, hold)
    times = times[:len(st) - 1]
    if not times:
        return None
    k = mob.get_height() / max(getattr(mob, "room_h0", mob.get_height()), 1e-6)
    left, y = mob.get_left()[0], mob.get_center()[1]

    def placed(tex: str) -> Mobject:
        m = _typeset(node, tex).scale(k)
        m.move_to([left + m.get_width() / 2, y, 0])
        m.fix_in_frame()
        return m

    shown = [placed(t) for t in st[:len(times) + 1]]
    segs = [(t0, t1, morph(a, b)) for (t0, t1), a, b in zip(times, shown, shown[1:])]
    final = placed(st[len(times)])
    holder = Group()
    state = {"seg": -1}

    def update(_m, alpha: float) -> None:
        t = alpha * hold
        if state["seg"] == -1:
            mob.set_opacity(0)
            holder.set_submobjects([shown[0]])
            state["seg"] = 0
        n = max((i for i, s in enumerate(segs) if s[0] <= t + 1e-9), default=-1)
        if n < 0:
            return
        t0, t1, anim = segs[n]
        if state.get("begun") != n:   # finish the step before, start this one
            if state.get("begun") is not None:
                segs[state["begun"]][2].finish()
            anim.begin()
            state["begun"] = n
            holder.set_submobjects([a.mobject for a in anim.animations])
        anim.interpolate(float(np.clip((t - t0) / max(t1 - t0, 1e-6), 0, 1)))
        if alpha >= 1 - 1e-9:   # the formula on screen is now the last stage, for the beats after
            anim.finish()
            # take the last stage's glyphs and string data, but keep this object's own family and
            # parents: a copied family cache would name the other object, and the scene could
            # then never remove this one (its glyphs stayed on screen beats later)
            subs = list(final.submobjects)
            mob.__dict__.update({k: v for k, v in final.__dict__.items()
                                 if k not in ("family", "parents", "submobjects", "played", "room", "room_h0")})
            mob.set_submobjects(subs)
            holder.set_submobjects([])

    return UpdateFromAlphaFunc(holder, update, run_time=hold, rate_func=linear, remover=True)


live.wants_beat = True


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
        # a run of old glyphs is its own group on screen while it moves; it leaves when the move
        # ends (the new formula takes its place), or it stays drawn after the formula is gone
        anims.append(Transform(a, b, remover=True))
        moved_old |= {id(m) for m in a.family_members_with_points()}
        moved_new |= {id(m) for m in b.family_members_with_points()}
    anims += [FadeOut(m, rate_func=EARLY) for m in old.family_members_with_points() if id(m) not in moved_old]
    anims += [FadeIn(m, rate_func=LATE) for m in new.family_members_with_points() if id(m) not in moved_new]
    return AnimationGroup(*anims)
