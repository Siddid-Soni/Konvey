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
    ARC_PARTS,
    HOOK_TYPES,
    OBJECT_KINDS,
    QUESTION_ANSWERS,
    TRIPLE_RELATIONS,
    KnowledgePack,
    ObjectSpec,
    ScenePlan,
    Walkthrough,
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
    for walk in kp.walkthroughs():
        walk.concept = match_concept(walk.concept, kp) or walk.concept
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
        problems = _walkthrough_problems(kp.walkthrough, names)
        for i, walk in enumerate(kp.more_walkthroughs):
            problems += [f"more_walkthroughs[{i}]: {p}" for p in _walkthrough_problems(walk, names)]
        if problems:
            raise ValidationError("KNOWLEDGE_PACK.walkthrough:\n- " + "\n- ".join(problems))
        problems = _story_problems(kp)
        if problems:
            raise ValidationError("KNOWLEDGE_PACK story (example, hook, viewer questions, payoff):\n- "
                                  + "\n- ".join(problems))
    return kp


MIN_EXAMPLES_CONSIDERED = 3
MIN_QUESTIONS, MAX_QUESTIONS = 3, 8


def _story_problems(kp: KnowledgePack) -> list[str]:
    """The parts of the pack that decide what the video is about beyond its facts: which example,
    how it opens, which 'why?'s it answers, where it ends."""
    problems = []
    named = kp.chosen_example is not None and kp.chosen_example.named_in_request
    need = 1 if named else MIN_EXAMPLES_CONSIDERED
    if len(kp.examples_considered) < need:
        problems.append(f"examples_considered has {len(kp.examples_considered)}; give {need} or more different "
                        "examples, each {'example', 'makes_visible', 'leads_to'}, then choose one"
                        + ("" if named else " (only an example the request itself names needs no rivals)"))
    if kp.chosen_example is None or not kp.chosen_example.example.strip():
        problems.append("chosen_example is missing: {'example', 'reason', 'named_in_request'}")
    elif not named and not kp.chosen_example.reason.strip():
        problems.append("chosen_example.reason is empty: say what it shows that the other examples do not")
    if kp.hook is None:
        problems.append("hook is missing: {'shown', 'tension', 'question', 'withheld', 'why_care', 'problem'}")
    else:
        kp.hook.type = kp.hook.type.strip().lower()
        if kp.hook.type and kp.hook.type not in HOOK_TYPES:
            problems.append(f"hook.type {kp.hook.type!r} is not one of {list(HOOK_TYPES)}")
        for f, what in (("shown", "the concrete thing the opening puts on screen"),
                        ("tension", "what is strange about it, or the instinct the viewer cannot justify yet"),
                        ("question", "the open question the opening ends on")):
            if not getattr(kp.hook, f).strip():
                problems.append(f"hook.{f} is empty: {what}")
        if not 1 <= len([w for w in kp.hook.withheld if w.strip()]) <= 4:
            problems.append("hook.withheld needs 1-4 short phrases the opening must not say because they give the "
                            "answer away (the result, the method's name, the principle's name)")
        if not kp.hook.why_care.strip():
            problems.append("hook.why_care is empty: why should anyone spend ten minutes on this question "
                            "(what it matters for, what it is really about, why it seems impossible, why it "
                            "confuses everyone)? The question itself goes in hook.problem")
        if not kp.hook.problem.strip():
            problems.append("hook.problem is empty: the concrete question, stated after why_care")
    a = kp.naive_attempt
    if a is None or not (a.attempt.strip() and a.falls_short.strip() and a.sharper_question.strip()):
        problems.append("naive_attempt needs 'attempt' (what anyone would try first), 'falls_short' (exactly where "
                        "it fails, with numbers) and 'sharper_question' (the better question that leads to)")
    if not kp.promise.strip():
        problems.append("promise is empty: what the viewer will be able to see or do by the end, concretely")
    if not 2 <= len(kp.exploration) <= 4:
        problems.append(f"exploration has {len(kp.exploration)} cases; give 2-4 small cases, simplest first, "
                        "up to the troublesome one, each {'case', 'what_happens'}")
    ins = kp.insight
    if ins is None or not all(getattr(ins, f).strip() for f in ("hunch", "made_precise", "idea", "why_it_holds",
                                                                 "why_it_settles")):
        problems.append("insight needs 'hunch', 'made_precise', 'idea', 'why_it_holds' and 'why_it_settles'")
    n = len(kp.viewer_questions)
    if not MIN_QUESTIONS <= n <= MAX_QUESTIONS:
        problems.append(f"viewer_questions has {n}; give {MIN_QUESTIONS}-{MAX_QUESTIONS}: every 'why?' a viewer "
                        "would ask (why this number, why not fewer, why the formula holds, why it has this "
                        "name, why it matters), each {'question', 'answer', 'shown_by'}")
    for i, q in enumerate(kp.viewer_questions):
        q.shown_by = q.shown_by.strip().lower()
        if q.shown_by not in QUESTION_ANSWERS:
            problems.append(f"viewer_questions[{i}].shown_by {q.shown_by!r} is not one of {list(QUESTION_ANSWERS)}")
        if not q.answer.strip():
            problems.append(f"viewer_questions[{i}] ({q.question!r}) has no answer")
    pay = kp.payoff
    if pay is None or not all(getattr(pay, f).strip() for f in ("lesson", "generalisation", "surprise",
                                                                 "closes_opening")):
        problems.append("payoff needs 'lesson' (what this was an example of), 'generalisation' (the general "
                        "rule), 'surprise' (a different situation the same idea settles) and 'closes_opening' "
                        "(how the ending answers hook.why_care)")
    return problems


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


