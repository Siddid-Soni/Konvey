# Speech journey: handoff (2026-10-18)

What we tried to get a good narrator voice, what we measured, and what broke. Written as input
for building our own TTS model.

## Goal
A narrator for short explainer videos that:
- clones a specific character voice (Paige, female, and Dynamo, male, from the game Deadlock),
- sounds lively and natural (an enthusiastic teacher, not a flat reader),
- stays **cohesive** across a whole video: same pitch, energy and pace from line to line,
- lets us place **holds** (pauses) between lines on purpose,
- supports expressive control (emotion, laughs, emphasis) without breaking.

Hardware: Linux laptop, **RTX 3070 Ti Laptop, 8 GB VRAM** (about 7.66 GB usable). This limit shaped
most decisions.

## The core problems (in order of importance)
1. **Per-line voicing is not cohesive.** Each line voiced on its own gets a fresh take: pitch, energy
   and pace reset at every cut. The user hears it clearly. Every model had this problem when voiced
   line by line.
2. **Holds can't come from punctuation.** Models put the same short pause at a line end as at any
   sentence end. `...`, dashes, newlines and blank lines do nothing (measured, below). Only explicit
   pause tokens work, and only some models have them.
3. **Voice-clone quality depends heavily on the reference clip.** Picking references from transcripts
   or acoustic metrics failed. They have to be picked by ear. Natural conversation lines beat game
   callouts like select/unselect or pings.
4. **Expressive tags make autoregressive models unstable** (stop early, loop, or read tags aloud).
5. **8 GB VRAM**: several good models don't fit, or fit only with hacks (8-bit, codec on the CPU).

## Models tried

| Model | Cloning | Verdict | Key facts |
|---|---|---|---|
| Chatterbox Turbo (ResembleAI) | yes | usable, first narrator | temp 1.0; liked a "lively" reference at temp 1.2 with `[advertisement]` tag on the first line |
| Chatterbox original | yes | kept setting | exaggeration 0.8, cfg_weight 0.8; original-model tags only (`[laughter]`, `[sigh]`, `[gasp]`…) |
| VoxCPM2 (openbmb) | yes | **rejected, removed** | per-line pitch jumps; chaining drifted; reads tags aloud |
| Kokoro-82M | **no** (presets only) | fast, no cloning | 50× real time; fine-tune is the only way to get a custom voice |
| Qwen3-TTS 1.7B CustomVoice | no (9 presets) | presets OK | natural-language style instruction; English natives are Ryan, Aiden |
| Qwen3-TTS 1.7B Base | yes | good clone, steady | ignores punctuation for pauses; official single-speaker fine-tune script |
| Breeze TTS 2 (3B) | yes | **removed** | 7 GB backbone overfills 8 GB; codec had to run on the CPU; non-commercial |
| KittenTTS 2 (1.7B) | yes (5–30 s ref) | promising | `<pause>` works; chunks long text (seams); reads some tags aloud |
| Higgs TTS 3 (4B) | yes | best control, unstable | real pause tokens; 21 emotions etc.; 8-bit to fit; ~half of heavily tagged takes fail |

### Chatterbox (first narrator)
- Only the **start of a reference** shapes delivery: about the first 6 s (original model), 15 s (Turbo),
  10 s (decoder). So put the liveliest line first.
- A sound tag at the very end of a line can be **cut off**: the model samples its stop token mid-laugh.
  Keep at least three words after a tag. A lone `[chuckle]` at temp 1.0 is cut short, so doubling it
  (`[chuckle] [chuckle]`) helped.
- Numbers written as digits ("6/9") are read badly. Spell them out in the text sent to TTS ("six ninths").
- Pitch varies about 35 Hz from take to take with the same settings.
- Lesson on references: some downloaded clips named after a hero were actually another character
  speaking *to* that hero. Always listen.

### VoxCPM2 (rejected)
- Voiced per line: pitch **jumped 3.8 semitones** between lines.
- Chaining each line on the previous one (as a continuation prompt) **drifted away** from the
  target voice: speaker similarity 0.93 → 0.80. A two-line window drifted most (→ 0.73).
- Best compromise: every line continues *the first line + the previous line*, with the reference
  attached each time. That gave 1.7-semitone jumps and similarity 0.94 → 0.86. Still not good enough.
