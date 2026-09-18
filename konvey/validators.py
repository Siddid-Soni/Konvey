"""Domain validation for README section 2 (run order steps 2-4).

- Agent 1 -> strict JSON parse + triple relations closed.
- Agent 2 -> 3 scenes, precedes S1->S2->S3, durations sum to target,
  every predicate compiles to a layout op, animation from taxonomy.
- Agent 3 x3 -> py_compile (ast.parse) + forbid ImageMobject/external/torch.

All validators raise :class:`ValidationError` (a ValueError) with a message
naming the offending field, so Workflow function steps can fail closed.
"""

from __future__ import annotations

import ast
import json
import re
from typing import Any, Union

from pydantic import ValidationError as PydanticValidationError

from .schemas import (
    ANIMATION_TOKENS,
    CUSTOM_ANIMATION_TOKENS,
    LAYOUT_OPS,
    SPATIAL_RELATIONS,
    TRIPLE_RELATIONS,
    KnowledgePack,
    ScenePlan,
)


class ValidationError(ValueError):
    pass


# Paper 2509.04481 Sec 3.2 + manim-reference/spatial-layout.md: open-language
# relations Agent 2 must normalize to canonical predicates before compiling
# to layout ops (ground truth: examples/example-03 README maps
# contains -> on top of, stands near -> at left/right of).
OPEN_RELATION_MAP: dict[str, str] = {
    "contains": "on top of",
    "includes": "on top of",
    "sits atop": "on top of",
    "sits on": "on top of",
    "stands near": "at left of",
    "near": "at left of",
    "left of": "at left of",
    "right of": "at right of",
    "over": "above",
    "under": "below",
    "beneath": "below",
}


def normalize_spatial_relation(relation: str) -> str:
    """Map open-language spatial relations to canonical predicates."""
    rel = relation.strip().lower()
    if rel in SPATIAL_RELATIONS:
        return relation.strip()
    return OPEN_RELATION_MAP.get(rel, relation)


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
            raise ValidationError(f"Agent output is not strict JSON: {e}") from e


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
        return model.model_validate(extract_json(content))
    raise ValidationError(f"Unexpected agent content type: {type(content).__name__}")


# ---------------------------------------------------------------------------
# Agent 1
# ---------------------------------------------------------------------------

def validate_knowledge_pack(kp: Union[KnowledgePack, dict, str]) -> KnowledgePack:
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
        if triple[1] not in TRIPLE_RELATIONS:
            raise ValidationError(
                f"KNOWLEDGE_PACK.knowledge_triples[{i}] relation {triple[1]!r} not in "
                f"allowed {list(TRIPLE_RELATIONS)}"
            )
    return kp


# ---------------------------------------------------------------------------
# Agent 2
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[A-Za-z]+")
_BASE_WORDS = {"Write", "Show", "Creation", "Lagged", "Start", "Map", "Animation", "Group"}


def _animation_tokens_ok(anim_type: str) -> list[str]:
    """Split composite types (e.g. 'Write+ShowCreation') and report unknown tokens."""
    unknown = []
    for tok in _TOKEN_RE.findall(anim_type):
        if tok in ANIMATION_TOKENS or tok in CUSTOM_ANIMATION_TOKENS or tok in _BASE_WORDS:
            continue
        # Allow concatenated CamelCase containing a known token
        # (e.g. 'WriteShowCreation' without '+').
        if any(known in tok for known in ANIMATION_TOKENS if len(known) > 4):
            continue
        unknown.append(tok)
    return unknown