def _walkthrough_problems(w: Walkthrough | None, concept_names: set[str]) -> list[str]:
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
        if not step.why.strip():
            problems.append(f"steps[{i}] ({step.action!r}) has no why: give the rule or comparison that "
                            "decides it, with its numbers")
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
        check_plan_requested(plan, knowledge)
        check_plan_answers(plan, knowledge)
        check_plan_arc(plan, knowledge)
        check_plan_formulas(plan)
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
     "edges", "items", "holds", "parts", "chains"}
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
        "surface3d": ["x", "y", "z"], "paths": ["fn"], "particles": ["bodies"], "waves": ["fn"], "flow": ["fn"],
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
    """Every worked example is shown whole: each step of each walkthrough gets its own beat, in
    order (a beat's ``walkthrough`` says which example its step is from)."""
    walks = knowledge.walkthroughs()
    if not walks:
        return
    shown: dict[int, list[int]] = {w: [] for w in range(len(walks))}
    errors = []
    for scene in plan.scenes:
        for b, beat in enumerate(scene.beats):
            if beat.walkthrough_step is None:
                continue
            if not 0 <= beat.walkthrough < len(walks):
                errors.append(f"Scene {scene.id} beat {b}: walkthrough {beat.walkthrough} is not 0 "
                              f"(walkthrough) or 1..{len(walks) - 1} (more_walkthroughs)")
                continue
            n = len(walks[beat.walkthrough].steps)
            if not 0 <= beat.walkthrough_step < n:
                errors.append(f"Scene {scene.id} beat {b}: walkthrough_step {beat.walkthrough_step} "
                              f"is not a step index 0..{n - 1}")
                continue
            shown[beat.walkthrough].append(beat.walkthrough_step)
    for w, walk in enumerate(walks):
        name = "walkthrough" if w == 0 else f"more_walkthroughs[{w - 1}] (walkthrough {w})"
        steps = shown[w]
        missing = [i for i in range(len(walk.steps)) if i not in steps]
        if missing:
            errors.append(f"{name} steps never shown: " + "; ".join(
                f"{i} ({walk.steps[i].action!r})" for i in missing)
                + ". Give each step its own beat (set walkthrough_step"
                + ("" if w == 0 else f" and walkthrough {w}") + ") whose objects show that step's state")
        dup = sorted({i for i in steps if steps.count(i) > 1})
        if dup:
            errors.append(f"{name} steps {dup} are shown by more than one beat; one beat per step")
        if steps != sorted(steps):
            errors.append(f"{name} steps appear out of order {steps}; show them in order")
    if errors:
        raise ValidationError("SCENE_PLAN must show the whole worked example:\n- " + "\n- ".join(errors))


_WHERE = re.compile(r"(S[123])\D*?(\d+)")


