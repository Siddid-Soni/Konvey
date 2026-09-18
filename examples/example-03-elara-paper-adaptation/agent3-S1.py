"""Example 03 S1 — Elara discovers map (paper Table 2 Frame 1)."""
from manim_imports_ext import *


class SingleScene(InteractiveScene):
    def construct(self):
        # Paper triple normalization: contains -> on top of, stands near -> at left of
        hollow_oak = Rectangle(height=3, width=1.5)
        hollow_oak.move_to(ORIGIN)
        ancient_map = Text("map")
        ancient_map.move_to(hollow_oak.get_center())
        elara = Dot()
        elara.next_to(hollow_oak, LEFT, buff=0.5)
        oak_label = Text("hollow oak")
        oak_label.next_to(hollow_oak, DOWN, buff=0.3)

        # VO: "Elara discovers the ancient map inside the hollow oak."
        self.play(
            LaggedStartMap(FadeIn, VGroup(hollow_oak, ancient_map, elara), shift=UP, lag_ratio=0.2),
            Write(oak_label),
        )
        self.wait()
        self.play(Indicate(elara), FlashAround(ancient_map))
        self.wait()
