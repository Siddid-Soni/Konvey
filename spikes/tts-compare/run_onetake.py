"""Voices all test lines in ONE take (cohesive pitch/energy/pace), then cuts it back into lines.

Cuts come from Whisper word timestamps matched to the known text: each boundary sits in the gap
between a line's last word and the next line's first word (pauses inside a line can't fool it).
Writes <name>-onetake.wav (the take) and <name>-onetake-cut.wav (cut, rejoined with the usual gaps).
Usage: run_onetake.py qwen paige-mono dynamo-mono  |  run_onetake.py cut kitten-paige-mono"""

import difflib
import re
import sys
import time
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
from common import LINES, OUT, save, words  # noqa: E402

engine, names = sys.argv[1], sys.argv[2:]
TEXT = " ".join(LINES)


def cut(audio, sr):
    """Splits the take at line boundaries found from word timestamps."""
    from faster_whisper import WhisperModel
    w = WhisperModel("small.en", device="cpu", compute_type="int8")
    segs, _ = w.transcribe(librosa.resample(audio, orig_sr=sr, target_sr=16000), word_timestamps=True, beam_size=5)
    heard = [(w_, x.start, x.end) for s in segs for x in s.words for w_ in words(x.word)]
    # align text words to heard words; a line starts at the heard word its first text word maps to
    text = words(TEXT)
    to_heard = {}
    for a, b, n in difflib.SequenceMatcher(a=text, b=[h[0] for h in heard], autojunk=False).get_matching_blocks():
        to_heard.update({a + i: b + i for i in range(n)})
    bounds, k = [], 0
    for line in LINES[:-1]:
        k += len(words(line))
        nxt = next(to_heard[i] for i in range(k, len(text)) if i in to_heard)   # first matched word of the next line
        bounds.append(int((heard[nxt - 1][2] + heard[nxt][1]) / 2 * sr))      # mid-gap before it
    edges = [0] + bounds + [len(audio)]
    return [librosa.effects.trim(audio[a:b], top_db=40)[0] for a, b in zip(edges, edges[1:])]


def finish(name, audio, sr, secs):
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    sf.write(OUT / f"{name}-onetake.wav", audio, sr)
    save(f"{name}-onetake-cut", cut(audio, sr), sr, [secs])


if engine == "cut":   # takes voiced elsewhere (e.g. Kitten's env, which has no Whisper)
    for name in names:
        audio, sr = librosa.load(OUT / f"{name}-onetake.wav", sr=None)
        save(f"{name}-onetake-cut", cut(audio, sr), sr, [0])
elif engine == "qwen":
    import torch
    from huggingface_hub import snapshot_download
    from qwen_tts import Qwen3TTSModel
    model = Qwen3TTSModel.from_pretrained(snapshot_download("Qwen/Qwen3-TTS-12Hz-1.7B-Base", local_files_only=True),
                                          device_map="cuda:0", dtype=torch.bfloat16)
    for name in names:
        ref = OUT / "refs" / f"{name}.wav"
        prompt = model.create_voice_clone_prompt(ref_audio=str(ref), ref_text=ref.with_suffix(".txt").read_text().strip())
        t = time.time()
        wavs, sr = model.generate_voice_clone(text=TEXT, language="English", voice_clone_prompt=prompt)
        finish(f"qwen-base-{name}", wavs[0], sr, time.time() - t)
