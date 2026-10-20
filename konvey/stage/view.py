"""The 2D camera over the overlay, and dimming everything but what the line is about.

Beat attributes (all optional):

- ``page="W,H"``: the page is W frames wide and H frames tall (default ``1,1``). The frame first
  shows its top-left region; whatever is laid out beyond it waits off screen until the camera
  goes there.
- ``view="ref"``: the camera frames ``ref`` (a leaf id, ``id>part``, a container ``div`` id, or
  ``page`` for the whole page) with a margin; ``zoom="2"`` instead keeps ``ref`` centred at that
  zoom. A beat without ``view`` shows the home frame.
- ``focus="ref, ref"``: everything else on the page dims, so the eye goes to those parts.

The camera is a uniform scale + shift of the laid-out page (lines keep their width), applied to each beat's mobjects
before the beat plays. An element kept from one beat to the next moves between the two views,
so the whole page glides together, as a camera pan or zoom does. Subtitles stay put.
"""

from __future__ import annotations

import numpy as np

from manimlib import FRAME_HEIGHT, FRAME_WIDTH, Mobject

from .attach import resolve
from .tree import BeatError

MARGIN = 1.2      # a framed part fills 1/MARGIN of the frame
MAX_ZOOM = 4.0
DIM = 0.22        # opacity factor of what is not in focus
FIXED = ("caption",)   # never moves with the camera


def page_size(attrs: dict) -> tuple[float, float]:
    """``page="2,1"`` -> (2.0, 1.0) frames."""
    raw = attrs.get("page", "").strip()
    if not raw:
        return 1.0, 1.0
    try:
        w, _, h = raw.partition(",")
        out = float(w), float(h or 1)
    except ValueError:
        raise BeatError(f'page="{raw}": write "W,H" in frames, e.g. page="2,1"') from None
    if not (1 <= out[0] <= 4 and 1 <= out[1] <= 4):
        raise BeatError(f'page="{raw}": each side is 1 to 4 frames')
    return out


def _cites(n) -> set[str]:
    """Ids of the elements a leaf sits on or is built from (of, on, from, to; tex from="sym: id>part")."""
    out = set()
    for a in ("of", "on", "from", "to"):
        for ref in n.attrs.get(a, "").split(";"):
            ref = ref.partition(":")[2] if n.tag == "tex" and a == "from" else ref
            head = ref.partition(">")[0].strip().lstrip("#")
            if head:
                out.add(head)
    return out


def _union(rects):
    rects = [r for r in rects if r is not None]
    if not rects:
        return None
    return (min(r[0] for r in rects), min(r[1] for r in rects),
            max(r[2] for r in rects), max(r[3] for r in rects))


def _of(m: Mobject):
    pts = [x.get_points() for x in m.get_family() if x.has_points()]
    if not pts:
        return None
    p = np.vstack(pts)
    return float(p[:, 0].min()), float(p[:, 1].min()), float(p[:, 0].max()), float(p[:, 1].max())


def _container(overlay, key: str):
    for root in overlay:
        for n in root.walk():
            if n.id == key and n.tag in ("div", "section"):
                return n
    return None


def framed(beat, nodes: dict, mobs: dict) -> tuple[tuple, bool] | None:
    """(rect, is_region) of what the beat's ``view`` names. A part brings along what is attached
    to it (its label, a brace, a ring), so zooming in never cuts them off; a container or the page
    means the content laid out in it, not its empty margins."""
    ref = beat.attrs.get("view", "").strip().lstrip("#")
    if not ref:
        return None
    where = f'beat {beat.index} view="{ref}"'
    content = {i: m for i, m in mobs.items() if nodes[i].tag not in FIXED}
    if ref == "page":
        return _union(_of(m) for m in content.values()), True
    head = ref.partition(">")[0].strip()
    if head not in mobs:
        box = _container(beat.overlay, head)
        if box is None:
            resolve(ref, mobs, where)   # raises, naming the beat's ids
        inside = {n.id for n in box.walk() if n.id in content}
        return _union(_of(content[i]) for i in inside), True
    rects = [_of(resolve(ref, mobs, where))]
    for i, m in content.items():
        n = nodes[i]
        if head in _cites(n) and n.tag != "tex":   # what is attached to it
            rects.append(_of(m))
            for a in ("from", "to"):               # and what its arrow points at, whole
                if n.attrs.get(a):
                    rects.append(_of(resolve(n.attrs[a], mobs, where)))
    return _union(rects), False


SUBTITLE = 0.9   # units at the bottom of the frame the subtitle covers