- Voicing one long take and **cutting at pauses** failed: pauses inside lines ("...") fooled the cutter.
- Reads `[word]` and `(word)` aloud. A style direction like `(cheerful, energetic)` works only in
  reference-only mode; with a prompt clip it is read aloud.
- Needed `optimize=False` on 8 GB (compiled CUDA graphs ran out of memory).
- User verdict: model not good. Fully removed.

### Kokoro-82M
- Presets only (af_heart, af_bella, af_nicole, bf_emma, am_michael, bm_george tried). Very clean,
  0 to 1.5% WER, about 0.01 RTF on GPU.
- No cloning. Fine-tuning is possible but not officially supported (no released training code).
  Community route: StyleTTS2-based two-stage training (e.g. the kikiri-tts recipe: acoustic/alignment
  stage, then adversarial/prosody stage with a WavLM discriminator).
  - Needs **hours** of clean single-speaker audio. Community fine-tunes used ~700 clips up to ~11 hours.
  - On little data, the adversarial stage added a ~25 ms **echo/comb artifact**; one fine-tune shipped
    an earlier checkpoint because of it.
  - A known trick: generate the training set with a cloning model (one fine-tune used Chatterbox
    clones), then fine-tune Kokoro on that, for a small fast model in the cloned voice.
- Voices are "voicepacks" (per-voice style tensors).

### Qwen3-TTS (1.7B)
- **CustomVoice**: 9 preset speakers, `instruct=` natural-language style ("Cheerful and energetic…").
  The instruction raised WER a little (6% vs 0–1.5%).
- **Base**: cloning from reference audio + its exact transcript. A clone prompt can be built once and
  reused for every line (`create_voice_clone_prompt`), which keeps lines more consistent.
  - Handled a **44 s and a 68 s reference** fine, at the same speed. No documented maximum.
  - RTF ~0.8 on the 3070 Ti (bf16, no flash-attn).
  - Output cap: 8192 frames at 12.5 Hz ≈ 11 min per take.
- **VoiceDesign** model: a voice from a text description, reusable as a clone reference (not tried).
- **Official fine-tuning** (Base, single speaker): JSONL of `{audio, text, ref_audio}` with the same
  `ref_audio` for all rows. `prepare_data.py` adds codec codes, then `sft_12hz.py` trains. The result
  is called like a preset speaker name. The example uses batch 32, lr 2e-6, 10 epochs.
  Full fine-tuning 1.7B needs far more than 8 GB (rented GPU); 0.6B is borderline.
- Tokenizer: Qwen2 BPE, no pause tokens. Punctuation is ordinary tokens.
- CustomVoice and Base can't share one process on 8 GB: free the first model fully before loading the next.

### Breeze TTS 2 (removed)
- About 3B parameters, built on the Qwen3-TTS audio tokenizer. Features: voice clone, voice design,
  "voice direction" (clone + instruction), inline events `(laugh)`, `(sigh)`.
- Needs ~7.7 GiB eager. On 8 GB it ran out of memory until the audio codec was moved to the CPU, which
  gave RTF ~2. Directed takes (cfg 4) ran out of memory with references over ~20 s.
- Reads `(...)` as an event, so bracketed asides in reference transcripts had to become commas.
- Weights are non-commercial. User verdict: not working. Removed.

### KittenTTS 2 (1.7B)
- `pip install kittenml`. 47 voices; clones from **5–30 s** references. RTF ~0.45 on GPU.
- Tags (with `preset="expressive"`): one leading emotion per line `[excited]`, `[contemplative]`,
  `[surprised]`, `[joyful]`…; inline events `<pause>`, `<um>`, `<gasp>`, `<laugh>`, `<sigh>`…;
  emphasis `(((word)))`.
- `<pause>` **works**: line-end pauses went 0.93 → 1.57 s, inside-line pauses unchanged.
- Reads some events **aloud**: `<laugh>` became "laugh"/"lack"; `<gasp>` became "gasp" in one voice.
- **Chunks text** over ~380 characters into separate generations joined with 0.16 s gaps. So long
  takes get seams: the cohesion problem returns at chunk boundaries.
- License: free commercial use under USD 1M revenue/funding.

