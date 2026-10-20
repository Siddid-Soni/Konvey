"""SpeechScene: a StageScene whose beats are timed by their narration audio.

A beat with ``speech="S1-b03"`` plays ``audio/S1-b03.wav`` (next to the beat file) from the
start of its transition, and holds until the clip has ended plus a short pad. Beats without
``speech`` keep StageScene's timing.
"""

from __future__ import annotations

import json
from pathlib import Path

from konvey.stage.scene import StageScene

PAD = 0.5   # seconds of silence after a line before the next beat starts moving


class SpeechScene(StageScene):
    def setup(self):
        super().setup()
        run = Path(self.beats_file).parent
        self.speech = json.loads((run / "speech.json").read_text())
        self.audio_dir = run / "audio"
        self._beat_start = 0.0   # the next beat's transition starts where the last hold ended

    def _hold(self, b, on_screen, nodes, ws, cs):
        sid = b.attrs.get("speech")
        if sid and sid in self.speech:
            spent = self.time - self._beat_start          # transition already played
            self.add_sound(str(self.audio_dir / f"{sid}.wav"), time_offset=-spent)
            b.attrs["hold"] = str(max(0.8, self.speech[sid]["sec"] + PAD - spent))
        super()._hold(b, on_screen, nodes, ws, cs)
        self._beat_start = self.time
