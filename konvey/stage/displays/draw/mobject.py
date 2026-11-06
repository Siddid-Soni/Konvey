"""``<draw>``: a flat diagram built from shapes in its own coordinates (manimgl)."""

from __future__ import annotations

import json

import numpy as np

from manimlib import *  # noqa: F401,F403

from ... import icons

from ...tree import BeatError, Node
from ...theme import current
from ..base import _num, _label, Block, _own_layer, HOP, _swap


DRAW_ATTRS = {
    "rect": {"id", "x", "y", "w", "h", "color", "fill", "label", "round", "z"},
    "circle": {"id", "x", "y", "r", "color", "fill", "dashed", "label", "z"},
    "polygon": {"id", "points", "color", "fill", "label", "z"},
    "line": {"id", "from", "to", "points", "color", "width", "arrow", "dashed", "label", "z"},
    "label": {"id", "x", "y", "text", "color", "size", "z"},
    "arc": {"id", "x", "y", "r", "from", "to", "color", "width", "fill", "dashed", "label", "z"},
    "icon": {"id", "x", "y", "h", "name", "color", "label", "z"},
}
for _attrs in DRAW_ATTRS.values():
    _attrs.update({"move", "around"})
DRAW_MOVES = ("auto", "slide", "hop")
MIN_LABEL = 22      # smallest font size a label shows at, also after the page scaled the drawing down
TURN_TOL = 0.04     # a radius kept to this fraction counts as the same: the shape turns along the arc
LABEL_GAP = 0.06    # clear space (units) a label keeps from other labels and strokes


