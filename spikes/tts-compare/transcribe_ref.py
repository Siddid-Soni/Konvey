"""Writes Paige's reference transcript (paige-ref.txt), which Qwen Base cloning needs."""

import sys
from pathlib import Path

import librosa
from faster_whisper import WhisperModel

sys.path.insert(0, str(Path(__file__).parent))
from common import HERE, PAIGE_REF  # noqa: E402

segments, _ = WhisperModel("small.en", device="cpu", compute_type="int8").transcribe(
    librosa.load(PAIGE_REF, sr=16000)[0], beam_size=5)   # numpy in: faster-whisper's own decoder breaks on this av
text = " ".join(s.text.strip() for s in segments)
(HERE / "paige-ref.txt").write_text(text + "\n")
print(text)
