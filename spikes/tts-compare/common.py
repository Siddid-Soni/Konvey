"""Shared bits for the TTS trial scripts: the test lines and joining one voice's lines into a clip."""

import json
import re
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "out" / "tts-compare"
LINES = json.loads((HERE / "lines.json").read_text())
PAIGE_REF = ROOT / "assets" / "voices" / "paige" / "ref.wav"
GAP = 0.45   # s of silence between lines


def save(name: str, clips: list[np.ndarray], sr: int, seconds: list[float]) -> None:
    """Writes the joined clip to out/tts-compare/<name>.wav and logs generation speed."""
    OUT.mkdir(parents=True, exist_ok=True)
    gap = np.zeros(int(GAP * sr), dtype=np.float32)
    audio = np.concatenate([x for c in clips for x in (np.asarray(c, dtype=np.float32).reshape(-1), gap)][:-1])
    sf.write(OUT / f"{name}.wav", audio, sr)
    dur = len(audio) / sr
    print(f"{name}: {dur:.1f}s audio in {sum(seconds):.1f}s (RTF {sum(seconds) / dur:.2f})", flush=True)


NUMBERS = {"6": "six", "7": "seven", "36": "thirty six", "1": "one"}   # Whisper writes numbers as digits


def words(t):
    t = re.sub(r"\d+", lambda m: NUMBERS.get(m.group(), m.group()), t.lower().replace("-", " "))
    return re.findall(r"[a-z0-9']+", t)
