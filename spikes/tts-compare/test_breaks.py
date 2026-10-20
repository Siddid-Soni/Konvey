"""Does a line-end mark ("...", dashes, newlines) make the model hold longer at line ends than at sentence ends inside a line?
Voices the test lines in one take per mark (paige-mono, qwen) and measures pauses from word timestamps."""

import difflib
import sys
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
import torch
from faster_whisper import WhisperModel
from huggingface_hub import snapshot_download
from qwen_tts import Qwen3TTSModel

sys.path.insert(0, str(Path(__file__).parent))
from common import LINES, OUT, words  # noqa: E402

# how each line END is marked before the lines are joined into one take (the tokenizers have no pause token;
# "...", dashes and newlines are ordinary text tokens in Qwen)
MARKS = {"space": "{} ", "newline": "{}\n", "paragraph": "{}\n\n", "dots": "{} ... ", "emdash": "{}— ", "spaced-emdash": "{} — "}
engine = sys.argv[1] if len(sys.argv) > 1 else "qwen"
pick = sys.argv[2:] or list(MARKS)   # with engine "measure": file stems in out/tts-compare/marks
ref = OUT / "refs" / "paige-mono.wav"
ref_text = ref.with_suffix(".txt").read_text().strip()
if engine == "qwen":
    model = Qwen3TTSModel.from_pretrained(snapshot_download("Qwen/Qwen3-TTS-12Hz-1.7B-Base", local_files_only=True),
                                          device_map="cuda:0", dtype=torch.bfloat16)
    prompt = model.create_voice_clone_prompt(ref_audio=str(ref), ref_text=ref_text)

    def take(text):
        torch.manual_seed(0)
        wavs, sr = model.generate_voice_clone(text=text, language="English", voice_clone_prompt=prompt)
        return np.asarray(wavs[0], dtype=np.float32), sr

(OUT / "marks").mkdir(exist_ok=True)
whisper = WhisperModel("small.en", device="cpu", compute_type="int8")
text, line_end, sentence_end = [], set(), set()   # script words; indexes of words ending a line / a sentence inside one
for n, line in enumerate(LINES):
    for token in line.split():
        text += words(token)
        if token[-1] in ".?!:" and token != line.split()[-1]:
            sentence_end.add(len(text) - 1)
    if n < len(LINES) - 1:
        line_end.add(len(text) - 1)
for name in pick:
    if engine == "measure":   # takes voiced elsewhere (e.g. Kitten's env)
        audio, sr = librosa.load(OUT / "marks" / f"{name}.wav", sr=None)
    else:
        audio, sr = take("".join(MARKS[name].format(line) for line in LINES[:-1]) + LINES[-1])
        sf.write(OUT / "marks" / f"{engine}-paige-{name}.wav", audio, sr)
    segs, _ = whisper.transcribe(librosa.resample(audio, orig_sr=sr, target_sr=16000),
                                 word_timestamps=True, beam_size=5)
    heard = [(w, x.start, x.end) for s in segs for x in s.words for w in words(x.word)]
    to_heard = {}
    for a, b, k in difflib.SequenceMatcher(a=text, b=[h[0] for h in heard], autojunk=False).get_matching_blocks():
        to_heard.update({a + i: b + i for i in range(k)})
    gap = lambda ids: [round(heard[to_heard[i] + 1][1] - heard[to_heard[i]][2], 2)  # noqa: E731
                       for i in sorted(ids) if i in to_heard and to_heard[i] + 1 < len(heard)]
    ends, inside = [float(x) for x in gap(line_end)], gap(sentence_end)
    print(f"{engine} {name:13s} line ends {ends} (mean {np.mean(ends):.2f})   inside lines mean {np.mean(inside):.2f}"
          f"   words heard {len(heard)}/{len(text)}", flush=True)
