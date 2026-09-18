"""Pydantic contracts for the Konvey 3-agent pipeline.

Mirrors the strict JSON schemas in:
- prompts/agent1-knowledge-discovery/{zero-shot,few-shot,cot}.md
- prompts/agent2-planning-scene-generation/{zero-shot,few-shot,cot}.md
- prompts/sets/set-0{1,2,3}/*/agent{1,2}.md
- examples/*/agent1-output.json, agent2-output.json

These models are passed to Agno as ``output_schema`` (Agent 1 + 2), so the
LLM returns validated objects instead of free-form text. Domain checks with
closed vocabularies (relations, layout ops, precedes chain, durations) live
in :mod:`konvey.validators` so they can run as Workflow function steps with
clear error messages (README section 2, steps 2-3).
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

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

SPATIAL_RELATIONS: tuple[str, ...] = (
    "above",
    "below",
    "at left of",
    "at right of",
    "on top of",
)

# manimlib/mobject/mobject.py ops Agent 2 may emit (see
# manim-reference/spatial-layout.md). Superset of the zero-shot list so
# set-01..03 prompts and attention.py idioms (arrange_to_fit_width,
# match_height) validate.
LAYOUT_OPS: tuple[str, ...] = (
    "next_to",
    "to_edge",
    "to_corner",
    "move_to",
    "arrange",
    "arrange_in_grid",
    "arrange_to_fit_width",
    "align_to",
    "match_x",
    "match_y",
    "match_height",
    "shift",
    "scale",
    "frame_reorient",
    "target",
)

# Base animation tokens from manim-reference/animations.md +
# agent2 zero-shot ladder. Agent 2 often emits compositions
# ("Write+ShowCreation", "LaggedStart(AnimationGroup(...))"), so
# validation tokenizes on non-letters instead of exact matching.
ANIMATION_TOKENS: frozenset[str] = frozenset(
    {
        "ShowPartial",
        "ShowCreation",
        "Uncreate",
        "DrawBorderThenFill",
        "Write",
        "ShowIncreasingSubsets",
        "ShowSubmobjectsOneByOne",
        "AddTextWordByWord",
        "Fade",
        "FadeIn",
        "FadeOut",
        "FadeInFromPoint",
        "FadeOutToPoint",
        "FadeTransform",
        "FadeTransformPieces",
        "VFadeIn",
        "VFadeOut",
        "VFadeInThenOut",
        "GrowFromPoint",
        "GrowFromCenter",
        "GrowFromEdge",
        "GrowArrow",
        "FocusOn",
        "Indicate",
        "Flash",
        "CircleIndicate",
        "ShowPassingFlash",
        "FlashAround",
        "FlashUnder",
        "ShowCreationThenDestruction",
        "ShowCreationThenFadeOut",
        "ApplyWave",
        "WiggleOutThenIn",
        "TurnInsideOut",
        "FlashyFadeIn",
        "Homotopy",
        "PhaseFlow",
        "MoveAlongPath",
        "ChangingDecimal",
        "ChangeDecimalToValue",
        "CountInFrom",
        "Transform",
        "ReplacementTransform",
        "TransformFromCopy",
        "MoveToTarget",
        "ApplyMethod",
        "Restore",
        "ApplyFunction",
        "ApplyMatrix",
        "CyclicReplace",
        "Swap",
        "AnimationGroup",
        "Succession",
        "LaggedStart",
        "LaggedStartMap",
        "UpdateFromFunc",
        "UpdateFromAlphaFunc",
        "MaintainPositionRelativeTo",
        "Broadcast",
    }
)


# Video-specific custom animation classes from 3b1b/videos that Agent 2 may
# legitimately emit (ground truth: examples/example-02 uses ContextAnimation
# from _2024/transformers/attention.py). Unknown tokens still fail validation.
CUSTOM_ANIMATION_TOKENS: frozenset[str] = frozenset({"ContextAnimation"})


class KeyConcept(BaseModel):
    name: str
    definition_1line: str = Field(description="Falsifiable one-line definition")
    why_matters: str


class Analogy(BaseModel):
    analogy: str
    maps_to: str
    breaks_where: str = Field(description="Where the analogy breaks (required)")


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


class LayoutOp(BaseModel):
    op: str = Field(description=f"One of: {', '.join(LAYOUT_OPS)}")
    args: str = Field(description="Exact manim call fragment, e.g. 'a.next_to(b, UP, buff=0.5)'")


class AnimationSpec(BaseModel):
    type: str = Field(description="Base or composed animation type, e.g. 'LaggedStartMap'")
    code_hint: str = Field(description="Verbatim manim fragment Agent 3 implements")
    run_time: float
    lag_ratio: float = 0.0


class Beat(BaseModel):
    vo_line: str
    objects: List[str] = Field(max_length=5)
    object_types: List[str] = Field(default_factory=list)
    layout: List[LayoutOp] = Field(default_factory=list)
    spatial_predicates: List[List[str]] = Field(
        default_factory=list,
        description="[ObjectA, Relation, ObjectB]; relation from SPATIAL_RELATIONS",
    )
    animation: AnimationSpec


class Scene(BaseModel):
    id: Literal["S1", "S2", "S3"]
    purpose: Literal["hook", "build", "payoff"] = "build"  # type: ignore[assignment]
    vo_script: List[str]
    beats: List[Beat] = Field(min_length=1)
    duration_sec: float
    precedes: Optional[Literal["S2", "S3"]] = None


class ScenePlan(BaseModel):
    """Agent 2 output: KNOWLEDGE_PACK -> 3-scene plan. Decides layout + animation."""

    title: str
    scenes: List[Scene] = Field(min_length=3, max_length=3)


# Agent 3 input is one scene of the plan; output is manimgl source text.
SceneSpec = Scene


class CodedScene(BaseModel):
    """Validated Agent 3 result: one scene id + its manimgl source."""

    scene_id: Literal["S1", "S2", "S3"]
    code: str = Field(description="Full .py source with SingleScene.construct")
    vo_lines: List[str] = Field(default_factory=list)


class PipelineResult(BaseModel):
    """Everything run_pipeline() produces and writes to out_dir."""

    topic: str
    knowledge: KnowledgePack
    plan: ScenePlan
    scenes: List[CodedScene]
    out_dir: str
