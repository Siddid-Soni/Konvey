# Same content as layout_bad.py, laid out with the region helper from manim-reference/spatial-layout.md.
from manim_imports_ext import *

REGIONS = {
    "TITLE": (3.3 * UP, 13, 0.9), "MAIN": (0.3 * DOWN, 12, 5.0),
    "LEFT": (3.4 * LEFT + 0.3 * DOWN, 6.2, 5.0), "RIGHT": (3.4 * RIGHT + 0.3 * DOWN, 6.2, 5.0),
    "CAPTION": (3.3 * DOWN, 13, 0.9),
}

def place(mob, region):
    center, w, h = REGIONS[region]
    mob.set_max_width(w).set_max_height(h).move_to(center)
    return mob


class SingleScene(InteractiveScene):
    def construct(self):
        title = place(Text("Central Limit Theorem", font_size=60), "TITLE")
        # VO: "Start with a curve."
        axes = Axes((-3, 3), (0, 1), width=8, height=4)
        curve = axes.get_graph(lambda x: np.exp(-x*x), color=YELLOW)
        plot = place(VGroup(axes, curve), "LEFT")
        label = Text("bell curve", font_size=30).next_to(curve, UP, buff=0.25)
        self.play(Write(title), ShowCreation(axes), ShowCreation(curve), Write(label))
        self.wait()
        # VO: "Now a formula."
        formula = place(Tex(r"\frac{1}{\sqrt{2\pi}} e^{-x^2/2}", font_size=72), "RIGHT")
        note = place(Text("this is a very long explanatory sentence that runs off", font_size=40), "CAPTION")
        self.play(Write(formula), FadeIn(note))
        self.wait()

