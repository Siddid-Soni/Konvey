"""Voice prompts (story agents, v7): checks for the DramaBox prompt the Visual Planner writes per line.

The Writer's words are final; the planner only adds a speaker and voice directions around them
(prompts/shared/visual-planner-v7.md, "The voice"). These checks hold it to that: the quoted words
are the line's words in order (punctuation and one short sound at a turn may change), no colon or
semicolon inside the quotes, the speaker is short, directions are voice only, and nothing laughs.
A line whose prompt still fails after repair falls back to :func:`plain`, which is always valid.
"""

from __future__ import annotations

import re

from .speech.checks import laughter
from .speech.dramabox import DIALOGUE, dialogue

PLAIN = "A calm young woman speaks evenly"
SOUNDS = re.compile(r"^(?:oh+|a+h+|hm+|m+|whoa|wow)$")  # a short sound the planner may add at a turn
SPEAKER = re.compile(r"^an? (?:(?P<mood>[a-z-]+) )?(?:young )?woman\b", re.I)
BODY = re.compile(r"\b(?:point\w*|lean\w*|nod\w*|tap\w*|gestur\w*|smil\w*|grin\w*|wink\w*|shrug\w*|"
                  r"turn\w* to|look\w* at|wav\w*|hold\w* up|draw\w*|writ\w*)\b", re.I)


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:['’][a-z]+)?", text.lower().replace("’", "'"))


def directions(vo: str) -> list[str]:
    """Everything outside the quotes, the speaker first."""
    return [d.strip(" ,") for d in DIALOGUE.split(vo)[::2] if d.strip(" ,")]


def opening(vo: str) -> str:
    """The speaker and first direction, lowercased (to spot the same delivery line after line)."""
    return vo.split("“", 1)[0].strip(" ,").lower()


def plain(line: str) -> str:
    return f"{PLAIN}, “{re.sub(r'[:;]', ',', line.strip())}”"


def problems(line: str, vo: str) -> list[str]:
    """Why ``vo`` is not a valid DramaBox prompt for the Writer's ``line``."""
    out = []
    if not vo or not DIALOGUE.search(vo):
        return ["no words in curly quotes “…”"]
    said = [w for w in words(dialogue(vo)) if not SOUNDS.match(w)]
    want = [w for w in words(line) if not SOUNDS.match(w)]
    if said != want:
        out.append("the quoted words are not the line's words, word for word, in order")
    if re.search(r"[:;]", dialogue(vo)):
        out.append("a colon or semicolon inside the quotes; the voice reads it badly, use a comma or '...'")
    head = vo.split("“", 1)[0].strip(" ,")
    m = SPEAKER.match(head)
    if not m:
        out.append(f"the speaker {head!r} is not 'A young woman' with at most one mood word")
    elif re.match(r"\s+(?:with|who|wearing|in|of|from|named|and)\b", head[m.end():], re.I):
        out.append(f"the speaker {head!r} describes more than a mood word (more words get spoken as garble)")
    if not vo.rstrip().endswith("”"):
        out.append("it does not end with a closing quote")
    if laugh := laughter(vo):
        out.append(f"{laugh} is laughter; the voice never laughs")
    for d in directions(vo):
        if BODY.search(d):
            out.append(f"direction {d!r} is a body or screen action; describe the voice only")
        if re.search(r"\d", d):
            out.append(f"direction {d!r} holds a digit")
    for d in directions(vo)[1:]:
        if not re.match(r"she\b", d, re.I):
            out.append(f"direction {d!r} does not start with 'She'")
    return out
