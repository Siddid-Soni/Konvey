"""StageScene: plays a beat file (spec §6.6–6.7).

Per beat:
  1. transition  — exits, then moves/morphs + world/camera interpolation + enters
  2. hold        — camera drift, world actions (tumble), emphasis, displays' ``live`` motion

Beat attributes: ``t`` (transition seconds), ``hold`` (seconds),
``transition="wipe"``, ``letterbox="open|close"``, ``drift`` (deg of orbit
during hold). Leaf attributes: ``enter``, ``exit``, ``emphasize``.
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import numpy as np

from manimlib import *  # noqa: F401,F403

from . import displays, layout, motion, view
from . import theme as themes
from .animations import emphasize_anim, enter_anim, exit_anim
from .attach import attached, place, resolve
from .audit import audit_beat
from .overlay import build_card, build_leaf, fit
from .parse import LEAF_TAGS, Beat, BeatError, parse_beats, prepare_beats
from .world import (CameraState, World, WorldState, apply_camera, lerp_camera, lerp_state, world_exits,
                    shadow_area, tumble_rotations)
from scipy.spatial.transform import Rotation, Slerp

WORDS_PER_SEC = 2.7   # narration pace used to size beats that give no hold=
from .marks import BAR_OPEN   # letterbox bar height once open (units)  # noqa: E402


def _reshaped(n, mob, box, world):
    """An axes picture whose box the layout gave other proportions (spare room above or beside
    it) is rebuilt at those proportions instead of being scaled to fit inside them."""
    w, h = mob.get_width(), mob.get_height()
    if min(w, h) < 1e-6 or abs((box.w / box.h) / (w / h) - 1) < 0.03:
        return mob
    try:   # its drawing size; without w/h, what it was built at (labels included: close enough)
        aw, ah = float(n.attrs.get("w") or w), float(n.attrs.get("h") or h)
    except ValueError:
        return mob
    k = (box.w / w) / (box.h / h)    # how much wider, relative to taller, the box is
    attrs = dict(n.attrs)
    n.attrs["w"], n.attrs["h"] = f"{aw * max(k, 1.0):.4g}", f"{ah * max(1 / k, 1.0):.4g}"
    try:
        return build_leaf(n, world)
    except Exception:   # noqa: BLE001 - the picture at its own proportions is still right
        n.attrs.clear()
        n.attrs.update(attrs)
        return mob


def _redrawn(n, mob, box, world, grow: bool):
    """A picture drawn to a size (``layout.REDRAW``) is rebuilt at the size the layout gives it
    instead of being scaled there, so its numbers, names and line widths keep their size as it
    grows (3b1b sizes the axes, never the text)."""
    view = getattr(mob, "view", None)
    if view is None:
        return mob
    k = min(box.w / max(mob.get_width(), 1e-6), box.h / max(mob.get_height(), 1e-6))
    if (abs(k - 1) < 0.02 and not grow) or (k > 1 and not grow):
        return mob
    attrs = dict(n.attrs)
    if grow:   # alone in its room: it takes the whole box, its axes running to the edges
        n.attrs["w"], n.attrs["h"], n.attrs["_fill"] = f"{box.w:.4g}", f"{box.h:.4g}", "1"
    else:
        n.attrs["w"], n.attrs["h"] = f"{view.get_width() * k:.4g}", f"{view.get_height() * k:.4g}"
    try:
        return build_leaf(n, world)
    except Exception:   # noqa: BLE001 - scaled is still right, only its text grows
        n.attrs.clear()
        n.attrs.update(attrs)
        return mob


def _settle_points(beats: list[Beat]) -> None:
    """Replay a scene's point positions (``at`` and descents) and write where each
    point ends up into the last beat, which is shown on its own as the next scene's
    opening frame."""
    from .field import FieldWorld

    field_ = FieldWorld(beats)
    state = None
    for b in beats:
        state = field_.state_from(b.world, state)
        for i, n in b.world.items():
            if n.tag == "point" and "descend" in n.attrs and state.get(i):
                state[i]["xy"] = field_.descent_path(n, state[i]["xy"])[-1]
    for i, n in beats[-1].world.items():
        if n.tag == "point" and state and state.get(i):
            x, y = state[i]["xy"]
            n.attrs["at"] = f"{x:.6g},{y:.6g}"
            n.attrs.pop("descend", None)
            n.attrs.pop("steps", None)


def _empty_boxes(b: Beat) -> list[str]:
    """Ids of the beat's empty containers (the boxes left free for the 3D view)."""
    out = []

    def walk(nodes):
        for n in nodes:
            if n.tag in ("div", "section"):
                if not n.children and n.id:
                    out.append(n.id)
                walk(n.children)
    walk(b.overlay)
    return out


