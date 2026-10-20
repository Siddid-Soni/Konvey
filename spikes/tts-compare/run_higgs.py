"""Higgs TTS 3 (transformers port, 8-bit to fit 8 GB): clones line by line, one take, pause tokens, a styled take.
Run with higgs/.venv/bin/python. One-take files are cut afterwards in the qwen env (it has Whisper):
    qwen/.venv/bin/python run_onetake.py cut higgs-paige-mono higgs-dynamo-mono
Usage: run_higgs.py [clone] [pause] [style] [tagged]"""

import sys
import time
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

sys.path.insert(0, str(Path(__file__).parent))
from common import LINES, OUT, save  # noqa: E402

REPO = "multimodalart/higgs-audio-v3-tts-4b-transformers"   # original weights + transformers code (read 2026-10-18)
REFS = ["paige-mono", "dynamo-mono"]
STYLE = "<|emotion:enthusiasm|><|prosody:expressive_high|>"   # delivery tags go at the start

tok = AutoTokenizer.from_pretrained(REPO)
model = AutoModelForCausalLM.from_pretrained(REPO, trust_remote_code=True, device_map="cuda:0",
                                             quantization_config=BitsAndBytesConfig(load_in_8bit=True)).eval()
SR = model.config.sample_rate
which = sys.argv[1:] or ["clone", "pause", "style"]
refs = {}
for name in REFS:
    wav = OUT / "refs" / f"{name}.wav"
    audio, sr = librosa.load(wav, sr=None)
    refs[name] = dict(reference_codes=model._encode_reference(torch.from_numpy(audio), sr),   # encoded once, reused
                      reference_text=wav.with_suffix(".txt").read_text().strip())


def speak(text, ref):
    torch.manual_seed(0)
    with torch.inference_mode():
        return model.generate_speech(text, tok, temperature=0.7, top_p=0.95, **refs[ref]).float().numpy()


if "clone" in which:
    for ref in REFS:
        clips, secs = [], []
        for line in LINES:
            t = time.time()
            clips.append(speak(line, ref)); secs.append(time.time() - t)
        save(f"higgs-{ref}-clone", clips, SR, secs)
        t = time.time()
        sf.write(OUT / f"higgs-{ref}-onetake.wav", speak(" ".join(LINES), ref), SR)
        print(f"higgs-{ref}-onetake: {time.time() - t:.1f}s", flush=True)

if "pause" in which:
    (OUT / "marks").mkdir(exist_ok=True)
    for name, mark in (("space", "{} "), ("pause-tag", "{} <|prosody:pause|> "), ("long-pause-tag", "{} <|prosody:long_pause|> ")):
        sf.write(OUT / "marks" / f"higgs-paige-{name}.wav", speak("".join(mark.format(l) for l in LINES[:-1]) + LINES[-1], "paige-mono"), SR)
        print(f"higgs marks {name} written", flush=True)

if "tagged" in which:   # every fitting tag, per sentence (tagged.json), one take per voice
    import json
    text = " ".join(json.loads((Path(__file__).parent / "tagged.json").read_text())["higgs"])
    for ref in REFS:
        sf.write(OUT / f"higgs-{ref}-tagged-onetake.wav", speak(text, ref), SR)
        print(f"higgs-{ref}-tagged-onetake written", flush=True)

if "style" in which:
    for ref in REFS:
        sf.write(OUT / f"higgs-{ref}-styled-onetake.wav", speak(STYLE + " ".join(LINES), ref), SR)
        print(f"higgs-{ref}-styled-onetake written", flush=True)
