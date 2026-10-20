"""Narration mode for the stage pipeline (see konvey.speech).

Nothing in konvey/pipeline.py changes: ``narration_mode()`` swaps Agent 2's prompt for the
narration copy of plan.md while a run is going, and the voice / wire / master steps work on
the run's output directory, so they can also re-voice an old run (``--skip-generate``).
"""

from __future__ import annotations

import contextlib
import html
import json
import re
import subprocess
from pathlib import Path

from ..prompts import REPO_ROOT

REF = REPO_ROOT / "assets" / "voices" / "dynamo" / "ref.wav"   # Deadlock's Dynamo, a professor
TEMPERATURE = 1.0   # Turbo; at 1.0 a lone [chuckle] is cut short, so voice() doubles it
PLAN = REPO_ROOT / "prompts" / "agent2-stage" / "plan-narration.md"
STAGE_NOTE = REPO_ROOT / "prompts" / "agent3-stage" / "narration.md"   # appended to Agent 3's prompt
TAG = re.compile(r"\s*\[(?:chuckle|laugh|gasp|sigh|clear throat|dramatic|surprised|sarcastic)\]\s*")
BEAT_VO = re.compile(r'(<beat\b[^>]*?\bvo=")([^"]*)(")')
BEAT_TAG = re.compile(r"<beat\b[^>]*>")
CAPTION_ATTR = re.compile(r'\s+caption="[^"]*"')
# Narrated videos show no subtitles: the vo is heard, and its room goes to the picture.
SUBTITLES = False
# The duration is a ceiling in narration mode: any plan from 0 to 2x the limit passes the sum
# check (the prompt asks for at most the limit), so a short topic is not padded.
DURATION_TOLERANCE = 1.0


@contextlib.contextmanager
def narration_mode():
    """Inside this block Agent 2 reads plan-narration.md (its own full copy of plan.md) and its
    plan must pass the narration rules (checks.py) too, through the same repair loop; Agent 3's
    prompt ends with narration.md (no subtitles)."""
    from .. import agents, pipeline
    from ..stage import displays
    from .checks import check_plan_narration

    base = pipeline.build_agent_instructions
    plan = displays.fill_plan(PLAN.read_text(encoding="utf-8"))
    note = STAGE_NOTE.read_text(encoding="utf-8")

    def with_speech(agent, *a, **kw):
        if agent == 2:
            return plan
        text = base(agent, *a, **kw)
        return text + "\n\n" + note if agent == 3 else text

    validate = pipeline.validate_scene_plan
    extract = pipeline.extract_beats

    def validate_narrated(*a, **kw):
        plan = validate(*a, **kw)
        check_plan_narration(plan)
        return plan

    def extract_narrated(content):
        # Agent 3's scene is checked the way it renders: without the subtitle (wire() turns it
        # off later), so the layout check gives the picture that room instead.
        html = extract(content)
        return html if SUBTITLES else BEAT_TAG.sub(captions_off, html)

    agents.build_agent_instructions = pipeline.build_agent_instructions = with_speech
    pipeline.validate_scene_plan = validate_narrated
    pipeline.extract_beats = extract_narrated
    try:
        yield
    finally:
        agents.build_agent_instructions = pipeline.build_agent_instructions = base
        pipeline.validate_scene_plan = validate
        pipeline.extract_beats = extract


def run_narrated(config, render: bool = True, log=print, highlight: str | None = None):
    """Plan in narration mode, voice, wire and (optionally) render + master ``video.mp4``.

    Returns the PipelineResult; scenes that were rejected are still voiced and rendered as
    written, like run_konvey.py --render does.
    """
    from ..pipeline import run_pipeline

    config.duration_tolerance = max(config.duration_tolerance, DURATION_TOLERANCE)
    with narration_mode():
        result = run_pipeline(config)
    from .checks import narration_problems

    warnings = narration_problems(result.plan)[1]
    if warnings:   # soft rules: kept with the run to compare against 3b1b later
        (Path(config.out_dir) / "narration-warnings.txt").write_text("\n".join(warnings) + "\n")
    finish(config.out_dir, render=render, log=log, highlight=highlight)
    return result


def finish(out_dir: str | Path, render: bool = True, log=print, highlight: str | None = None) -> Path | None:
    """Voice + wire a run that Agent 3 has written; render and master it if ``render``."""
    out = Path(out_dir).resolve()
    voice(out, log=log)
    wire(out)
    if not render:
        return None
    from ..render import render_run

    video = render_run(out, log=log, highlight=highlight)
    master(video)
    log(f"video: {video}")
    return video