class DrawBlock(Block):
    """``<draw w h x y>`` holding ``rect``/``circle``/``polygon``/``line``/``label`` children at
    coordinates in the canvas's own units (``x``/``y`` ranges, default 0..w and 0..h, y up). For
    pictures no other tag draws: a lever, a number line, plane geometry. Every
    child has an id; between beats a child with the same id slides/reshapes/recolours to its
    new place (a long move hops over unless ``move="slide"``; ``move="hop"`` always arcs), new
    ids fade in, missing ones fade out."""

    tag = "draw"

    def __init__(self, node: Node):
        th = current()
        w, h = float(node.attrs.get("w", 8)), float(node.attrs.get("h", 4))
        (x0, x1) = (_num(v) for v in (node.attrs.get("x") or f"0,{w:g}").split(",")[:2])
        (y0, y1) = (_num(v) for v in (node.attrs.get("y") or f"0,{h:g}").split(",")[:2])
        if x1 <= x0 or y1 <= y0:
            raise BeatError(f'<draw id={node.id}> x/y ranges must run from low to high, like x="0,10"')
        sx, sy = w / (x1 - x0), h / (y1 - y0)
        self.width = w
        P = self.P = lambda x, y: np.array([(x - x0) * sx - w / 2, (y - y0) * sy - h / 2, 0.0])  # noqa: E731
        self.span = max(x1 - x0, y1 - y0)
        size = max(MIN_LABEL, float(node.attrs.get("size", 26)))
        # the whole canvas, invisible: the block keeps the same size and origin in every beat,
        # so a shape that does not move stays exactly where it was
        frame = self.frame = Rectangle(width=w, height=h).set_stroke(opacity=0).set_fill(opacity=0)
        self.items: dict[str, VGroup] = {}
        self.texts: dict[str, str] = {}
        self.kinds: dict[str, str] = {}
        self.moves: dict[str, str] = {}
        self.geo: dict[str, dict] = {}       # where each shape is, in the draw's own coordinates
        self.labels: list[tuple[Mobject, float, bool]] = []   # (text, font size, may step aside)
        self.zoom, self._fitted = 1.0, False
        if not node.children:
            raise BeatError(f'<draw id={node.id}> is empty: put <rect>, <circle>, <polygon>, <line> or '
                            "<label> inside it")
        for c in node.children:
            where = f"<draw id={node.id}> <{c.tag} id={c.id}>"
            if not c.id:
                raise BeatError(f"<draw id={node.id}> <{c.tag}> needs an id (unique inside the draw)")
            if c.id in self.items:
                raise BeatError(f'<draw id={node.id}>: two shapes have id="{c.id}"')
            extra = set(c.attrs) - DRAW_ATTRS[c.tag]
            if extra:
                raise BeatError(f"{where}: unknown attributes {sorted(extra)}; allowed {sorted(DRAW_ATTRS[c.tag])}")
            move = c.attrs.get("move", "auto").strip().lower() or "auto"
            if move not in DRAW_MOVES:
                raise BeatError(f'{where} move="{c.attrs["move"]}": use move="slide" (straight, a message along a '
                                'wire), "hop" (arc over) or "auto"')
            self.moves[c.id] = move
            geo = self.geo[c.id] = {}
            if c.attrs.get("around", "").strip():
                try:
                    ax, ay = (float(v) for v in c.attrs["around"].split(","))
                except ValueError as e:
                    raise BeatError(f'{where} around="{c.attrs["around"]}": the centre it turns about, '
                                    'like around="0,0"') from e
                geo["around"] = (ax, ay)

            def num(key, default=None, c=c, where=where):
                if key not in c.attrs:
                    if default is None:
                        raise BeatError(f'{where} needs {key}=')
                    return default
                try:
                    return float(c.attrs[key])
                except ValueError as e:
                    raise BeatError(f'{where} {key}="{c.attrs[key]}" is not a number') from e

            def pts(raw, c=c, where=where):
                try:
                    out = [P(*(float(v) for v in q.split(","))) for q in raw.split(";") if q.strip()]
                except (ValueError, TypeError) as e:
                    raise BeatError(f'{where}: points like "x,y; x,y; x,y" (two numbers each)') from e
                return out

            color = th.color(c.attrs.get("color"), "ink" if c.tag in ("line", "label") else "c1")
            fill = c.attrs.get("fill", "").strip().lower()
            fill_op = 0.0 if fill in ("none", "false", "0") else (0.85 if fill in ("true", "") else num("fill"))
            if c.tag == "label":
                text = c.attrs.get("text", "").strip()
                if not text:
                    raise BeatError(f'{where} needs text="…"')
                fs = max(MIN_LABEL, num("size", size))
                mob = _label(text, fs, th.color(c.attrs.get("color"), "ink"))
                mob.move_to(P(num("x"), num("y")))
                item = VGroup(mob)
                self.texts[c.id] = text
                self.labels.append((mob, fs, True))
                geo["at"] = (num("x"), num("y"))
            else:
                if c.tag == "rect":
                    rw, rh = num("w") * sx, num("h") * sy
                    rnd = num("round", 0.0)
                    shape = (RoundedRectangle(width=rw, height=rh, corner_radius=min(rnd * sx, rw / 2, rh / 2))
                             if rnd > 0 else Rectangle(width=rw, height=rh))
                    shape.move_to(P(num("x"), num("y")))
                    geo["at"] = (num("x"), num("y"))
                elif c.tag == "circle":
                    shape = Circle(radius=num("r") * sx).move_to(P(num("x"), num("y")))
                    geo.update(at=(num("x"), num("y")), r=num("r"))
                elif c.tag == "arc":
                    # degrees counter-clockwise from +x, in the canvas's own units (an angle mark at a
                    # vertex: centre there, from/to = the directions of its two sides)
                    a0, a1 = num("from"), num("to")
                    if abs(a1 - a0) < 1e-6 or abs(a1 - a0) > 360:
                        raise BeatError(f'{where} from="{a0:g}" to="{a1:g}": give two different angles in '
                                        "degrees (counter-clockwise from the +x direction)")
                    cx, cy, r = num("x"), num("y"), num("r")
                    geo.update(at=(cx, cy), r=r, arc=(a0, a1), wedge=fill not in ("", "none", "false", "0"))
                    ts = np.radians(np.linspace(a0, a1, max(8, int(abs(a1 - a0) / 4))))
                    rim = [P(cx + r * np.cos(t), cy + r * np.sin(t)) for t in ts]
                    if fill in ("", "none", "false", "0"):
                        fill_op = 0.0
                        shape = VMobject().set_points_as_corners(rim)
                    else:   # a filled sector: the angle's whole wedge
                        shape = VMobject().set_points_as_corners([P(cx, cy), *rim, P(cx, cy)])
                elif c.tag == "icon":   # a line icon (konvey.stage.icons): a chip, a disk, a person
                    name = c.attrs.get("name", "").strip()
                    if not icons.exists(name):
                        near = icons.suggest(name)
                        raise BeatError(f'{where} name="{name}": no such icon' +
                                        (f"; close: {', '.join(near)}" if near else ""))
                    shape = icons.icon(name, num("h") * sy, interpolate_color(th.bg, color, 0.25), color)
                    shape.move_to(P(num("x"), num("y")))
                    geo["at"] = (num("x"), num("y"))
                elif c.tag == "polygon":
                    corners = pts(c.attrs.get("points", ""))
                    if len(corners) < 3:
                        raise BeatError(f'{where} needs points="x,y; x,y; x,y" (3 or more corners)')
                    shape = Polygon(*corners)
                    geo["at"] = tuple(np.mean([[float(v) for v in q.split(",")] for q in
                                               c.attrs["points"].split(";") if q.strip()], axis=0))
                else:   # line
                    path = (pts(c.attrs["points"]) if "points" in c.attrs else
                            pts(f'{c.attrs.get("from", "")};{c.attrs.get("to", "")}'))
                    if len(path) < 2:
                        raise BeatError(f'{where} needs from="x,y" to="x,y" (or points="x,y; x,y; …")')
                    raw = (c.attrs["points"] if "points" in c.attrs else
                           f'{c.attrs.get("from", "")};{c.attrs.get("to", "")}')
                    ends = [tuple(float(v) for v in q.split(",")) for q in raw.split(";") if q.strip()]
                    geo["at"] = tuple(np.mean(ends, axis=0))
                    if len(ends) == 2:
                        geo["ends"] = ends
                    stroke = num("width", 4.0)
                    shape = VMobject().set_points_as_corners(path).set_stroke(color, stroke)
                    if c.attrs.get("dashed", "").lower() in ("true", "1", "yes"):
                        shape = DashedVMobject(shape, num_dashes=max(6, int(shape.get_arc_length() / 0.15)))
                        shape.set_stroke(color, stroke)
                    tip = VMobject()
                    if c.attrs.get("arrow", "").lower() in ("true", "1", "yes"):
                        u = path[-1] - path[-2]
                        u = u / (np.linalg.norm(u) or 1)
                        side = np.array([-u[1], u[0], 0.0]) * (0.05 + 0.012 * stroke)
                        L = 0.12 + 0.03 * stroke
                        tip = Polygon(path[-1], path[-1] - L * u + side, path[-1] - L * u - side)
                        tip.set_fill(color, 1).set_stroke(width=0)
                    shape = VGroup(shape, tip)
                    fill_op = 0.0
                if c.tag == "arc":
                    shape.set_fill(color, fill_op).set_stroke(color, num("width", 3.0))
                elif c.tag not in ("line", "icon"):
                    shape.set_fill(color, fill_op).set_stroke(color, 2.5)
                if c.tag in ("circle", "arc") and c.attrs.get("dashed", "").lower() in ("true", "1", "yes"):
                    # an outline only: a dashed ring (a path's circle, a cone's rim), a dashed angle mark
                    width = num("width", 3.0) if c.tag == "arc" else 2.5
                    shape = DashedVMobject(shape.set_fill(opacity=0), num_dashes=max(8, int(shape.get_arc_length() / 0.15)))
                    shape.set_stroke(color, width)
                    fill_op = 0.0
                text = c.attrs.get("label", "").strip()
                lab = VMobject()
                if text:
                    on_fill = fill_op > 0.5 and c.tag != "line"
                    lab = _label(text, size, th.bg if on_fill else th.ink)
                    if c.tag == "line":
                        mid = shape[0].get_center() if len(shape[0].get_points()) else shape.get_center()
                        lab.next_to(mid, UP, buff=0.08).set_backstroke(th.bg, 4)
                        self.labels.append((lab, size, True))
                    elif c.tag == "arc":   # inside the angle, just past the arc
                        t = np.radians((num("from") + num("to")) / 2)
                        rr = num("r") + 0.5 * max(lab.get_width(), lab.get_height()) / sx + 0.1 / sx
                        lab = _label(text, size, color)
                        lab.move_to(P(num("x") + rr * np.cos(t), num("y") + rr * np.sin(t)))
                        self.labels.append((lab, size, False))
                    elif c.tag == "icon":   # under the icon
                        lab = _label(text, size, th.ink)
                        lab.next_to(shape, DOWN, buff=0.12)
                        self.labels.append((lab, size, False))
                    else:
                        lab.move_to(shape)
                        room = shape.get_width() * 0.9
                        if lab.get_width() > room > 0:
                            lab.set_width(room)
                item = VGroup(shape, lab)
                self.texts[c.id] = text
            self.items[c.id] = item
            self.kinds[c.id] = c.tag
        # paint order: z (default 0), then document order
        order = sorted(range(len(node.children)), key=lambda k: (float(node.children[k].attrs.get("z", 0) or 0), k))
        layers = [self.items[node.children[k].id] for k in order]
        for k, item in enumerate(layers):
            _own_layer(item, k)
        super().__init__(frame, *layers)
        self._unclutter()
        self.content = json.dumps([node.tag, node.attrs.get("w"), node.attrs.get("h"), node.attrs.get("x"),
                                   node.attrs.get("y"), [[c.tag, sorted(c.attrs.items())] for c in node.children]])


    # --- labels that stay readable -----------------------------------------------------
    def scale(self, scale_factor, *args, **kwargs):
        """The page fitting the drawing into its box (the first shrink) keeps its labels at
        ``MIN_LABEL`` at least: they grow back about their own centres, then step aside again.
        Copies (an animation's start or target) share the label list and are left alone."""
        super().scale(scale_factor, *args, **kwargs)
        mine = {id(m) for m in self.get_family()}
        if not self._fitted and np.isscalar(scale_factor) and 0.25 <= scale_factor < 1 and \
                all(id(m) in mine for m, _, _ in self.labels):
            self._fitted = True
            self.zoom *= scale_factor
            for mob, fs, _ in self.labels:
                if fs * self.zoom < MIN_LABEL:
                    mob.scale(MIN_LABEL / (fs * self.zoom))
            self._unclutter()
        return self

    def _unclutter(self) -> None:
        """Agent 3 places labels at its own coordinates, so two may land on each other or on a
        line. Each movable label, in order, takes the nearest spot (rings of small steps around
        where it was written) clear of the labels before it and of every stroke. Deterministic:
        the same picture is uncluttered the same way in every beat, so nothing jitters."""
        movable = [m for m, _, ok in self.labels if ok and len(m.get_all_points())]
        if not movable:
            return
        texts = {id(x) for m, _, _ in self.labels for x in m.get_family()}
        # sample strokes finer than the smallest label, so none slips between two samples
        fine = 0.25 * min(max(_box(m)[3] - _box(m)[2], 0.02) for m in movable)
        strokes = []
        for item in self.items.values():
            for m in item.get_family():
                if id(m) in texts or not isinstance(m, VMobject):
                    continue
                pts = m.get_points()
                if len(pts) > 1 and m.get_stroke_width() > 0 and m.get_stroke_opacity() > 0:
                    strokes.append(_densify(pts[:, :2], fine))
        stroke = np.concatenate(strokes) if strokes else np.zeros((0, 2))
        # fixed text (a shape's own label, an angle's) is in the way like a placed label
        placed = [_box(m) for m, _, ok in self.labels if not ok and len(m.get_all_points())]
        for m in movable:
            x0, x1, y0, y1 = _box(m)
            step = 0.3 * max(y1 - y0, 0.12)
            best, best_score = (0.0, 0.0), None
            for dx, dy in _spots(step):
                b = (x0 + dx, x1 + dx, y0 + dy, y1 + dy)
                pad = max(0.25 * step, LABEL_GAP)
                hits = int(np.count_nonzero((stroke[:, 0] > b[0] - pad) & (stroke[:, 0] < b[1] + pad) &
                                            (stroke[:, 1] > b[2] - pad) & (stroke[:, 1] < b[3] + pad)))
                over = sum(_overlap(b, q, pad) for q in placed)
                score = (over > 1e-6, hits > 0, over, hits, dx * dx + dy * dy)
                if best_score is None or score < best_score:
                    best, best_score = (dx, dy), score
                if score[:2] == (False, False):
                    break
            m.shift([best[0], best[1], 0.0])
            placed.append(_box(m))

    def to_screen(self, x: float, y: float) -> np.ndarray:
        """A point of the draw's own coordinates where it is on screen now."""
        return self.frame.get_center() + self.P(x, y) * (self.frame.get_width() / self.width)


