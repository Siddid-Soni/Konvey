"""``<simview sim="simId" show="phase|graph">``: another view of a model ``<sim>`` (its velocity or
phase plane, a graph over time), driven by the same timeline, so the two move in step.
``show="graph" y="spread, far"``: any of the model's live numbers over time, drawn as the clock
runs (time axis to the furthest time any beat reaches); ``ref="sqrt(t)"`` adds a dashed curve
in t to compare against (scaled as given, in the same units as the numbers).
``konvey.stage.models``; the <sim> display's prepare links the two."""

from __future__ import annotations

from .. import Display

DISPLAY = Display(tag="simview", order=151, shrink=0.6, grow=True, steady=True)
