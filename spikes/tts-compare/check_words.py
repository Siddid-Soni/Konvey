"""Transcribes every sample and prints its word error rate against the test lines (catches garbling or skips)."""

import re
import sys
from pathlib import Path

import librosa
from faster_whisper import WhisperModel

sys.path.insert(0, str(Path(__file__).parent))
from common import LINES, OUT  # noqa: E402

NUM = {"36": "thirty six", "7": "seven", "6": "six"}


def words(t):
    t = re.sub(r"\d+", lambda m: NUM.get(m.group(), m.group()), t.lower().replace("-", " "))
    return re.findall(r"[a-z']+", t)


def wer(ref, hyp):
    d = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, d[0] = d[0], i
        for j, h in enumerate(hyp, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r != h))
    return d[-1] / len(ref)


model = WhisperModel("small.en", device="cpu", compute_type="int8")
ref = words(" ".join(LINES))
for wav in sorted(OUT.glob("*.wav")):
    if wav.stem == "paige-ref":
        continue
    segs, _ = model.transcribe(librosa.load(wav, sr=16000)[0], beam_size=5)
    hyp = " ".join(s.text for s in segs)
    print(f"{wav.stem:32s} WER {wer(ref, words(hyp)):5.1%}")
