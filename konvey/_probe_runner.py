"""Subprocess entry point for :mod:`konvey.layout_probe`.

Runs one generated ``SingleScene`` with animations skipped (no video is
written), and at every ``self.wait()`` -- the beat boundary the Agent 3
prompts require -- snapshots what is on screen and measures it:

* text vs text      : any overlap of two text bounding boxes  -> error
* text vs drawing   : drawn points of another object inside a text box -> error
* shape vs shape    : partial (non-containing) overlap backed by real points -> warning
* off-frame         : anything sticking out of the visible frame -> error
* clutter           : too many independent objects at once -> warning
* tiny text         : text shorter than a readable height -> warning
* runtime_error     : the scene crashes (NameError, bad kwargs, ...) -> error

Everything is computed in *screen* coordinates (the camera frame's view
matrix is applied, so moved/zoomed/3D-reoriented frames are handled; fixed-
in-frame mobjects are used as is). Objects are reported by the variable name
they have inside ``construct`` plus the line and ``# VO:`` beat they belong
to, so the report can be pasted back to the coding agent verbatim.

Usage: python -I _probe_runner.py <scene.py> <out.json> [config-json]
"""

from __future__ import annotations

import os
import sys

# This file lives inside the konvey package, next to konvey/validators.py,
# which would shadow the pip `validators` package manimgl imports.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _HERE]

import json  # noqa: E402
import tempfile
import traceback
from pathlib import Path

import numpy as np

DEFAULTS = {
    "margin": 0.15,           # how far inside the frame edge things must stay
    "text_pad": 0.04,         # bbox shrink before text/text tests (touching != overlap)
    "point_frac": 0.02,       # fraction of an object's points inside a text box to count
    "shape_overlap_frac": 0.15,  # partial shape overlap (of smaller box area) to warn
    "max_units": 9,           # visible top-level objects before a clutter warning
    "min_text_height": 0.16,  # screen units; digits at font_size 24 are ~0.18
}

TEXT_TYPES = ("StringMobject", "Text", "MarkupText", "Tex", "TexText", "DecimalNumber",
              "Integer", "SVGMobject_TEXT")
# Things that are *meant* to touch / surround / connect other objects.
# Matched through the class hierarchy (Arrow, DashedLine, ... are Lines).
DECORATOR_BASES = {"Line", "Brace", "SurroundingRectangle", "BackgroundRectangle",
                   "CoordinateSystem", "NumberLine", "Cross", "FullScreenRectangle"}
# Matched by exact type only: Circle and Dot subclass Arc in manimgl.
DECORATOR_EXACT = {"Arc", "ArcBetweenPoints", "CurvedArrow", "CurvedDoubleArrow",
                   "BraceLabel", "Underline"}


def _mro_names(mob) -> set[str]:
    return {c.__name__ for c in type(mob).__mro__}


def _is_text(mob) -> bool:
    names = _mro_names(mob)
    return bool(names & {"StringMobject", "DecimalNumber"}) or type(mob).__name__ in TEXT_TYPES


def _is_decorator(mob) -> bool:
    return type(mob).__name__ in DECORATOR_EXACT or bool(_mro_names(mob) & DECORATOR_BASES)


def _visible(mob) -> bool:
    for sm in mob.get_family():
        if not sm.has_points():
            continue
        try:
            op = 0.0
            if hasattr(sm, "get_fill_opacities"):
                op = max(op, float(np.max(sm.get_fill_opacities(), initial=0)))
            if hasattr(sm, "get_stroke_opacities"):
                widths = sm.get_stroke_widths() if hasattr(sm, "get_stroke_widths") else [1]
                if float(np.max(widths, initial=0)) > 0:
                    op = max(op, float(np.max(sm.get_stroke_opacities(), initial=0)))
            if not hasattr(sm, "get_fill_opacities") and hasattr(sm, "get_opacity"):
                op = max(op, float(sm.get_opacity()))
            if op > 0.05:
                return True
        except Exception:
            return True
    return False


