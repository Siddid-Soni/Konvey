"""Example 05 S2 — flip + slide offsets, then bars (dice.py + discrete.py idiom)."""
from manim_imports_ext import *


class SingleScene(InteractiveScene):
    def construct(self):
        top_row = VGroup(*[Text(str(i)) for i in range(1, 7)])
        low_row = VGroup(*[Text(str(i)) for i in range(6, 0, -1)])
        top_row.arrange(RIGHT, buff=0.3)
        low_row.next_to(top_row, DOWN, buff=0.6)
        self.add(top_row, low_row)
        # VO: "Flip the second row, slide it; each offset reveals one sum's pairs."
        self.play(low_row.animate.shift(2 * RIGHT), run_time=2)
        self.wait()
        pair_rect = SurroundingRectangle(VGroup(top_row[0], low_row[-1]), buff=0.1)
        pair_rect.set_stroke(YELLOW, 2)
        self.play(ShowCreation(pair_rect))
        self.wait()
        # VO: "Weighted dice: multiply each pair, add them; bars are the convolution."
        bars = VGroup(*[Rectangle(width=0.4, height=0.3 * (i + 1)) for i in range(6)])
        bars.arrange(RIGHT, buff=0.05)
        bars.next_to(low_row, DOWN, buff=0.8)
        labels = VGroup(*[DecimalNumber(0.1 * (i + 1)) for i in range(6)])
        for label, bar in zip(labels, bars):
            label.next_to(bar, UP, SMALL_BUFF)
            label.set_max_width(0.7 * bar.get_width())
        self.play(LaggedStartMap(FadeIn, bars, shift=UP, lag_ratio=0.1))
        self.play(Write(labels))
        self.wait()
