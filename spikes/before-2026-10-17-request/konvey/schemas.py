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


class KnowledgePack(BaseModel):
    """Agent 1 output: USER_PROMPT -> KNOWLEDGE_PACK JSON. No visuals, no code."""

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


class Scene(BaseModel):
    id: Literal["S1", "S2", "S3"]
    purpose: Literal["hook", "build", "payoff"] = "build"  # type: ignore[assignment]
    vo_script: List[str]
    beats: List[Beat] = Field(min_length=1)
    duration_sec: float
    precedes: Optional[Literal["S2", "S3"]] = None


class ScenePlan(BaseModel):
    """Agent 2 output (via StagePlan.to_scene_plan): KNOWLEDGE_PACK -> 3-scene plan."""

    title: str
    scenes: List[Scene] = Field(min_length=3, max_length=3)


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
