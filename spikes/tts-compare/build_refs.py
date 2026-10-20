"""Joins hand-picked lines (ref_picks.json, numbers from the picker page) into cloning references:
out/tts-compare/refs/<name>.wav and its exact transcript <name>.txt. Usage: build_refs.py [name ...]"""

import json
import re
import sys
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT, ROOT  # noqa: E402

SR, GAP = 24000, 0.35
picks = {k: v for k, v in json.loads((Path(__file__).parent / "ref_picks.json").read_text()).items() if k[0] != "_"}
refs = OUT / "refs"
refs.mkdir(parents=True, exist_ok=True)
for name, (hero, numbers) in picks.items():
    if sys.argv[1:] and name not in sys.argv[1:]:
        continue
    folder = ROOT / "out" / "voice-lines" / hero
    rows = json.loads((folder / "numbered.json").read_text())
    chosen = [rows[n - 1] for n in numbers]
    gap = np.zeros(int(GAP * SR), dtype=np.float32)
    clips = [librosa.effects.trim(librosa.load(folder / r["file"], sr=SR)[0], top_db=35)[0] for r in chosen]
    audio = np.concatenate([x for c in clips for x in (c, gap)][:-1])
    sf.write(refs / f"{name}.wav", audio / max(1e-6, np.abs(audio).max()) * 0.9, SR)
    # some models read (...) as a sound tag, so asides in brackets become commas
    text = re.sub(r"\s*\(([^)]*)\)\s*", r", \1, ", " ".join(r["text"] for r in chosen))
    text = re.sub(r",\s*,", ",", text)
    (refs / f"{name}.txt").write_text(text + "\n")
    print(f"{name}: {len(audio) / SR:.1f}s from lines {numbers}")
