"""Load the repo's markdown prompts as Agno agent instructions.

Layout (see prompts/README.md):
- Agent 1: prompts/agent1-knowledge-discovery/{few-shot,zero-shot,cot}.md
  + prompts/shared/agent1-{grounding,stage}.md
- Agent 2: prompts/agent2-stage/plan.md (topic-free, same for every mode)
- Agent 3: prompts/agent3-stage/reference.md (+ worked examples picked per scene)

Default policy from README section 2: few-shot, CoT on failure, zero-shot baseline.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

PromptMode = Literal["few-shot", "zero-shot", "cot"]

REPO_ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=None)
def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_agent1_template(mode: PromptMode) -> str:
    """Return the raw markdown template for Agent 1 (placeholders intact)."""
    path = REPO_ROOT / "prompts" / "agent1-knowledge-discovery" / f"{mode}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return _read_text(path)


def load_stage_template() -> str:
    """Agent 3 prompt (beat HTML; same for every mode): the tag reference only. Worked
    examples are chosen per scene (konvey.stage.examples) and sent with the scene, so they
    can be matched to its visuals and kept off its topic."""
    from .stage import displays   # each display's own docs fill {{display_tags}} / {{display_sections}}

    return displays.fill_agent3(_read_text(REPO_ROOT / "prompts" / "agent3-stage" / "reference.md"))


def load_plan_template() -> str:
    """Agent 2 prompt: topic-free planner, same for every mode; the stage director decides
    layout and motion."""
    from .stage import displays   # {{plan_kinds: …}}: each display's row in the kinds table

    return displays.fill_plan(_read_text(REPO_ROOT / "prompts" / "agent2-stage" / "plan.md"))


def build_agent_instructions(agent: int, mode: PromptMode = "few-shot", grounded: bool = True) -> str:
    """Compose system instructions for Agent 1, 2 or 3."""
    if agent == 3:
        return load_stage_template()
    if agent == 2:
        return load_plan_template()
    if agent != 1:
        raise ValueError(f"agent must be 1, 2 or 3, got {agent!r}")
    shared = REPO_ROOT / "prompts" / "shared"
    rules = "\n\n" + _read_text(shared / "agent1-grounding.md") if grounded else ""
    # What the stage renderer can draw shapes what data Agent 1 gathers.
    rules += "\n\n" + _read_text(shared / "agent1-stage.md")
    return load_agent1_template(mode) + rules
