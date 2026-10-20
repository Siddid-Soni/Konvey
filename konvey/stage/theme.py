"""Visual themes for the stage renderer: every colour, font and material in one place.

Overlay, scene and world modules read the active theme (:func:`current`) instead of
module-level constants. The render wrapper sets it per scene (``StageScene.theme``),
so a run re-renders with the theme it was written with.

Agent 3 names colours semantically (``ink``, ``muted``, ``accent``, ``c1``…``c5``);
:meth:`Theme.color` resolves those, maps CSS names such as ``red`` to the nearest
palette entry by hue, and passes hex through.
"""

from __future__ import annotations

import colorsys
from dataclasses import dataclass, replace

SEMANTIC = ("bg", "ink", "muted", "accent")


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str
    ink: str
    muted: str
    accent: str
    palette: tuple[str, ...]           # c1..c5: series / multi-object colours, c1 first
    heading_font: str
    body_font: str
    mono_font: str
    heading_weight: str                # manimgl weight name: "NORMAL" | "BOLD"
    solid: str                         # default colour of 3D solids
    solid_shading: tuple[float, float, float]
    floor: str                         # "plane" (floor + grid) | "ring" | "none"
    floor_color: str
    grid_color: str
    shadow_fill: str
    caption: str                       # "subtitle" (plain text) | "pill" (dark band)
    letterbox: bool
    panel_fill: str
    panel_stroke: str
    up_tint: str                       # solid faces lit from above (tint="by-light")
    down_tint: str                     # faces towards the floor
    marker: str                        # balls/points riding on a surface
    trail: str                         # the path a point leaves behind
    mesh: str                          # grid lines drawn on surfaces (must contrast with `solid`)
    cards: bool                        # class="card" draws a box (else layout only; "panel" always draws)
    snap_hex: bool                     # raw hex snaps to the nearest theme colour (keeps the palette)
    highlight: str = ""                # highlighted shapes' outline; "" = the accent (use(highlight=))

    @property
    def lit(self) -> str:
        """The colour a highlighted shape's outline is drawn in."""
        return self.highlight or self.accent

    @property
    def dark(self) -> str:
        """A black or dark thing (a dark sock, a black stone): darker than ``muted`` but still
        apart from the background; shapes in it get a light edge (``needs_edge``)."""
        return _blend(self.bg, self.ink, 0.17)

    def needs_edge(self, hex_: str) -> bool:
        """Too close to the background to be seen without an outline."""
        return abs(_hsv(hex_)[2] - _hsv(self.bg)[2]) < 0.25

    def color(self, value: str | None, default: str = "ink") -> str:
        """Semantic name, CSS colour name or hex -> hex. Unknown names raise ValueError."""
        v = (value or default).strip()
        key = v.lower()
        if key in SEMANTIC:
            return getattr(self, key)
        if key in ("dark", "black"):
            return self.dark
        if key in ("light", "white"):
            return self.ink
        if len(key) == 2 and key[0] == "c" and key[1].isdigit():
            i = int(key[1]) - 1
            if 0 <= i < len(self.palette):
                return self.palette[i]
            raise ValueError(f"colour {v!r}: this theme has c1..c{len(self.palette)}")
        if key.startswith("#") and len(key) in (4, 7):
            return self.nearest(v) if self.snap_hex else v
        if key in CSS_COLORS:
            return self.nearest(CSS_COLORS[key])
        raise ValueError(f"unknown colour {v!r}; use one of {', '.join(self.color_names())}")

    def color_names(self) -> list[str]:
        return ["ink", "muted", "accent", *(f"c{i + 1}" for i in range(len(self.palette))), "dark"]

    def nearest(self, hex_: str) -> str:
        """The theme colour closest in hue to ``hex_`` (greys go to ink/muted/bg)."""
        h, s, v = _hsv(hex_)
        if s < 0.2:
            return self.ink if v > 0.75 else self.muted if v > 0.25 else self.bg
        cands = [self.accent, *self.palette]
        return min(cands, key=lambda c: _hue_dist(h, _hsv(c)[0]))