class _Screen:
    def __init__(self, frame):
        self.frame = frame
        self.view = np.array(frame.get_view_matrix(refresh=True)).copy()
        euler = np.array(frame.get_euler_angles())
        self.is_3d = bool(np.any(np.abs(euler) > 1e-3))
        from manimlib.constants import FRAME_HEIGHT, FRAME_WIDTH
        self.half_w, self.half_h = FRAME_WIDTH / 2, FRAME_HEIGHT / 2

    def points(self, mob) -> np.ndarray:
        pts = []
        for sm in mob.get_family():
            if not sm.has_points():
                continue
            p = np.asarray(sm.get_points(), dtype=float)
            if p.ndim != 2 or len(p) == 0:
                continue
            if not sm.is_fixed_in_frame():
                p4 = np.hstack([p, np.ones((len(p), 1))])
                p = p4 @ self.view.T
                p = p[:, :3]
            pts.append(p[:, :2])
        if not pts:
            return np.zeros((0, 2))
        return np.vstack(pts)


def _bbox(pts: np.ndarray):
    return np.array([pts.min(axis=0), pts.max(axis=0)])  # [[x0,y0],[x1,y1]]


def _shrink(b, d):
    out = b.copy()
    out[0] += d
    out[1] -= d
    return out


def _inter(a, b):
    lo = np.maximum(a[0], b[0])
    hi = np.minimum(a[1], b[1])
    wh = hi - lo
    if np.any(wh <= 0):
        return None
    return np.array([lo, hi])


def _area(b):
    wh = b[1] - b[0]
    return float(max(wh[0], 0) * max(wh[1], 0))


def _contains(outer, inner, tol=0.05):
    return bool(np.all(outer[0] - tol <= inner[0]) and np.all(inner[1] <= outer[1] + tol))


def _frac_points_in(pts, box):
    if len(pts) == 0:
        return 0.0
    inside = np.all((pts >= box[0]) & (pts <= box[1]), axis=1)
    return float(inside.mean()), int(inside.sum())


def _fmt_box(b):
    return f"x[{b[0][0]:.2f},{b[1][0]:.2f}] y[{b[0][1]:.2f},{b[1][1]:.2f}]"


def _text_label(mob) -> str:
    for attr in ("text", "tex_string", "string"):
        s = getattr(mob, attr, None)
        if isinstance(s, str) and s.strip():
            s = " ".join(s.split())
            return s[:40]
    return ""