def pages(out_dir: Path) -> list[Path]:
    return sorted(p for p in out_dir.glob("agent3-S*.html") if p.name.count(".") == 1)


def tagged(page: Path) -> Path:
    """The scene as Agent 3 wrote it (tags in ``vo``), kept before wire() cleans the captions."""
    return page.with_name(page.stem + ".tagged.html")


def lines(out_dir: Path) -> list[dict]:
    """Every voiced beat: ``{"id": "S1-b03", "text": caption with tags, "say": TTS text}``."""
    from .spoken import spoken

    found = []
    for page in pages(out_dir):
        sid = page.stem.split("-")[-1]
        src = tagged(page) if tagged(page).exists() else page
        for i, m in enumerate(BEAT_VO.finditer(src.read_text(encoding="utf-8"))):
            text = html.unescape(m.group(2)).strip()
            if text:
                say = spoken(text)
                if TEMPERATURE >= 1.0:
                    say = say.replace("[chuckle]", "[chuckle] [chuckle]")
                found.append({"id": f"{sid}-b{i:02d}", "text": text, "say": say})
    return found


def voice(out_dir: Path, log=print) -> dict:
    """Voice every line with Chatterbox -> audio/<id>.wav and speech.json (text, say, sec)."""
    from .tts import synthesize

    todo = lines(out_dir)
    log(f"      voicing {len(todo)} lines (Chatterbox Turbo) ...")
    secs = synthesize([{"id": x["id"], "text": x["say"]} for x in todo], REF, out_dir / "audio",
                      TEMPERATURE, log=log)
    speech = {x["id"]: {"text": x["text"], "say": x["say"], "sec": secs[x["id"]]} for x in todo}
    (out_dir / "speech.json").write_text(json.dumps(speech, indent=1))
    log(f"      voiced {len(speech)} lines, {sum(secs.values()):.1f}s of speech")
    return speech


def captions_off(m: re.Match, key: str = 'vo="') -> str:
    """A ``<beat …>`` that has ``key`` (its vo, or its clip) without the automatic caption (any
    caption= it had goes)."""
    tag = m.group(0)
    if key not in tag or re.search(r'\bvo=""', tag):
        return tag
    return CAPTION_ATTR.sub("", tag)[:-1].rstrip("/ ") + ' caption="none">'


def no_caption(m: re.Match) -> str:
    """A voiced beat (one with ``speech=``) without the automatic caption."""
    return captions_off(m, 'speech="')


SPIKE_IMPORT = re.compile(r"sys\.path\.insert\(0, '[^']*spikes/speech'\)\nfrom scene import SpeechScene")


def wire(out_dir: Path) -> None:
    """Each voiced beat names its clip and (SUBTITLES off) gets ``caption="none"``; the vo keeps
    no voice tags; wrappers use SpeechScene."""
    for page in pages(out_dir):
        sid = page.stem.split("-")[-1]
        if not tagged(page).exists():
            tagged(page).write_text(page.read_text(encoding="utf-8"), encoding="utf-8")
        n = iter(range(10_000))

        def sub(m):
            i = next(n)
            text = html.unescape(m.group(2)).strip()
            if not text:
                return m.group(0)
            clean = html.escape(TAG.sub(" ", text).strip(), quote=True)
            return f'{m.group(1)}{clean}" speech="{sid}-b{i:02d}{m.group(3)}'

        src = BEAT_VO.sub(sub, tagged(page).read_text(encoding="utf-8"))
        if not SUBTITLES:
            src = BEAT_TAG.sub(no_caption, src)
        page.write_text(src, encoding="utf-8")
        py = page.with_suffix(".py")
        src = SPIKE_IMPORT.sub("from konvey.speech.scene import SpeechScene", py.read_text(encoding="utf-8"))
        src = src.replace("from konvey.stage.scene import StageScene",
                          "from konvey.speech.scene import SpeechScene")
        py.write_text(src.replace("(StageScene)", "(SpeechScene)"), encoding="utf-8")


def master(video: Path) -> None:
    """Speech peaks at -1 dBFS but sits near -19 LUFS, which sounds feeble: compress it gently and
    bring the whole track to -14 LUFS (streaming loudness), true peak under -1.5 dBFS."""
    tmp = video.with_name("video-master.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-af",
                    "acompressor=threshold=-24dB:ratio=3:attack=5:release=120:makeup=2,"
                    "loudnorm=I=-14:TP=-1.5:LRA=7", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
                    str(tmp)], check=True)
    tmp.replace(video)
