"""Domain validation for README section 2 (run order steps 2-4).

- Agent 1 -> strict JSON parse + triple relations closed.
- Agent 2 -> 3 scenes, precedes S1->S2->S3, durations sum to target, grounding,
  the walkthrough shown one step per beat.
- Agent 3 beat HTML is checked by konvey.stage.check.

All validators raise :class:`ValidationError` (a ValueError) with a message
naming the offending field, so Workflow function steps can fail closed.
"""

from __future__ import annotations

import json
import re
from typing import Any, Union

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from .stage import displays
from .schemas import (
    OBJECT_KINDS,
    TRIPLE_RELATIONS,
    KnowledgePack,
    ObjectSpec,
    ScenePlan,
)


class ValidationError(ValueError):
    pass


# ---------------------------------------------------------------------------
# JSON extraction (CoT wraps JSON in <output_json>, others in fences)
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_OUTPUT_JSON_RE = re.compile(r"<output_json>\s*(.*?)</output_json>", re.DOTALL | re.IGNORECASE)


def extract_json(text: str) -> Any:
    """Pull the JSON payload out of raw agent text (fences / tags / bare)."""
    text = text.strip()
    m = _OUTPUT_JSON_RE.search(text)
    if m:
        text = m.group(1).strip()
    else:
        m = _FENCE_RE.search(text)
        if m:
            text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Last resort: slice from first { to last }.
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValidationError(f"No JSON object found in agent output: {text[:200]!r}")
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as e:
            # Long nested replies (the 1-agent Solo's ~18k chars) mostly fail at the very end
            # with brackets closed in the wrong order. Rebalance them and try once more.
            try:
                return json.loads(_balance_brackets(text[start:]))
            except json.JSONDecodeError:
                raise ValidationError(f"Agent output is not strict JSON: {e}") from e


def _balance_brackets(text: str) -> str:
    """Close what was left open when a closer arrives, drop stray closers, close everything
    still open at the end, and drop trailing commas. Strings are copied untouched."""
    out, stack, in_str, esc = [], [], False, False
    pair = {"}": "{", "]": "["}
    for ch in text:
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if pair[ch] not in stack:
                continue                       # stray closer
            while stack[-1] != pair[ch]:      # close what was left open inside
                out.append("}" if stack.pop() == "{" else "]")
            stack.pop()
        out.append(ch)
    out += ["}" if o == "{" else "]" for o in reversed(stack)]
    return re.sub(r",\s*([}\]])", r"\1", "".join(out))


def coerce_content(content: Any, model: type) -> Any:
    """Agno returns BaseModel on success, str on fallback parse failure."""
    if isinstance(content, model):
        return content
    if isinstance(content, dict):
        try:
            return model.model_validate(content)
        except PydanticValidationError as e:
            raise ValidationError(f"{model.__name__} schema violation: {e}") from e
    if isinstance(content, str):
        # agno hands back the raw text when its own parse failed. A schema error here must
        # become a ValidationError like the dict case, or it skips the repair loop and the
        # run dies on the first fixable mistake.
        try:
            return model.model_validate(extract_json(content))
        except PydanticValidationError as e:
            raise ValidationError(f"{model.__name__} schema violation: {e}") from e
    if isinstance(content, BaseModel):   # another schema's model (e.g. StagePlan for ScenePlan)
        return coerce_content(content.model_dump(), model)
    raise ValidationError(f"Unexpected agent content type: {type(content).__name__}")


# ---------------------------------------------------------------------------
# Agent 1
# ---------------------------------------------------------------------------

MIN_WALK_STEPS, MAX_WALK_STEPS = 3, 10