def _adopt_ids(prev: Beat, first: Beat) -> None:
    """Scenes are written independently, so the same surface may be ``valley`` in S1
    and ``bowl`` in S2. Rename the previous scene's world actors to this scene's ids,
    matched by tag in order, so the scene change morphs one object instead of
    crossfading two."""
    def kind(n):   # a solid is only the same thing if it has the same shape
        if n.tag == "solid" and n.attrs.get("shape") == "hull":
            # a hull keeps its corner count, so only a hull with as many corners can take its id
            from .solids import hull_points
            try:
                return (n.tag, "hull", len(hull_points(n)))
            except BeatError:
                return (n.tag, "hull", None)
        if n.tag == "diagram":   # only the same figure: another tree is another picture
            from .diagram3d import Diagram
            return (n.tag, Diagram._sig(n))
        return (n.tag, n.attrs.get("shape", "box")) if n.tag == "solid" else (n.tag,)

    rename = {}
    for k in {kind(n) for n in prev.world.values() if n.id}:
        old = [n.id for n in prev.world.values() if kind(n) == k and n.id]
        new = [n.id for n in first.world.values() if kind(n) == k and n.id]
        rename.update({o: n for o, n in zip(old, new)})
    world = {}
    for key, n in prev.world.items():
        for attr in ("id", "on", "of", "from", "to", "at"):   # ends may name a solid
            if n.attrs.get(attr) in rename:
                n.attrs[attr] = rename[n.attrs[attr]]
        world[n.attrs.get("id") or key] = n
    prev.world = world
    if prev.camera.get("show"):
        prev.camera["show"] = ",".join(rename.get(x.strip(), x.strip())
                                       for x in prev.camera["show"].split(","))
    for d in displays.all_displays():   # overlay displays that carry over (one system each side)
        if d.adopt is not None:
            d.adopt(prev, first)
    for leaf in prev.leaves().values():   # readouts bound to a renamed actor follow it
        actor, _, field_ = leaf.attrs.get("bind", "").partition(".")
        if actor in rename:
            leaf.attrs["bind"] = f"{rename[actor]}.{field_}"


_PRELUDE = re.compile(r'prelude_file = str\(Path\(__file__\)\.with_name\("([^"]+)"\)\)')


def scene_beats(html: Path, depth: int = 0) -> list[Beat]:
    """A scene's beats as its own render prepared them: opened on the previous scene's last beat
    (found through the scene's wrapper next to it), itself as that scene rendered it. A look
    carried over several cuts (a drawing's frame, a system's size) so stays the same at each
    cut; the opening beat is dropped again."""
    beats = parse_beats(html.read_text())
    prepare_beats(beats, strict=False)
    wrapper = html.with_suffix(".py")
    m = _PRELUDE.search(wrapper.read_text()) if wrapper.exists() and depth < 32 else None
    prev = html.with_name(m.group(1)) if m else None
    if prev is None or not prev.exists():
        return beats
    last = scene_beats(prev, depth + 1)[-1]
    _adopt_ids(last, beats[0])
    prepare_beats([last, *beats], strict=False)
    return beats


def _covers(a: Mobject, b: Mobject) -> bool:
    """a (where it is now) overlaps b's place on the page."""
    if not a.get_family() or not b.get_family():
        return False
    (ax0, ay0, _), (ax1, ay1, _) = a.get_corner(DL), a.get_corner(UR)
    (bx0, by0, _), (bx1, by1, _) = b.get_corner(DL), b.get_corner(UR)
    return ax0 < bx1 - 0.05 and bx0 < ax1 - 0.05 and ay0 < by1 - 0.05 and by0 < ay1 - 0.05