class Prober:
    def __init__(self, scene_path: Path, cfg: dict):
        self.scene_path = scene_path
        self.cfg = {**DEFAULTS, **cfg}
        self.src_lines = scene_path.read_text(encoding="utf-8").splitlines()
        self.issues: list[dict] = []
        self.snapshots: list[dict] = []
        self._seen: set[tuple] = set()
        self.baseline: set[int] = set()

    # -- naming ---------------------------------------------------------
    def _names(self, construct_locals: dict) -> dict[int, str]:
        names: dict[int, str] = {}
        from manimlib.mobject.mobject import Mobject
        for k, v in construct_locals.items():
            if k == "self":
                continue
            if isinstance(v, Mobject):
                names.setdefault(id(v), k)
                for i, sm in enumerate(v.submobjects):
                    names.setdefault(id(sm), f"{k}[{i}]")
            elif isinstance(v, (list, tuple)):
                for i, sm in enumerate(v):
                    if isinstance(sm, Mobject):
                        names.setdefault(id(sm), f"{k}[{i}]")
        return names

    def _name(self, mob, names, fallback_idx) -> str:
        n = names.get(id(mob))
        if n:
            return n
        lab = _text_label(mob)
        base = type(mob).__name__
        if lab:
            return f"{base}('{lab}')"
        # Temporary groups (e.g. the one LaggedStartMap builds) -> describe by members.
        child_names = [names.get(id(sm)) for sm in mob.submobjects]
        if mob.submobjects and all(child_names):
            bases = {c.split("[")[0] for c in child_names}
            if len(bases) == 1:
                b = bases.pop()
                idx = ",".join(c[len(b) + 1:-1] for c in child_names if c.startswith(b + "["))
                return f"{b}[{idx}]" if idx else b
            shown = ", ".join(child_names[:3]) + (", ..." if len(child_names) > 3 else "")
            return f"group({shown})"
        return f"<unnamed {base} #{fallback_idx}>"

    def _vo_for_line(self, lineno: int) -> str:
        for i in range(min(lineno, len(self.src_lines)) - 1, -1, -1):
            s = self.src_lines[i].strip()
            if s.startswith("# VO:"):
                return s[len("# VO:"):].strip().strip('"')
            if s.startswith("def construct"):
                break
        return ""

    # -- reporting -----------------------------------------------------
    def _add(self, severity, kind, objects, line, detail):
        key = (kind, tuple(sorted(objects)))
        if key in self._seen:
            return
        self._seen.add(key)
        self.issues.append({
            "severity": severity, "kind": kind, "objects": list(objects),
            "line": line, "vo": self._vo_for_line(line), "detail": detail,
        })

    # -- the check -----------------------------------------------------
    def snapshot(self, scene, line: int, construct_locals: dict):
        cfg = self.cfg
        screen = _Screen(scene.frame)
        names = self._names(construct_locals)
        units = []
        for idx, mob in enumerate(scene.mobjects):
            if id(mob) in self.baseline or mob is scene.frame:
                continue
            if not mob.get_family() or not any(sm.has_points() for sm in mob.get_family()):
                continue
            if not _visible(mob):
                continue
            pts = screen.points(mob)
            if len(pts) == 0:
                continue
            leaves = [sm for sm in mob.get_family() if sm.has_points()]
            units.append({"mob": mob, "name": self._name(mob, names, idx), "pts": pts,
                          "box": _bbox(pts), "leaves": {id(sm) for sm in leaves},
                          "named": id(mob) in names,
                          "is_text": _all_leaves_under(mob, _is_text),
                          "is_decor": _all_leaves_under(mob, _is_decorator)})

        # Drop wrapper groups whose leaves are all already on screen via other
        # units (e.g. the Group LaggedStartMap leaves behind); keep named first.
        units.sort(key=lambda u: (not u["named"], -len(u["leaves"])))
        kept, covered = [], set()
        for u in units:
            if u["leaves"] and u["leaves"] <= covered:
                continue
            kept.append(u)
            covered |= u["leaves"]
        units = kept

        self.snapshots.append({
            "line": line, "vo": self._vo_for_line(line), "is_3d_frame": screen.is_3d,
            "objects": [{"name": u["name"], "type": type(u["mob"]).__name__,
                         "box": _fmt_box(u["box"])} for u in units],
        })

        # 1. off-frame
        hw, hh, m = screen.half_w, screen.half_h, cfg["margin"]
        for u in units:
            b = u["box"]
            over = {
                "left": -hw + m - b[0][0], "right": b[1][0] - (hw - m),
                "bottom": -hh + m - b[0][1], "top": b[1][1] - (hh - m),
            }
            bad = {k: v for k, v in over.items() if v > 0.02}
            if bad:
                if _is_decorator(u["mob"]) and type(u["mob"]).__name__ in (
                        "FullScreenRectangle", "FullScreenFadeRectangle", "NumberPlane"):
                    continue
                sides = ", ".join(f"{k} by {v:.2f}" for k, v in bad.items())
                self._add("error", "off_frame", [u["name"]], line,
                          f"{u['name']} {_fmt_box(b)} leaves the safe frame "
                          f"(x in [{-hw + m:.2f},{hw - m:.2f}], y in [{-hh + m:.2f},{hh - m:.2f}]): {sides}")

        # 2. collect text leaves (top-most text-like mobjects in every unit)
        texts = []
        for u in units:
            stack = [u["mob"]]
            while stack:
                mob = stack.pop()
                if _is_text(mob):
                    pts = screen.points(mob)
                    if len(pts):
                        nm = names.get(id(mob)) or (
                            u["name"] if mob is u["mob"] else
                            f"{u['name']}>" + (f"'{_text_label(mob)}'" if _text_label(mob) else type(mob).__name__))
                        texts.append({"mob": mob, "unit": u, "name": nm, "pts": pts, "box": _bbox(pts)})
                    continue
                stack.extend(mob.submobjects)

        # 2a. tiny text
        for t in texts:
            h = t["box"][1][1] - t["box"][0][1]
            if 0 < h < cfg["min_text_height"] and len(t["pts"]) > 8:
                self._add("warning", "tiny_text", [t["name"]], line,
                          f"{t['name']} is only {h:.2f} units tall on screen; likely unreadable (use font_size >= 24)")

        # 2b. text vs text
        pad = cfg["text_pad"]
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                a, b = texts[i], texts[j]
                if a["mob"] in b["mob"].get_family() or b["mob"] in a["mob"].get_family():
                    continue
                inter = _inter(_shrink(a["box"], pad), _shrink(b["box"], pad))
                if inter is None:
                    continue
                self._add("error", "text_overlap", [a["name"], b["name"]], line,
                          f"text {a['name']} {_fmt_box(a['box'])} overlaps text {b['name']} "
                          f"{_fmt_box(b['box'])}; overlap region {_fmt_box(inter)}")

        # 2c. text vs drawn content of other units
        for t in texts:
            tbox = _shrink(t["box"], pad)
            for u in units:
                if u is t["unit"] or t["mob"] in u["mob"].get_family():
                    continue
                if _inter(tbox, u["box"]) is None:
                    continue
                # drop text inside u from u's points (handled by text-vs-text)
                own_text = [sm for sm in u["mob"].get_family() if _is_text(sm)]
                pts = u["pts"]
                if own_text:
                    non_text = [sm for sm in u["mob"].get_family()
                                if sm.has_points() and not any(sm in tt.get_family() for tt in own_text)]
                    if not non_text:
                        continue
                    pts = np.vstack([_pts_single(screen, sm) for sm in non_text])
                frac, n = _frac_points_in(pts, tbox)
                if n >= 2 and frac >= cfg["point_frac"] or n >= 6:
                    self._add("error", "text_on_drawing", [t["name"], u["name"]], line,
                              f"text {t['name']} {_fmt_box(t['box'])} sits on top of drawn lines/shapes of "
                              f"{u['name']} {_fmt_box(u['box'])} ({n} of its points are inside the text box)")

        # 3. shape vs shape (partial overlap, not containment, not decorators)
        shapes = [u for u in units if not u["is_text"] and not u["is_decor"]]
        for i in range(len(shapes)):
            for j in range(i + 1, len(shapes)):
                a, b = shapes[i], shapes[j]
                inter = _inter(a["box"], b["box"])
                if inter is None:
                    continue
                if _contains(a["box"], b["box"]) or _contains(b["box"], a["box"]):
                    continue
                smaller = min(_area(a["box"]), _area(b["box"])) or 1e-9
                if _area(inter) / smaller < cfg["shape_overlap_frac"]:
                    continue
                _, na = _frac_points_in(a["pts"], inter)
                _, nb = _frac_points_in(b["pts"], inter)
                if na and nb:
                    self._add("warning", "shape_overlap", [a["name"], b["name"]], line,
                              f"{a['name']} {_fmt_box(a['box'])} and {b['name']} {_fmt_box(b['box'])} "
                              f"partially overlap ({_area(inter) / smaller:.0%} of the smaller one)")

        # 4. clutter
        if len(units) > cfg["max_units"]:
            self._add("warning", "clutter", [u["name"] for u in units], line,
                      f"{len(units)} separate objects on screen at once (> {cfg['max_units']}); "
                      "FadeOut what the current beat no longer needs")


