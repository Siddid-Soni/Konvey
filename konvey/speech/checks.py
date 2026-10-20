"""Narration-mode rules for the plan, measured on 3Blue1Brown's videos (captions + frames).

About one line in five keeps the picture still. A held line finishes or comments on what is
already shown ("…and that is the whole trick"); a new idea changes the picture. Holds rarely run long: three
or more held lines in a row is about 1% of his lines. Numbers on screen are rounded for a
listener (≈16.7%, never 0.042731).

Hard (the plan goes back for repair): a held line that says a number not on screen, numbers too
exact for a listener. Soft (warnings only; the hold numbers come from six videos so far): long
runs of held lines, too many held lines in a scene.
"""

from __future__ import annotations

import json
import re

from ..validators import MAX_VO_WORDS, ValidationError, _numbers_in
from .dramabox import DIALOGUE, dialogue

MAX_HELD_RUN = 2          # held beats in a row
HELD_SHARE = 1 / 3        # of a scene's beats (3b1b: 13–29% per video)
MAX_SIG_DIGITS = 3        # a shown or spoken decimal: 0.507 yes, 0.042731 no
# Keys whose numbers the viewer reads off the screen (a chart's series are drawn, not read).
SHOWN_KEYS = frozenset({"text", "tex", "value", "label", "labels", "number", "caption", "values"})
_DECIMAL = re.compile(r"(?<![\w.])\d*\.\d+")


def _state(beat) -> str:
    """Everything on screen in a beat: ids, kinds and data."""
    return json.dumps(sorted((o.id, o.kind, o.data) for o in beat.objects if not isinstance(o, str)),
                      sort_keys=True, default=str)


def _shown_numbers(beat) -> set[float]:
    return {round(abs(n), 6) for o in beat.objects if not isinstance(o, str)
            for n in _numbers_in(o.data)}


def _unrounded(text: str) -> list[str]:
    return [m for m in _DECIMAL.findall(text) if len(m.split(".")[1].lstrip("0") or "0")
            + len(m.split(".")[0].lstrip("0")) > MAX_SIG_DIGITS]


def held_beats(scene) -> list[int]:
    """Beats whose screen is the same as the beat before."""
    states = [_state(b) for b in scene.beats]
    return [i for i in range(1, len(states)) if states[i] == states[i - 1]]


# Phrases every plan copied from the old narrated example ("Take a guess before we count… Most
# people say 25"). Soft: fine now and then, not every time. (The count-list opening itself is a
# hard rule now: validators.check_plan_arc.)
# laughter anywhere in a vo line, direction or sound (user: no laughing in the speech)
LAUGH = re.compile(r"\b(?:laugh\w*|giggl\w*|chuckl\w*|snicker\w*|cackl\w*|(?:he){2,}h?|(?:ha){2,}h?|(?:hi){2,}|teehee)\b", re.I)


def laughter(text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in LAUGH.finditer(text)})


STOCK_PHRASES = ("take a guess", "most people say", "most people guess", "before we count",
                 "before we work it out", "before we check")


def opening_warnings(plan) -> list[str]:
    """Soft checks on the narration's wording (see STOCK_PHRASES)."""
    warnings = []
    said = " ".join(dialogue(l).lower() for s in plan.scenes for l in s.vo_script)
    stock = [p for p in STOCK_PHRASES if p in said]
    if stock:
        warnings.append(f"stock phrases {stock}: say it in words specific to this topic, or let the "
                        "picture ask the question")
    return warnings


def narration_problems(plan) -> tuple[list[str], list[str]]:
    """(errors, warnings)."""
    errors, warnings = [], opening_warnings(plan)
    for scene in plan.scenes:
        for i, beat in enumerate(scene.beats):
            if not DIALOGUE.search(beat.vo_line):
                errors.append(f"Scene {scene.id} beat {i}: the vo_line has no dialogue in curly quotes. Write it "
                              "as a DramaBox prompt: a speaker description, then the spoken words in “…”, with "
                              f"stage directions between: {beat.vo_line!r}")
            elif re.match(r"\s*(?:[“\"]|(?:she|her)\b)", beat.vo_line, re.I):
                errors.append(f"Scene {scene.id} beat {i}: the vo_line starts without a speaker description; each "
                              "line is voiced on its own, so begin it with one (A curious young woman speaks "
                              f"warmly, “…”): {beat.vo_line!r}")
            elif laugh := laughter(beat.vo_line):
                errors.append(f"Scene {scene.id} beat {i}: {laugh} is laughter; the voice never laughs. Put the "
                              f"delight in the words and the pace instead: {beat.vo_line!r}")
            elif (n := len(dialogue(beat.vo_line).split())) > MAX_VO_WORDS:
                errors.append(f"Scene {scene.id} beat {i}: the dialogue has {n} spoken words (max "
                              f"{MAX_VO_WORDS}); one idea per beat, split it into two beats or cut it")
        held = held_beats(scene)
        run, longest = 0, []
        for i in range(1, len(scene.beats)):
            run = run + 1 if i in held else 0
            if run > MAX_HELD_RUN and not longest:
                longest = list(range(i - run + 1, i + 1))
        if longest:
            warnings.append(f"Scene {scene.id}: beats {longest} all keep the picture of beat "
                          f"{longest[0] - 1} unchanged ({len(longest)} lines in a row; usually at "
                          f"most {MAX_HELD_RUN}). Each new idea changes the picture: show the thing the line "
                          "names, mark or dim part of it, or add the number it says")
        allowed = max(1, int(len(scene.beats) * HELD_SHARE))
        if len(held) > allowed and not longest:
            warnings.append(f"Scene {scene.id}: beats {held} keep the picture unchanged; at most "
                          f"{allowed} of its {len(scene.beats)} beats usually do. Hold only on a line that "
                          "finishes or comments on what is on screen; a new idea changes the picture")
        for i in held:
            beat = scene.beats[i]
            shown = _shown_numbers(beat)
            missing = [n for n in _numbers_in(dialogue(beat.vo_line)) if round(abs(n), 6) not in shown
                       and not any(abs(abs(n) - s) <= 0.05 * max(abs(n), s) for s in shown)]
            if missing:
                errors.append(f"Scene {scene.id} beat {i}: the line says {missing[:3]} but keeps the "
                              "picture of the beat before, where they are not shown. A held line may "
                              "only talk about what is on screen: show them in this beat")
        exact = {}
        for i, beat in enumerate(scene.beats):
            bad = _unrounded(dialogue(beat.vo_line))
            for o in beat.objects:
                if not isinstance(o, str) and o.kind in ("number", "text", "tex"):
                    bad += [b for k, v in o.data.items() if k in SHOWN_KEYS for b in _unrounded(str(v))]
            if bad:
                exact[i] = sorted(set(bad))
        if exact:
            values = sorted({v for vs in exact.values() for v in vs})
            errors.append(f"Scene {scene.id} beats {list(exact)}: {values[:4]} are too exact for a "
                          "listener; round them in the line and on screen (2–3 significant digits, or "
                          "a percent: 0.042731 → 4.3%, 82.57 → 83)")
    return errors, warnings


def check_plan_narration(plan, log=print) -> None:
    errors, warnings = narration_problems(plan)
    for w in warnings:
        log(f"      narration warning: {w}")
    if errors:
        raise ValidationError("SCENE_PLAN narration:\n- " + "\n- ".join(errors))
