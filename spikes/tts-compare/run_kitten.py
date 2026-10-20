"""KittenTTS 2: preset voices, cloning (5-30 s references), one take cut into lines, and its <pause> tag.
Run with kitten/.venv/bin/python. Usage: run_kitten.py [presets] [clone] [pause] [tagged]"""

import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from kittenml import KittenTTS

sys.path.insert(0, str(Path(__file__).parent))
from common import LINES, OUT, save  # noqa: E402

PRESETS = ["Bella", "Luna", "Rosie", "Jasper", "Bruno", "Hugo", "Victor"]
REFS = ["paige-mono", "dynamo-mono"]   # Kitten clones from 5-30 s; the "all"/"short" references are longer

m = KittenTTS("KittenML/kitten-tts-2")
which = sys.argv[1:] or ["presets", "clone", "pause"]


def lines_one_by_one(name, **voice):
    clips, secs = [], []
    for line in LINES:
        t = time.time()
        clips.append(m.generate(line, **voice)); secs.append(time.time() - t)
    save(name, clips, m.sample_rate, secs)


if "presets" in which:
    for v in PRESETS:
        lines_one_by_one(f"kitten-{v.lower()}", voice=v)

if "clone" in which:
    for ref in REFS:
        wav = OUT / "refs" / f"{ref}.wav"
        voice = dict(reference=str(wav), reference_text=wav.with_suffix(".txt").read_text().strip())
        lines_one_by_one(f"kitten-{ref}-clone", **voice)
        # one take; cut it with: qwen/.venv/bin/python run_onetake.py cut kitten-<ref> (needs Whisper)
        sf.write(OUT / f"kitten-{ref}-onetake.wav", np.asarray(m.generate(" ".join(LINES), **voice), dtype=np.float32), m.sample_rate)

if "tagged" in which:   # every fitting tag (tagged.json), one take per clone, expressive preset (tags need it)
    import json
    text = "\n".join(json.loads((Path(__file__).parent / "tagged.json").read_text())["kitten"])   # one leading tag per line
    for ref in REFS:
        wav = OUT / "refs" / f"{ref}.wav"
        audio = m.generate(text, reference=str(wav), reference_text=wav.with_suffix(".txt").read_text().strip(), preset="expressive")
        sf.write(OUT / f"kitten-{ref}-tagged-onetake.wav", np.asarray(audio, dtype=np.float32), m.sample_rate)
        print(f"kitten-{ref}-tagged-onetake written", flush=True)

if "pause" in which:   # does <pause> at line ends give a real hold? (measured in test_breaks-style below)
    (OUT / "marks").mkdir(exist_ok=True)
    wav = OUT / "refs" / "paige-mono.wav"
    voice = dict(reference=str(wav), reference_text=wav.with_suffix(".txt").read_text().strip())
    for name, mark in (("space", "{} "), ("pause-tag", "{} <pause> ")):
        audio = m.generate("".join(mark.format(l) for l in LINES[:-1]) + LINES[-1], **voice)
        sf.write(OUT / "marks" / f"kitten-paige-{name}.wav", np.asarray(audio, dtype=np.float32), m.sample_rate)
        print(f"kitten marks {name} written", flush=True)