def _box(m: Mobject) -> tuple[float, float, float, float]:
    pts = m.get_all_points()
    return float(pts[:, 0].min()), float(pts[:, 0].max()), float(pts[:, 1].min()), float(pts[:, 1].max())


def _overlap(a, b, pad: float = 0.0) -> float:
    w = min(a[1], b[1]) + pad - max(a[0], b[0])
    h = min(a[3], b[3]) + pad - max(a[2], b[2])
    return max(0.0, w) * max(0.0, h)


def _densify(pts: np.ndarray, step: float) -> np.ndarray:
    """Points every ``step`` along a polyline (its bezier control points are close enough)."""
    out = [pts[:1]]
    for a, b in zip(pts[:-1], pts[1:]):
        n = int(np.linalg.norm(b - a) / step)
        if n:
            out.append(a + np.outer(np.arange(1, n + 1) / (n + 1), b - a))
        out.append(b[None])
    return np.concatenate(out)


def _spots(step: float):
    """Where a label may step to: where it was, then rings of 8 directions (up, down, right
    and left first) one step further out each time, up to 12 steps."""
    yield 0.0, 0.0
    dirs = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, 1), (1, -1), (-1, -1)]
    for k in range(1, 13):
        for dx, dy in dirs:
            yield dx * k * step, dy * k * step


