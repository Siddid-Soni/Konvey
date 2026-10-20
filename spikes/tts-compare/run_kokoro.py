"""Kokoro-82M preset voices on the test lines. Run with kokoro/.venv/bin/python."""

import sys
import time

import numpy as np
from kokoro import KPipeline

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import LINES, save  # noqa: E402

VOICES = ["af_heart", "af_bella", "af_nicole", "bf_emma", "am_michael", "bm_george"]

pipes = {"a": KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M"),
         "b": KPipeline(lang_code="b", repo_id="hexgrad/Kokoro-82M")}
for voice in VOICES:
    clips, secs = [], []
    for text in LINES:
        t = time.time()
        clips.append(np.concatenate([r.audio.numpy() for r in pipes[voice[0]](text, voice=voice, speed=1.0)]))
        secs.append(time.time() - t)
    save(f"kokoro-{voice}", clips, 24000, secs)
