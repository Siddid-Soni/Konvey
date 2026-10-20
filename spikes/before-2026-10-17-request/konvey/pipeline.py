"""Orchestration for the Konvey pipeline.

```text
USER_PROMPT -> Agent1 -> KNOWLEDGE_PACK -> Agent2 -> 3-scene plan
    -> split S1/S2/S3 -> Agent3 x3 in parallel -> beat HTML (konvey.stage)
```

:func:`run_pipeline` is plain Python orchestration (Agent.run calls, a ThreadPoolExecutor
for the 3x Agent 3 fan-out, file writes). Checks: strict JSON + closed triple relations +
walkthrough (A1), 3 scenes + precedes chain + duration sum + grounding (A2), beat HTML
statically and, with manimgl + Chromium, laid out and played headless (A3).
"""

from __future__ import annotations

import json
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from . import agents as agent_factory
from .agents import ModelLike
from .compute import ComputeLog
from .cost import CostLog, fmt_usd, track
from .probe import probe_available
from .prompts import PromptMode, build_agent_instructions
from .schemas import (
    CodedScene,
    KnowledgePack,
    PipelineResult,
    Scene,
    ScenePlan,
    StagePlan,
)
from .validators import (
    ValidationError,
    coerce_content,
    computed_numbers,
    example_vo_lines_from_template,
    validate_knowledge_pack,
    validate_scene_plan,
)


@dataclass
class PipelineConfig:
    user_prompt: str
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
    # Grounding: worked examples (A1), typed data-carrying objects + every
    # concept taught + no invented numbers + no copied VO + walkthrough shown (A2).
    grounded: bool = True
    # Lay out and play each scene headless (konvey.stage.check) and repair on runtime
    # errors. Needs manimgl + playwright (uv --group render --group layout); skipped
    # when unavailable.
    probe: bool = True
    # Extra attempts per agent with the validator's errors fed back.
    repair_rounds: int = 2
    # Visual theme (konvey.stage.theme.THEMES).
    theme: str = "editorial"
    # Filled during a run: every Agent 1 compute tool call;
    # written to <out_dir>/compute-log.json.
    compute_log: ComputeLog = field(default_factory=ComputeLog)
    # Filled during a run: every model request's tokens and price; <out_dir>/cost.json.
    cost_log: CostLog = field(default_factory=CostLog)
    # Filled during a run: (agent label, attempt, full rejection text);
    # written to <out_dir>/repair-log.txt.
    repair_log: list = field(default_factory=list)


def _agent_text(response: Any) -> Any:
    return response.content


def _feedback_block(feedback: Optional[str], previous: Any = None) -> str:
    if not feedback:
        return ""
    if isinstance(previous, str) and previous.strip():
        # Patch, don't regenerate: a fresh answer fixes one problem and makes new ones.
        return (
            "\n\nYOUR PREVIOUS OUTPUT WAS REJECTED. Here it is:\n"
            f"{previous}\n\nKeep everything in it that is right and change only what the "
            f"problems below require, then output the full corrected JSON:\n{feedback}"
        )
    return (
        "\n\nYOUR PREVIOUS ATTEMPT WAS REJECTED. Fix every problem below and output the full "
        f"corrected result:\n{feedback}"
    )


def run_knowledge(
    user_prompt: str,
    knowledge_agent: Any,
    require_grounding: bool = False,
    feedback: Optional[str] = None,
    previous: Optional[str] = None,
) -> KnowledgePack:
    resp = knowledge_agent.run(
        f"USER_PROMPT: {user_prompt}\nOutput strict JSON with same keys."
        + _feedback_block(feedback, previous)
    )
    raw = _agent_text(resp)
    try:
        kp = coerce_content(raw, KnowledgePack)
        return validate_knowledge_pack(kp, require_grounding=require_grounding,
                                       require_walkthrough=require_grounding)
    except ValidationError as e:
        e.coded = _as_json_text(raw)  # carried into the repair prompt
        raise


