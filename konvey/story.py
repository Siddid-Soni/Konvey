"""Story-first agents (four-agent redesign, W1c): the Explorer's findings and the Writer's script.

Standalone for now (scripts/story_eval_v2.py); not used by the pipeline. The Explorer works the
question and returns linked findings plus the picture the story is told on; the Writer turns
them into moves, each a change in what the viewer thinks and in the picture.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator

STEPS: tuple[str, ...] = ("hook", "why_care", "problem", "naive_attempt", "promise", "exploration",
                          "key_insight", "why_it_holds", "objections", "lesson", "generalisation",
                          "surprise", "closes_opening")
# v3: Act 1 tells the idea on one example; Act 2 (deepening onward) takes it into the topic itself.
STEPS_V3: tuple[str, ...] = ("hook", "why_care", "problem", "naive_attempt", "promise", "exploration",
                             "key_insight", "why_it_holds", "objections", "deepening", "generalisation",
                             "lesson", "surprise", "closes_opening")
Number = Union[int, float, str, List[Union[int, float, str]]]


class QuestionOption(BaseModel):
    framing: str = Field(description="One way to pose what the video answers")
    why_interesting: str = Field(description="What a viewer cannot answer yet, or would not expect")


class Example(BaseModel):
    example: str
    makes_visible: str
    leads_to: str


class PictureState(BaseModel):
    id: str = Field(description="P1, P2, …")
    shows: str = Field(description="What is on screen in this state, concretely")
    chapter: Optional[str] = Field(default=None, description="The deepening chapter this state belongs to (v3)")


class Picture(BaseModel):
    object: str = Field(description="The one thing the story is told on")
    states: List[PictureState] = Field(min_length=3)
    key_change: str = Field(description="The change between two states that carries the insight, e.g. 'P2 → P3: …'")


class Finding(BaseModel):
    id: str
    step: str
    claim: str
    numbers: Dict[str, Number] = Field(default_factory=dict)
    say: Dict[str, str] = Field(default_factory=dict, description="How each number is spoken: {'1.6449': 'about 1.64'}")
    assumption: Optional[str] = Field(default=None, description="What the claim rests on that is not the real thing, e.g. 'on a 95-word sample'")
    holds_for: str = Field(default="every case", description="How far the claim reaches: every case, this strategy, this example, checked up to …")
    source: str = "computed"
    check: str = Field(default="", description="v4: restricted Python whose asserts state the claim exactly, "
                                               "recomputed (e.g. 'assert len(range(10, 61)) == 51')")

    sim: Optional[Dict] = Field(default=None, description="v7: the run it was read off, rerun before the writer: "
                                                          "{rule, settings, t, values}")

    @field_validator("check", mode="before")
    @classmethod
    def _check_text(cls, v):
        # models write null for a finding they think needs none, or a list of asserts
        return "\n".join(map(str, v)) if isinstance(v, list) else v or ""


class Series(BaseModel):
    id: str = Field(description="S1, S2, …")
    cases: List[str] = Field(description="Finding ids, in the order they are shown")
    takeaway: str = Field(description="What the whole run of cases shows, in one sentence")


class Discovery(BaseModel):
    id: str = Field(description="D1, D2, …")
    case: str = Field(description="The finding (or series) the viewer is looking at when they notice")
    notice: str = Field(description="What is in that case's numbers or picture that points the way")
    step: str = Field(description="The reframe or strange step it suggests")
    pays_off: List[str] = Field(description="Findings that show the step was right")


class Chapter(BaseModel):
    """v3: the idea, once understood, taken into a new setting that shows more of the topic."""

    id: str = Field(description="C1, C2, …")
    setting: str
    question: str = Field(default="", description="What the first example leaves open")
    reveals: str = Field(description="What this setting shows about the topic that the first example could not")
    picture: str = Field(description="Its picture state")
    findings: List[str] = Field(default_factory=list)


class TraceStep(BaseModel):
    action: str = Field(description="What happens in this step, with its numbers")
    state: Dict = Field(description="The full state after it, in values a picture can show")


class Trace(BaseModel):
    """v7: a worked run, every step's state, so the picture shows each step exactly."""

    id: str = Field(description="T1, T2, …")
    of: str = Field(description="What run this is, concretely")
    findings: List[str] = Field(default_factory=list)
    start: Dict = Field(default_factory=dict)
    steps: List[TraceStep] = Field(min_length=1)