# --- turning along an arc -----------------------------------------------------------------
def _angle(p, c) -> float:
    return float(np.degrees(np.arctan2(p[1] - c[1], p[0] - c[0])))


def _sweep(a: float, b: float) -> float:
    """Degrees from angle a to b the short way (half a turn goes counter-clockwise)."""
    d = (b - a + 180.0) % 360.0 - 180.0
    return 180.0 if d == -180.0 else d


def _close(p, q, tol: float) -> bool:
    return float(np.hypot(p[0] - q[0], p[1] - q[1])) <= tol


def _turn(old: DrawBlock, new: DrawBlock, i: str, turns: list) -> tuple | None:
    """(centre, degrees) when shape i keeps its distance to a centre while it moves: an
    ``around=`` centre; a line with one end fixed and the same length (a spoke, a clock hand);
    a shape whose place is on a circle drawn in both beats (a point running round the unit
    circle); or, given the turns found so far, one that keeps its distance to their centre and
    turns about as far (a label riding with the point)."""
    a, b = old.geo.get(i, {}), new.geo.get(i, {})
    if "at" not in a or "at" not in b:
        return None
    tol = 0.01 * new.span
    pa, pb = a["at"], b["at"]

    def about(c):
        ra, rb = np.hypot(pa[0] - c[0], pa[1] - c[1]), np.hypot(pb[0] - c[0], pb[1] - c[1])
        if ra < tol or abs(ra - rb) > TURN_TOL * ra + tol:
            return None
        d = _sweep(_angle(pa, c), _angle(pb, c))
        return (c, d) if abs(d) >= 2 else None

    if "around" in b:
        return about(b["around"])
    if "ends" in a and "ends" in b:
        for k in range(2):
            for j in range(2):
                if _close(a["ends"][k], b["ends"][j], tol):
                    c, fa, fb = a["ends"][k], a["ends"][1 - k], b["ends"][1 - j]
                    la, lb = np.hypot(fa[0] - c[0], fa[1] - c[1]), np.hypot(fb[0] - c[0], fb[1] - c[1])
                    if la > tol and abs(la - lb) <= TURN_TOL * la + tol:
                        d = _sweep(_angle(fa, c), _angle(fb, c))
                        if abs(d) >= 2:
                            return c, d
        return None
    for k, g in new.geo.items():
        if k == i or new.kinds[k] != "circle" or old.kinds.get(k) != "circle":
            continue
        og = old.geo.get(k, {})
        c, r = g["at"], g["r"]
        if og.get("at") == c and og.get("r") == r and r > tol and \
                all(abs(np.hypot(p[0] - c[0], p[1] - c[1]) - r) <= TURN_TOL * r + tol for p in (pa, pb)):
            return about(c)
    for c, d in turns:
        hit = about(c)
        if hit is not None and abs(hit[1] - d) <= 12:
            return hit
    return None


