# TTS trial (2026-10-18): Kokoro, Qwen3-TTS, KittenTTS 2, Higgs TTS 3 (Breeze TTS 2 tried and removed)

Same four lines (`lines.json`) through each model; listen at `out/tts-compare/index.html`.
Kept apart from Konvey's `.venv` (Chatterbox needs transformers 5, qwen-tts pins 4.57.3):

    (cd kokoro && uv sync); (cd qwen && uv sync)          # two trial envs
    kokoro/.venv/bin/python run_kokoro.py                  # 6 preset voices
    qwen/.venv/bin/python transcribe_ref.py                # paige-ref.txt, needed for cloning
    qwen/.venv/bin/python run_qwen.py [custom] [clone]     # CustomVoice presets; Base clones Paige
    qwen/.venv/bin/python check_words.py                   # Whisper WER per sample
    kokoro/.venv/bin/python make_page.py

- Breeze TTS 2 was tried and removed (user: not working; 7 GB backbone overfilled the 8 GB card, codec had to run on CPU).
- Qwen CustomVoice and Base can't share one process on 8 GB; `run_qwen.py` frees one before the next.

## References and cohesion (2026-10-18, later)
- `fetch_convo_lines.py paige dynamo` -> out/voice-lines/<hero>/ (conversation lines + exact transcripts);
  `make_picker.py` -> out/voice-lines/index.html to pick lines by ear (auto-ranking by pitch picked bad lines).
- `ref_picks.json` (user's picks by number) -> `build_refs.py` -> out/tts-compare/refs/<name>.{wav,txt}.
- Per-line voicing sounds non-cohesive (user). `run_onetake.py` voices all lines in one take and cuts
  at Whisper word timestamps aligned to the known text (difflib), mid-gap before each line's first word.
  Checked: all cuts land between the right words. Whisper drops words at an abrupt clip start, so pad
  with ~1 s silence when transcribing a cut piece.

## KittenTTS 2 and Higgs TTS 3
    (cd kitten && uv sync); (cd higgs && uv sync)
    kitten/.venv/bin/python run_kitten.py [presets] [clone] [pause]
    higgs/.venv/bin/python run_higgs.py [clone] [pause] [style]       # 8-bit (bitsandbytes) to fit 8 GB
    qwen/.venv/bin/python run_onetake.py cut kitten-paige-mono higgs-paige-mono ...   # cut their one-takes
    qwen/.venv/bin/python test_breaks.py measure higgs-paige-pause-tag ...           # pause lengths
- Kitten: clones from 5-30 s; splits text over ~380 chars into chunks joined by 0.16 s gaps (seams in long takes).
  `<pause>` lengthens line-end pauses 0.93 -> 1.57 s. Emotions as a leading `[excited]` etc.
- Higgs: runs through multimodalart/higgs-audio-v3-tts-4b-transformers (original weights + 2 code files, read before
  running: torch/transformers only). Up to 2048 frames (~82 s) per take. Real pause tokens: `<|prosody:pause|>`
  0.44 -> 0.81 s, `<|prosody:long_pause|>` -> 2.35 s at line ends; inside-line pauses unchanged. 21 emotions,
  speed/pitch, sfx. RTF ~2 at 8-bit on the 3070 Ti.
