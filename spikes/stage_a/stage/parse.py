"""Beat HTML -> typed node tree (spec §6.1).

A beat file holds a sequence of ``<beat>`` elements. Each beat is a full
snapshot of the screen at the end of that beat:

- overlay HTML (div/row/col + leaf tags) laid out by Chromium, drawn fixed in frame;
- ``<world>`` with 3D actors (state is interpolated between beats);
- ``<camera>`` (orientation + which overlay element the world is centred on).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser

TEXT_TAGS = {"h1", "h2", "h3", "text", "caption"}
LEAF_TAGS = TEXT_TAGS | {"tex", "value"}
CONTAINER_TAGS = {"div", "section"}
WORLD_TAGS = {"ground", "cube", "shadow", "rays"}
KNOWN = LEAF_TAGS | CONTAINER_TAGS | WORLD_TAGS | {"beats", "beat", "world", "camera", "em", "br"}


class BeatError(ValueError):
    pass


@dataclass
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["Node"] = field(default_factory=list)
    # Leaves: text as (string, emphasised) segments; tex keeps its raw source.
    segments: list[tuple[str, bool]] = field(default_factory=list)

    @property
    def id(self) -> str | None:
        return self.attrs.get("id")

    @property
    def text(self) -> str:
        return " ".join("".join(s for s, _ in self.segments).split(" ")).strip()

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()


@dataclass
class Beat:
    index: int
    attrs: dict[str, str]
    overlay: list[Node]          # top-level overlay nodes
    world: dict[str, Node]       # actor tag -> node
    camera: dict[str, str]

    def leaves(self) -> dict[str, Node]:
        return {n.id: n for root in self.overlay for n in root.walk()
                if n.tag in LEAF_TAGS or "card" in n.attrs.get("class", "").split()}


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("beats")
        self.stack = [self.root]
        self.leaf: Node | None = None
        self.emph = False

    def handle_starttag(self, tag, attrs):
        if tag not in KNOWN:
            raise BeatError(f"line {self.getpos()[0]}: unknown tag <{tag}>. Allowed: {sorted(KNOWN)}")
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
        elif tag not in {"camera", "br"} | WORLD_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag in LEAF_TAGS:
            self.leaf = None

    def handle_endtag(self, tag):
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
        if self.leaf is not None:
            if self.leaf.tag == "tex":
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
                world = {a.tag: a for a in c.children}
            elif c.tag == "camera":
                camera = c.attrs
            else:
                overlay.append(c)
        beat = Beat(i, b.attrs, overlay, world, camera)
        for n in beat.leaves().values():
            if n.tag == "tex":
                n.segments = [("".join(s for s, _ in n.segments).strip(), False)]
        beats.append(beat)
    if not beats:
        raise BeatError("no <beat> elements found")
    return beats