def _all_leaves_under(mob, pred) -> bool:
    """True if every point-bearing leaf of mob sits under a mobject matching pred."""
    found_any = False
    stack = [mob]
    while stack:
        m = stack.pop()
        if pred(m):
            found_any = True
            continue
        if m.has_points() and not m.submobjects:
            return False
        if m.has_points() and m.submobjects:
            return False
        stack.extend(m.submobjects)
    return found_any


def _base(name: str) -> str:
    return name.split("[")[0]


def _collapse(issues: list[dict]) -> list[dict]:
    """Merge pairwise issues among siblings (x[0] vs x[3] ...) into one finding."""
    out, groups = [], {}
    for it in issues:
        objs = it["objects"]
        if it["kind"] in ("text_overlap", "tiny_text", "shape_overlap", "text_on_drawing") and objs \
                and all("[" in o for o in objs[:1]):
            # group by kind, line, and the set of bases involved
            key = (it["kind"], it["line"], tuple(sorted({_base(o) for o in objs})))
            groups.setdefault(key, []).append(it)
        else:
            out.append(it)
    for (kind, line, bases), items in groups.items():
        if len(items) == 1:
            out.append(items[0])
            continue
        members = sorted({o for it in items for o in it["objects"]})
        first = items[0]
        shown = ", ".join(members[:8]) + (" ..." if len(members) > 8 else "")
        if kind == "text_overlap" and len(bases) == 1:
            detail = (f"{len(members)} elements of {bases[0]} overlap each other ({shown}); "
                      f"they are stacked, e.g. {first['detail'].split('; ')[0]}. "
                      f"Did you forget {bases[0]}.arrange(...) or set their positions?")
        elif kind == "tiny_text":
            detail = f"{len(members)} text objects are too small to read ({shown}); e.g. {first['detail']}"
        else:
            detail = f"{len(items)} similar {kind} issues among {shown}; e.g. {first['detail']}"
        out.append({**first, "objects": members, "detail": detail})
    order = {"error": 0, "warning": 1}
    out.sort(key=lambda i: (order.get(i["severity"], 2), i["line"]))
    return out