### Higgs TTS 3 (4B)
- Official serving is SGLang-Omni or vLLM-Omni (Docker). We used a community transformers port
  (original weights + two small code files, which we read before running: torch/transformers only),
  loaded **8-bit with bitsandbytes** to fit 8 GB. RTF ~2. Codec runs in fp32.
- Output cap: 2048 frames at 25 fps ≈ 82 s per take (configurable; context 8192).
- **Real control tokens** (43, single tokens in the tokenizer, `<|category:value|>`):
  - sentence-level (start of a sentence): 21 emotions, `speed_*`, `pitch_high/low`, `expressive_high/low`,
    `whispering/shouting/singing`
  - inline: `<|prosody:pause|>`, `<|prosody:long_pause|>`, sound effects followed by their sound with no
    space (`<|sfx:laughter|>Haha`)
- Pause tokens **work precisely**: line ends 0.44 s → **0.81 s** (pause) → **2.35 s** (long_pause);
  inside-line pauses unchanged.
- **Instability with heavy tagging:**
  - `...` next to tags made it **stop early** (dropped the last third of the text) or **loop**
    ("Haha, that's 1 in 6" repeated for 55 s). Rule: no ellipses in Higgs text.
  - Even without ellipses, one voice failed on 2 of 4 seeds (one stopped early, one looped to the cap).
  - So any use needs a **completeness check** (transcribe, compare with the script) and **retry**.
- When it works, the laugh renders as a real laugh and whispering comes through.
- License: research/non-commercial, plus a free creator grant for monetized videos if Boson AI is credited.

## Measurements

### Line-end holds by text mark (one take, 4 lines, Paige clone)
Average pause at the 3 line ends vs sentence ends inside lines:

| Mark at line end | Qwen Base | Breeze | Kitten | Higgs |
|---|---|---|---|---|
| space (baseline) | 0.29 s | 0.55 s | 0.93 s | 0.44 s |
| newline | 0.31 | 0.77 | | |
| blank line | 0.29 | 0.69 | | |
| ` ...` | 0.32 | 0.58 | | |
| `—` / ` —` | 0.25 / 0.36 | 0.53 / 0.54 | | |
| pause tag | none exists | none exists | **1.57** (`<pause>`) | **0.81** / **2.35** (pause / long_pause) |
| *inside-line sentence ends* | *0.35–0.45* | *0.47–0.66* | *0.68–0.77* | *0.47–0.60* |

Single takes each, so differences of about 0.1 s may be noise.

### Intelligibility
Whisper (small.en) WER against the script was 0–7.6% for every sample of every model. Intelligibility
was never the problem; voice match, cohesion and expressiveness were.

## The one-take + cut approach (best answer to cohesion so far)
Voice a whole passage in **one take** (cohesive by construction), then cut it back into lines:
- Transcribe the take with Whisper **word timestamps**. Align the known script words to the heard
  words with a sequence matcher (difflib). Each cut goes mid-gap before the first word of the next line.
- Normalize numbers both ways first (Whisper writes "6", the script says "six"), or alignment slips.
- Checked on 4 takes × 4 lines: all 16 cuts landed between the right words.
- Gotcha: Whisper **drops words at an abrupt clip start**. When verifying a cut piece, pad it with ~1 s
  of silence or it looks like the cut lost words when it didn't.
- After cutting, the gap between lines can be set to anything (per-line holds), independent of the model.
- Limits: the take length cap (Kitten chunks at ~380 chars; Higgs ~82 s; Qwen ~11 min), and long
  takes risk early stop/looping on unstable models.

## Data we found (for cloning references and fine-tuning)
- **deadlock.vlviewer.com** (fan site) has every voice line with exact transcripts:
  - `https://deadlock.vlviewer.com/characters/<hero>.json` lists `interactions` (lines with text,
    category, filename) and `conversations` (each with a `jsonPath` to the full dialogue, with per-line
    speaker, text, filename).
  - Its own audio CDN is addressed by sha256 (`cdn.vlviewer.com/deadlock/audio/sha256/<2>/<hash>.mp3`),
    and the hash list wasn't easy to reach.
- **deadlock.wiki** has the same files (capitalized file name), with URLs and durations from its API:
  `https://deadlock.wiki/api.php?action=query&titles=File:<Name>.mp3|...&prop=imageinfo&iiprop=url&format=json`
  (50 titles per request). The CDN wants a browser user agent and a referer.