def _hsv(hex_: str) -> tuple[float, float, float]:
    x = hex_.lstrip("#")
    if len(x) == 3:
        x = "".join(c * 2 for c in x)
    r, g, b = (int(x[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hsv(r, g, b)


def _blend(a: str, b: str, t: float) -> str:
    """``a`` moved ``t`` of the way to ``b`` (hex colours)."""
    pa, pb = (tuple(int(x.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) for x in (a, b))
    return "#" + "".join(f"{round(u + (v - u) * t):02x}" for u, v in zip(pa, pb))


def _hue_dist(a: float, b: float) -> float:
    d = abs(a - b)
    return min(d, 1 - d)


# CSS names an LLM is likely to write; resolved to the nearest theme colour.
CSS_COLORS = {   # typical mid tones, not the pure CSS primaries ("blue" means #3b82f6-ish)
    "red": "#ef4444", "crimson": "#dc2626", "orange": "#f97316", "yellow": "#eab308",
    "gold": "#d4a853", "amber": "#f59e0b", "green": "#22c55e", "lime": "#84cc16",
    "teal": "#14b8a6", "cyan": "#06b6d4", "blue": "#3b82f6", "navy": "#1e3a8a",
    "purple": "#a855f7", "violet": "#8b5cf6", "magenta": "#d946ef", "pink": "#ec4899",
    "brown": "#92400e", "white": "#ffffff", "black": "#000000", "grey": "#808080",
    "gray": "#808080", "silver": "#c0c0c0",
}


CLASSIC = Theme(
    name="classic",
    bg="#0b0f17", ink="#e5e7eb", muted="#9ca3af", accent="#facc15",
    palette=("#3b82f6", "#f43f5e", "#f59e0b", "#8b5cf6", "#22c55e"),
    heading_font="Noto Sans", body_font="Noto Sans", mono_font="Noto Sans Mono",
    heading_weight="BOLD",
    solid="#3b82f6", solid_shading=(0.3, 0.4, 0.2),
    floor="plane", floor_color="#1e293b", grid_color="#334155", shadow_fill="#020617",
    caption="pill", letterbox=True,
    panel_fill="#111827", panel_stroke="#374151",
    up_tint="#f59e0b", down_tint="#8b5cf6",
    marker="#f43f5e", trail="#fb7185", mesh="#e5e7eb",
    cards=True, snap_hex=False,
)

EDITORIAL = Theme(
    name="editorial",
    bg="#0B0B0C", ink="#F2EDE4", muted="#8C877E", accent="#D4A853",
    # slate blue, sage, clay, dusty rose, sand: muted next to the gold accent, which stays
    # unique so "accent" always means "look here"
    palette=("#7F96B8", "#8FA98A", "#C47A5A", "#C2909C", "#B5A88C"),
    heading_font="C059", body_font="Adwaita Sans", mono_font="Adwaita Mono",
    heading_weight="NORMAL",
    solid="#F2EDE4", solid_shading=(0.3, 0.35, 0.3),
    floor="none", floor_color="#141413", grid_color="#D4A853", shadow_fill="#2A2721",
    caption="subtitle", letterbox=False,
    panel_fill="#141413", panel_stroke="#2A2824",
    up_tint="#D4A853", down_tint="#7F96B8",
    marker="#D4A853", trail="#D4A853", mesh="#0B0B0C",
    cards=False, snap_hex=True,
)

THEMES = {t.name: t for t in (EDITORIAL, CLASSIC)}
DEFAULT = "editorial"

_active = THEMES[DEFAULT]


def get_theme(name: str) -> Theme:
    try:
        return THEMES[name]
    except KeyError:
        raise ValueError(f"unknown theme {name!r}; available: {', '.join(THEMES)}") from None


def use(name: str, highlight: str | None = None) -> Theme:
    """Make ``name`` the active theme for everything built after this call. ``highlight`` (a
    theme colour name such as ``c2``, or a hex used exactly) replaces the accent as the colour
    highlighted shapes are outlined in."""
    global _active
    th = get_theme(name)
    if highlight and highlight.strip():
        v = highlight.strip()
        th = replace(th, highlight=v if v.startswith("#") and len(v) in (4, 7) else th.color(v))
    _active = th
    return _active


def current() -> Theme:
    return _active