def validate_knowledge_pack(
    kp: Union[KnowledgePack, dict, str], require_grounding: bool = False,
    require_walkthrough: bool = False,
) -> KnowledgePack:
    if isinstance(kp, str):
        kp = extract_json(kp)
    if isinstance(kp, dict):
        try:
            kp = KnowledgePack.model_validate(kp)
        except PydanticValidationError as e:
            raise ValidationError(f"KNOWLEDGE_PACK schema violation: {e}") from e
    assert isinstance(kp, KnowledgePack)
    if not kp.core_claim.strip():
        raise ValidationError("KNOWLEDGE_PACK.core_claim must be non-empty")
    if len(kp.mechanism_steps) < 3:
        raise ValidationError(
            f"KNOWLEDGE_PACK.mechanism_steps needs >=3 causal steps "
            f"(Agent 2 splits them into 3 frames), got {len(kp.mechanism_steps)}"
        )
    if not kp.knowledge_triples:
        raise ValidationError("KNOWLEDGE_PACK.knowledge_triples must be non-empty")
    for i, triple in enumerate(kp.knowledge_triples):
        if len(triple) != 3 or not all(isinstance(x, str) and x.strip() for x in triple):
            raise ValidationError(
                f"KNOWLEDGE_PACK.knowledge_triples[{i}] must be [Subject, Relation, Object], got {triple!r}"
            )
    # Triples outside the closed vocabulary are dropped, not fatal: nothing downstream
    # needs every triple, and failing a whole run on one off-list verb wastes a repair.
    valid = [t for t in kp.knowledge_triples if t[1].strip().lower() in TRIPLE_RELATIONS]
    if not valid:
        bad = sorted({t[1] for t in kp.knowledge_triples})
        raise ValidationError(
            f"KNOWLEDGE_PACK.knowledge_triples: no triple uses an allowed relation (got {bad}); "
            f"allowed {list(TRIPLE_RELATIONS)}"
        )
    kp.knowledge_triples = [[t[0], t[1].strip().lower(), t[2]] for t in valid]
    names = {c.name.strip().lower() for c in kp.key_concepts}
    for i, ex in enumerate(kp.worked_examples):
        others = {e.concept.strip().lower() for j, e in enumerate(kp.worked_examples) if j != i}
        name = match_concept(ex.concept, kp, others)
        if name is None:
            raise ValidationError(
                f"KNOWLEDGE_PACK.worked_examples[{i}].concept {ex.concept!r} must equal a "
                f"key_concepts[].name, one of {[c.name for c in kp.key_concepts]}"
            )
        ex.concept = name
    if kp.walkthrough is not None:
        kp.walkthrough.concept = match_concept(kp.walkthrough.concept, kp) or kp.walkthrough.concept
    if require_grounding:
        covered = {ex.concept.strip().lower() for ex in kp.worked_examples if ex.values}
        missing = [c.name for c in kp.key_concepts if c.name.strip().lower() not in covered]
        if missing:
            raise ValidationError(
                f"KNOWLEDGE_PACK.worked_examples must give concrete values for every key concept; "
                f"missing {missing}. Add {{'concept', 'setup', 'values', 'formula'}} with the real "
                "numbers a viewer should see, e.g. {'n': [1, 2, 4, 8], 'steps': [0, 1, 2, 3]}."
            )
    if require_walkthrough:
        problems = _walkthrough_problems(kp, names)
        if problems:
            raise ValidationError("KNOWLEDGE_PACK.walkthrough:\n- " + "\n- ".join(problems))
    return kp


def _concept_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def match_concept(name: str, kp: KnowledgePack, taken: set[str] = frozenset()) -> str | None:
    """The key_concepts[].name a worked example or the walkthrough means. Models write the name
    loosely ("k-means step" for "K-means step", "Assignment" for "Assignment step") or name the
    whole topic ("K-means"); rejecting that costs an Agent 1 call, so: the same name ignoring case
    and punctuation, else the one name containing it (or contained in it), else a close spelling, else (the topic itself) the first key concept not ``taken`` by another
    example. None when it names something else."""
    import difflib

    by_key = {_concept_key(c.name): c.name for c in kp.key_concepts}
    key = _concept_key(name)
    if key in by_key:
        return by_key[key]
    within = [k for k in by_key if len(min(k, key, key=len)) >= 4 and (k in key or key in k)]
    if len(within) == 1:                      # "Assignment" for "Assignment step"
        return by_key[within[0]]
    close = difflib.get_close_matches(key, list(by_key), n=1, cutoff=0.8)
    if close:
        return by_key[close[0]]
    topic = _concept_key(kp.topic)
    if key and (key in topic or difflib.SequenceMatcher(None, key, topic).ratio() >= 0.8):
        free = [c.name for c in kp.key_concepts if c.name.strip().lower() not in taken]
        return (free or [kp.key_concepts[0].name])[0]
    return None


