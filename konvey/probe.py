"""Whether the headless runtime check can run here.

konvey.stage.check lays each scene out with Chromium and plays it with manimgl, which is in
the ``render`` dependency group (uv run --group render --group layout ...).
"""

from __future__ import annotations


def probe_available() -> bool:
    import importlib.util

    return importlib.util.find_spec("manimlib") is not None