def check_plan_requested(plan: ScenePlan, knowledge: KnowledgePack) -> None:
    """Everything the request asked to be shown is placed: ``requested_shown`` names, for each
    ``KNOWLEDGE_PACK.requested`` item, beats of this plan that show it."""
    if not knowledge.requested:
        return
    beats = {(s.id, b) for s in plan.scenes for b in range(len(s.beats))}
    by_text = {_concept_key(e.item): e for e in plan.requested_shown}
    errors = []
    for i, item in enumerate(knowledge.requested):
        entry = by_text.get(_concept_key(item))
        if entry is None and i < len(plan.requested_shown):
            entry = plan.requested_shown[i]
        if entry is None or not entry.where:
            errors.append(f"{item!r} is not placed: add {{\"item\": {item!r}, \"where\": [\"S2 beat 1\", …]}} "
                          "naming the beats whose objects show it, and make sure they do")
            continue
        for w in entry.where:
            m = _WHERE.search(w)
            if not m or (m.group(1), int(m.group(2))) not in beats:
                errors.append(f"{item!r}: {w!r} is not a beat of this plan (write \"S2 beat 3\", "
                              "beats counted from 0)")
    if errors:
        raise ValidationError("SCENE_PLAN.requested_shown: show everything the request asked for:\n- "
                              + "\n- ".join(errors))


def _beat_refs(where: list[str], beats: set[tuple[str, int]]) -> tuple[list[tuple[str, int]], list[str]]:
    """("S2 beat 3" entries that are beats of the plan, entries that are not)."""
    good, bad = [], []
    for w in where:
        m = _WHERE.search(w)
        if m and (m.group(1), int(m.group(2))) in beats:
            good.append((m.group(1), int(m.group(2))))
        else:
            bad.append(w)
    return good, bad


def check_plan_answers(plan: ScenePlan, knowledge: KnowledgePack) -> None:
    """Every 'why?' Agent 1 expects a viewer to ask is answered on screen: ``answers`` names,
    for each ``KNOWLEDGE_PACK.viewer_questions`` item, beats of this plan that answer it."""
    if not knowledge.viewer_questions:
        return
    beats = {(s.id, b) for s in plan.scenes for b in range(len(s.beats))}
    by_text = {_concept_key(a.question): a for a in plan.answers}
    errors = []
    for i, q in enumerate(knowledge.viewer_questions):
        entry = by_text.get(_concept_key(q.question))
        if entry is None and i < len(plan.answers):
            entry = plan.answers[i]
        if entry is None or not entry.where:
            errors.append(f"{q.question!r} is never answered: add {{\"question\": {q.question!r}, \"where\": "
                          f"[\"S2 beat 1\", …]}} naming the beats that answer it ({q.shown_by}: {q.answer})")
            continue
        _, bad = _beat_refs(entry.where, beats)
        errors += [f"{q.question!r}: {w!r} is not a beat of this plan (write \"S2 beat 3\", beats counted "
                   "from 0)" for w in bad]
    if errors:
        raise ValidationError("SCENE_PLAN.answers: answer every question a viewer would ask:\n- "
                              + "\n- ".join(errors))


# Steps that come in this order (each one's first beat no earlier than the one before it).
ARC_ORDER = (("hook", "why_care", "problem", "naive_attempt", "key_insight", "why_it_holds", "lesson",
              "generalisation", "surprise", "closes_opening"),
             ("promise", "exploration", "key_insight"))
_COUNT = r"(?:\d+|two|three|four|five|six|seven|eight|nine|ten|twelve)"
# The stock opening: a count of things and a count of something else ("Five towns, seven roads, …").
INVENTORY_OPENING = re.compile(rf"^\W*(?:here are |picture |imagine |say you have |we have )?{_COUNT}\s+\w+"
                               rf"[^.?!]{{0,40}}?\b{_COUNT}\s+\w+", re.I)
_SPOKEN = re.compile(r"“([^”]*)”")