def _walkthrough_problems(kp: KnowledgePack, concept_names: set[str]) -> list[str]:
    w = kp.walkthrough
    if w is None:
        return ["missing: add one concrete example solved from start to finish, "
                "{'concept', 'question', 'start', 'steps': [{'action', 'state'}], 'result'}"]
    problems = []
    if w.concept.strip().lower() not in concept_names:
        problems.append(f"concept {w.concept!r} must equal a key_concepts[].name")
    if not w.start:
        problems.append("start must give the exact values before the first step")
    if not MIN_WALK_STEPS <= len(w.steps) <= MAX_WALK_STEPS:
        problems.append(f"has {len(w.steps)} steps; give {MIN_WALK_STEPS}-{MAX_WALK_STEPS} "
                        "(pick a smaller instance if the full run is longer)")
    for i, step in enumerate(w.steps):
        if not step.state:
            problems.append(f"steps[{i}] ({step.action!r}) has no state: give the exact values after it")
    return problems


# ---------------------------------------------------------------------------
# Agent 2
# ---------------------------------------------------------------------------

# A VO line is also the on-screen caption: one idea, readable in ~6 s.
MAX_VO_WORDS = 20


def validate_scene_plan(
    plan: Union[ScenePlan, dict, str],
    target_duration_sec: float = 90.0,
    duration_tolerance: float = 0.25,
    knowledge: KnowledgePack | None = None,
    example_vo_lines: tuple[str, ...] | list[str] = (),
    computed: set[float] = frozenset(),
) -> ScenePlan:
    """Structural checks; with ``knowledge`` also grounding (see check_plan_grounding) and
    the knowledge pack's walkthrough shown one step per beat."""
    if isinstance(plan, str):
        plan = extract_json(plan)
    if isinstance(plan, dict):
        try:
            plan = ScenePlan.model_validate(plan)
        except PydanticValidationError as e:
            raise ValidationError(f"SCENE_PLAN schema violation: {e}") from e
    assert isinstance(plan, ScenePlan)

    ids = [s.id for s in plan.scenes]
    if ids != ["S1", "S2", "S3"]:
        raise ValidationError(f"SCENE_PLAN must have scenes [S1, S2, S3] in order, got {ids}")
    precedes = [s.precedes for s in plan.scenes]
    if precedes != ["S2", "S3", None]:
        raise ValidationError(
            f"SCENE_PLAN precedes chain must be S1->S2->S3 ([S2, S3, None]), got {precedes}"
        )

    total = sum(s.duration_sec for s in plan.scenes)
    if target_duration_sec > 0 and abs(total - target_duration_sec) > target_duration_sec * duration_tolerance:
        raise ValidationError(
            f"SCENE_PLAN durations sum to {total}s, target {target_duration_sec}s "
            f"(tolerance {duration_tolerance:.0%})"
        )

    for scene in plan.scenes:
        if not scene.vo_script:
            raise ValidationError(f"Scene {scene.id}: vo_script must be non-empty")
        for b, beat in enumerate(scene.beats):
            tag = f"Scene {scene.id} beat {b}"
            if beat.vo_line not in scene.vo_script:
                raise ValidationError(f"{tag}: vo_line must match an entry in vo_script")
            n_words = len(beat.vo_line.split())
            if n_words > MAX_VO_WORDS:
                raise ValidationError(
                    f"{tag}: vo_line has {n_words} words (max {MAX_VO_WORDS}); one idea per beat, "
                    f"split it into two beats or cut it: {beat.vo_line!r}")
            if not beat.objects:
                raise ValidationError(f"{tag}: objects must be non-empty (<=5)")
    if knowledge is not None:
        check_plan_grounding(plan, knowledge, computed)
        check_plan_walkthrough(plan, knowledge)
        check_plan_pictures(plan)
        check_plan_displays(plan)
    if example_vo_lines:
        check_vo_not_copied(plan, example_vo_lines)
    return plan


# ---------------------------------------------------------------------------
# Grounding: plan data must come from the knowledge pack
# ---------------------------------------------------------------------------

# A comma is a thousands separator only before exactly 3 digits: "12,000" is one number,
# "4,6,4,2" (a grid row) is four.
_NUM_RE = re.compile(r"(?<![A-Za-z_\d])[-+]?(?:\d{1,3}(?:,\d{3})+(?!\d)|\d+)(?:\.\d+)?(?:[eE][-+]?\d+)?")
# ObjectSpec.data keys whose numbers are displayed to the viewer and must be
# traceable. Structural keys (rows, balls, seed, size, ...) are free choices.
DISPLAY_KEYS: frozenset[str] = frozenset(
    {"text", "tex", "value", "values", "labels", "counts", "label", "caption", "number", "series",
     "edges", "items", "holds", "parts"}
)


