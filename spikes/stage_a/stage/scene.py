"""StageScene: plays a beat file (spec §6.6–6.7).

Per beat:
  1. transition  — exits, then moves/morphs + world/camera interpolation + enters
  2. hold        — camera drift, world actions (tumble), emphasis

Beat attributes: ``t`` (transition seconds), ``hold`` (seconds),
``transition="wipe"``, ``letterbox="open|close"``, ``drift`` (deg of orbit
during hold). Leaf attributes: ``enter``, ``exit``, ``emphasize``.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

from manimlib import *  # noqa: F401,F403

from . import layout
from .overlay import ACCENT, KineticText, Value, build_card, build_leaf, fit
from .parse import LEAF_TAGS, Beat, parse_beats
from .world import (CameraState, World, WorldState, apply_camera, lerp_camera, lerp_state,
                    shadow_area, tumble_rotations)
from scipy.spatial.transform import Rotation, Slerp

BG = "#0b0f17"
BAR_OPEN = 0.55      # letterbox bar height once open (units)


# --- kinetic typography ----------------------------------------------------
def kinetic_in(mob: KineticText, run_time: float) -> Animation:
    anims = []
    for word, s in zip(mob.words, mob.word_strings):
        hot = s.strip(".,?!:;—") in mob.emph_words
        anims.append(Succession(
            FadeIn(word, shift=0.35 * UP, scale=1.6 if hot else 1.25, run_time=0.5),
            *( [Indicate(word, scale_factor=1.15, color=ACCENT, run_time=0.4)] if hot else []),
        ))
    return LaggedStart(*anims, lag_ratio=min(0.35, 2.5 / max(len(anims), 1)), run_time=run_time)


def kinetic_out(mob: KineticText) -> Animation:
    return LaggedStart(*(FadeOut(w, shift=0.4 * UP, scale=0.8) for w in mob.words),
                       lag_ratio=0.05, run_time=0.6)


def enter_anim(node, mob, run_time) -> Animation:
    kind = node.attrs.get("enter", "kinetic" if isinstance(mob, KineticText) else "fade")
    if node.tag == "tex" and "enter" not in node.attrs:
        kind = "write"
    if kind == "kinetic" and isinstance(mob, KineticText):
        return kinetic_in(mob, run_time)
    if kind == "write":
        return Write(mob, run_time=run_time)
    if kind == "grow":
        return GrowFromCenter(mob, run_time=run_time)
    if kind == "draw":
        return DrawBorderThenFill(mob, run_time=run_time)
    return FadeIn(mob, shift=0.25 * UP, run_time=run_time)


def exit_anim(node, mob) -> Animation:
    kind = node.attrs.get("exit", "kinetic" if isinstance(mob, KineticText) else "fade")
    if kind == "kinetic" and isinstance(mob, KineticText):
        return kinetic_out(mob)
    if kind == "shrink":
        return ShrinkToCenter(mob, run_time=0.5)
    return FadeOut(mob, shift=0.2 * UP, run_time=0.5)


def emphasize_anim(kind: str, mob) -> Animation:
    if kind == "flash":
        return FlashAround(mob, color=ACCENT, time_width=0.6, run_time=1.2)
    if kind == "circle":
        return ShowCreationThenFadeAround(mob, surrounding_rectangle_config={"color": ACCENT})
    return Indicate(mob, color=ACCENT, scale_factor=1.12)


class StageScene(Scene):
    beats_file: str = ""
    camera_config = dict(background_color=BG)

    def setup(self):
        super().setup()
        src = (Path(self.beats_file)).read_text()
        self.beats = parse_beats(src)
        self.world = World()

    # --- layout ------------------------------------------------------------
    def _layout(self) -> tuple[list[dict], list[dict]]:
        """Build every leaf at natural size, solve the page, fit into boxes."""
        built, sizes = [], {}
        for b in self.beats:
            mobs = {i: build_leaf(n, self.world) for i, n in b.leaves().items()
                    if n.tag in LEAF_TAGS}
            built.append(mobs)
            sizes[b.index] = {i: (m.get_width(), m.get_height()) for i, m in mobs.items()}
        boxes = layout.solve(self.beats, sizes,
                             dump=str(Path(self.beats_file).with_suffix(".layout.html")))
        for b, mobs, bx in zip(self.beats, built, boxes):
            for i, n in b.leaves().items():
                if n.tag not in LEAF_TAGS:
                    mobs[i] = build_card(n, bx[i])
                else:
                    fit(mobs[i], bx[i])
                mobs[i].fix_in_frame()
        return built, boxes

    # --- main loop ---------------------------------------------------------------
    def construct(self):
        built, boxes = self._layout()
        frame = self.camera.frame
        self.add(self.world.group)
        bars = VGroup(*(Rectangle(FRAME_WIDTH + 1, FRAME_HEIGHT / 2, fill_color=BLACK,
                                  fill_opacity=1, stroke_width=0) for _ in range(2)))
        bars[0].move_to(UP * FRAME_HEIGHT / 4)
        bars[1].move_to(DOWN * FRAME_HEIGHT / 4)
        bars.fix_in_frame()
        self.add(bars)

        on_screen: dict[str, Mobject] = {}
        prev_nodes: dict = {}
        wstate, cstate = None, None
        for b, mobs, bx in zip(self.beats, built, boxes):
            nodes = b.leaves()
            new_w = WorldState.from_beat(b.world, wstate)
            new_c = CameraState.from_beat(b.camera, bx, cstate)
            w0 = wstate or replace(new_w, show={})
            c0 = cstate or new_c
            T = float(b.attrs.get("t", 1.6))

            if b.attrs.get("transition") == "wipe":
                self._wipe(on_screen, mobs, w0, new_w, new_c)
                on_screen = dict(mobs)
            else:
                # same id + same content: move/resize. tex with morph="match": morph.
                # anything else that changed leaves (kinetic out) and re-enters.
                same = {i for i in nodes if i in on_screen
                        and getattr(on_screen[i], "content", None) == getattr(mobs[i], "content", None)}
                morph = {i for i, n in nodes.items() if i in on_screen and i not in same
                         and n.tag == "tex" and n.attrs.get("morph") == "match"}
                gone = [i for i in on_screen if i not in same | morph]
                if gone:
                    self.play(*(exit_anim(prev_nodes[i], on_screen[i]) for i in gone))
                    self.remove(*(on_screen[i] for i in gone))
                moves, enters = [], []
                for i in same:
                    old, new = on_screen[i], mobs[i]
                    # a Value's number rebuilds every frame; move the label and it follows
                    moves.append(Transform(old.label, new.label) if isinstance(old, Value)
                                 else Transform(old, new))
                moves += [TransformMatchingTex(on_screen[i], mobs[i]) for i in morph]
                for i, n in nodes.items():
                    if i not in same | morph:
                        enters.append(enter_anim(n, mobs[i], T))
                        self.add(mobs[i])
                world_anim = UpdateFromAlphaFunc(
                    Mobject(), lambda _m, a, w0=w0, w1=new_w, c0=c0, c1=new_c: (
                        self.world.apply(lerp_state(w0, w1, smooth(a))),
                        apply_camera(frame, lerp_camera(c0, c1, smooth(a)))),
                    run_time=T + 0.4, rate_func=linear)
                if b.attrs.get("letterbox") == "open":
                    enters.insert(0, self._bars(bars, BAR_OPEN))
                if b.attrs.get("letterbox") == "close":
                    enters.append(self._bars(bars, FRAME_HEIGHT / 2))
                self.play(world_anim, *moves, *([LaggedStart(*enters, lag_ratio=0.25)] if enters else []),
                          run_time=T + 0.4)
                for i in morph:
                    self.remove(on_screen[i])
                    self.add(mobs[i])
                on_screen = {i: on_screen[i] if i in same else mobs[i] for i in nodes}

            self.bring_to_front(*on_screen.values(), bars)
            wstate, cstate = new_w, new_c
            prev_nodes = nodes
            self._hold(b, on_screen, nodes, wstate, cstate)

    # --- pieces --------------------------------------------------------------------
    def _bars(self, bars, h) -> Animation:
        top, bot = bars
        return AnimationGroup(
            top.animate.set_height(h, stretch=True).move_to(UP * (FRAME_HEIGHT / 2 - h / 2)),
            bot.animate.set_height(h, stretch=True).move_to(DOWN * (FRAME_HEIGHT / 2 - h / 2)),
            run_time=1.4)

    def _wipe(self, on_screen, mobs, w0, w1, c1):
        panel = Rectangle(FRAME_WIDTH + 2, FRAME_HEIGHT + 1, fill_color="#111827",
                          fill_opacity=1, stroke_color=ACCENT, stroke_width=6)
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
        hold = float(b.attrs.get("hold", 2.0))
        drift = float(b.attrs.get("drift", 0))
        emph = [emphasize_anim(n.attrs["emphasize"], on_screen[i])
                for i, n in nodes.items() if "emphasize" in n.attrs]
        cube = b.world.get("cube")
        tumble = int(cube.attrs.get("tumble", 0)) if cube is not None else 0
        frame = self.camera.frame

        if tumble:
            self._tumble(b, ws, cs, hold, drift, tumble, emph)
            return
        anim = UpdateFromAlphaFunc(
            Mobject(), lambda _m, a: apply_camera(frame, lerp_camera(cs, cs, 0, drift * a)),
            run_time=hold, rate_func=linear)
        self.play(anim, *emph)
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
