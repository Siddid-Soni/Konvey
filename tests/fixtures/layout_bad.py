# Deliberately broken layout: label on the curve, formula on the label, note off-frame.
from manim_imports_ext import *
class SingleScene(InteractiveScene):
    def construct(self):
        title = Text("Central Limit Theorem", font_size=60)
        title.to_edge(UP)
        # VO: "Start with a curve."
        axes = Axes((-3, 3), (0, 1), width=8, height=4)
        curve = axes.get_graph(lambda x: np.exp(-x*x), color=YELLOW)
        label = Text("bell curve").move_to(axes.c2p(0, 0.9))
        self.play(Write(title), ShowCreation(axes), ShowCreation(curve), Write(label))
        self.wait()
        # VO: "Now a formula."
        formula = Tex(r"\frac{1}{\sqrt{2\pi}} e^{-x^2/2}", font_size=72)
        formula.next_to(title, DOWN)
        note = Text("this is a very long explanatory sentence that runs off", font_size=40).to_edge(DOWN).shift(3*RIGHT)
        self.play(Write(formula), FadeIn(note))
        self.wait()
