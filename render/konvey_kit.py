"""Data-driven builders for generated scenes (ObjectSpec kinds bars/galton/tiles).

Agent 2 puts the real values in ``objects[].data``; Agent 3 passes them here
instead of hand-building rectangles and inventing heights, ball counts or
partitions. Everything uses ``Text`` (not ``Tex``) so it renders without LaTeX.

    chart = BarChart(["WEARY", "SLATE"], [4.9, 5.8], value_suffix=" bits")
    board = GaltonBoard(rows=5)
    paths = board.simulate(64, seed=1)           # list of [+1/-1, ...]
    self.play(board.drop_balls(paths))           # balls fall + stack by count
    tiles = WordTiles("CRANE", "xyxgx")          # g=green y=yellow x=grey
"""

from __future__ import annotations

import random
from math import comb

from manimlib import *  # noqa: F401,F403

TILE_COLORS = {"g": "#6AAA64", "y": "#C9B458", "x": "#3A3A3C"}


def _fmt(value, fmt: str) -> str:
    return fmt.format(value) if isinstance(value, (int, float)) else str(value)


class BarChart(VGroup):
    """Labelled bars whose heights are proportional to ``values``.

    ``.bars``, ``.labels`` and ``.value_labels`` are aligned VGroups, so a beat
    can highlight ``chart.bars[i]`` or transform one chart into another.
    """

    def __init__(
        self,
        labels,
        values,
        max_height: float = 3.5,
        bar_width: float = 0.8,
        buff: float = 0.3,
        color=BLUE,
        value_fmt: str = "{:g}",
        value_suffix: str = "",
        font_size: int = 28,
        show_values: bool = True,
        **kwargs,
    ):
        if len(labels) != len(values):
            raise ValueError(f"BarChart: {len(labels)} labels but {len(values)} values")
        top = max(abs(v) for v in values) or 1
        self.labels = VGroup(*(Text(str(lab), font_size=font_size) for lab in labels))
        self.value_labels = VGroup(*(
            Text(_fmt(v, value_fmt) + value_suffix, font_size=font_size) for v in values
        ))
        # Widen gaps so neither the labels nor the value labels collide.
        widest = max(m.get_width() for m in [*self.labels, *self.value_labels])
        buff = max(buff, widest - bar_width + 0.2)
        self.bars = VGroup(*(
            Rectangle(width=bar_width, height=max(max_height * abs(v) / top, 1e-3))
            .set_fill(color, 0.8).set_stroke(WHITE, 1)
            for v in values
        ))
        self.bars.arrange(RIGHT, buff=buff, aligned_edge=DOWN)
        for bar, lab in zip(self.bars, self.labels):
            lab.next_to(bar, DOWN, buff=0.15)
        parts = [self.bars, self.labels]
        for bar, val in zip(self.bars, self.value_labels):
            val.next_to(bar, UP, buff=0.1)
        if show_values:
            parts.append(self.value_labels)
        super().__init__(*parts, **kwargs)
        self.values = list(values)


