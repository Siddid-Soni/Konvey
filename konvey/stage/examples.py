"""Genre examples for Agent 3 (spec §4.4) and the same-topic guard (§2.4).

Each file in ``prompts/agent3-stage/examples/`` is one worked scene in one *genre* (the kind
of visual: 3D world, chart, cells, diagram, equation), with front matter::

    ---
    genre: chart
    kinds: chart, bars, graph            # plan object kinds that call for this genre
    topic_keywords: coffee, cooling      # what the example is about
    fits: rate, growth, trend            # optional: domain words of requests it suits
    ---

:func:`select` scores genres by the object kinds Agent 2 planned for a scene, keeps the best
one or two, and drops any example whose topic keywords appear in the request (user prompt and
Agent 1/2 output), so Agent 3 never sees an example about the topic it is drawing. Several
examples share a kind (``drawing``: message flow, queue, timeline, memory map, stack); among
them the ``fits`` words found in the request decide. ``fits`` holds generic domain words
(server, thread, page), never the example's own topic: those belong in ``topic_keywords``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..schemas import Scene

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "prompts" / "agent3-stage" / "examples"
HEADER = "## Examples (different topics — do not copy content)"
MAX_EXAMPLES = 2
# With nothing to score on (a scene of only text), these genres teach the most.
FALLBACK = ("diagram", "equation")
# Kinds almost every scene has; they count for less than the visual that defines a genre.
GENERIC = {"tex": 0.4, "text": 0.4, "number": 0.4}
# Each fits word found in the request adds this, capped below one planned kind: fits only
# breaks ties between examples of the same kinds, it never outranks a matching visual.
FIT_WEIGHT, FIT_CAP = 0.3, 0.9


@dataclass(frozen=True)
class Example:
    name: str
    genre: str
    kinds: frozenset[str]
    topic_keywords: tuple[str, ...]
    body: str
    fits: tuple[str, ...] = ()


def _front_matter(text: str, path: Path) -> tuple[dict[str, str], str]:
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise ValueError(f"{path}: missing --- front matter ---")
    meta = {}
    for line in m.group(1).splitlines():
        key, _, val = line.partition(":")
        meta[key.strip()] = val.strip()
    return meta, text[m.end():].strip()


def _items(raw: str) -> list[str]:
    return [v.strip() for v in raw.split(",") if v.strip()]


def load_examples(directory: Path = EXAMPLES_DIR) -> list[Example]:
    out = []
    for path in sorted(directory.glob("*.md")):
        meta, body = _front_matter(path.read_text(encoding="utf-8"), path)
        out.append(Example(path.stem, meta["genre"], frozenset(_items(meta.get("kinds", ""))),
                           tuple(_items(meta.get("topic_keywords", ""))), body,
                           tuple(_items(meta.get("fits", "")))))
    return out


def _stem(word: str) -> str:
    """Plural -> singular, crudely: enough to match 'cones' with 'cone'."""
    for suffix, repl in (("ies", "y"), ("sses", "ss"), ("xes", "x"), ("ches", "ch"), ("shes", "sh")):
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            return word[: -len(suffix)] + repl
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def _words(text: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", text.lower())]


def mentions(text: str, keyword: str) -> bool:
    """Whole-word (stemmed) match of a one- or multi-word keyword."""
    words, key = _words(text), _words(keyword)
    if not key:
        return False
    n = len(key)
    return any(words[i:i + n] == key for i in range(len(words) - n + 1))


def overlaps(example: Example, context: str) -> list[str]:
    return [k for k in example.topic_keywords if mentions(context, k)]


def scene_kinds(scene: Scene) -> set[str]:
    """Planned kinds; a solid given by its corners also counts as ``hull`` (its own example)."""
    objs = [obj for beat in scene.beats for obj in beat.objects if not isinstance(obj, str)]
    kinds = {obj.kind for obj in objs}
    if any(obj.kind == "solid" and obj.data.get("shape") == "hull" for obj in objs):
        kinds.add("hull")
    return kinds


def fit(ex: Example, context: str) -> float:
    """Bonus for the request's domain words this example suits (0 without ``fits``)."""
    words = set(_words(context))
    hits = sum(1 for f in ex.fits if (set(_words(f)) <= words) and mentions(context, f))
    return min(FIT_CAP, FIT_WEIGHT * hits)


def _score(ex: Example, kinds: set[str], context: str = "") -> float:
    base = sum(GENERIC.get(k, 1.0) for k in ex.kinds & kinds)
    return base + fit(ex, context) if base > 0 else 0.0


def select(scene: Scene, context: str, examples: list[Example] | None = None,
           limit: int = MAX_EXAMPLES, log=None) -> list[Example]:
    """Up to ``limit`` examples for this scene, never one about the request's topic.

    Genres are ranked by how many of the scene's object kinds they cover (ties broken by the
    request's ``fits`` words); the best genre is always taken and the next only if it covers
    something too. A genre whose examples all
    overlap the topic is skipped in favour of the next-closest genre."""
    examples = load_examples() if examples is None else examples
    kinds = scene_kinds(scene)
    allowed = []
    for ex in examples:
        hit = overlaps(ex, context)
        if hit:
            if log:
                log(f"      examples: skip {ex.name} (same topic: {', '.join(hit)})")
            continue
        allowed.append(ex)
    if not allowed:
        if log:
            log("      examples: none left after the same-topic guard; reference only")
        return []
    fallback = {g: len(FALLBACK) - i for i, g in enumerate(FALLBACK)}
    score = {ex.name: _score(ex, kinds, context) for ex in allowed}
    ranked = sorted(allowed, key=lambda e: (-score[e.name], -fallback.get(e.genre, 0), e.name))
    picked = [ranked[0]]
    for ex in ranked[1:]:
        if len(picked) >= limit:
            break
        if score[ex.name] > 0 and ex.genre not in {p.genre for p in picked}:
            picked.append(ex)
    return picked


def examples_block(picked: list[Example]) -> str:
    if not picked:
        return ""
    return HEADER + "\n\n" + "\n\n".join(ex.body for ex in picked)
