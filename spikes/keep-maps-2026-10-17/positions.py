"""One map for the whole video: a ``<graph>`` keeps the node positions it first had.

Each scene's director writes its own coordinates (the three scenes are written in parallel), and a
scene opens on the previous one's last frame, so a later scene with other coordinates animated the
map into a new shape: towns slid past each other and the roads swapped places. Run over every
scene's beats in order, this gives each graph id the positions of its first appearance; a node that
first shows up later is carried over by the best fit (scale, turn, shift) of the nodes the two
share, so it lands where that scene meant it relative to them."""

from __future__ import annotations

import re

import numpy as np

GRAPH_TAG = re.compile(r"<graph\b[^>]*>")


def _attr(tag: str, name: str) -> str | None:
    m = re.search(rf'\s{name}="([^"]*)"', tag)
    return m.group(1) if m else None


def _positions(raw: str) -> dict[str, np.ndarray] | None:
    """``"A:0,0;B:2,1"`` -> name -> (x, y); names only (``"A,B,C"``) -> the circle the renderer
    puts them on (graph/mobject.py ``_graph_nodes``)."""
    if ":" not in raw:
        names = [n.strip() for n in raw.replace(";", ",").split(",") if n.strip()]
        return {n: 1.6 * np.array([np.cos(a), np.sin(a)])
                for k, n in enumerate(names) for a in [np.pi / 2 - k * 2 * np.pi / len(names)]}
    out = {}
    for part in (p.strip() for p in raw.split(";") if p.strip()):
        name, _, xy = part.partition(":")
        try:
            out[name.strip()] = np.array([float(v) for v in xy.split(",")], dtype=float)
        except ValueError:
            return None
        if out[name.strip()].shape != (2,):
            return None
    return out


def _fit(src: np.ndarray, dst: np.ndarray):
    """The scale + rotation (or mirror) + shift taking ``src`` points closest to ``dst``."""
    ms, md = src.mean(0), dst.mean(0)
    x, y = src - ms, dst - md
    var = (x ** 2).sum()
    if len(src) < 2 or var < 1e-12:
        return lambda p: p - ms + md
    u, s, vt = np.linalg.svd(y.T @ x)
    rot = u @ vt
    scale = s.sum() / var
    return lambda p: scale * (rot @ (p - ms)) + md


def _num(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def keep_positions(pages: list[str]) -> list[str]:
    """The scenes' beat HTML, in order, with every graph drawn where it first stood."""
    first: dict[str, dict[str, np.ndarray]] = {}

    def pin(m: re.Match) -> str:
        tag = m.group(0)
        gid, raw = _attr(tag, "id"), _attr(tag, "nodes")
        if not gid or raw is None or _attr(tag, "layout"):
            return tag
        pos = _positions(raw)
        if pos is None:
            return tag
        known = first.setdefault(gid, {})
        shared = [n for n in pos if n in known]
        if not known:
            known.update(pos)
            return tag
        if not shared:
            return tag
        if len(shared) == len(pos) and all(np.allclose(pos[n], known[n]) for n in pos):
            return tag   # already where it first stood
        move = _fit(np.array([pos[n] for n in shared]), np.array([known[n] for n in shared]))
        for n, p in pos.items():
            if n not in known:
                known[n] = move(p)
        nodes = ";".join(f"{n}:{_num(known[n][0])},{_num(known[n][1])}" for n in pos)
        return tag.replace(f'nodes="{raw}"', f'nodes="{nodes}"', 1)

    return [GRAPH_TAG.sub(pin, page) for page in pages]