def _numbers_in(value: Any) -> list[float]:
    out: list[float] = []
    if isinstance(value, bool):
        return out
    if isinstance(value, (int, float)):
        out.append(float(value))
    elif isinstance(value, str):
        for m in _NUM_RE.findall(value):
            try:
                out.append(float(m.replace(",", "")))
            except ValueError:
                pass
    elif isinstance(value, dict):
        for v in value.values():
            out.extend(_numbers_in(v))
    elif isinstance(value, (list, tuple)):
        for v in value:
            out.extend(_numbers_in(v))
    return out


def knowledge_numbers(knowledge: KnowledgePack) -> set[float]:
    """Every number stated anywhere in the knowledge pack (values + prose)."""
    # 6 significant figures, not 6 decimals: tiny values (errors like 2.1e-06) must survive.
    return {float(f"{abs(n):.6g}") for n in _numbers_in(json.loads(knowledge.model_dump_json()))}


def computed_numbers(calls: list[dict]) -> set[float]:
    """Every number Agent 1's compute tools printed (``compute-log.json``): a value it worked
    out but left out of the pack is still a real one, not an invented one. Error lines are
    skipped (a line number is not a result)."""
    out = [ln for c in calls for ln in str(c.get("output", "")).splitlines()
           if not ln.startswith(("ERROR", "REJECTED", "..."))]
    return {float(f"{abs(n):.6g}") for n in _numbers_in("\n".join(out))}


def _nearest(n: float, known: set[float], k: int = 8) -> list[str]:
    """The ``k`` known values closest to ``n``, in order, for a rejection to pick from."""
    near = sorted(sorted(known, key=lambda v: abs(v - abs(n)))[:k])
    return [f"{v:g}" for v in near]


def _traceable(n: float, known: set[float]) -> bool:
    a = abs(n)
    # Tolerate rounding to the precision the plan shows (5.8 vs 5.82).
    return any(abs(a - k) <= max(0.05 * max(a, k), 1e-9) for k in known)


SOLID_SHAPES = ("sphere", "box", "cylinder", "cone", "prism", "pyramid",
                "tetrahedron", "octahedron", "dodecahedron", "icosahedron", "hull")


def _object_problems(obj: ObjectSpec) -> list[str]:
    kind, d = obj.kind, obj.data
    if kind not in OBJECT_KINDS and kind not in displays.aliases():   # an old name ("system") still reads
        return [f"kind {kind!r} not in {list(OBJECT_KINDS)}"]
    disp = displays.for_kind(kind)
    need = disp.needs if disp else {
        "text": ["text"], "galton": ["rows"], "solid": ["shape"], "field": ["fn"], "line": ["from", "to"],
        "angle": ["at", "from", "to"], "face": ["points"],
    }.get(kind, [])
    problems = [f"kind {kind!r} needs data[{k!r}]" for k in need if k not in d]
    if disp is not None and disp.check_object is not None:
        problems += disp.check_object(d)
    if kind == "galton" and isinstance(d.get("rows"), int):
        if d["rows"] > 16:
            problems.append(f"galton rows {d['rows']} > 16: pegs become invisible; use <= 16")
        if isinstance(d.get("balls"), int) and d["balls"] < 20 * d["rows"]:
            problems.append(f"galton balls {d['balls']} too few for {d['rows']} rows; use >= {20 * d['rows']}")
    if kind == "solid" and not problems and d["shape"] not in SOLID_SHAPES:
        problems.append(f"solid shape {d['shape']!r}: use one of {', '.join(SOLID_SHAPES)}")
    if kind == "solid" and not problems and d["shape"] == "hull":
        pts = d.get("points")
        if not (isinstance(pts, list) and len(pts) >= 4
                and all(isinstance(p, (list, tuple)) and len(p) == 3 for p in pts)):
            problems.append("solid shape 'hull' needs data['points']: its corners [[x, y, z], ...] (4 or more)")
    return problems


def check_plan_displays(plan: ScenePlan) -> None:
    """Rules across beats that a display sets for its kind (a system's items move between parts, ...)."""
    errors = []
    for disp in displays.all_displays():
        if disp.check_plan is not None:
            errors += [f"<{disp.tag}> {e}" for e in disp.check_plan(plan)]
    if errors:
        raise ValidationError("SCENE_PLAN pictures:\n- " + "\n- ".join(errors))


# Kinds that make up a beat's picture (text/tex/number are captions to it).
PICTURE_KINDS = frozenset({"solid", "field", "line", "angle", "face", "galton", "shape", "arrow", "axes", "custom",
                           *(d.kind for d in displays.all_displays() if d.kind and d.picture)})


