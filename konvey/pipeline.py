"""Orchestration for the Konvey pipeline.

```text
USER_PROMPT -> Agent1 -> KNOWLEDGE_PACK -> Agent2 -> 3-scene plan
    -> split S1/S2/S3 -> Agent3 x3 in parallel -> SingleScene .py files
```

Two entry points share the same helpers/validators:

- :func:`run_pipeline` — plain Python orchestration (Agent.run calls,
  ThreadPoolExecutor for the 3x Agent 3 fan-out, file writes). Easiest to
  test, debug and run; recommended default.
- :func:`build_workflow` — the same DAG as an Agno ``Workflow`` with
  ``Step(agent=...)`` + function ``Step(executor=...)`` validation gates and
  ``Parallel`` for the coding fan-out. Use for AgentOS / streaming.

Both paths enforce README section 2 checks: strict JSON + closed triple
relations (A1), 3 scenes + precedes chain + duration sum + predicate->layout
compilation (A2), py_compile + forbidden-pattern scan (A3).
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from agno.workflow import Parallel, Step, StepInput, StepOutput, Workflow

from . import agents as agent_factory
from .agents import ModelLike
from .prompts import PromptMode, PromptSet
from .schemas import (
    CodedScene,
    KnowledgePack,
    PipelineResult,
    Scene,
    ScenePlan,
)
from .validators import (
    ValidationError,
    coerce_content,
    validate_knowledge_pack,
    validate_manim_code,
    validate_scene_plan,
)


@dataclass
class PipelineConfig:
    user_prompt: str
    prompt_set: PromptSet = "set-01-mlp-facts"
    mode_agent1: PromptMode = "few-shot"
    mode_agent2: PromptMode = "few-shot"
    mode_agent3: PromptMode = "few-shot"
    duration_sec: float = 90.0
    duration_tolerance: float = 0.25
    model: Optional[ModelLike] = None
    out_dir: str = "out/konvey-run"
    # Raised to Agent 1/2 on validation failure ("CoT on failure" policy).
    cot_retry: bool = True
    # Print flushed progress lines (which agent is running, what finished).
    verbose: bool = True


def _agent_text(response: Any) -> Any:
    return response.content


def run_knowledge(
    user_prompt: str,
    knowledge_agent: Any,
) -> KnowledgePack:
    resp = knowledge_agent.run(f"USER_PROMPT: {user_prompt}\nOutput strict JSON with same keys.")
    kp = coerce_content(_agent_text(resp), KnowledgePack)
    return validate_knowledge_pack(kp)


def run_planning(
    knowledge: KnowledgePack,
    planning_agent: Any,
    duration_sec: float = 90.0,
    duration_tolerance: float = 0.25,
) -> ScenePlan:
    resp = planning_agent.run(
        f"KNOWLEDGE_PACK: {knowledge.model_dump_json()}\n"
        f"Target duration: {duration_sec}\n"
        "Output same schema: 3 scenes, beats with layout+animation."
    )
    plan = coerce_content(_agent_text(resp), ScenePlan)
    return validate_scene_plan(plan, duration_sec, duration_tolerance)


def run_coding(scene: Scene, coding_agent: Any) -> CodedScene:
    resp = coding_agent.run(f"Input SCENE_SPEC: {scene.model_dump_json()}\nRules: implement verbatim; code only.")
    content = _agent_text(resp)
    code = content if isinstance(content, str) else str(content)
    return CodedScene(scene_id=scene.id, code=validate_manim_code(code), vo_lines=list(scene.vo_script))


def _write_outputs(out_dir: Path, knowledge: KnowledgePack, plan: ScenePlan, coded: list[CodedScene]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "agent1-output.json").write_text(
        knowledge.model_dump_json(indent=2), encoding="utf-8"
    )
    (out_dir / "agent2-output.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    for scene in sorted(coded, key=lambda s: s.scene_id):
        (out_dir / f"agent3-{scene.scene_id}.py").write_text(scene.code, encoding="utf-8")


def _with_cot_retry(factory_name: str, config: PipelineConfig) -> Any:
    """Build agent, switching mode to CoT when the few-shot attempt failed."""
    mode_attr = {"knowledge": "mode_agent1", "planning": "mode_agent2", "coding": "mode_agent3"}[factory_name]
    maker = {
        "knowledge": agent_factory.create_knowledge_agent,
        "planning": agent_factory.create_planning_agent,
        "coding": agent_factory.create_coding_agent,
    }[factory_name]
    return maker(model=config.model, prompt_set=config.prompt_set, mode=getattr(config, mode_attr))


def _log(config: PipelineConfig, message: str) -> None:
    if config.verbose:
        print(message, flush=True)


def _model_label(agent: Any) -> str:
    model = getattr(agent, "model", None)
    model_id = getattr(model, "id", None) or getattr(model, "name", None) or model
    return str(model_id)


def run_pipeline(config: PipelineConfig) -> PipelineResult:
    """Run USER_PROMPT -> KNOWLEDGE_PACK -> plan -> 3x manimgl files."""
    _log(config, f"[1/4] Agent 1 Knowledge Discovery running (prompt_set={config.prompt_set}) ...")
    knowledge_agent = _with_cot_retry("knowledge", config)
    _log(config, f"      model: {_model_label(knowledge_agent)}")
    try:
        knowledge = run_knowledge(config.user_prompt, knowledge_agent)
    except ValidationError:
        if not config.cot_retry or config.mode_agent1 == "cot":
            raise
        _log(config, "      validation failed, retrying Agent 1 with CoT ...")
        knowledge = run_knowledge(
            config.user_prompt,
            agent_factory.create_knowledge_agent(model=config.model, prompt_set=config.prompt_set, mode="cot"),
        )
    _log(config, f"[1/4] Agent 1 done: topic={knowledge.topic!r}")

    _log(config, "[2/4] Agent 2 Planning + Scene Generation running ...")
    planning_agent = _with_cot_retry("planning", config)
    try:
        plan = run_planning(planning_agent=planning_agent, knowledge=knowledge,
                            duration_sec=config.duration_sec, duration_tolerance=config.duration_tolerance)
    except ValidationError:
        if not config.cot_retry or config.mode_agent2 == "cot":
            raise
        _log(config, "      validation failed, retrying Agent 2 with CoT ...")
        plan = run_planning(
            knowledge=knowledge,
            planning_agent=agent_factory.create_planning_agent(
                model=config.model, prompt_set=config.prompt_set, mode="cot"),
            duration_sec=config.duration_sec, duration_tolerance=config.duration_tolerance,
        )
    total = sum(s.duration_sec for s in plan.scenes)
    _log(config, f"[2/4] Agent 2 done: title={plan.title!r} scenes={[s.id for s in plan.scenes]} total={total}s")

    _log(config, "[3/4] Agent 3 Manim Coding running (S1, S2, S3 in parallel) ...")
    coding_agent = _with_cot_retry("coding", config)
    scenes = {s.id: s for s in plan.scenes}

    def _code(scene_id: str) -> CodedScene:
        _log(config, f"      coding {scene_id} ...")
        try:
            coded = run_coding(scenes[scene_id], coding_agent)
        except ValidationError:
            if not config.cot_retry or config.mode_agent3 == "cot":
                raise
            _log(config, f"      {scene_id} validation failed, retrying with CoT ...")
            cot_coder = agent_factory.create_coding_agent(
                model=config.model, prompt_set=config.prompt_set, mode="cot")
            coded = run_coding(scenes[scene_id], cot_coder)
        _log(config, f"      {scene_id} done ({len(coded.code.splitlines())} lines)")
        return coded

    with ThreadPoolExecutor(max_workers=3) as pool:
        coded = list(pool.map(_code, ["S1", "S2", "S3"]))

    _log(config, f"[4/4] Writing outputs to {config.out_dir} ...")
    out_dir = Path(config.out_dir)
    _write_outputs(out_dir, knowledge, plan, coded)
    _log(config, "[4/4] Done.")
    return PipelineResult(
        topic=knowledge.topic, knowledge=knowledge, plan=plan, scenes=coded, out_dir=str(out_dir)
    )


# ---------------------------------------------------------------------------
# Agno Workflow view of the same DAG
# ---------------------------------------------------------------------------

@dataclass
class _WorkflowCtx:
    config: PipelineConfig
    coding_agent: Any = None
    extra: dict = field(default_factory=dict)


def _previous_model(step_input: StepInput, step_name: str, model: type) -> Any:
    """Find a prior structured output (content may be BaseModel/dict/str)."""
    candidates: list[Any] = []
    if step_input.previous_step_content is not None:
        candidates.append(step_input.previous_step_content)
    if step_input.previous_step_outputs:
        out = step_input.get_step_output(step_name)
        if out is not None:
            candidates.append(out.content)
        candidates.extend(o.content for o in step_input.previous_step_outputs.values())
    if isinstance(step_input.input, model):
        candidates.append(step_input.input)
    for c in candidates:
        try:
            return coerce_content(c, model)
        except (ValidationError, ValueError, TypeError, AttributeError):
            continue
    raise ValidationError(f"Could not find validated {model.__name__} in previous steps")


def build_workflow(config: PipelineConfig) -> Workflow:
    """Build the Agno Workflow: knowledge -> validate -> plan -> validate -> Parallel(3x code) -> assemble."""
    knowledge_agent = agent_factory.create_knowledge_agent(
        model=config.model, prompt_set=config.prompt_set, mode=config.mode_agent1)
    planning_agent = agent_factory.create_planning_agent(
        model=config.model, prompt_set=config.prompt_set, mode=config.mode_agent2)
    coding_agent = agent_factory.create_coding_agent(
        model=config.model, prompt_set=config.prompt_set, mode=config.mode_agent3)

    def validate_knowledge_fn(step_input: StepInput) -> StepOutput:
        kp = _previous_model(step_input, "Knowledge", KnowledgePack)
        kp = validate_knowledge_pack(kp)
        return StepOutput(content=kp.model_dump_json(), success=True)

    def validate_plan_fn(step_input: StepInput) -> StepOutput:
        plan = _previous_model(step_input, "Planning", ScenePlan)
        plan = validate_scene_plan(plan, config.duration_sec, config.duration_tolerance)
        return StepOutput(content=plan.model_dump_json(), success=True)

    def make_code_fn(scene_id: str):
        def _code_fn(step_input: StepInput) -> StepOutput:
            plan = _previous_model(step_input, "Validate plan", ScenePlan)
            scene = next(s for s in plan.scenes if s.id == scene_id)
            coded = run_coding(scene, coding_agent)
            return StepOutput(content=coded.code, success=True)

        _code_fn.__name__ = f"code_{scene_id.lower()}"
        return _code_fn

    def assemble_fn(step_input: StepInput) -> StepOutput:
        plan = _previous_model(step_input, "Validate plan", ScenePlan)
        kp = _previous_model(step_input, "Validate knowledge", KnowledgePack)
        parallel_content = step_input.get_step_content("Code scenes")
        if isinstance(parallel_content, dict):
            by_step = parallel_content
        else:  # fall back to scanning previous outputs
            by_step = {}
            for name, output in (step_input.previous_step_outputs or {}).items():
                if output.steps:
                    for sub in output.steps:
                        if sub.step_name and sub.content:
                            by_step[sub.step_name] = str(sub.content)
        order = {"Code S1": "S1", "Code S2": "S2", "Code S3": "S3"}
        coded = [
            CodedScene(scene_id=scene_id, code=validate_manim_code(by_step[step_name]))
            for step_name, scene_id in order.items()
            if step_name in by_step
        ]
        if len(coded) != 3:
            raise ValidationError(
                f"Assemble: expected code for S1/S2/S3, got steps {sorted(by_step)}"
            )
        out_dir = Path(config.out_dir)
        _write_outputs(out_dir, kp, plan, coded)
        summary = json.dumps(
            {"topic": kp.topic, "title": plan.title,
             "files": [f"agent3-{c.scene_id}.py" for c in coded], "out_dir": str(out_dir)}
        )
        return StepOutput(content=summary, success=True)

    return Workflow(
        name="Konvey explainer-video pipeline",
        description="Knowledge Discovery -> Planning + Scene Generation -> 3x parallel Manim Coding",
        steps=[
            Step(name="Knowledge", agent=knowledge_agent),
            Step(name="Validate knowledge", executor=validate_knowledge_fn),
            Step(name="Planning", agent=planning_agent),
            Step(name="Validate plan", executor=validate_plan_fn),
            Parallel(
                Step(name="Code S1", executor=make_code_fn("S1")),
                Step(name="Code S2", executor=make_code_fn("S2")),
                Step(name="Code S3", executor=make_code_fn("S3")),
                name="Code scenes",
            ),
            Step(name="Assemble", executor=assemble_fn),
        ],
    )


# ---------------------------------------------------------------------------
# Offline dry-run (no LLM): validates an existing example end-to-end
# ---------------------------------------------------------------------------

def run_dry_run(example_dir: str | Path, out_dir: str | Path) -> PipelineResult:
    """Validate examples/<example>/ outputs + code without calling any model."""
    example_dir, out_dir = Path(example_dir), Path(out_dir)
    knowledge = validate_knowledge_pack(
        json.loads((example_dir / "agent1-output.json").read_text(encoding="utf-8")))
    plan = validate_scene_plan(
        json.loads((example_dir / "agent2-output.json").read_text(encoding="utf-8")))
    coded: list[CodedScene] = []
    for scene in plan.scenes:
        code_file = example_dir / f"agent3-{scene.id}.py"
        if not code_file.exists():
            continue  # some examples ship only a subset of scenes
        coded.append(CodedScene(
            scene_id=scene.id,
            code=validate_manim_code(code_file.read_text(encoding="utf-8")),
            vo_lines=list(scene.vo_script),
        ))
    if not coded:
        raise ValidationError(f"No agent3-*.py files found in {example_dir}")
    _write_outputs(out_dir, knowledge, plan, coded)
    return PipelineResult(
        topic=knowledge.topic, knowledge=knowledge, plan=plan, scenes=coded, out_dir=str(out_dir)
    )