def _pts_single(screen, sm):
    p = np.asarray(sm.get_points(), dtype=float)[:, :3]
    if not sm.is_fixed_in_frame():
        p = (np.hstack([p, np.ones((len(p), 1))]) @ screen.view.T)[:, :3]
    return p[:, :2]


def main(argv):
    scene_path = Path(argv[1]).resolve()
    out_path = Path(argv[2])
    cfg = json.loads(argv[3]) if len(argv) > 3 else {}
    result = {"ok": False, "issues": [], "snapshots": [], "error": None}

    # Shim for 3b1b/videos' `from manim_imports_ext import *` when the real
    # module is not importable.
    shim_dir = Path(tempfile.mkdtemp(prefix="konvey_probe_"))
    try:
        import manim_imports_ext  # noqa: F401
    except Exception:
        (shim_dir / "manim_imports_ext.py").write_text("from manimlib import *\n", encoding="utf-8")
        sys.path.insert(0, str(shim_dir))

    prober = Prober(scene_path, cfg)
    try:
        import importlib.util
        from manimlib.scene.scene import Scene

        spec = importlib.util.spec_from_file_location("konvey_probe_scene", scene_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        scene_cls = getattr(module, cfg.get("scene_name", "SingleScene"))

        orig_wait = Scene.wait
        scene_file = str(scene_path)

        def patched_wait(self, *a, **kw):
            out = orig_wait(self, *a, **kw)
            frame = sys._getframe(1)
            while frame is not None and frame.f_code.co_filename != scene_file:
                frame = frame.f_back
            line = frame.f_lineno if frame else -1
            local_vars = dict(frame.f_locals) if frame else {}
            prober.snapshot(self, line, local_vars)
            return out

        scene_cls.wait = patched_wait
        orig_setup = scene_cls.setup

        def patched_setup(self, *a, **kw):
            r = orig_setup(self, *a, **kw)
            prober.baseline = {id(m) for m in self.mobjects}
            for attr in ("selection", "selection_highlight", "selection_rectangle",
                         "crosshair", "information_label", "color_palette"):
                if hasattr(self, attr):
                    prober.baseline.add(id(getattr(self, attr)))
            return r

        scene_cls.setup = patched_setup
        scene = scene_cls(skip_animations=True,
                          file_writer_config=dict(write_to_movie=False, save_last_frame=False))
        scene.run()
        result["ok"] = True
    except BaseException as e:  # noqa: BLE001 - report anything the scene throws
        tb = traceback.extract_tb(e.__traceback__)
        line = next((fr.lineno for fr in reversed(tb) if fr.filename == str(scene_path)), -1)
        prober.issues.append({
            "severity": "error", "kind": "runtime_error", "objects": [], "line": line,
            "vo": prober._vo_for_line(line) if line > 0 else "",
            "detail": f"{type(e).__name__}: {e}"[:400],
        })
        result["error"] = f"{type(e).__name__}: {e}"[:400]
        result["traceback"] = traceback.format_exc()[-1500:]
    result["issues"] = _collapse(prober.issues)
    result["snapshots"] = prober.snapshots
    out_path.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    main(sys.argv)
