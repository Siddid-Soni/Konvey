# Narration voices (konvey.speech)

- **Narrator: Paige** (Deadlock), voiced by DramaBox (`konvey/speech/dramabox.py`). The reference is her
  monologue `paige/raw/Bookworm_match_start_punkgoat_bookworm_convo01_04.mp3` (16.9 s; DramaBox uses its first
  10 s, `narrate.REF`), picked by ear 2026-10-18. The clip sets the timbre; each line's delivery comes from the
  planner's bracketed stage directions.
- `paige/raw/`: Paige's lines fetched from the deadlock.wiki API; `paige/clips.json`: six tone clips with
  transcripts, picked by ear (made for the Qwen3-TTS engine, now removed; kept as candidate references).
- Removed 2026-10-18 with the Chatterbox and Qwen engines: Dynamo's references (`dynamo/`) and
  `turbo-tags.json`, archived with this file's old text in
  `out/archive/chatterbox-qwen-narration-2026-10-18.tar.gz`.
