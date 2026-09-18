"""Agno agent factories for the three Konvey roles.

- Agent 1 Knowledge Discovery: USER_PROMPT -> KNOWLEDGE_PACK (structured).
- Agent 2 Planning + Scene Generation: KNOWLEDGE_PACK -> 3-scene plan (structured).
- Agent 3 Manim Coding: SCENE_SPEC (1 scene) -> .py source (plain text).

Instructions come verbatim from the repo's markdown prompts
(:mod:`konvey.prompts`) so prompt edits stay in ``prompts/``. Model is
configurable: pass any Agno ``Model`` (or ``"provider:id"`` string), or leave
``None`` to use MiniMax with ``MINIMAX_API_KEY`` + ``KONVEY_MODEL_ID``
(default MiniMax-M3) from the environment / ``.env`` file.
"""

from __future__ import annotations

import os
from typing import Optional, Union

from agno.agent import Agent
from agno.models.minimax import MiniMax
from dotenv import load_dotenv

from .prompts import PromptMode, PromptSet, build_agent_instructions
from .schemas import KnowledgePack, ScenePlan

ModelLike = Union[str, object]  # str "provider:id" or agno Model instance

DEFAULT_MODEL_ID = "MiniMax-M3"


def resolve_model(model: Optional[ModelLike] = None) -> Union[str, object]:
    if model is not None:
        return model
    load_dotenv()  # picks up .env (MINIMAX_API_KEY, KONVEY_MODEL_ID)
    return MiniMax(id=os.getenv("KONVEY_MODEL_ID", DEFAULT_MODEL_ID))


def create_knowledge_agent(
    model: Optional[ModelLike] = None,
    prompt_set: PromptSet = "set-01-mlp-facts",
    mode: PromptMode = "few-shot",
) -> Agent:
    return Agent(
        name="KnowledgeDiscovery",
        model=resolve_model(model),  # type: ignore[arg-type]
        description="3Blue1Brown-style knowledge distillation. Outputs strict JSON, no visuals, no code.",
        instructions=build_agent_instructions(1, prompt_set, mode),
        output_schema=KnowledgePack,
        markdown=False,
    )


def create_planning_agent(
    model: Optional[ModelLike] = None,
    prompt_set: PromptSet = "set-01-mlp-facts",
    mode: PromptMode = "few-shot",
) -> Agent:
    return Agent(
        name="PlanningSceneGeneration",
        model=resolve_model(model),  # type: ignore[arg-type]
        description="Plans 3 scenes S1->S2->S3 with VO, layout ops and animation hints. Decides animation; writes no full python.",
        instructions=build_agent_instructions(2, prompt_set, mode),
        output_schema=ScenePlan,
        markdown=False,
    )


def create_coding_agent(
    model: Optional[ModelLike] = None,
    prompt_set: PromptSet = "set-01-mlp-facts",
    mode: PromptMode = "few-shot",
) -> Agent:
    return Agent(
        name="ManimCoder",
        model=resolve_model(model),  # type: ignore[arg-type]
        description="Implements one SCENE_SPEC as manimgl SingleScene.construct. Implements beats verbatim; never re-plans.",
        instructions=build_agent_instructions(3, prompt_set, mode),
        markdown=False,
    )