def _picture_states(beat) -> dict[str, str]:
    """What each picture shows, minus a drawing's free-text ``shows`` (reworded every beat even
    when nothing on screen changes)."""
    return {o.id: json.dumps({k: v for k, v in o.data.items() if not (o.kind == "drawing" and k == "shows")},
                             sort_keys=True, default=str)
            for o in beat.objects if not isinstance(o, str) and o.kind in PICTURE_KINDS}


def check_plan_grounding(plan: ScenePlan, knowledge: KnowledgePack, computed: set[float] = frozenset()) -> None:
    """Every key concept is taught by a beat; every object carries data; every
    displayed number is traceable to the knowledge pack or to what Agent 1's tools printed
    (``computed``; no invented values)."""
    concepts = {c.name.strip().lower(): c.name for c in knowledge.key_concepts}
    known = knowledge_numbers(knowledge) | set(computed)
    taught: set[str] = set()
    errors: list[str] = []
    for scene in plan.scenes:
        for b, beat in enumerate(scene.beats):
            tag = f"Scene {scene.id} beat {b}"
            if beat.teaches is not None:
                key = beat.teaches.strip().lower()
                if key not in concepts:
                    errors.append(f"{tag}: teaches {beat.teaches!r} is not a key concept {list(concepts.values())}")
                taught.add(key)
            for obj in beat.objects:
                if isinstance(obj, str):
                    errors.append(
                        f"{tag}: object {obj!r} is a bare name; give {{'id', 'kind', 'data', 'source'}} "
                        "with the content it displays"
                    )
                    continue
                errors.extend(f"{tag} object {obj.id!r}: {p}" for p in _object_problems(obj))
                if obj.source.strip().lower() == "visual":
                    continue
                for key, val in obj.data.items():
                    if key not in DISPLAY_KEYS:
                        continue
                    bad = [n for n in _numbers_in(val) if not _traceable(n, known)]
                    if bad:
                        near = "; ".join(f"{n:g}: {', '.join(_nearest(n, known))}" for n in bad[:3])
                        errors.append(
                            f"{tag} object {obj.id!r}: data[{key!r}] shows {bad} which do not appear in "
                            "KNOWLEDGE_PACK (use worked_examples values; never invent numbers). Known values "
                            f"nearest to them ({near}): use one of those, or drop the number"
                        )
    untaught = [name for key, name in concepts.items() if key not in taught]
    if untaught:
        errors.append(f"key concepts never taught by any beat (set beat.teaches): {untaught}")
    if errors:
        raise ValidationError("SCENE_PLAN grounding failed:\n- " + "\n- ".join(errors))


# Kinds that make up a beat's picture (text/tex/number are captions to it).
MAX_CUTS_PER_SCENE = 1


def plan_cuts(plan: ScenePlan) -> list[tuple[str, int]]:
    """(scene id, beat index) of every beat whose picture shares no id with the previous beat's."""
    cuts = []
    for scene in plan.scenes:
        prev: set[str] = set()
        for b, beat in enumerate(scene.beats):
            ids = {o.id for o in beat.objects if not isinstance(o, str) and o.kind in PICTURE_KINDS}
            if b and prev and not (ids & prev):
                cuts.append((scene.id, b))
            prev = ids
    return cuts


def check_plan_motion(plan: ScenePlan) -> None:
    """Each scene evolves one picture: at most MAX_CUTS_PER_SCENE beats replace it outright."""
    by_scene: dict[str, list[int]] = {}
    for sid, b in plan_cuts(plan):
        by_scene.setdefault(sid, []).append(b)
    errors = [f"Scene {sid}: beats {beats} each replace the whole picture (no visual id carried over "
              f"from the beat before); at most {MAX_CUTS_PER_SCENE} per scene. Keep the main visual's "
              "id and change its data, add one element beside it, or merge the beats"
              for sid, beats in by_scene.items() if len(beats) > MAX_CUTS_PER_SCENE]
    if errors:
        raise ValidationError("SCENE_PLAN plays like slides:\n- " + "\n- ".join(errors))


MAX_WORDS_ONLY_PER_SCENE = 1