def beat_hold(b: Beat) -> float:
    """Seconds to hold after the transition: explicit ``hold``, else long enough to read the VO."""
    if "hold" in b.attrs:
        return float(b.attrs["hold"])
    words = len(b.attrs.get("vo", "").split())
    return max(1.5, words / WORDS_PER_SEC - float(b.attrs.get("t", 1.6)))


class StageScene(Scene):
    beats_file: str = ""
    strict_layout: bool = False   # konvey.stage.check sets True: overflow is an error there
    prelude_file: str = ""        # previous scene's beats; its last beat is shown instantly first
    theme: str = themes.DEFAULT   # see konvey.stage.theme; the wrapper records it per run
    highlight: str = ""           # the video's highlight colour (theme.use); "" = the accent
    # 4x multisampling, as manimgl's ThreeDScene: without it thin lines in 3D (depth-tested, so
    # not smoothed by the 2D stroke shader) come out stair-stepped and shimmer as they move
    samples = 4

    def __init__(self, *args, **kwargs):
        th = themes.use(self.theme, self.highlight)
        self.default_camera_config = {**self.default_camera_config, "background_color": th.bg}
        super().__init__(*args, **kwargs)

    def setup(self):
        super().setup()
        src = (Path(self.beats_file)).read_text()
        self.beats = parse_beats(src)
        prepare_beats(self.beats, strict=False)
        # Continuity between scenes: open on the previous scene's final frame.
        self.has_prelude = bool(self.prelude_file) and Path(self.prelude_file).exists()
        if self.has_prelude:
            prelude = scene_beats(Path(self.prelude_file))
            last = prelude[-1]
            last.attrs.pop("letterbox", None)
            _settle_points(prelude)
            _adopt_ids(last, self.beats[0])
            self.beats = [last, *self.beats]
            for i, b in enumerate(self.beats):
                b.index = i
        # the scene's own beats may not change a system's look, nor the previous scene's (an
        # error only while checking; a render always draws, with the first look)
        prepare_beats(self.beats, strict=self.strict_layout)
        self.world = World(self.beats)
        self.world.field.frame = self.camera.frame   # label3d projects through the camera

    def update_frame(self, dt: float = 0, force_draw: bool = False) -> None:
        self.world.field.refresh_view()
        self._steady_overlay()
        super().update_frame(dt, force_draw)

    def _steady_overlay(self) -> None:
        """manimgl widens strokes by the frame's scale and anti-aliases over ``pixel_size``
        (frame width / pixels), fixed-in-frame or not. When the 3D camera zooms out, overlay
        text and charts turned thick and blurry; keep both constant in screen units."""
        scale = self.camera.frame.get_scale()
        for m in self.get_mobject_family_members():
            u = getattr(m, "uniforms", None)
            if u is None or not u.get("is_fixed_in_frame") or "anti_alias_width" not in u:
                continue
            base = m.__dict__.setdefault("_konvey_aaw", float(u["anti_alias_width"]))
            m.uniforms["anti_alias_width"] = base / scale
            m.uniforms["scale_stroke_with_zoom"] = 1.0

    # --- layout ------------------------------------------------------------
    def _layout(self) -> tuple[list[dict], list[dict]]:
        """Build every leaf at natural size, solve the page, fit into boxes."""
        built, sizes = [], {}
        self.views = []   # each beat's 2D camera (centre, zoom), to know when it moves
        for b in self.beats:
            mobs = {}
            for i, n in b.leaves().items():
                if n.tag not in LEAF_TAGS:
                    continue
                try:
                    mobs[i] = build_leaf(n, self.world)
                except Exception as e:  # noqa: BLE001 - name the element for Agent 3
                    msg = str(e).strip().replace("\n", " ")
                    raise BeatError(f"beat {b.index} <{n.tag} id={i}>: {type(e).__name__}: {msg}") from e
            built.append(mobs)
            # an element that grows while the line is spoken (a formula gaining terms) asks for its largest size
            sizes[b.index] = {i: getattr(m, "room", None) or (m.get_width(), m.get_height()) for i, m in mobs.items()}
        boxes = layout.solve(self.beats, sizes, strict=self.strict_layout,
                             dump=str(Path(self.beats_file).with_suffix(".layout.html")))
        for b, mobs, bx in zip(self.beats, built, boxes):
            nodes = b.leaves()
            for i, n in nodes.items():
                if n.tag not in LEAF_TAGS:
                    mobs[i] = build_card(n, bx[i])
                elif not attached(n):
                    if n.tag in layout.STRETCH:
                        mobs[i] = _reshaped(n, mobs[i], bx[i], self.world)
                    if n.tag in layout.REDRAW:
                        mobs[i] = _redrawn(n, mobs[i], bx[i], self.world, layout.growable(n) or n.tag in layout.WIDE)
                    fit(mobs[i], bx[i], grow=layout.growable(n))
                    if getattr(mobs[i], "room", None):   # it starts at the left of the room it will fill
                        k = mobs[i].get_height() / max(mobs[i].room_h0, 1e-6)
                        mobs[i].shift(RIGHT * (bx[i].x - mobs[i].room[0] * k / 2 - mobs[i].get_left()[0]))
            place(nodes, mobs, strict=self.strict_layout)   # against the parts they name, now that those are placed
            bars_h = BAR_OPEN if themes.current().letterbox else 0.0
            try:
                view.apply_focus(b.attrs, nodes, mobs, b.index)
                c, z = view.camera(b, nodes, mobs, bars_h)
            except BeatError:
                if self.strict_layout:   # the check names it; a render keeps the beat, unframed
                    raise
                for k in ("view", "zoom", "focus"):
                    b.attrs.pop(k, None)
                c, z = view.camera(b, nodes, mobs, bars_h)
            self.views.append((tuple(np.round(c, 4)), round(z, 4)))
            view.apply_camera(b.attrs, nodes, mobs, c, z)
            view.hide_cut(b, nodes, mobs, bars_h)
            for m in mobs.values():
                m.fix_in_frame()
        return built, boxes

    # --- main loop ---------------------------------------------------------------
    def construct(self):
        built, boxes = self._layout()
        frame = self.camera.frame
        self.add(self.world.group)
        letterbox = themes.current().letterbox
        bars = VGroup()   # themes without letterbox ignore letterbox= on beats
        if letterbox:
            # Bars start closed (black) only when the first beat opens them; otherwise open.
            opening = self.beats[0].attrs.get("letterbox") == "open"
            bar_h = FRAME_HEIGHT / 2 if opening else BAR_OPEN
            bars = VGroup(*(Rectangle(FRAME_WIDTH + 1, bar_h, fill_color=BLACK,
                                      fill_opacity=1, stroke_width=0) for _ in range(2)))
            bars[0].move_to(UP * (FRAME_HEIGHT / 2 - bar_h / 2))
            bars[1].move_to(DOWN * (FRAME_HEIGHT / 2 - bar_h / 2))
            bars.fix_in_frame()
            self.add(bars)

        self.frame_problems: list[str] = []
        on_screen: dict[str, Mobject] = {}
        prev_nodes: dict = {}
        wstate, cstate = None, None
        for b, mobs, bx in zip(self.beats, built, boxes):
            nodes = b.leaves()
            new_w = WorldState.from_beat(b.world, wstate, self.world.field)
            focus_ok = "focus" in b.camera or not b.world
            if not focus_ok:
                # no focus=: frame the world in the beat's one empty box, as it was surely meant
                empty = _empty_boxes(b)
                if len(empty) == 1:
                    b.camera["focus"], focus_ok = empty[0], True
            show_ids = [x.strip() for x in b.camera.get("show", "").split(",") if x.strip()]
            shown = self.world.shown(show_ids, new_w, b.world) if show_ids else None
            new_c = CameraState.from_beat(b.camera, bx, cstate, self.world.extent(new_w), shown=shown)
            if "zoom" not in b.camera:
                self._true_fit(new_c, self.world.extent(new_w), b, bx)
                new_c.zoom *= float(b.camera.get("push", 1.0))   # closer than the fit, same centre
                if cstate is not None:   # measuring moved the camera; exits play from the old view
                    apply_camera(frame, cstate)
            # world actors that run during the line (a traced path, a sweeping plane) keep running
            # through the transition at the same speed: the transition takes its share of this
            # beat's stretch, the hold the rest (they used to stand still between beats)
            T_beat = float(b.attrs.get("t", 1.6)) + 0.4
            running = {}   # id -> (key, from, to): this beat's stretch of each running actor
            for i, actor in self.world.field.actors.items():
                keys = getattr(actor, "LIVE", None)
                st = new_w.fields.get(i) if keys else None
                if st and wstate is not None and (wstate.fields.get(i) or {}).get("show", 0) > 0:
                    v0, v1 = st[keys[0]], st[keys[1]]
                    running[i] = (keys[0], v0, v1)
                    st[keys[0]] = v0 + (v1 - v0) * T_beat / (T_beat + beat_hold(b))
            w0 = wstate or replace(new_w, show={}, fields={
                k: ({**v, "show": 0.0} if v else v) for k, v in new_w.fields.items()})
            c0 = cstate or new_c
            T = float(b.attrs.get("t", 1.6))

            if self.has_prelude and b.index == 0:
                # Previous scene's end state, shown as-is (no animation, no hold).
                cube = b.world.get("cube")
                if cube is not None and "tumble" in cube.attrs:
                    new_w.rot = tumble_rotations(int(cube.attrs.get("seed", 7)),
                                                 int(cube.attrs.get("samples", 5000)))[int(cube.attrs["tumble"]) - 1]
                for i, actor in self.world.field.actors.items():   # where that scene's hold left them
                    keys = getattr(actor, "LIVE", None)
                    st = new_w.fields.get(i) if keys else None
                    if st:
                        st[keys[0]] = st[keys[1]]
                self.world.apply(new_w)
                apply_camera(frame, new_c)
                self.add(*mobs.values())
                on_screen, prev_nodes = dict(mobs), nodes
                wstate, cstate = new_w, new_c
                self.bring_to_front(*on_screen.values(), bars)
                continue

            if b.attrs.get("transition") == "wipe":
                self._wipe(on_screen, mobs, w0, new_w, new_c)
                on_screen = dict(mobs)
            else:
                # same id + same content: move/resize. Same id + same tag, new content: it turns
                # into the new one in place (motion.morph: cells slide, words stay, lines
                # reshape). Only what is gone, or became a different kind of thing, leaves.
                same = {i for i in nodes if i in on_screen
                        and getattr(on_screen[i], "content", None) == getattr(mobs[i], "content", None)}
                morph = {i for i, n in nodes.items() if i in on_screen and i not in same
                         and prev_nodes[i].tag == n.tag}
                gone = [i for i in on_screen if i not in same | morph]
                exits = [exit_anim(prev_nodes[i], on_screen[i]) for i in gone]
                # 3D actors that leave fade out with the overlay exits, before anything new
                # enters, so a new chart never draws on top of a fading sphere.
                w_exit = world_exits(w0, new_w)
                if w_exit is not None:
                    exits.append(UpdateFromAlphaFunc(
                        Mobject(), lambda _m, a, w0=w0, w1=w_exit: self.world.apply(
                            lerp_state(w0, w1, smooth(a))), run_time=0.7))
                    w0 = w_exit
                if exits and running:
                    # what leaves goes first; the running actors keep going meanwhile (an exit
                    # used to freeze a traced path for a moment)
                    exit_s = 1.0
                    total = exit_s + T_beat + beat_hold(b)
                    marks = {}
                    for i, (key, v0, v1) in running.items():
                        ve = v0 + (v1 - v0) * exit_s / total
                        marks[i] = (key, v0, ve)
                        new_w.fields[i][key] = ve + (v1 - ve) * T_beat / (T_beat + beat_hold(b))

                    def advance(_m, a, base=w0, marks=marks):
                        fields = {k: (dict(v) if v else v) for k, v in base.fields.items()}
                        for i, (key, v0, ve) in marks.items():
                            fields[i][key] = v0 + (ve - v0) * a
                        self.world.apply(replace(base, fields=fields))

                    exits.append(UpdateFromAlphaFunc(Mobject(), advance, run_time=exit_s, rate_func=linear))
                    w0 = replace(w0, fields={k: (dict(v) if v else v) for k, v in w0.fields.items()})
                    for i, (key, v0, ve) in marks.items():
                        w0.fields[i][key] = ve
                # a clean cut (everything leaves, no 3D actor goes): the old picture fades while the
                # new one comes in, instead of an empty screen between the two
                clean = bool(exits) and not (same | morph) and w_exit is None and not running
                if exits and not clean:
                    self.play(*exits)
                    self.remove(*(on_screen[i] for i in gone))
                fades = []
                for a in exits if clean else ():
                    a.rate_func = squish_rate_func(a.rate_func, 0.0, 0.5)
                    fades.append(a)
                moves, enters = [], []
                for i in same:
                    move = displays.hook(nodes[i].tag, "move") or Transform
                    moves.append(move(on_screen[i], mobs[i]))
                sources = motion.picture_sources(mobs, on_screen)
                for d in displays.all_displays():   # what a display's morphs share in this beat
                    shared = displays.hook(d.tag, "beat_sources")
                    if shared is not None:
                        sources.update(shared(on_screen, mobs))
                moves += [motion.morph(on_screen[i], mobs[i], sources) for i in morph]
                # a new element whose place is still covered by something that moves away this
                # beat (a system shrinking to make room for a chart under it) enters after the move
                movers = [on_screen[i] for i in same | morph]
                late = []
                # the 2D camera moves in this beat: what is new appears once it has arrived, not at
                # its final place while the page is still gliding there
                # (only when something stays to glide: after a clean cut, waiting is a blank screen)
                stays = bool(same | morph) or any(w0.show.get(k, 0) > 0 for k, v in new_w.show.items() if v > 0)
                travel = b.index > 0 and self.views[b.index] != self.views[b.index - 1] and stays
                for i, n in nodes.items():
                    if i not in same | morph:
                        if travel or any(_covers(m, mobs[i]) for m in movers):
                            late.append(i)     # added by its own play, so it is not drawn early
                            continue
                        enters.append(self._enter(b, n, mobs, on_screen, T))
                        self.add(mobs[i])
                world_anim = UpdateFromAlphaFunc(
                    Mobject(), lambda _m, a, w0=w0, w1=new_w, c0=c0, c1=new_c: (
                        self.world.apply(lerp_state(w0, w1, smooth(a),
                                                    enter_t=smooth(max(0.0, 2 * a - 1)))),
                        apply_camera(frame, lerp_camera(c0, c1, smooth(a)))),
                    run_time=T + 0.4, rate_func=linear)
                if letterbox and b.attrs.get("letterbox") == "open":
                    enters.insert(0, self._bars(bars, BAR_OPEN))
                if letterbox and b.attrs.get("letterbox") == "close":
                    enters.append(self._bars(bars, FRAME_HEIGHT / 2))
                self.play(world_anim, *fades, *moves, *([LaggedStart(*enters, lag_ratio=0.25)] if enters else []),
                          run_time=T + 0.4)
                if fades:
                    self.remove(*(on_screen[i] for i in gone))
                for i in morph:
                    # parts of the new element may have been added on their own by a fade
                    self.remove(on_screen[i], *mobs[i].get_family())
                    self.add(mobs[i])
                if late:    # after the morphs are swapped in, or a morphed plot is missing meanwhile
                    self.add(*(mobs[i] for i in late))
                    self.play(*(self._enter(b, nodes[i], mobs, mobs, T * 0.7) for i in late), run_time=T * 0.7)
                    self.add(*(mobs[i] for i in late))
                on_screen = {i: on_screen[i] if i in same else mobs[i] for i in nodes}

            if self.strict_layout and not (self.has_prelude and b.index == 0):
                self.world.field.refresh_view()
                leaves = {i: n for i, n in nodes.items() if n.tag in LEAF_TAGS}
                self.frame_problems += audit_beat(b.index, leaves, on_screen, self.world.field,
                                                  frame, focus_ok)
            self.bring_to_front(*on_screen.values(), bars)
            wstate, cstate = new_w, new_c
            prev_nodes = nodes
            self._hold(b, on_screen, nodes, wstate, cstate)
        if self.frame_problems:   # check mode: what the viewer would see, beat by beat
            raise ValueError("frame errors:\n- " + "\n- ".join(self.frame_problems))

    def _enter(self, b: Beat, n, mobs: dict, on_screen: dict, T: float) -> Animation:
        """How a new element comes in; a formula with ``from`` is assembled from the picture
        parts it names (wherever they are right now)."""
        if n.tag == "tex" and n.attrs.get("from"):
            live = {**mobs, **on_screen}
            return motion.assemble(n, mobs[n.id], lambda ref: resolve(
                ref, live, f"beat {b.index} <tex id={n.id}> from="))
        if not mobs[n.id].family_members_with_points():   # a mark the render left out (its target is missing)
            return FadeIn(mobs[n.id], run_time=T)
        return enter_anim(n, mobs[n.id], T)

    def _true_fit(self, c: CameraState, pts, b: Beat, bx) -> None:
        """The zoom estimate is orthographic, but the camera has perspective: the near side of a
        big body comes out larger and spilled over the text below. Project through the real
        camera and rescale until the points fill the focus box at the intended margin."""
        if pts is None or not len(pts):
            return
        from .solids import project

        key = b.camera.get("focus", "").lstrip("#")
        box = bx.get(key) if key else None
        cx, cy, w, h = (box.x, box.y, box.w, box.h) if box else (0, 0, FRAME_WIDTH, FRAME_HEIGHT)
        frame = self.camera.frame
        for _ in range(5):
            apply_camera(frame, c)
            q = np.array([project(frame, p)[:2] for p in pts])
            lo, hi = q.min(axis=0), q.max(axis=0)
            # perspective makes the picture lopsided around the target point (the near end
            # bigger): centre what is drawn on the box, then fill it
            off = (lo + hi) / 2 - np.array([cx, cy])
            need = max((hi[0] - lo[0]) / (0.84 * w), (hi[1] - lo[1]) / (0.84 * h))
            if not np.isfinite(need) or need <= 0:
                break
            c.focus = (c.focus[0] - off[0], c.focus[1] - off[1])
            if abs(need - 1) < 0.03 and np.abs(off).max() < 0.05:
                break
            c.zoom = float(np.clip(c.zoom / need, 0.25, 4.0))

    # --- pieces --------------------------------------------------------------------
    def _bars(self, bars, h) -> Animation:
        top, bot = bars
        return AnimationGroup(
            top.animate.set_height(h, stretch=True).move_to(UP * (FRAME_HEIGHT / 2 - h / 2)),
            bot.animate.set_height(h, stretch=True).move_to(DOWN * (FRAME_HEIGHT / 2 - h / 2)),
            run_time=1.4)

    def _wipe(self, on_screen, mobs, w0, w1, c1):
        th = themes.current()
        panel = Rectangle(FRAME_WIDTH + 2, FRAME_HEIGHT + 1, fill_color=th.panel_fill,
                          fill_opacity=1, stroke_color=th.accent, stroke_width=6)
        panel.fix_in_frame().move_to(LEFT * (FRAME_WIDTH + 2))
        self.add(panel)
        self.play(panel.animate.move_to(ORIGIN), run_time=0.6, rate_func=rush_into)
        self.remove(*on_screen.values())
        on_screen.clear()
        self.world.apply(w1)
        apply_camera(self.camera.frame, c1)
        self.add(*mobs.values())
        self.bring_to_front(panel)
        self.play(panel.animate.move_to(RIGHT * (FRAME_WIDTH + 2)), run_time=0.7,
                  rate_func=rush_from)
        self.remove(panel)

    def _hold(self, b: Beat, on_screen, nodes, ws: WorldState, cs: CameraState):
        hold = beat_hold(b)
        # No idle orbit during holds (the user found the swing distracting): the camera moves
        # only when a beat asks for a new view. `drift` in older beats is ignored.
        drift = 0.0
        emph = [emphasize_anim(n.attrs["emphasize"], on_screen[i], n.tag)
                for i, n in nodes.items() if "emphasize" in n.attrs]
        # displays that keep moving while the line is spoken (a simulation running)
        for i, n in nodes.items():
            live = displays.hook(n.tag, "live")
            if live is None or i not in on_screen:
                continue
            # a hook that follows another element (a formula changing with its plot) gets the beat's nodes
            anim = live(n, on_screen[i], hold, nodes) if getattr(live, "wants_beat", False) else live(n, on_screen[i], hold)
            if anim is not None:
                emph.append(anim)
        cube = b.world.get("cube")
        tumble = int(cube.attrs.get("tumble", 0)) if cube is not None else 0
        frame = self.camera.frame

        if tumble:
            self._tumble(b, ws, cs, hold, drift, tumble, emph)
            return
        descents = {i: n for i, n in b.world.items() if n.tag == "point" and "descend" in n.attrs}
        if descents:
            self._descend(descents, ws, cs, hold, drift, emph)
            return
        # world actors that run while the line is spoken (a path being traced, a plane sweeping):
        # their state key goes from where it is to this beat's target (actors3d LIVE)
        live = {}
        for i, actor in self.world.field.actors.items():
            keys = getattr(actor, "LIVE", None)
            st = ws.fields.get(i) if keys else None
            if st and st.get("show", 0) > 0 and abs(st[keys[1]] - st[keys[0]]) > 1e-9:
                live[i] = (keys[0], st[keys[0]], st[keys[1]])

        def run(_m, a):
            apply_camera(frame, lerp_camera(cs, cs, 0, drift * a))
            if live:
                fields = {k: (dict(v) if v else v) for k, v in ws.fields.items()}
                for i, (key, v0, v1) in live.items():
                    fields[i][key] = v0 + (v1 - v0) * a
                self.world.apply(replace(ws, fields=fields))

        self.play(UpdateFromAlphaFunc(Mobject(), run, run_time=hold, rate_func=linear), *emph)
        for i, (key, v0, v1) in live.items():   # the next beat starts where this one ended
            ws.fields[i][key] = v1
        # bake the drift into the camera state for the next beat
        cs.theta += drift

    def _tumble(self, b, ws, cs, hold, drift, k, emph):
        cube = b.world["cube"]
        seed = int(cube.attrs.get("seed", 7))
        total = int(cube.attrs.get("samples", 5000))
        rots = tumble_rotations(seed, total)
        areas = np.array([shadow_area(r) for r in rots])
        running = np.cumsum(areas) / np.arange(1, total + 1)
        frame = self.camera.frame
        ff_time = 2.0
        seg = (hold - ff_time) / k
        path = [ws.rot, *rots[:k]]
        vals = self.world.values

        def update(_m, a):
            t = a * hold
            apply_camera(frame, lerp_camera(cs, cs, 0, drift * a))
            if t < hold - ff_time:
                i, f = divmod(t / seg, 1)
                i = int(i)
                f = smooth(min(1, f / 0.45))
                rot = Slerp([0, 1], Rotation.concatenate([path[i], path[i + 1]]))(f)
                self.world.apply(replace(ws, rot=rot))
                landed = i + (1 if f >= 1 else 0)
                vals["tumble.n"] = landed
                vals["tumble.mean"] = running[landed - 1] if landed else 0.0
            else:
                f = smooth((t - (hold - ff_time)) / ff_time)
                n = int(k + f * (total - k))
                vals["tumble.n"] = n
                vals["tumble.mean"] = running[n - 1]

        self.play(UpdateFromAlphaFunc(Mobject(), update, run_time=hold, rate_func=linear), *emph)
        cs.theta += drift
        ws.rot = rots[k - 1]

    def _descend(self, descents, ws, cs, hold, drift, emph):
        """Animate real gradient-descent steps for each ``<point descend=lr steps=n>``."""
        field_ = self.world.field
        paths = {i: field_.descent_path(n, ws.fields[i]["xy"]) for i, n in descents.items()}
        frame = self.camera.frame
        vals = self.world.values

        def update(_m, a):
            apply_camera(frame, lerp_camera(cs, cs, 0, drift * a))
            fields = {k: (dict(v) if v else v) for k, v in ws.fields.items()}
            hops = {}
            for i, path in paths.items():
                k = len(path) - 1
                pos, frac = divmod(a * k, 1)
                pos = min(int(pos), k - 1)
                f = smooth(min(1.0, frac / 0.6)) if a < 1 else 1.0
                fields[i]["xy"] = path[pos] + f * (path[pos + 1] - path[pos])
                field_.set_trail(i, path[:pos + 2], f)
                hops[i] = field_.hop(i, path[pos], path[pos + 1], f)
                vals[f"{i}.step"] = pos + (1 if f >= 1 else 0)
            self.world.apply(replace(ws, fields=fields))
            for i, p in hops.items():   # ride the arc, not the surface, mid-step
                field_.mobs[i].move_to(p)

        self.play(UpdateFromAlphaFunc(Mobject(), update, run_time=hold, rate_func=linear), *emph)
        cs.theta += drift
        for i, path in paths.items():
            ws.fields[i]["xy"] = path[-1]

