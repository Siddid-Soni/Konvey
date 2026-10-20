"""Pydantic contracts for the Konvey 3-agent pipeline.

Mirrors the strict JSON schemas in:
- prompts/agent1-knowledge-discovery/{zero-shot,few-shot,cot}.md
- prompts/agent2-stage/plan.md

These models are passed to Agno as ``output_schema`` (Agent 1 + 2), so the
LLM returns validated objects instead of free-form text. Domain checks with
closed vocabularies (relations, precedes chain, durations) live
in :mod:`konvey.validators` so they can run as Workflow function steps with
clear error messages (README section 2, steps 2-3).
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

from .stage.displays import kinds as _display_kinds

# Closed vocabularies (paper 2509.04481 Sec 3.2 / README section 1).
TRIPLE_RELATIONS: tuple[str, ...] = (
    "is-a",
    "part-of",
    "causes",
    "stores",
    "transforms",
    "contrasts-with",
    "example-of",
)

class KeyConcept(BaseModel):
    name: str
    definition_1line: str = Field(description="Falsifiable one-line definition")
    why_matters: str


class WorkedExample(BaseModel):
    """Concrete numbers for one key concept, so later agents never invent data.

    Ground truth: 3b1b/captions 2022/wordle ("weary ... 4.9 bits", "slate ...
    5.8 bits") and 2023/clt (5 rows, bucket counts 1-5-10-10-5-1).
    """

    concept: str = Field(description="Must equal a key_concepts[].name")
    setup: str = Field(description="Concrete instance a viewer can picture, e.g. 'a list of 8 numbers, looking for one of them'")
    values: Dict[str, Any] = Field(
        description="Named concrete values shown on screen, e.g. {'n': [1, 2, 4, 8], 'steps': [0, 1, 2, 3]}"
    )
    formula: Optional[str] = Field(default=None, description="Defining formula if any, e.g. 'I = log2(1/p)'")


class Analogy(BaseModel):
    analogy: str
    maps_to: str
    breaks_where: str = Field(description="Where the analogy breaks (required)")


class WalkStep(BaseModel):
    action: str = Field(description="What happens in this step, one sentence")
    why: str = Field(default="", description="The rule or comparison that decides this step, with its numbers")
    state: Dict[str, Any] = Field(
        description="Exact values right after this step, e.g. {'kept': [5, 8], 'compared': 8}"
    )


class Walkthrough(BaseModel):
    """One concrete instance solved from start to finish, every step written out, so the
    video can show the whole example instead of its first step and a summary."""

    concept: str = Field(description="The key_concepts[].name this example shows working")
    question: str = Field(description="What the example works out, with its concrete inputs")
    start: Dict[str, Any] = Field(description="Exact values before the first step")
    steps: List[WalkStep] = Field(description="Every step in order, none skipped or merged (3-10)")
    result: str = Field(description="The answer the steps reach, with its number")


# How 3Blue1Brown approaches a question (github.com/3b1b/captions, measured on his standalone
# videos; see docs/superpowers/specs/2026-10-19-3b1b-gaps-plan.md): why this question is worth your time, the obvious attempt and
# where it falls short, a sharper question and a promise, small cases growing to the troublesome
# one, a hunch made precise, the key insight with why it holds and why it settles the question,
# objections and edge cases answered, then a step back: the lesson, the general rule, a surprise,
# and the opening's why closed. No "why?" is left open.
HOOK_TYPES: tuple[str, ...] = (
    "stakes",      # what it matters for: "central to scientific discovery"
    "vehicle",     # what the question is really about: "a lesson in information theory"
    "surprise",    # it seems impossible or too good: "the universe is messing with you"
    "confusion",   # famous yet rarely understood: "one of the most famous equations, and most confusing"
)
QUESTION_ANSWERS: tuple[str, ...] = ("picture", "derivation", "counterexample", "trials")
ARC_PARTS: tuple[str, ...] = ("hook", "why_care", "problem", "naive_attempt", "promise", "exploration",
                              "key_insight", "why_it_holds", "lesson", "generalisation",
                              "surprise", "closes_opening")


class ExampleOption(BaseModel):
    example: str = Field(description="One concrete instance the video could be built around")
    makes_visible: str = Field(description="What a viewer sees happen in it")
    leads_to: str = Field(description="Where it leads: the general rule or the surprise it sets up")


class ChosenExample(BaseModel):
    example: str = Field(description="The example the video uses (one of examples_considered)")
    reason: str = Field(description="Why it beats the others: what it shows that they do not")
    named_in_request: bool = Field(default=False, description="True when the request itself names this example")


class Hook(BaseModel):
    """How 3Blue1Brown opens: a concrete thing on screen, what is strange about it, and a question the
    viewer cannot answer yet. The answer is held back ("This is a 3… appreciate how crazy it is
    that brains can do this so effortlessly"; "the pattern equals pi every time. But it doesn't.
    At some point it stops.")."""

    shown: str = Field(default="", description="The concrete thing the opening puts in front of the viewer: an object, "
                                               "an observation, a choice they face, with its numbers")
    tension: str = Field(default="", description="What is strange about it, or the instinct the viewer has but cannot "
                                                 "yet justify")
    question: str = Field(default="", description="The open question the opening ends on; the viewer cannot answer it yet")
    withheld: List[str] = Field(default_factory=list,
                                description="1-4 short phrases the opening must not say because they give the answer "
                                            "away: the result, the method's name, the principle's name, its key word")
    type: str = Field(default="", description=f"Which kind of reason to care comes after: one of {', '.join(HOOK_TYPES)}")
    why_care: str = Field(description="After the question: why it deserves the viewer's next ten minutes (what it "
                                      "matters for, what it is really a lesson in), without the answer")
    problem: str = Field(description="The concrete question the video works on, stated after why_care")
    idea: str = Field(default="", description="(old name) the opening in one sentence")


class Attempt(BaseModel):
    attempt: str = Field(description="The first thing anyone would try")
    falls_short: str = Field(description="Exactly where and why it fails or disappoints, with numbers")
    sharper_question: str = Field(description="The better question its failure leads to")


class Case(BaseModel):
    case: str = Field(description="One small case, simplest first")
    what_happens: str = Field(description="What the viewer sees happen in it, with numbers")


class Insight(BaseModel):
    hunch: str = Field(description="The vague idea the small cases suggest")
    made_precise: str = Field(description="The hunch made exact, usually by putting a number to it")
    idea: str = Field(description="The key insight, one sentence")
    why_it_holds: str = Field(description="Why the insight is true, step by step")
    why_it_settles: str = Field(description="Why the insight answers the sharper question in every case")


class ViewerQuestion(BaseModel):
    question: str = Field(description="A 'why?' or an objection a smart beginner would raise while watching "
                                      "('you might think…')")
    answer: str = Field(description="The answer, with its numbers or its argument")
    shown_by: str = Field(description=f"How the video answers it on screen: one of {', '.join(QUESTION_ANSWERS)}")


class Payoff(BaseModel):
    lesson: str = Field(default="", description="What this was an example of: the technique or idea to keep")
    generalisation: str = Field(description="The example's lesson as the general rule, with the rule's numbers or formula")
    surprise: str = Field(description="A different situation the same idea settles, which the viewer would not expect, with its numbers")
    closes_opening: str = Field(default="", description="How the ending answers hook.why_care")


class KnowledgePack(BaseModel):
    """Agent 1 output: USER_PROMPT -> KNOWLEDGE_PACK JSON. No layout, no code; what the request
    asks to be shown is carried in ``requested``."""

    topic: str
    audience: str = "smart beginner, no prerequisites beyond high-school math"
    core_claim: str
    key_concepts: List[KeyConcept] = Field(min_length=1)
    mechanism_steps: List[str] = Field(
        min_length=1, description="Ordered causal steps, 4-7 preferred"
    )
    common_misconceptions: List[str] = Field(default_factory=list)
    analogy_candidates: List[Analogy] = Field(default_factory=list)
    narration_beats_3b1b_style: List[str] = Field(
        description="Concrete hook -> intuition -> late formal term"
    )
    knowledge_triples: List[List[str]] = Field(
        description="[Subject, Relation, Object]; relation from TRIPLE_RELATIONS"
    )
    scope_exclusions: List[str] = Field(default_factory=list)
    worked_examples: List[WorkedExample] = Field(
        default_factory=list,
        description="One or more per key concept: concrete setup + values (grounded mode requires them)",
    )
    walkthrough: Optional[Walkthrough] = Field(
        default=None,
        description="One example worked fully, step by step (required in grounded mode)",
    )
    more_walkthroughs: List[Walkthrough] = Field(
        default_factory=list,
        description="One more example worked fully for each further method the request asks to see "
                    "working (e.g. a second way to handle the same case); usually empty",
    )
    requested: List[str] = Field(
        default_factory=list,
        description="Each thing the request asks the video to show or do (a picture, a table, an "
                    "example, a method, a comparison), one per entry, in the request's words; "
                    "empty when it names none",
    )
    examples_considered: List[ExampleOption] = Field(
        default_factory=list,
        description="3-4 different examples the video could be built around (just 1 when the "
                    "request names its example)",
    )
    chosen_example: Optional[ChosenExample] = Field(default=None, description="The example used, and why")
    hook: Optional[Hook] = Field(default=None, description="The opening: a concrete thing, what is strange about it, an open question; then why it matters")
    naive_attempt: Optional[Attempt] = Field(default=None, description="The obvious attempt and where it falls short")
    promise: str = Field(default="", description="What the viewer will be able to see or do by the end, concretely")
    exploration: List[Case] = Field(default_factory=list, description="2-4 small cases, simplest first, up to the troublesome one")
    insight: Optional[Insight] = Field(default=None, description="The hunch, made precise, the key insight and its why")
    viewer_questions: List[ViewerQuestion] = Field(
        default_factory=list,
        description="Every 'why?' a viewer would ask (3-8), each answered and shown on screen",
    )
    payoff: Optional[Payoff] = Field(default=None, description="The step back: lesson, general rule, a surprise, the opening's why closed")

    def walkthroughs(self) -> List[Walkthrough]:
        """``walkthrough`` then ``more_walkthroughs``: a beat's ``walkthrough`` index counts here."""
        return ([self.walkthrough] if self.walkthrough is not None else []) + list(self.more_walkthroughs)


# Object kinds Agent 2 may declare. "bars", "galton" and "tiles" are built by
# render/konvey_kit.py from data, so Agent 3 never computes or invents values.
# Kinds drawn by a stage display (konvey/stage/displays/<name>/) come from there.
OBJECT_KINDS: tuple[str, ...] = (
    "text",
    *_display_kinds(),
    "galton",
    "shape",
    "arrow",
    "axes",
    "solid",
    "field",
    "line",
    "angle",
    "face",
    "surface3d",
    "paths",
    "particles",
    "waves",
    "flow",
    "custom",
)


class ObjectSpec(BaseModel):
    """One on-screen object with the data it displays."""

    id: str = Field(description="Python variable name Agent 3 must use")
    kind: str = Field(description=f"One of: {', '.join(OBJECT_KINDS)}")
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Content to display: {'text': ...}, {'labels': [...], 'values': [...]}, {'rows': 5, 'balls': 64}",
    )
    source: str = Field(
        default="",
        description="Where data came from, e.g. 'worked_examples[0].values' or 'visual' for pure decoration",
    )


class Beat(BaseModel):
    vo_line: str
    teaches: Optional[str] = Field(
        default=None, description="key_concepts[].name this beat makes visible (grounded mode requires it)"
    )
    objects: List[Union[ObjectSpec, str]] = Field(max_length=5)
    walkthrough_step: Optional[int] = Field(
        default=None,
        description="Index into KNOWLEDGE_PACK.walkthrough.steps this beat shows (one step per beat)",
    )
    walkthrough: int = Field(
        default=0, description="Which worked example walkthrough_step counts in: 0 = walkthrough, "
                               "1 = more_walkthroughs[0], ...")
    camera: Optional[Dict[str, Any]] = Field(
        default=None, description="Where the 2D camera looks: {view, zoom, focus: [...], shot}, by name; "
                                  "the stage writes it on the beat (konvey.stage.check.apply_plan_state)")


class Scene(BaseModel):
    id: Literal["S1", "S2", "S3"]
    purpose: Literal["hook", "build", "payoff"] = "build"  # type: ignore[assignment]
    vo_script: List[str]
    beats: List[Beat] = Field(min_length=1)
    duration_sec: float
    precedes: Optional[Literal["S2", "S3"]] = None


class Shown(BaseModel):
    """Where the plan shows one thing the request asked for."""

    item: str = Field(description="KNOWLEDGE_PACK.requested[i], verbatim")
    where: List[str] = Field(description='The beats that show it, e.g. ["S2 beat 1", "S2 beat 2"]')


class ArcPlace(BaseModel):
    """Where the plan shows one step of the arc."""

    part: str = Field(description=f"One of: {', '.join(ARC_PARTS)}")
    where: List[str] = Field(description='The beats that show it, e.g. ["S1 beat 0"]')


class Answered(BaseModel):
    """Where the plan answers one of the viewer's questions."""

    question: str = Field(description="KNOWLEDGE_PACK.viewer_questions[i].question, verbatim")
    where: List[str] = Field(description='The beats whose picture answers it, e.g. ["S2 beat 3"]')


class ScenePlan(BaseModel):
    """Agent 2 output (via StagePlan.to_scene_plan): KNOWLEDGE_PACK -> 3-scene plan."""

    title: str
    scenes: List[Scene] = Field(min_length=3, max_length=3)
    requested_shown: List[Shown] = Field(default_factory=list)
    answers: List[Answered] = Field(default_factory=list)
    arc: List[ArcPlace] = Field(default_factory=list)


# --- planner output ------------------------------------------------------------------
# What the planner is asked for (prompts/agent2-stage/plan.md), and nothing else: agno appends
# the output model's JSON schema to the system prompt. Converted to ScenePlan right after
# (to_scene_plan), so everything downstream sees one plan type.


class StageObject(BaseModel):
    """One thing on screen in a beat, with the data it shows."""

    id: str = Field(description="snake_case id; the same id in a later beat is the same object, changed in place")
    kind: str = Field(description=f"One of: {', '.join(OBJECT_KINDS)}")
    data: Dict[str, Any] = Field(default_factory=dict, description="What it shows, per its kind (see the kinds table)")
    source: str = Field(default="", description="Where the data comes from, e.g. 'walkthrough.steps[2].state', or 'visual'")


class StageBeat(BaseModel):
    vo_line: str = Field(description="One line of the scene's vo_script, verbatim; at most 20 words")
    teaches: Optional[str] = Field(default=None, description="key_concepts[].name this beat makes visible")
    walkthrough_step: Optional[int] = Field(default=None, description="Index of the walkthrough step this beat shows, else null")
    walkthrough: int = Field(default=0, description="Which worked example that step is from: 0 = walkthrough, 1 = more_walkthroughs[0], ...")
    objects: List[StageObject] = Field(min_length=1, max_length=5, description="1 to 5 objects")


class StageScene(BaseModel):
    id: Literal["S1", "S2", "S3"]
    purpose: Literal["hook", "build", "payoff"] = "build"
    vo_script: List[str] = Field(description="The scene's narration, one line per beat, in order")
    duration_sec: float
    precedes: Optional[Literal["S2", "S3"]] = Field(default=None, description="S1 -> 'S2', S2 -> 'S3', S3 -> null")
    beats: List[StageBeat] = Field(min_length=1)


class StagePlan(BaseModel):
    """Stage planner output: exactly three scenes S1, S2, S3."""

    title: str
    scenes: List[StageScene] = Field(min_length=3, max_length=3)
    requested_shown: List[Shown] = Field(
        default_factory=list,
        description="One entry per KNOWLEDGE_PACK.requested item: the item and the beats that show it")
    answers: List[Answered] = Field(
        default_factory=list,
        description="One entry per KNOWLEDGE_PACK.viewer_questions item: the question and the beats that answer it")
    arc: List[ArcPlace] = Field(
        default_factory=list,
        description=f"One entry per step of the arc ({', '.join(ARC_PARTS)}): the beats that show it, in that order")

    def to_scene_plan(self) -> "ScenePlan":
        return ScenePlan.model_validate(self.model_dump())


# Agent 3 input is one scene of the plan; output is beat HTML.
SceneSpec = Scene


class CodedScene(BaseModel):
    """Validated Agent 3 result: one scene id + its beat HTML."""

    scene_id: Literal["S1", "S2", "S3"]
    code: str = Field(description="The <beats> document")
    vo_lines: List[str] = Field(default_factory=list)


class PipelineResult(BaseModel):
    """Everything run_pipeline() produces and writes to out_dir."""

    topic: str
    knowledge: KnowledgePack
    plan: ScenePlan
    scenes: List[CodedScene]
    out_dir: str
    # scene_id -> problems still present after all repair rounds (code kept anyway)
    rejected: Dict[str, List[str]] = Field(default_factory=dict)