class GaltonBoard(VGroup):
    """Triangular peg board with ``rows`` rows and ``rows + 1`` buckets.

    Bucket ``k`` collects balls with ``k`` right-bounces, i.e. sum ``2k - rows``
    of the +1/-1 hops. ``.bucket_labels`` shows those sums.
    """

    def __init__(self, rows: int = 5, spacing: float = 0.6, peg_radius: float = 0.06,
                 bucket_height: float = 2.0, font_size: int = 24, **kwargs):
        self.rows = rows
        self.spacing = spacing
        self.pegs = VGroup()
        for r in range(rows):
            for i in range(r + 1):
                x = (i - r / 2) * spacing
                y = -r * spacing * 0.866
                self.pegs.add(Dot([x, y, 0], radius=peg_radius))
        floor_y = -rows * spacing * 0.866
        self.bucket_centers = [
            np.array([(k - rows / 2) * spacing, floor_y - bucket_height / 2, 0]) for k in range(rows + 1)
        ]
        self.buckets = VGroup(*(
            Rectangle(width=spacing * 0.9, height=bucket_height).move_to(c).set_stroke(GREY_B, 2)
            for c in self.bucket_centers
        ))
        self.bucket_labels = VGroup(*(
            Text(f"{2 * k - rows:+d}" if 2 * k != rows else "0", font_size=font_size)
            .next_to(b, DOWN, buff=0.1)
            for k, b in enumerate(self.buckets)
        ))
        super().__init__(self.pegs, self.buckets, self.bucket_labels, **kwargs)

    def peg_point(self, row: int, index: int):
        """Center of peg ``index`` in ``row`` (0-based), following this board's transform."""
        return self.pegs[row * (row + 1) // 2 + index].get_center()

    def simulate(self, n_balls: int, seed: int = 0) -> list[list[int]]:
        rng = random.Random(seed)
        return [[rng.choice((-1, 1)) for _ in range(self.rows)] for _ in range(n_balls)]

    def counts(self, paths) -> list[int]:
        out = [0] * (self.rows + 1)
        for steps in paths:
            out[sum(1 for s in steps if s > 0)] += 1
        return out

    def expected_counts(self, n_balls: int) -> list[float]:
        """Binomial expectation n * C(rows, k) / 2^rows (Pascal's triangle row)."""
        return [n_balls * comb(self.rows, k) / 2 ** self.rows for k in range(self.rows + 1)]

    def ball_path(self, steps) -> VMobject:
        """Polyline from above the top peg, peg to peg, into the bucket for ``steps``."""
        idx = 0
        top = self.peg_point(0, 0)
        points = [top + UP * self.spacing * 0.8, top]
        for r, s in enumerate(steps[:-1]):
            idx += 1 if s > 0 else 0
            points.append(self.peg_point(r + 1, idx))
        k = sum(1 for s in steps if s > 0)
        bucket = self.buckets[k]
        points.append(bucket.get_top())
        return VMobject().set_points_as_corners(points)

    def drop_balls(self, paths, ball_radius: float | None = None, color=YELLOW,
                   run_time: float = 4.0, lag_ratio: float | None = None) -> Animation:
        """Animate every ball along its path, landing stacked in its bucket.

        After the animation, ``self.balls`` holds the stacked balls (add or
        fade them like any other mobject).
        """
        # Shrink balls so the fullest bucket's stack still fits inside it.
        fullest = max(self.counts(paths)) or 1
        fit = self.buckets[0].get_height() / (2 * fullest)
        r = min(ball_radius or self.spacing * 0.12, fit)
        heights = [0] * (self.rows + 1)
        self.balls = VGroup()
        anims = []
        for steps in paths:
            k = sum(1 for s in steps if s > 0)
            path = self.ball_path(steps)
            bottom = self.buckets[k].get_bottom()
            rest = bottom + UP * (r + heights[k] * 2 * r)
            heights[k] += 1
            path.add_line_to(rest)
            ball = Dot(radius=r).set_color(color).move_to(path.get_start())
            self.balls.add(ball)
            anims.append(MoveAlongPath(ball, path, run_time=1.0))
        lag = lag_ratio if lag_ratio is not None else min(0.5, 2.0 / max(len(paths), 1))
        return LaggedStart(*anims, lag_ratio=lag, run_time=run_time)


class WordTiles(VGroup):
    """Row of letter tiles; ``pattern`` colors them g=green, y=yellow, x=grey."""

    def __init__(self, word: str, pattern: str | None = None, size: float = 0.7,
                 buff: float = 0.1, font_size: int = 36, **kwargs):
        if pattern is not None and len(pattern) != len(word):
            raise ValueError(f"WordTiles: pattern {pattern!r} length != word {word!r}")
        tiles = []
        for i, ch in enumerate(word.upper()):
            sq = Square(side_length=size).set_stroke(GREY_B, 2)
            if pattern:
                sq.set_fill(TILE_COLORS[pattern[i].lower()], 1)
            letter = Text(ch, font_size=font_size).move_to(sq)
            tiles.append(VGroup(sq, letter))
        super().__init__(*tiles, **kwargs)
        self.arrange(RIGHT, buff=buff)
        self.word = word.upper()
        self.pattern = pattern


def value_label(label: str, value, fmt: str = "{:g}", suffix: str = "", font_size: int = 36) -> Text:
    """``Text('label: value')`` with consistent number formatting."""
    return Text(f"{label}: {_fmt(value, fmt)}{suffix}", font_size=font_size)