def camera(beat, nodes: dict, mobs: dict, bars: float = 0.0) -> tuple[np.ndarray, float]:
    """(centre, zoom) of the beat's view; the home frame is ((0, 0), 1). ``bars``: the height the
    letterbox bars cover at the top and at the bottom; the framed part stays clear of them and of
    the subtitle. ``zoom`` asks for a magnification, but never so much that the framed part (with
    what is attached to it) is cut off."""
    if beat.attrs.get("view") and beat.world:
        raise BeatError(f'beat {beat.index} view="{beat.attrs["view"]}": view moves the flat page, '
                        'not the 3D world; in a beat with a <world>, move <camera> instead')
    got = framed(beat, nodes, mobs)
    if got is None or got[0] is None:
        return np.zeros(2), 1.0
    (x0, y0, x1, y1), region = got
    sub = SUBTITLE if any(n.tag == "caption" for n in nodes.values()) else 0.0
    room_h = FRAME_HEIGHT - 2 * bars - sub
    fit = min(FRAME_WIDTH / max(x1 - x0, 1e-3), room_h / max(y1 - y0, 1e-3)) / MARGIN
    if beat.attrs.get("zoom"):
        try:
            z = min(float(beat.attrs["zoom"]), fit)
        except ValueError:
            raise BeatError(f'beat {beat.index} zoom="{beat.attrs["zoom"]}": a number, e.g. 2') from None
    else:
        z = min(fit, 1.0) if region else fit   # a region is travelled to, not magnified
    z = float(np.clip(z, 1 / MAX_ZOOM, MAX_ZOOM))
    # the framed part's centre lands at the centre of the room left above the subtitle
    c = np.array([(x0 + x1) / 2, (y0 + y1) / 2 - sub / 2 / z])
    return c, z


def apply_camera(attrs: dict, nodes: dict, mobs: dict, c: np.ndarray, z: float) -> None:
    """Move the beat's mobjects as the camera at (c, z) sees them (in place). The subtitle
    is laid out at the bottom of the whole page; it goes to the bottom of the frame."""
    _, ph = page_size(attrs)
    shift = np.array([*-c, 0.0])
    for i, m in mobs.items():
        if nodes[i].tag in FIXED:
            if ph > 1 or page_size(attrs)[0] > 1:
                m.move_to([0, m.get_center()[1] + (ph - 1) * FRAME_HEIGHT, 0])
            continue
        if z == 1.0 and not c.any():
            continue
        m.shift(shift)
        m.scale(z, about_point=np.zeros(3))   # lines keep their width, as under 3b1b's camera


def _fade(m: Mobject, k: float) -> None:
    for sm in m.get_family():
        if not sm.has_points():
            continue
        for key in ("fill_rgba", "stroke_rgba"):
            if key in sm.data.dtype.names:
                sm.data[key][:, 3] *= k


def _visible(m: Mobject) -> bool:
    for sm in m.get_family():
        if sm.has_points():
            for key in ("fill_rgba", "stroke_rgba"):
                if key in sm.data.dtype.names and (sm.data[key][:, 3] > 0).any():
                    return True
    return False


def apply_focus(attrs: dict, nodes: dict, mobs: dict, index: int) -> None:
    """Dim every element except the parts ``focus`` names (and attached marks on them)."""
    raw = attrs.get("focus", "").strip()
    if not raw:
        return
    refs = [r.strip().lstrip("#") for r in raw.split(",") if r.strip()]
    keep: dict[str, list[Mobject] | None] = {}   # id -> parts to keep bright (None: all of it)
    for r in refs:
        head, _, part = r.partition(">")
        head = head.strip()
        found = resolve(r, mobs, f'beat {index} focus="{raw}"')
        # a bare coordinate (plot>x=2 with nothing drawn there) is an invisible point: dimming
        # all but it dims the whole screen, the readout the line is about too, so it is skipped
        if part.strip() and not _visible(found):
            continue
        if not part.strip():
            keep[head] = None
        elif keep.get(head, []) is not None:
            keep.setdefault(head, []).append(found)
    if not keep:
        return
    for i, m in mobs.items():
        n = nodes[i]
        if n.tag in FIXED or i in keep and keep[i] is None:
            continue
        # marks drawn on a focused thing (an arrow, a ring, a note beside it), and a formula
        # built from it (tex from="2: id>part"), stay bright
        if any(o in keep for o in _cites(n)):
            continue
        bright = {id(x) for p in keep.get(i) or [] for x in p.get_family()}
        for sm in m.get_family():
            if id(sm) not in bright and not sm.submobjects:
                _fade(sm, DIM)


def hide_cut(beat, nodes: dict, mobs: dict, bars: float = 0.0) -> None:
    """In a beat with ``view``, an element the frame's edge would cut through fades out (it comes
    back when the camera pulls out): a half-shown neighbour at the edge reads as a mistake. The
    framed element and what is attached to it are never hidden. Call after ``apply_camera``."""
    ref = beat.attrs.get("view", "").strip().lstrip("#")
    if not ref or ref == "page":
        return
    head = ref.partition(">")[0].strip()
    box = _container(beat.overlay, head)
    keep = {head} | ({n.id for n in box.walk() if n.id} if box is not None else set())
    x1, y1 = FRAME_WIDTH / 2, FRAME_HEIGHT / 2 - bars
    for i, m in mobs.items():
        n = nodes[i]
        if n.tag in FIXED or i in keep or keep & _cites(n):
            continue
        r = _of(m)
        if r is None:
            continue
        inside = r[0] >= -x1 - 1e-3 and r[2] <= x1 + 1e-3 and r[1] >= -y1 - 1e-3 and r[3] <= y1 + 1e-3
        outside = r[2] <= -x1 or r[0] >= x1 or r[3] <= -y1 or r[1] >= y1
        if not inside and not outside:
            _fade(m, 0.0)