def _rotate2(v: np.ndarray, deg: float) -> np.ndarray:
    t = np.radians(deg)
    out = v.copy()
    out[..., 0] = v[..., 0] * np.cos(t) - v[..., 1] * np.sin(t)
    out[..., 1] = v[..., 0] * np.sin(t) + v[..., 1] * np.cos(t)
    return out


def _turn_path(c0: np.ndarray, c1: np.ndarray, deg: float, rigid: bool, a0: np.ndarray):
    """A ``path_func``: every point turns ``deg`` about the centre (``rigid``: a spoke turns
    with it), or the shape is carried round upright with its centre ``a0`` (a dot, a label).
    Whatever the turn does not explain (a recolour, a longer spoke) blends in linearly."""
    def path(p0, p1, t):
        c = c0 + (c1 - c0) * t
        if rigid:
            q, q1 = c + _rotate2(p0 - c0, deg * t), c1 + _rotate2(p0 - c0, deg)
        else:
            q = p0 + (c + _rotate2(a0 - c0, deg * t) - a0)
            q1 = p0 + (c1 + _rotate2(a0 - c0, deg) - a0)
        return q + t * (p1 - q1)
    return path


def _sweep_arc(a: VGroup, b: VGroup, old: DrawBlock, new: DrawBlock, ga: dict, gb: dict) -> Animation:
    """An angle mark that opens or closes: its sides sweep, the arc is redrawn at every frame
    between the two angles (a point-by-point morph would cut across the wedge)."""
    (a0, a1), (b0, b1) = ga["arc"], gb["arc"]
    (cx, cy), r = gb["at"], gb["r"]
    ca, cb = a[0].get_stroke_color(), b[0].get_stroke_color()

    def upd(m, t):
        t = smooth(t)
        f, g = a0 + (b0 - a0) * t, a1 + (b1 - a1) * t
        ts = np.radians(np.linspace(f, g, max(8, int(abs(g - f) / 4))))
        rim = [old.to_screen(cx + r * np.cos(u), cy + r * np.sin(u)) * (1 - t) +
               new.to_screen(cx + r * np.cos(u), cy + r * np.sin(u)) * t for u in ts]
        centre = old.to_screen(cx, cy) * (1 - t) + new.to_screen(cx, cy) * t
        m.set_points_as_corners([centre, *rim, centre] if gb.get("wedge") else rim)
        m.set_stroke(interpolate_color(ca, cb, t))

    return UpdateFromAlphaFunc(a[0], upd)


