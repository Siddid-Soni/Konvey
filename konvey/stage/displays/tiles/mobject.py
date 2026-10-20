"""``<tiles>`` (manimgl): letter tiles from render/konvey_kit.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from manimlib import *  # noqa: F401,F403

from ...tree import Node

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "render"))
import konvey_kit  # noqa: E402


def build(node: Node, world=None) -> Mobject:
    word = node.attrs.get("word", "")
    mob = konvey_kit.WordTiles(word, node.attrs.get("colors", "x" * len(word)))
    mob.content = json.dumps(["tiles", word, node.attrs.get("colors")])
    return mob
