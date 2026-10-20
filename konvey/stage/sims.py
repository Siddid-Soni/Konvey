"""Simulation rules for ``<sim>`` (pure Python: the renderer, the checker and the planner share them).

Every rule is seeded, so the video, the readouts and any check compute the same numbers.

- ``drop``: balls fall through ``rows`` rows of pegs, going left or right at each peg with
  probability ``p`` (½), and land in one of ``rows + 1`` bins (a Galton board). ``drop_runs``
  gives each ball's left/right choices and its bin.
- ``trials``: a list of cases written out (every outcome of a small experiment, or a sample of
  them), some of which count (``hits``); the montage shows them one after another and tallies.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .tree import BeatError

MAX_BALLS = 2000
MAX_ROWS = 16
MAX_CASES = 64


@dataclass(frozen=True)
class Run:
    moves: tuple[int, ...]   # 0 = left, 1 = right, one per row of pegs
    bin: int                 # = sum(moves)


def drop_runs(rows: int, balls: int, seed: int = 1, p: float = 0.5) -> list[Run]:
    """The first ``balls`` balls of a board with ``rows`` rows; ball k is the same ball for any
    ``balls`` ≥ k (one stream per seed), so later beats only add balls."""
    rng = random.Random(seed)
    out = []
    for _ in range(balls):
        moves = tuple(1 if rng.random() < p else 0 for _ in range(rows))
        out.append(Run(moves, sum(moves)))
    return out


def bin_counts(rows: int, balls: int, seed: int = 1, p: float = 0.5) -> list[int]:
    counts = [0] * (rows + 1)
    for r in drop_runs(rows, balls, seed, p):
        counts[r.bin] += 1
    return counts


def _int(attrs: dict, key: str, default: int, lo: int, hi: int, where: str) -> int:
    raw = str(attrs.get(key, default)).strip()
    try:
        v = int(raw)
    except ValueError:
        raise BeatError(f'{where} {key}="{raw}": a whole number') from None
    if not lo <= v <= hi:
        raise BeatError(f'{where} {key}="{raw}": between {lo} and {hi}')
    return v


@dataclass(frozen=True)
class Drop:
    rows: int
    balls: int
    seed: int
    p: float


def drop_spec(attrs: dict, where: str) -> Drop:
    rows = _int(attrs, "rows", 8, 1, MAX_ROWS, where)
    balls = _int(attrs, "balls", 0, 0, MAX_BALLS, where)
    seed = _int(attrs, "seed", 1, 0, 10**9, where)
    try:
        p = float(attrs.get("p", 0.5))
    except ValueError:
        raise BeatError(f'{where} p="{attrs.get("p")}": a probability such as 0.5') from None
    if not 0 < p < 1:
        raise BeatError(f'{where} p="{attrs.get("p")}": between 0 and 1')
    return Drop(rows, balls, seed, p)


@dataclass(frozen=True)
class Trials:
    cases: tuple[tuple[str, ...], ...]   # each case: its tokens ("H", "T", …)
    hits: frozenset[int]
    shown: int


def trials_spec(attrs: dict, where: str) -> Trials:
    raw = attrs.get("cases", "").strip()
    if not raw:
        raise BeatError(f'{where} rule="trials" needs cases="H H T; H T H; …" (one case per ";", '
                        'its parts split by spaces)')
    cases = tuple(tuple(c.split()) for c in raw.split(";") if c.strip())
    if len(cases) > MAX_CASES:
        raise BeatError(f'{where} has {len(cases)} cases; at most {MAX_CASES} stay readable')
    hits = set()
    for h in (x.strip() for x in attrs.get("hits", "").split(",") if x.strip()):
        if not h.isdigit() or int(h) >= len(cases):
            raise BeatError(f'{where} hits="{attrs.get("hits")}": case numbers 0..{len(cases) - 1}')
        hits.add(int(h))
    shown = _int(attrs, "shown", len(cases), 0, len(cases), where)
    return Trials(cases, frozenset(hits), shown)


RULES = ("drop", "trials")