def run_planning(
    knowledge: KnowledgePack,
    planning_agent: Any,
    duration_sec: float = 90.0,
    duration_tolerance: float = 0.25,
    grounded: bool = False,
    example_vo_lines: tuple[str, ...] | list[str] = (),
    feedback: Optional[str] = None,
    previous: Optional[str] = None,
    computed: set[float] = frozenset(),
) -> ScenePlan:
    resp = planning_agent.run(
        f"KNOWLEDGE_PACK: {knowledge.model_dump_json()}\n"
        f"Target duration: {duration_sec}\n"
        "Output the plan JSON: 3 scenes, every walkthrough step its own beat."
        + _feedback_block(feedback, previous)
    )
    raw = _agent_text(resp)
    try:
        # the planner answers in its own schema (StagePlan), converted here
        plan = coerce_content(raw, StagePlan).to_scene_plan()
        return validate_scene_plan(
            plan, duration_sec, duration_tolerance,
            knowledge=knowledge if grounded else None,
            example_vo_lines=example_vo_lines if grounded else (),
            computed=computed,
        )
    except ValidationError as e:
        e.coded = _as_json_text(raw)
        raise


def _as_json_text(raw: Any) -> str:
    if hasattr(raw, "model_dump_json"):
        return raw.model_dump_json()
    return raw if isinstance(raw, str) else json.dumps(raw, default=str)


class CodeRejected(ValidationError):
    """Agent 3 beats parsed but failed a check; carries the beats for repair."""

    def __init__(self, coded: CodedScene, problems: list[str]):
        self.coded = coded
        self.problems = problems
        super().__init__(f"{coded.scene_id} rejected:\n- " + "\n- ".join(problems))


def extract_beats(content: str) -> str:
    """Pull the ``<beats>…</beats>`` document out of a model reply (fences, chatter)."""
    start, end = content.find("<beats"), content.rfind("</beats>")
    if start >= 0 and end < 0:
        raise ValidationError(
            "Agent3 output was cut off before </beats>: the document is too long for one reply. Write "
            "it shorter: leave out attributes that do not change from the beat before where the tag "
            "allows it (a hull keeps its points), use repeats like \"1,1,2*3\" for a corner written "
            "several times, and keep only the actors each beat needs")
    if start < 0 or end < 0:
        raise ValidationError("Agent3 output has no <beats>...</beats> document; output only that document")
    return content[start:end + len("</beats>")] + "\n"


def run_staging(
    scene: Scene,
    stage_agent: Any,
    check_dir: Optional[Path] = None,
    feedback: Optional[str] = None,
    previous_html: Optional[str] = None,
    examples: str = "",
    prelude: Optional[Callable[[], Optional[str]]] = None,
) -> CodedScene:
    """Agent 3: SCENE_SPEC -> beat HTML, checked statically and
    (with manimgl + Chromium available) by laying out and playing it headless.
    ``examples`` (konvey.stage.examples) are worked scenes on other topics.
    ``prelude`` returns the previous scene's accepted beats (blocking until it is
    accepted); the runtime check then plays this scene continuing from it."""
    from .stage.check import apply_plan_state, check_runtime, check_static

    prompt = (examples + "\n\n" if examples else "") + \
        f"NOW THE REAL TASK.\nInput SCENE_SPEC: {scene.model_dump_json(exclude_none=True)}\nOutput only the <beats> document."
    if previous_html:
        prompt += f"\n\nYOUR PREVIOUS BEATS:\n{previous_html}"
    resp = stage_agent.run(prompt + _feedback_block(feedback))
    content = _agent_text(resp)
    try:
        html = extract_beats(content if isinstance(content, str) else str(content))
    except ValidationError as e:
        # Keep the previous attempt (if any), so a bad last reply never loses a scene.
        kept = CodedScene(scene_id=scene.id, code=previous_html or "", vo_lines=list(scene.vo_script))
        raise CodeRejected(kept, [str(e)]) from e
    html = apply_plan_state(html, scene)    # a system's planned state is copied in, not left to the model
    coded = CodedScene(scene_id=scene.id, code=html, vo_lines=list(scene.vo_script))
    problems = check_static(html, scene)
    if check_dir is not None and not problems:
        problems += check_runtime(html, check_dir, scene.id, prelude_html=prelude() if prelude else None)
    if problems:
        raise CodeRejected(coded, problems)
    return coded