def _draw(old: DrawBlock, new: DrawBlock) -> Animation:
    """Shapes matched by id: each slides, reshapes and recolours to its new look; one moving
    across a large part of the canvas hops over (a box lifted from one shelf to another) unless
    its new beat says ``move="slide"`` (a message along a wire); ``move="hop"`` always arcs.
    Labels that change are swapped in place; new shapes fade in, missing ones fade out."""
    anims = []
    # what turns about a centre: spokes and points on circles first, then what rides with them
    same = [i for i in new.items if i in old.items and old.kinds[i] == new.kinds[i] and new.moves[i] != "slide"]
    turns: dict[str, tuple] = {}
    for i in same:
        if (hit := _turn(old, new, i, [])) is not None:
            turns[i] = hit
    for i in same:
        if i not in turns and (hit := _turn(old, new, i, list(turns.values()))) is not None:
            turns[i] = hit
    for i, b in new.items.items():
        a = old.items.get(i)
        if a is None:
            anims.append(FadeIn(b, scale=0.9))
            continue
        if old.kinds[i] != new.kinds[i]:
            anims.append(FadeTransform(a, b))
            continue
        ga, gb = old.geo[i], new.geo[i]
        if new.kinds[i] == "arc" and ga["arc"] != gb["arc"] and ga["at"] == gb["at"] and ga["r"] == gb["r"]:
            anims.append(_sweep_arc(a, b, old, new, ga, gb))
            mid = (sum(gb["arc"]) - sum(ga["arc"])) / 2
            c0, c1 = old.to_screen(*ga["at"]), new.to_screen(*gb["at"])
            path = _turn_path(c0, c1, mid, False, a[1].get_center())
            anims.append(Transform(a[1], b[1], path_func=path) if old.texts[i] == new.texts[i]
                         else _swap(a[1], b[1]))
            continue
        dx = b.get_center()[0] - a.get_center()[0]
        move = new.moves.get(i, "auto")
        hop = move == "hop" or (move == "auto" and abs(dx) >= 0.25 * new.width)
        arc = 0.0 if move == "slide" or not hop else (HOP if dx < 0 else -HOP)
        how = {"path_arc": arc}
        if i in turns:
            (cx, cy), deg = turns[i]
            c0, c1 = old.to_screen(cx, cy), new.to_screen(cx, cy)
            rigid = new.kinds[i] in ("line", "polygon")
            how = {"path_func": _turn_path(c0, c1, deg, rigid, a[0].get_center())}
            # a label rides round upright with its shape, about the shape's own centre
            lab_how = {"path_func": _turn_path(c0, c1, deg, False, a[1].get_center() if rigid
                                               else a[0].get_center())}
        else:
            lab_how = how
        if new.kinds[i] == "label":
            anims.append(Transform(a, b, **how) if old.texts[i] == new.texts[i] else _relabel(a, b))
            continue
        anims.append(Transform(a[0], b[0], **how))
        if old.texts[i] == new.texts[i]:
            anims.append(Transform(a[1], b[1], **lab_how))
        else:
            anims.append(_swap(a[1], b[1]))
    anims += [FadeOut(a, scale=0.9) for i, a in old.items.items() if i not in new.items]
    return AnimationGroup(*anims)


def _relabel(a: Mobject, b: Mobject) -> Animation:
    """A ``<label>`` whose text changed: the old one fades first, the new one after, never two
    texts blended on top of each other."""
    return AnimationGroup(FadeOut(a, rate_func=squish_rate_func(smooth, 0.0, 0.4)),
                          FadeIn(b, rate_func=squish_rate_func(smooth, 0.45, 1.0)))


def _point(self, x: float, y: float) -> np.ndarray:
    """Where the drawing's own (x, y) is on the page now, after the layout has fitted it."""
    return self.frame.get_center() + self.P(x, y) * (self.frame.get_width() / self.width)


def _bounds(self) -> tuple[float, float, float, float]:
    (a, b, _), (c, d, _) = self.frame.get_corner(DL), self.frame.get_corner(UR)
    return a, b, c, d


DrawBlock.point, DrawBlock.bounds = _point, _bounds


def build(node: Node, world=None) -> DrawBlock:
    return DrawBlock(node)


def morph(old: DrawBlock, new: DrawBlock, sources=None) -> Animation:
    return _draw(old, new)