def check_plan_arc(plan: ScenePlan, knowledge: KnowledgePack) -> None:
    """The video follows the arc of how 3Blue1Brown approaches a question (``ARC_PARTS``): every
    step placed on real beats, the why first (S1 beat 0, never a list of counts), the steps in
    order, and the ending closing the opening's why in S3."""
    if knowledge.hook is None:
        return
    order = [(s.id, b) for s in plan.scenes for b in range(len(s.beats))]
    beats = set(order)
    placed: dict[str, list[tuple[str, int]]] = {}
    errors = []
    for entry in plan.arc:
        part = entry.part.strip().lower()
        if part not in ARC_PARTS:
            errors.append(f"arc part {entry.part!r} is not one of {list(ARC_PARTS)}")
            continue
        good, bad = _beat_refs(entry.where, beats)
        errors += [f"arc {part}: {w!r} is not a beat of this plan" for w in bad]
        if good:
            placed[part] = sorted(good, key=order.index)
    missing = [p for p in ARC_PARTS if p not in placed]
    if missing:
        errors.append(f"arc steps not placed: {missing}. Give each its beats: "
                      + ", ".join(f'{{"part": "{p}", "where": ["S1 beat 0"]}}' for p in missing[:2]) + ", …")
    if "hook" in placed and placed["hook"][0] != ("S1", 0):
        errors.append("the video must open with the hook (S1 beat 0): the concrete thing, what is strange about "
                      "it, the open question")
    # the answer is held back: nothing in `withheld` is said before the key insight
    stop = order.index(placed["key_insight"][0]) if "key_insight" in placed else len(order)
    lines = {(sc.id, i): line for sc in plan.scenes for i, line in enumerate(sc.vo_script)}
    before = [lines[b] for b in order[:stop] if b in lines]
    heard = " ".join(" ".join(_SPOKEN.findall(l)) or l for l in before).lower()
    told = [w for w in knowledge.hook.withheld if w.strip() and _says(heard, w)]
    if told:
        errors.append(f"the answer is given away before the key insight: the narration says {told}, which "
                      "hook.withheld holds back. Open on the concrete thing and the question, and let the "
                      "insight reveal it")
    for chain in ARC_ORDER:
        firsts = [(p, order.index(placed[p][0])) for p in chain if p in placed]
        for (p, a), (q, b) in zip(firsts, firsts[1:]):
            if b < a:
                errors.append(f"arc {q} (first at {_beat_name(order[b])}) comes before {p} "
                              f"({_beat_name(order[a])}); the order is {' → '.join(chain)}")
    if "closes_opening" in placed and placed["closes_opening"][-1][0] != "S3":
        errors.append("closes_opening belongs in S3: the ending answers the opening's why")
    first = plan.scenes[0].vo_script[0] if plan.scenes and plan.scenes[0].vo_script else ""
    said = " ".join(_SPOKEN.findall(first)) or first
    if INVENTORY_OPENING.search(said):
        errors.append(f"S1 opens with a list of counts ({said!r}). Open on the one concrete thing in "
                      f"hook.shown ({knowledge.hook.shown!r}); the counts arrive with the picture later")
    if errors:
        raise ValidationError("SCENE_PLAN.arc: follow the arc of the question:\n- " + "\n- ".join(errors))


def _says(heard: str, phrase: str) -> bool:
    """``phrase`` (all its words, in order, as whole words) is in ``heard``."""
    words = re.findall(r"[\w']+", phrase.lower())
    return bool(words) and re.search(r"\b" + r"\W+".join(map(re.escape, words)) + r"\b", heard) is not None


def _beat_name(b: tuple[str, int]) -> str:
    return f"{b[0]} beat {b[1]}"


def check_plan_formulas(plan: ScenePlan) -> None:
    """A formula is built on screen, never just shown: the first beat with a ``tex`` object names,
    in ``data.built_from``, the beats (up to and including this one) whose pictures it is read off
    or derived in."""
    order = [(s.id, b) for s in plan.scenes for b in range(len(s.beats))]
    beats = set(order)
    seen: set[str] = set()
    errors = []
    for scene in plan.scenes:
        for b, beat in enumerate(scene.beats):
            for obj in beat.objects:
                if isinstance(obj, str) or obj.kind != "tex" or obj.id in seen:
                    continue
                seen.add(obj.id)
                src = obj.data.get("built_from")
                src = [src] if isinstance(src, str) else src if isinstance(src, list) else []
                tag = f"Scene {scene.id} beat {b} tex {obj.id!r}"
                if not src:
                    errors.append(f"{tag} appears without being built: give data['built_from'], the beats "
                                  "(e.g. [\"S2 beat 2\", \"S2 beat 3\"]) whose pictures show each of its "
                                  "parts first, so the formula is read off the picture, not announced")
                    continue
                good, bad = _beat_refs([str(x) for x in src], beats)
                errors += [f"{tag}: built_from {w!r} is not a beat of this plan" for w in bad]
                late = [f"{s} beat {k}" for s, k in good if order.index((s, k)) > order.index((scene.id, b))]
                if late:
                    errors.append(f"{tag}: built_from names later beats {late}; a formula comes after the "
                                  "pictures it is built from")
    if errors:
        raise ValidationError("SCENE_PLAN formulas:\n- " + "\n- ".join(errors))


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