def validate_scene_plan(
    plan: Union[ScenePlan, dict, str],
    target_duration_sec: float = 90.0,
    duration_tolerance: float = 0.25,
) -> ScenePlan:
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
            if not beat.objects:
                raise ValidationError(f"{tag}: objects must be non-empty (<=5)")
            for pred in beat.spatial_predicates:
                if len(pred) != 3 or pred[1] not in SPATIAL_RELATIONS:
                    raise ValidationError(
                        f"{tag}: spatial predicate {pred!r} must use relation in "
                        f"{list(SPATIAL_RELATIONS)}"
                    )
            if beat.spatial_predicates and not beat.layout:
                raise ValidationError(
                    f"{tag}: every spatial predicate must compile to a layout[] op, "
                    "but layout is empty"
                )
            for op in beat.layout:
                if op.op not in LAYOUT_OPS:
                    raise ValidationError(
                        f"{tag}: layout op {op.op!r} not in allowed {list(LAYOUT_OPS)}"
                    )
            unknown = _animation_tokens_ok(beat.animation.type)
            if unknown:
                raise ValidationError(
                    f"{tag}: animation type {beat.animation.type!r} uses unknown "
                    f"token(s) {unknown}; see manim-reference/animations.md"
                )
            if beat.animation.run_time <= 0:
                raise ValidationError(f"{tag}: animation.run_time must be > 0")
    return plan


# ---------------------------------------------------------------------------
# Agent 3
# ---------------------------------------------------------------------------

# Forbidden *code* constructs. Checked against the AST (not raw text) so the
# CoT self-check comments mandated by prompts/agent3-manim-coding/cot.md
# ("# 4. Self-check: ... no forbidden APIs (ImageMobject/external/torch)?")
# cannot trigger false positives (ground truth: example-01 S1, example-02 S2).
FORBIDDEN_IMPORTS: tuple[str, ...] = (
    "torch",
    "scipy",
    "sklearn",
    "datasets",
    "requests",
    "urllib",
)

FORBIDDEN_NAMES: tuple[str, ...] = (
    "ImageMobject",
    "ImageMobjectFrom",
    "open",
)

EXTERNAL_ASSET_SUFFIXES: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".mp4", ".svg")
ABSOLUTE_PATH_MARKERS: tuple[str, ...] = ("/Users/", "/home/", "/tmp/")

REQUIRED_CODE_PATTERNS: tuple[str, ...] = (
    "from manim_imports_ext import *",
    "class SingleScene",
    "def construct",
    "# VO:",
    "self.wait()",
)


def strip_code_fences(code: str) -> str:
    m = _FENCE_RE.search(code.strip())
    if m and ("class SingleScene" in m.group(1) or "def construct" in m.group(1)):
        return m.group(1).strip()
    text = code.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text


class _ForbiddenCodeVisitor(ast.NodeVisitor):
    """Find forbidden constructs in real code (comments/strings excluded,
    except string *values* that reference external asset files)."""

    def __init__(self) -> None:
        self.hits: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name.split(".")[0] in FORBIDDEN_IMPORTS:
                self.hits.append(f"import {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if (node.module or "").split(".")[0] in FORBIDDEN_IMPORTS:
            self.hits.append(f"from {node.module} import ...")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in FORBIDDEN_NAMES:
            self.hits.append(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in FORBIDDEN_NAMES:
            self.hits.append(node.attr)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            lowered = node.value.lower()
            if any(sfx in lowered for sfx in EXTERNAL_ASSET_SUFFIXES) or any(
                marker in node.value for marker in ABSOLUTE_PATH_MARKERS
            ):
                self.hits.append(f"external asset path: {node.value[:60]!r}")
        self.generic_visit(node)


def validate_manim_code(code: str) -> str:
    """Strip fences, py_compile-equivalent parse, required/forbidden checks."""
    clean = strip_code_fences(code)
    try:
        tree = ast.parse(clean)
    except SyntaxError as e:
        raise ValidationError(f"Agent3 code does not compile: {e}") from e
    missing = [p for p in REQUIRED_CODE_PATTERNS if p not in clean]
    if missing:
        raise ValidationError(f"Agent3 code missing required pattern(s): {missing}")
    visitor = _ForbiddenCodeVisitor()
    visitor.visit(tree)
    if visitor.hits:
        raise ValidationError(
            f"Agent3 code uses forbidden construct(s) {sorted(set(visitor.hits))} "
            "(no ImageMobject/external assets/torch, see agent3 prompts)"
        )
    if "MoveToTarget" in clean and "generate_target" not in clean:
        raise ValidationError(
            "Agent3 code uses MoveToTarget without generate_target "
            "(target pattern: m.target = m.generate_target(); ...; MoveToTarget(m))"
        )
    return clean