class Term(BaseModel):
    term: str
    plain: str = Field(description="What it means, in plain words")
    picture: Optional[str] = Field(default=None, description="The picture state that shows it, if one does")


class Exploration(BaseModel):
    question_options: List[QuestionOption] = Field(min_length=2)
    question: str = Field(description="The chosen framing")
    assumes: str = Field(description="What the viewer already knows")
    examples: List[Example] = Field(min_length=1)
    chosen_example: Example
    picture: Picture
    findings: List[Finding] = Field(min_length=10)
    series: List[Series] = Field(default_factory=list)
    discovery: List[Discovery] = Field(min_length=1)
    introduces: List[Term] = Field(default_factory=list)
    topic_core: List[str] = Field(default_factory=list)
    deepening: List[Chapter] = Field(default_factory=list)
    traces: List[Trace] = Field(default_factory=list)
    left_out: List[str] = Field(default_factory=list)
    open_thread: str = ""


class Line(BaseModel):
    line: str
    uses: List[str] = Field(default_factory=list)


class Move(BaseModel):
    act: int = Field(default=1, description="1: the idea on the first example; 2: the topic (v3)")
    chapter: Optional[str] = Field(default=None, description="The deepening chapter this move plays (v3)")
    steps: List[str] = Field(min_length=1, description="The arc steps this move covers, consecutive, in order")
    viewer_thinks: str = Field(description="The expectation, guess or question the viewer holds going in")
    changes_to: str = Field(description="What they think by the end of the move")
    answered_in: int = Field(description="Index of the move that answers viewer_thinks (this one or later)")
    picture: str = Field(description="Picture state id during this move")
    change: str = Field(description="What changes in the picture during this move")
    discovery: Optional[str] = Field(default=None, description="The discovery id this move makes visible")
    series: Optional[str] = Field(default=None, description="The series this move plays as one montage")
    introduces: List[str] = Field(default_factory=list, description="Terms first used in this move")
    lines: List[Line] = Field(min_length=1)

    @field_validator("introduces", mode="before")
    @classmethod
    def _term_names(cls, v):
        # models often copy the explorer's {"term": …} objects here; keep the names
        return [x.get("term", "") if isinstance(x, dict) else x for x in v or []]


class Length(BaseModel):
    minutes: float = Field(description="The length the story needs, up to the maximum")
    why: str = Field(description="What in the story needs that much, or no more")
    act1_words: Optional[int] = Field(default=None, description="v5: planned words for Act 1")
    act2_words: Optional[int] = Field(default=None, description="v5: planned words for Act 2")


class Script(BaseModel):
    explains: str
    length: Length
    topic_type: str
    opening_kind: str
    opening_drafts: Dict[str, List[str]] = Field(default_factory=dict)
    moves: List[Move] = Field(min_length=6)


# --- v7: the visual planner -------------------------------------------------------------------


class Camera(BaseModel):
    """Where the 2D camera looks during a beat (the stage's view/zoom/focus/shot), by name only."""

    view: Optional[str] = Field(default=None, description="An object id or 'id>part' to frame; 'page' for the whole page")
    zoom: Optional[float] = Field(default=None, description="Optional; the engine fits the target when absent")
    focus: List[str] = Field(default_factory=list, description="Object ids or 'id>part' kept bright; the rest dims")
    shot: Optional[str] = Field(default=None, description="full | question | derive | compare | title")


class VisualBeat(BaseModel):
    move: int
    line: int
    vo: str = Field(default="", description="The DramaBox prompt: speaker, voice directions, the line's words in “…”")
    objects: List[Dict] = Field(min_length=1, max_length=5, description="StageObject: {id, kind, data, source}")
    camera: Optional[Camera] = None
    trace_step: Optional[str] = Field(default=None, description="'T1.start' or 'T1.2' when the beat shows that step")
    hold: bool = Field(default=False, description="Same objects and data as the beat before")


class VisualSection(BaseModel):
    id: str = Field(description="act1, C1, C2, …, end")
    moves: List[int]
    beats: List[VisualBeat]


class VisualPlan(BaseModel):
    title: str
    sections: List[VisualSection]
