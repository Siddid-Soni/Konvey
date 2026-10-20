"""Beat HTML -> typed node tree (spec §6.1).

A beat file holds a sequence of ``<beat>`` elements. Each beat is a full
snapshot of the screen at the end of that beat:

- overlay HTML (div/row/col + leaf tags) laid out by Chromium, drawn fixed in frame;
- ``<world>`` with 3D actors (state is interpolated between beats);
- ``<camera>`` (orientation + which overlay element the world is centred on).
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from html.parser import HTMLParser

from . import displays, shots
from .tree import BeatError, Node

TEXT_TAGS = {"h1", "h2", "h3", "text", "caption"}
DISPLAY_TAGS = set(displays.tags())  # <array>, <system>, … : konvey/stage/displays/<name>/
RAW_TAGS = {d.tag for d in displays.all_displays() if d.raw}     # inner text kept verbatim (LaTeX)
CHILD_TAGS = {d.tag: d.children for d in displays.all_displays() if d.children}   # <draw><rect>, <system><item>
PARENT_OF = {c: p for p, cs in CHILD_TAGS.items() for c in cs}
NESTED = {d.tag for d in displays.all_displays() if d.nested}   # <ul><li>left<li>chess</li></li></ul>
LEAF_TAGS = TEXT_TAGS | DISPLAY_TAGS
CONTAINER_TAGS = {"div", "section"}
WORLD_TAGS = {"ground", "cube", "shadow", "rays", "axes3d", "surface", "point", "gradient", "contours",
              "parametric", "trajectory", "slice", "waves", "orbits", "particles", "flow",
              "sphere", "solid", "light", "field", "label3d", "line3d", "angle3d", "face3d"}
ALIASES = displays.aliases()   # an old tag (<system>) reads as the display's tag now (<places>)
# Videos carry no subtitles: the narration is heard, and the picture takes the whole stage.
# caption="auto" on a beat (or CAPTION = "auto") brings back the vo as a subtitle.
CAPTION = "none"
KNOWN = LEAF_TAGS | CONTAINER_TAGS | WORLD_TAGS | set(PARENT_OF) | {"beats", "beat", "world", "camera", "em", "br"}


@dataclass
class Beat:
    index: int
    attrs: dict[str, str]
    overlay: list[Node]          # top-level overlay nodes
    world: dict[str, Node]       # actor tag -> node
    camera: dict[str, str]

    def leaves(self) -> dict[str, Node]:
        return {n.id: n for root in self.overlay for n in root.walk(lambda m: m.tag not in CHILD_TAGS)
                if n.tag in LEAF_TAGS or is_panel(n)}


def is_panel(n: Node) -> bool:
    """``class="panel"`` (``card`` is the old name) draws a backdrop box behind its box."""
    return bool({"panel", "card"} & set(n.attrs.get("class", "").split()))


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("beats")
        self.stack = [self.root]
        self.leaf: Node | None = None
        self.kids: list[Node] = []   # open children of a nested leaf
        self.emph = False

    def handle_starttag(self, tag, attrs):
        tag = ALIASES.get(tag, tag)
        if tag not in KNOWN:
            raise BeatError(f"line {self.getpos()[0]}: unknown tag <{tag}>. Allowed: {sorted(KNOWN)}")
        if self.leaf is not None and self.leaf.tag in CHILD_TAGS:
            allowed = CHILD_TAGS[self.leaf.tag]
            if tag not in allowed:
                raise BeatError(f"<{tag}> inside <{self.leaf.tag} id={self.leaf.id}>: only {sorted(allowed)} allowed")
            child = Node(tag, {k: (v or "") for k, v in attrs})
            (self.kids[-1] if self.kids else self.leaf).children.append(child)
            if self.leaf.tag in NESTED:
                self.kids.append(child)
            return
        if tag in PARENT_OF and tag not in DISPLAY_TAGS:   # <arc> in a <draw> is its shape, alone a mark
            raise BeatError(f"line {self.getpos()[0]}: <{tag}> belongs inside a <{PARENT_OF[tag]}>")
        if self.leaf is not None:
            if tag == "em":
                self.emph = True
            elif tag == "br":
                self.leaf.segments.append(("\n", False))
            else:
                raise BeatError(f"<{tag}> inside leaf <{self.leaf.tag} id={self.leaf.id}>: only <em>/<br> allowed")
            return
        node = Node(tag, {k: (v or "") for k, v in attrs})
        self.stack[-1].children.append(node)
        if tag in LEAF_TAGS:
            if not node.id:
                raise BeatError(f"line {self.getpos()[0]}: leaf <{tag}> needs an id")
            self.leaf = node
            self.kids = []
        elif tag not in {"camera", "br"} | WORLD_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        tag = ALIASES.get(tag, tag)
        inside = self.leaf is not None and tag in CHILD_TAGS.get(self.leaf.tag, ())
        self.handle_starttag(tag, attrs)
        if inside and self.kids:
            self.kids.pop()   # <li … /> closes itself
        elif tag in LEAF_TAGS and not inside:   # <arc/> in a <draw> is its shape, not a mark
            self.leaf = None

    def handle_endtag(self, tag):
        tag = ALIASES.get(tag, tag)
        if self.leaf is not None and tag in CHILD_TAGS.get(self.leaf.tag, ()):
            if self.kids:
                self.kids.pop()
            return
        if self.leaf is not None:
            if tag == "em":
                self.emph = False
            elif tag == self.leaf.tag:
                self.leaf = None
            return
        if tag in {"camera", "br"} | WORLD_TAGS:
            return
        if self.stack[-1].tag != tag:
            raise BeatError(f"line {self.getpos()[0]}: </{tag}> closes <{self.stack[-1].tag}>")
        self.stack.pop()

    def handle_data(self, data):
        if self.kids:   # a nested child's own words (an <li>'s label)
            text = " ".join(data.split())
            if text:
                self.kids[-1].segments.append((text, False))
            return
        if self.leaf is not None and self.leaf.tag not in CHILD_TAGS:
            if self.leaf.tag in RAW_TAGS:
                self.leaf.segments.append((data, False))
            else:
                text = " ".join(data.split())
                if data[:1].isspace():
                    text = " " + text
                if data[-1:].isspace() and text.strip():
                    text += " "
                if text:
                    self.leaf.segments.append((text, self.emph))


def parse_beats(source: str) -> list[Beat]:
    p = _Parser()
    p.feed(source)
    p.close()
    beats = []
    for i, b in enumerate(n for n in p.root.walk() if n.tag == "beat"):
        overlay, world, camera = [], {}, {}
        for c in b.children:
            if c.tag == "world":
                # A <camera> written inside <world> means the same thing: lift it out.
                for a in c.children:
                    if a.tag == "camera":
                        camera = a.attrs
                world = {a.attrs.get("id") or a.tag: a for a in c.children if a.tag != "camera"}
            elif c.tag == "camera":
                camera = c.attrs
            else:
                overlay.append(c)
        if b.attrs.get("shot"):   # the renderer composes the beat (konvey.stage.shots)
            overlay = shots.compose(b.attrs, overlay, bool(world), LEAF_TAGS, i)
        beat = Beat(i, b.attrs, overlay, world, camera)
        for n in beat.leaves().values():
            if n.tag in RAW_TAGS:
                raw = "".join(s for s, _ in n.segments)
                n.segments = [(raw.strip() if n.tag == "tex" else textwrap.dedent(raw).strip("\n"), False)]
        has_caption = any(n.tag == "caption" for n in beat.leaves().values())
        if b.attrs.get("vo") and not has_caption and b.attrs.get("caption", CAPTION) == "auto":
            # The narration line doubles as the on-screen caption, pinned to the bottom (only when
            # asked for: videos are voiced, and the room goes to the picture). On a page larger
            # than the frame the camera pins it to the frame's bottom, so it takes no page room.
            from .view import page_size
            style = "margin-top: auto" if page_size(b.attrs) == (1.0, 1.0) else \
                "position: absolute; left: 0; bottom: 0.3u; width: 14.22u; text-align: center"
            beat.overlay.append(Node("caption", {"id": "cap", "style": style},
                                     segments=[(b.attrs["vo"], False)]))
        beats.append(beat)
    if not beats:
        raise BeatError("no <beat> elements found")
    return beats


def prepare_beats(beats: list[Beat], strict: bool = True) -> None:
    """Scene-wide normalising each display asks for (a system keeps its look from its first beat);
    with ``strict`` (checking) a display may reject beats that would flicker."""
    for d in displays.all_displays():
        if d.prepare is not None:
            d.prepare(beats, strict)