- **Paige**: 1,561 lines with transcripts, about 26+ minutes in total, median **1.2 s** per line. Only
  26 lines are 3 s or longer. Mostly pings and combat callouts. **98 conversation lines** (more natural).
- **Dynamo**: 1,666 lines; **232 conversation lines** across 118 conversations.
- For fine-tuning, the real data is **too little and too clipped** (game callouts, ~26 min). Realistic
  path: real lines + synthetic narration-style lines from the best clone.

## Reference picking (lessons)
- Automatic ranking by pitch movement picked emotional but wrong lines (sad, flat). Picking by text
  tone also picked bad audio. **The user's ear is the only reliable judge.** A local page with a
  player per line, numbered and longest first, with tick boxes building a "hero: 1, 3, 6" list in
  click order, worked well.
- User picks (by number, longest first, 1.5 s+ conversation lines):
  - Paige: 1, 3, 6, 8, 17, 42 (line 1 is a 17 s chatty monologue, the best single reference)
  - Dynamo: 1, 2, 3, 12, 13, 18, 8, 5
- Built three references per voice: all picks joined (44 s / 68 s), the single longest line ("mono",
  17 s / 13 s), and a short ~18–24 s set. Joined with 0.35 s gaps, silence trimmed (top_db 35),
  normalized to 0.9 peak, with the exact concatenated transcript.

## Engineering problems hit (and fixes)
- **Dependency conflicts**: Chatterbox needs transformers 5; qwen-tts pins 4.57.3; Higgs port needs
  ≥ 5.5. Fix: a separate small uv project (own `.venv`) per model family.
- **8 GB VRAM**: free each model fully before loading the next (`del model; gc.collect();
  torch.cuda.empty_cache()`; a helper function holding the reference doesn't free it). Breeze needed
  the codec on the CPU; Higgs needed 8-bit; directed/cfg runs double memory.
- **Hugging Face downloads stalled** with 5 repos in parallel; downloading one at a time worked.
  Some libraries call the HF API even with weights cached; passing the local snapshot path fixed it.
- **faster-whisper**: its PyAV decoder broke (`metadata_errors` kwarg) → load audio with librosa and
  pass numpy. CUDA build wanted `libcublas.so.12` → ran on the CPU (int8), fine for short clips.
- **Killing processes by pattern** (`pkill -f`) also killed the shell running the command.
- `trust_remote_code` models: read the repo's `.py` files before running.

## Open questions for building our own model
- Cohesion: should the model generate a whole scene (long context) with line-boundary markers and
  emit timestamps itself, instead of external cut-by-ASR?
- Holds: dedicated pause tokens with controllable length (the Higgs approach works and is precise).
- Expressiveness without instability: sentence-level style tokens + inline events, trained so they
  never get spoken aloud and never trigger early stop or loops.
- Voice: few-shot cloning from a 15–45 s reference vs a fine-tuned single speaker.
- Data: ~26 min of short real game lines per character + synthetic long-form narration from a clone?
- Must fit and run on 8 GB (inference); training likely on a rented GPU.

## Where things are (on this machine)
- Trial scripts and per-model envs: `~/Projects/Konvey/spikes/tts-compare/` (README.md lists commands;
  `lines.json` test lines, `ref_picks.json`, `tagged.json`, `run_onetake.py` cutter, `test_breaks.py`)
- Samples and comparison page: `~/Projects/Konvey/out/tts-compare/index.html` (references in `refs/`,
  pause-mark takes in `marks/`)
- Downloaded conversation lines + picker page: `~/Projects/Konvey/out/voice-lines/{paige,dynamo}/`
  (`lines.json` with transcripts, `numbered.json` matching the picker numbers)
- Full Paige line list (1,561 lines: transcript, category, wiki URL, duration where the wiki gives one):
  `~/Projects/Konvey/out/voice-lines/paige-all-lines.json`
- Original voice assets: `~/Projects/Konvey/assets/voices/{paige,dynamo}/`
- Model weights in `~/.cache/huggingface/hub/` (Kokoro, Qwen Base + CustomVoice, Kitten, Higgs port +
  codec, Chatterbox, faster-whisper small.en)