def check_plan_pictures(plan: ScenePlan) -> None:
    """A video is pictures: in each scene at most one beat shows only words and numbers
    (text, tex, number readouts) and no visual."""
    errors = []
    for scene in plan.scenes:
        bare = [b for b, beat in enumerate(scene.beats)
                if not any(not isinstance(o, str) and o.kind in PICTURE_KINDS for o in beat.objects)]
        if len(bare) > MAX_WORDS_ONLY_PER_SCENE:
            errors.append(f"Scene {scene.id}: beats {bare} show only text/tex/number readouts; at most "
                          f"{MAX_WORDS_ONLY_PER_SCENE} per scene. Give each a visual the numbers belong "
                          "to (bars or a chart of the quantities, an array or grid of the items, a drawing "
                          "of the situation, a solid), and keep it across beats")
    if errors:
        raise ValidationError("SCENE_PLAN has beats with no picture:\n- " + "\n- ".join(errors))


def check_plan_walkthrough(plan: ScenePlan, knowledge: KnowledgePack) -> None:
    """The worked example is shown whole: every walkthrough step gets its own beat, in order."""
    walk = knowledge.walkthrough
    if walk is None:
        return
    n = len(walk.steps)
    shown: list[tuple[str, int]] = []
    errors = []
    for scene in plan.scenes:
        for b, beat in enumerate(scene.beats):
            if beat.walkthrough_step is None:
                continue
            if not 0 <= beat.walkthrough_step < n:
                errors.append(f"Scene {scene.id} beat {b}: walkthrough_step {beat.walkthrough_step} "
                              f"is not a step index 0..{n - 1}")
                continue
            shown.append((f"{scene.id} beat {b}", beat.walkthrough_step))
    steps = [i for _, i in shown]
    missing = [i for i in range(n) if i not in steps]
    if missing:
        errors.append("walkthrough steps never shown: " + "; ".join(
            f"{i} ({walk.steps[i].action!r})" for i in missing)
            + ". Give each step its own beat (set walkthrough_step) whose objects show that step's state")
    dup = sorted({i for i in steps if steps.count(i) > 1})
    if dup:
        errors.append(f"walkthrough steps {dup} are shown by more than one beat; one beat per step")
    if steps != sorted(steps):
        errors.append(f"walkthrough steps appear out of order {steps}; show them in order")
    if errors:
        raise ValidationError("SCENE_PLAN must show the whole worked example:\n- " + "\n- ".join(errors))


# ---------------------------------------------------------------------------
# Template copying: VO lines must not paraphrase the few-shot example
# ---------------------------------------------------------------------------

_VO_LINE_RE = re.compile(r'"vo_line"\s*:\s*"([^"]+)"')
_WORD_RE = re.compile(r"[a-z']+")


def example_vo_lines_from_template(template: str) -> list[str]:
    """VO lines of the worked example embedded in an Agent 2 prompt."""
    return sorted(set(_VO_LINE_RE.findall(template)))


# Glue words and numbers don't make a line a copy: "so the pair becomes 2 and 3" is just how a
# step reads, whatever the example said; a shared run has to carry real words to count.
_GLUE = frozenset("a an the and or but so then now it its is are was be to of in on at by for "
                  "with from as that this these those we you they he she one two".split())


def _vo_similarity(a: str, b: str) -> tuple[int, float]:
    """(content words in the longest shared run, overall similarity ratio)."""
    from difflib import SequenceMatcher

    wa, wb = _WORD_RE.findall(a.lower()), _WORD_RE.findall(b.lower())
    sm = SequenceMatcher(None, wa, wb, autojunk=False)
    longest = max((sum(1 for w in wa[m.a:m.a + m.size] if w not in _GLUE and not w.isdigit())
                   for m in sm.get_matching_blocks()), default=0)
    return longest, sm.ratio()


def check_vo_not_copied(plan: ScenePlan, example_vo_lines, max_run: int = 3, max_ratio: float = 0.6) -> None:
    """Reject VO lines that reuse the example's wording (e.g. 'Where did that
    fact live?' -> 'Where does that information live?')."""
    hits = []
    for scene in plan.scenes:
        for line in scene.vo_script:
            if len(_WORD_RE.findall(line.lower())) < 4:
                continue
            for ex in example_vo_lines:
                run, ratio = _vo_similarity(line, ex)
                if run >= max_run or ratio >= max_ratio:
                    hits.append(f"{scene.id}: {line!r} copies example line {ex!r}")
                    break
    if hits:
        raise ValidationError(
            "VO reuses the few-shot example's wording; the example shows structure only. "
            "Write lines specific to this topic:\n- " + "\n- ".join(hits)
        )
