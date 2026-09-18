"""Load the repo's markdown prompts as Agno agent instructions.

Layout (see prompts/README.md):
- Generic style-first prompts: prompts/agent{1,2,3}-*/{few-shot,zero-shot,cot}.md
- Per-video sets (preferred): prompts/sets/<set>/{agent1,agent2,agent3}.md
- Authority refs Agent 2/3 must obey: manim-reference/{animations,spatial-layout}.md

Default policy from README section 2: few-shot, CoT on failure, zero-shot
baseline. Per-video sets are the preferred entry point, picked by
PROMPT_SET_GUIDE (README section 4).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

PromptSet = Literal[
    "generic", "set-01-mlp-facts", "set-02-clt-galton-board", "set-03-shadows-cube"
]
PromptMode = Literal["few-shot", "zero-shot", "cot"]

REPO_ROOT = Path(__file__).resolve().parent.parent

AGENT_DIRS = {
    1: "agent1-knowledge-discovery",
    2: "agent2-planning-scene-generation",
    3: "agent3-manim-coding",
}

PROMPT_SET_GUIDE: dict[str, str] = {
    "set-01-mlp-facts": "ML mechanism / transformer internals (hook puzzle -> intuition -> late term)",
    "set-02-clt-galton-board": "Probability experiment / distributions (chaotic-one / precise-many)",
    "set-03-shadows-cube": "Geometry / 3D projection / optimization (special-cases -> general law)",
}


@lru_cache(maxsize=1)
def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_agent_template(agent: int, prompt_set: PromptSet, mode: PromptMode) -> str:
    """Return the raw markdown template for an agent (placeholders intact)."""
    if agent not in AGENT_DIRS:
        raise ValueError(f"agent must be 1, 2 or 3, got {agent!r}")
    if prompt_set == "generic":
        path = REPO_ROOT / "prompts" / AGENT_DIRS[agent] / f"{mode}.md"
    else:
        if mode != "few-shot":
            # Per-video sets only ship one prompt per agent (= few-shot for
            # that video); fall back to the generic mode file.
            path = REPO_ROOT / "prompts" / AGENT_DIRS[agent] / f"{mode}.md"
            if not path.exists():
                raise FileNotFoundError(f"Prompt file not found: {path}")
            return _read_text(path)
        names = {1: "agent1.md", 2: "agent2.md", 3: "agent3.md"}
        path = REPO_ROOT / "prompts" / "sets" / prompt_set / names[agent]
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return _read_text(path)


def load_animations_reference() -> str:
    return _read_text(REPO_ROOT / "manim-reference" / "animations.md")


def load_spatial_reference() -> str:
    return _read_text(REPO_ROOT / "manim-reference" / "spatial-layout.md")


def build_agent_instructions(agent: int, prompt_set: PromptSet, mode: PromptMode) -> str:
    """Compose system instructions: prompt file + authority refs where relevant."""
    template = load_agent_template(agent, prompt_set, mode)
    if agent == 1:
        return template
    if agent == 2:
        # Agent 2 decides layout + animation: bind it to the authority refs.
        return (
            template
            + "\n\n## Authority: animation taxonomy (manim-reference/animations.md)\n"
            + load_animations_reference()
            + "\n\n## Authority: spatial layout (manim-reference/spatial-layout.md)\n"
            + load_spatial_reference()
        )
    return template + "\n\n## Authority: spatial layout\n" + load_spatial_reference()
