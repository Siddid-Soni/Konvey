# Narration voices (konvey.speech)

Narration is voiced by DramaBox (`konvey/speech/dramabox.py`), which clones the timbre of one reference
clip (its first 10 s). Each line's delivery comes from the planner's bracketed stage directions.

Voice clips are **not committed**: use a recording you have the rights to (your own voice, or a clip
licensed for voice cloning). Either

- put it at `assets/voices/narrator.mp3` (any format ffmpeg reads works if you set the variable below), or
- set `KONVEY_VOICE_REF=/path/to/clip.wav` (in `.env` or the environment).

A clean 10–20 s monologue with steady tone works best. Everything else in this folder is gitignored.