def _write_compute_log(config: PipelineConfig, knowledge: KnowledgePack) -> None:
    """Save Agent 1's tool calls and report how much of the walkthrough they back up."""
    out = Path(config.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    calls = config.compute_log.calls
    (out / "compute-log.json").write_text(json.dumps(calls, indent=2), encoding="utf-8")
    msg = f"      compute: {len(calls)} tool calls"
    if knowledge.walkthrough is not None:
        from .validators import _numbers_in

        computed = {round(abs(n), 6) for c in calls for n in _numbers_in(c["output"])}
        walk = [n for n in _numbers_in(json.loads(knowledge.walkthrough.model_dump_json()))
                if abs(n) > 1]   # 0/1 are indices and flags, not results
        backed = sum(any(abs(abs(n) - k) <= 1e-6 * max(1, abs(n)) for k in computed) for n in walk)
        msg += f"; {backed}/{len(walk)} walkthrough numbers appear in a tool result"
    _log(config, msg)


def _write_outputs(out_dir: Path, knowledge: KnowledgePack, plan: ScenePlan, coded: list[CodedScene]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "agent1-output.json").write_text(
        knowledge.model_dump_json(indent=2), encoding="utf-8"
    )
    (out_dir / "agent2-output.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    from .stage.check import wrapper_source

    for scene in sorted(coded, key=lambda s: s.scene_id):
        html = out_dir / f"agent3-{scene.scene_id}.html"
        html.write_text(scene.code, encoding="utf-8")
        html.with_suffix(".py").write_text(wrapper_source(html), encoding="utf-8")


def _make_agent(factory_name: str, config: PipelineConfig, mode: Optional[PromptMode] = None) -> Any:
    mode_attr = {"knowledge": "mode_agent1", "planning": "mode_agent2", "coding": "mode_agent3"}[factory_name]
    maker = {
        "knowledge": agent_factory.create_knowledge_agent,
        "planning": agent_factory.create_planning_agent,
        "coding": agent_factory.create_coding_agent,
    }[factory_name]
    extra = {"compute_log": config.compute_log} if factory_name == "knowledge" else {}
    agent = maker(model=config.model, mode=mode or getattr(config, mode_attr), grounded=config.grounded,
                  **extra)
    label = {"knowledge": "Agent 1", "planning": "Agent 2", "coding": "Agent 3"}[factory_name]
    config.cost_log.out_dir = Path(config.out_dir)
    return track(agent, config.cost_log, label)


def _log(config: PipelineConfig, message: str) -> None:
    if config.verbose:
        print(message, flush=True)


def _model_label(agent: Any) -> str:
    model = getattr(agent, "model", None)
    model_id = getattr(model, "id", None) or getattr(model, "name", None) or model
    return str(model_id)


def _with_repair(config: PipelineConfig, factory_name: str, label: str, attempt_fn):
    """Call ``attempt_fn(agent, feedback, previous)``; on ValidationError feed the
    errors back, switching to CoT for the retries ("CoT on failure")."""
    mode_attr = {"knowledge": "mode_agent1", "planning": "mode_agent2", "coding": "mode_agent3"}[factory_name]
    agent = _make_agent(factory_name, config)
    feedback: Optional[str] = None
    previous = None
    rounds = config.repair_rounds if config.cot_retry else 0
    for attempt in range(rounds + 1):
        try:
            return attempt_fn(agent, feedback, previous)
        except ValidationError as e:
            raw = getattr(e, "coded", None)
            if isinstance(raw, str):  # keep the rejected reply for debugging
                out = Path(config.out_dir)
                out.mkdir(parents=True, exist_ok=True)
                (out / f"{factory_name}-rejected-{attempt + 1}.json").write_text(raw)
            if attempt == rounds:
                raise
            feedback = str(e)
            previous = raw
            config.repair_log.append((label, attempt + 1, feedback))
            lines = [ln.strip("- ") for ln in feedback.splitlines() if ln.strip()]
            first = (lines[1] if len(lines) > 1 and lines[0].endswith(":") else lines[0])[:160]
            _log(config, f"      {label} rejected (attempt {attempt + 1}): {first}")
            if getattr(config, mode_attr) != "cot" and attempt == 0:
                agent = _make_agent(factory_name, config, mode="cot")
    raise AssertionError("unreachable")


# Models whose provider caches a repeated prompt prefix (measured through OpenCode 2026-10-17:
# a prefix is readable only once the request that wrote it has finished; the session id does not
# matter).
CACHED_MODELS = ("claude-", "deepseek-")
WARM_UP = "Reply with the single word OK. (This only loads your instructions; the scene comes next.)"


def warm_cache(config: PipelineConfig, wrap: Callable[[Any], Any] = lambda agent: agent) -> None:
    """The three directors share one long system prompt. Started together, each pays for it in
    full (DeepSeek reads nothing, Claude writes it three times); one short request first puts
    it in the cache, so all three read it. ``wrap`` lets a caller count the call."""
    agent = _make_agent("coding", config)
    if not str(getattr(getattr(agent, "model", None), "id", "")).startswith(CACHED_MODELS):
        return
    try:
        wrap(agent).run(WARM_UP)
    except Exception as e:  # noqa: BLE001 - a cold cache only costs more, never breaks the run
        _log(config, f"      cache warm-up failed ({e}); directors start cold")


def run_pipeline(config: PipelineConfig) -> PipelineResult:
    """Run USER_PROMPT -> KNOWLEDGE_PACK -> plan -> 3x beat HTML."""
    _use_theme(config)
    use_probe = config.probe and probe_available() and _stage_check_available()
    _log(config, f"[1/4] Agent 1 Knowledge Discovery running "
                 f"(grounded={config.grounded}, probe={use_probe}) ...")
    _log(config, f"      model: {_model_label(_make_agent('knowledge', config))}")
    knowledge = _with_repair(config, "knowledge", "Agent 1", lambda agent, fb, prev: run_knowledge(
        config.user_prompt, agent, require_grounding=config.grounded, feedback=fb, previous=prev))
    _log(config, f"[1/4] Agent 1 done: topic={knowledge.topic!r} "
                 f"worked_examples={len(knowledge.worked_examples)}")
    # saved now, not with the rest: a plan that fails can then be diagnosed or resumed from it
    out_dir = Path(config.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "agent1-output.json").write_text(knowledge.model_dump_json(indent=2), encoding="utf-8")
    if config.compute_log.calls:
        _write_compute_log(config, knowledge)
    computed = computed_numbers(config.compute_log.calls)

    _log(config, "[2/4] Agent 2 Planning + Scene Generation running ...")
    example_lines = example_vo_lines_from_template(
        build_agent_instructions(2, config.mode_agent2)) if config.grounded else []
    plan = _with_repair(config, "planning", "Agent 2", lambda agent, fb, prev: run_planning(
        knowledge=knowledge, planning_agent=agent,
        duration_sec=config.duration_sec, duration_tolerance=config.duration_tolerance,
        grounded=config.grounded, example_vo_lines=example_lines, feedback=fb, previous=prev,
        computed=computed))
    total = sum(s.duration_sec for s in plan.scenes)
    _log(config, f"[2/4] Agent 2 done: title={plan.title!r} scenes={[s.id for s in plan.scenes]} total={total}s")

    _log(config, "[3/4] Agent 3 Stage beats running (S1, S2, S3 in parallel) ...")
    scenes = {s.id: s for s in plan.scenes}
    probe_dir = Path(config.out_dir) / "probe" if use_probe else None

    rejected: dict[str, list[str]] = {}
    # Same-topic guard: examples are matched against everything the request is about.
    topic_text = "\n".join([config.user_prompt, knowledge.model_dump_json(), plan.model_dump_json()])

    def _code(scene_id: str) -> CodedScene:
        _log(config, f"      coding {scene_id} ...")
        try:
            from .stage.examples import examples_block, select

            picked = select(scenes[scene_id], topic_text, log=lambda m: _log(config, m))
            _log(config, f"      {scene_id} examples: {[e.name for e in picked] or 'none'}")
            block = examples_block(picked)
            coded = _with_repair(config, "coding", scene_id, lambda agent, fb, prev: run_staging(
                scenes[scene_id], agent, check_dir=probe_dir,
                feedback=fb, previous_html=prev.code if prev else None, examples=block,
                prelude=_prelude(scene_id)))
        except CodeRejected as e:
            # Keep the last attempt so the other scenes and the plan survive;
            # its problems are written next to it for a manual look.
            rejected[scene_id] = e.problems
            _log(config, f"      {scene_id} STILL REJECTED after {config.repair_rounds} repairs "
                         f"({len(e.problems)} problems); keeping last attempt")
            return e.coded
        _log(config, f"      {scene_id} done ({len(coded.code.splitlines())} lines)")
        return coded

    # Scenes are written and statically checked in parallel; each runtime check waits for
    # the previous scene's final beats, so it plays the scene the way it renders.
    order = ["S1", "S2", "S3"]
    done: dict[str, Future] = {sid: Future() for sid in order}

    def _prelude(scene_id: str) -> Optional[Callable[[], Optional[str]]]:
        if order.index(scene_id) == 0:
            return None
        prev = order[order.index(scene_id) - 1]
        return lambda: done[prev].result().code

    def _run_scene(scene_id: str) -> CodedScene:
        try:
            result = _code(scene_id)
        except BaseException as e:
            done[scene_id].set_exception(e)
            raise
        done[scene_id].set_result(result)
        return result

    warm_cache(config)
    with ThreadPoolExecutor(max_workers=3) as pool:
        coded = list(pool.map(_run_scene, order))

    _log(config, f"[4/4] Writing outputs to {config.out_dir} ...")
    out_dir = Path(config.out_dir)
    _write_outputs(out_dir, knowledge, plan, coded)
    for scene_id in ("S1", "S2", "S3"):
        report = out_dir / f"agent3-{scene_id}.problems.txt"
        if scene_id in rejected:
            report.write_text("\n".join(rejected[scene_id]) + "\n", encoding="utf-8")
        elif report.exists():
            report.unlink()
    if config.repair_log:
        (out_dir / "repair-log.txt").write_text("\n\n".join(
            f"## {label} attempt {n}\n{text}" for label, n, text in config.repair_log) + "\n", encoding="utf-8")
    total = config.cost_log.summary()["total"]
    _log(config, "[4/4] Done." + (f" Rejected scenes: {sorted(rejected)}" if rejected else "")
         + f" Cost {fmt_usd(total['usd'])} for {total['requests']} model requests (cost.json).")
    return PipelineResult(
        topic=knowledge.topic, knowledge=knowledge, plan=plan, scenes=coded, out_dir=str(out_dir),
        rejected=rejected,
    )


def _stage_check_available() -> bool:
    import importlib.util

    return importlib.util.find_spec("playwright") is not None


def _use_theme(config: PipelineConfig) -> None:
    from .stage import theme

    theme.use(config.theme)
