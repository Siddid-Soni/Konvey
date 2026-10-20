"""``<simview>`` (manimgl): see ``konvey.stage.displays.sim.model``."""

from __future__ import annotations

from ...tree import BeatError, Node
from ..sim.mobject import live, morph  # noqa: F401 - the same clock and the same move-only morph
from ..sim.model import GraphView, LinesView, PhaseView

VIEWS = {"phase": PhaseView, "graph": GraphView}


def build(node: Node, world=None):
    show = node.attrs.get("show", "phase").strip()
    if show not in VIEWS:
        raise BeatError(f'<simview id={node.id}> show="{show}": use one of {", ".join(VIEWS)}')
    if show == "graph" and node.attrs.get("y", "").strip():   # chosen numbers over time
        return LinesView(node, world)
    return VIEWS[show](node, world)
