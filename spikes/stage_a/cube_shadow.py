"""Spike A entry point: manimgl cube_shadow.py CubeShadow -w --hd"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from stage.scene import StageScene  # noqa: E402


class CubeShadow(StageScene):
    beats_file = str(HERE / "cube_shadow.html")
