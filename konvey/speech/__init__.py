"""Narration mode: the planner writes spoken lines with stage directions, DramaBox voices every
beat, the scenes are timed by the audio and the video gets a mastered speech track.

    uv run --group render --group layout --group speech python run_konvey_narrated.py --prompt "..." \
        --out-dir out/speech-monty

Steps (konvey.speech.narrate): (1) the stage pipeline with Agent 2 on
prompts/agent2-stage/plan-narration.md; (2) every beat's ``vo``, numbers spelled out
(spoken.py), goes to DramaBox (dramabox.py, in process; voice in assets/voices/paige/) ->
audio/<id>.wav + speech.json;
(3) each ``vo`` loses its stage directions (the caption) and gets ``speech="<id>"``, the scene
wrappers use SpeechScene; (4) konvey.render joins the scenes, master() sets the loudness.
"""

from .narrate import narration_mode, run_narrated, voice, wire, master  # noqa: F401
