"""Fewer-agent pipelines (handoff 2026-10-16 §4), next to the 3-agent one.

```text
agents=2 (plan "2a"):
    USER_PROMPT -> Researcher (tools) -> {knowledge, plan}
                -> 3x stage director in parallel (same examples, checks, continuity, repairs)
agents=1:
    USER_PROMPT -> Solo (tools) -> <research>{knowledge, plan}</research> + 3x <scene><beats>
                -> same checks; repairs resend only the blocks that failed
```

The Researcher is Agent 1 and the stage planner in one call: its system prompt is
``prompts/lean/researcher.md`` wrapped around the same Agent 1 / planner instructions the
3-agent pipeline uses, so prompt edits there reach both. The Solo prompt adds the stage
reference (``prompts/lean/solo.md``). Outputs are written exactly like :func:`run_pipeline`
(agent1-output.json, agent2-output.json, agent3-S*.html + .py), so ``konvey.render`` works
unchanged; ``timings.json`` records the phase times and model calls for comparisons.

    uv run --group render --group layout python run_konvey_lean.py --agents 2 --prompt "..." --render
"""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Literal, Optional

from agno.agent import Agent
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from .agents import MAX_TOOL_CALLS, resolve_model
from .compute import make_tools
from .cost import fmt_usd, track
from .pipeline import (
    CodeRejected,
    PipelineConfig,
    _agent_text,
    _as_json_text,
    _feedback_block,
    _log,
    _model_label,
    _stage_check_available,
    _use_theme,
    _with_repair,
    _write_compute_log,
    _write_outputs,
    extract_beats,
    run_staging,
)
from .probe import probe_available
from .prompts import REPO_ROOT, build_agent_instructions, load_stage_template
from .schemas import CodedScene, KnowledgePack, PipelineResult, ScenePlan, StagePlan
from .validators import (
    ValidationError,
    example_vo_lines_from_template,
    extract_json,
    validate_knowledge_pack,
    validate_scene_plan,
)

AgentCount = Literal[1, 2]
LEAN_DIR = REPO_ROOT / "prompts" / "lean"
ORDER = ("S1", "S2", "S3")


class ResearchPack(BaseModel):
    """Researcher output: the knowledge pack and the plan built from it."""

    knowledge: KnowledgePack
    # StagePlan, not ScenePlan: agno puts this model's JSON schema in the Researcher's system
    # prompt, and ScenePlan carries Manim-only fields (layout, predicates, animation.code_hint)
    # that contradict the stage planner prompt; weak models then added half an `animation` block
    # and failed validation. validate_research converts to ScenePlan (.to_scene_plan()).
    plan: StagePlan


# ---------------------------------------------------------------------------
# Prompts and agents
# ---------------------------------------------------------------------------

def _fill(template: str, **parts: str) -> str:
    # str.replace, not format: the parts are full of JSON braces.
    for key, text in parts.items():
        template = template.replace("{" + key + "}", text.strip())
    return template


def researcher_instructions(config: PipelineConfig, mode: Optional[str] = None) -> str:
    return _fill(
        (LEAN_DIR / "researcher.md").read_text(encoding="utf-8"),
        agent1=build_agent_instructions(1, mode or config.mode_agent1, config.grounded),
        agent2=build_agent_instructions(2, config.mode_agent2, config.grounded),
    )


def solo_instructions(config: PipelineConfig) -> str:
    return _fill(
        (LEAN_DIR / "solo.md").read_text(encoding="utf-8"),
        agent1=build_agent_instructions(1, config.mode_agent1, config.grounded),
        agent2=build_agent_instructions(2, config.mode_agent2, config.grounded),
        agent3=load_stage_template(),
    )


def create_researcher_agent(config: PipelineConfig, mode: Optional[str] = None) -> Agent:
    return Agent(
        name="Researcher",
        model=resolve_model(config.model),  # type: ignore[arg-type]
        description="Researches the topic with compute tools, then outlines 3 scenes from it. Strict JSON.",
        instructions=researcher_instructions(config, mode),
        output_schema=ResearchPack,
        tools=make_tools(config.compute_log),
        tool_call_limit=MAX_TOOL_CALLS,
        markdown=False,
    )


def create_solo_agent(config: PipelineConfig) -> Agent:
    return Agent(
        name="SoloDirector",
        model=resolve_model(config.model),  # type: ignore[arg-type]
        description="Researches, plans and stages a whole 3-scene video (beat HTML) in one reply.",
        instructions=solo_instructions(config),
        tools=make_tools(config.compute_log),
        tool_call_limit=MAX_TOOL_CALLS,
        markdown=False,
    )


# Tests swap these for stubs.
_AGENT_MAKERS: dict[str, Callable[..., Any]] = {
    "researcher": create_researcher_agent,
    "solo": create_solo_agent,
}


def _make(name: str, config: PipelineConfig, **kw) -> Any:
    config.cost_log.out_dir = Path(config.out_dir)
    return track(_AGENT_MAKERS[name](config, **kw), config.cost_log, name.capitalize())


# ---------------------------------------------------------------------------
# Shared: validate the research, run timings
# ---------------------------------------------------------------------------

def _example_vo_lines(config: PipelineConfig) -> list[str]:
    if not config.grounded:
        return []
    return example_vo_lines_from_template(
        build_agent_instructions(2, config.mode_agent2))


def validate_research(raw: Any, config: PipelineConfig) -> tuple[KnowledgePack, ScenePlan]:
    """Same checks as Agent 1 and Agent 2 in the 3-agent pipeline; errors name the part."""
    if isinstance(raw, ResearchPack):
        data = json.loads(raw.model_dump_json())
    elif isinstance(raw, dict):
        data = raw
    else:
        data = extract_json(raw if isinstance(raw, str) else str(raw))
    if not isinstance(data, dict) or "knowledge" not in data or "plan" not in data:
        raise ValidationError('output must be one JSON object {"knowledge": {...}, "plan": {...}}')
    try:
        kp = validate_knowledge_pack(data["knowledge"], require_grounding=config.grounded,
                                     require_walkthrough=config.grounded)
    except ValidationError as e:
        raise ValidationError(f"in `knowledge`: {e}") from e
    try:
        try:   # the stage-only fields; stray Manim keys (an `animation` block) are dropped
            stage_plan = StagePlan.model_validate(data["plan"]).to_scene_plan()
        except PydanticValidationError as e:
            raise ValidationError(f"SCENE_PLAN schema violation: {e}") from e
        plan = validate_scene_plan(
            stage_plan, config.duration_sec, config.duration_tolerance,
            knowledge=kp if config.grounded else None,
            example_vo_lines=_example_vo_lines(config))
    except ValidationError as e:
        raise ValidationError(f"in `plan`: {e}") from e
    return kp, plan


class _Clock:
    def __init__(self):
        self.start = time.time()
        self.phases: dict[str, float] = {}
        self.calls = 0
        self._t = self.start

    def lap(self, phase: str) -> None:
        now = time.time()
        self.phases[phase] = round(now - self._t, 2)
        self._t = now

    def write(self, out_dir: Path, agents: int) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "timings.json").write_text(json.dumps({
            "agents": agents, "total_sec": round(time.time() - self.start, 2),
            "phases_sec": self.phases, "model_calls": self.calls}, indent=2) + "\n", encoding="utf-8")


def _counting(agent: Any, clock: _Clock) -> Any:
    """Count model calls (each .run, repairs included) without touching the agent class."""
    if getattr(agent, "_lean_counted", False):
        return agent
    run = agent.run

    def counted(*a, **k):
        clock.calls += 1
        return run(*a, **k)

    agent.run = counted
    agent._lean_counted = True
    return agent


def _use_checks(config: PipelineConfig) -> bool:
    return config.probe and probe_available() and _stage_check_available()


def _finish(config: PipelineConfig, kp: KnowledgePack, plan: ScenePlan, coded: list[CodedScene],
            rejected: dict[str, list[str]], clock: _Clock, agents: int) -> PipelineResult:
    out_dir = Path(config.out_dir)
    _write_outputs(out_dir, kp, plan, coded)
    for sid in ORDER:
        report = out_dir / f"agent3-{sid}.problems.txt"
        if sid in rejected:
            report.write_text("\n".join(rejected[sid]) + "\n", encoding="utf-8")
        elif report.exists():
            report.unlink()
    if config.repair_log:
        (out_dir / "repair-log.txt").write_text("\n\n".join(
            f"## {label} attempt {n}\n{text}" for label, n, text in config.repair_log) + "\n", encoding="utf-8")
    if config.compute_log.calls:
        _write_compute_log(config, kp)
    clock.lap("write")
    clock.write(out_dir, agents)
    cost = config.cost_log.summary()["total"]
    _log(config, f"[done] {agents}-agent run in {time.time() - clock.start:.0f}s, {clock.calls} model calls, "
                 f"{fmt_usd(cost['usd'])} ({cost['requests']} requests, cost.json)."
                 + (f" Rejected scenes: {sorted(rejected)}" if rejected else ""))
    return PipelineResult(topic=kp.topic, knowledge=kp, plan=plan, scenes=coded,
                          out_dir=str(out_dir), rejected=rejected)


def _short(feedback: str) -> str:
    lines = [ln.strip("- ") for ln in feedback.splitlines() if ln.strip()]
    return (lines[1] if len(lines) > 1 and lines[0].endswith(":") else lines[0])[:160] if lines else ""


# ---------------------------------------------------------------------------
# agents=2: Researcher -> 3 parallel stage directors
# ---------------------------------------------------------------------------

def run_research(config: PipelineConfig, clock: _Clock) -> tuple[KnowledgePack, ScenePlan]:
    """One Researcher call, repaired like Agent 1/2 (feedback + previous JSON, CoT after a miss)."""
    agent = _counting(_make("researcher", config), clock)
    _log(config, f"      model: {_model_label(agent)}")
    feedback: Optional[str] = None
    previous: Optional[str] = None
    rounds = config.repair_rounds if config.cot_retry else 0
    out = Path(config.out_dir)
    for attempt in range(rounds + 1):
        resp = agent.run(
            f"USER_PROMPT: {config.user_prompt}\nTarget duration: {config.duration_sec}\n"
            'Output the one JSON object {"knowledge": …, "plan": …}.'
            + _feedback_block(feedback, previous))
        raw = _agent_text(resp)
        try:
            return validate_research(raw, config)
        except ValidationError as e:
            previous = _as_json_text(raw)
            out.mkdir(parents=True, exist_ok=True)
            (out / f"researcher-rejected-{attempt + 1}.json").write_text(previous)
            if attempt == rounds:
                raise
            feedback = str(e)
            config.repair_log.append(("Researcher", attempt + 1, feedback))
            _log(config, f"      Researcher rejected (attempt {attempt + 1}): {_short(feedback)}")
            if config.mode_agent1 != "cot" and attempt == 0:
                agent = _counting(_make("researcher", config, mode="cot"), clock)
    raise AssertionError("unreachable")


def _direct_scenes(config: PipelineConfig, kp: KnowledgePack, plan: ScenePlan, clock: _Clock,
                   check_dir: Optional[Path]) -> tuple[list[CodedScene], dict[str, list[str]]]:
    """Same per-scene loop as run_pipeline's stage branch: written in parallel, runtime checks
    S1 -> S2 -> S3 each on the previous scene's accepted beats."""
    from .stage.examples import examples_block, select

    scenes = {s.id: s for s in plan.scenes}
    topic_text = "\n".join([config.user_prompt, kp.model_dump_json(), plan.model_dump_json()])
    done: dict[str, Future] = {sid: Future() for sid in ORDER}
    rejected: dict[str, list[str]] = {}

    def prelude(sid: str) -> Optional[Callable[[], Optional[str]]]:
        i = ORDER.index(sid)
        return (lambda: done[ORDER[i - 1]].result().code) if i else None

    def attempt(sid: str, block: str):
        def fn(agent, fb, prev):
            return run_staging(scenes[sid], _counting(agent, clock),
                               check_dir=check_dir, feedback=fb,
                               previous_html=prev.code if prev else None, examples=block,
                               prelude=prelude(sid))
        return fn

    def one(sid: str) -> CodedScene:
        picked = select(scenes[sid], topic_text, log=lambda m: _log(config, m))
        _log(config, f"      {sid} examples: {[e.name for e in picked] or 'none'}")
        try:
            coded = _with_repair(config, "coding", sid, attempt(sid, examples_block(picked)))
        except CodeRejected as e:
            rejected[sid] = e.problems
            _log(config, f"      {sid} STILL REJECTED after {config.repair_rounds} repairs "
                         f"({len(e.problems)} problems); keeping last attempt")
            coded = e.coded
        else:
            _log(config, f"      {sid} done ({len(coded.code.splitlines())} lines)")
        return coded

    def run(sid: str) -> CodedScene:
        try:
            result = one(sid)
        except BaseException as e:
            done[sid].set_exception(e)
            raise
        done[sid].set_result(result)
        return result

    with ThreadPoolExecutor(max_workers=3) as pool:
        coded = list(pool.map(run, ORDER))
    return coded, rejected


def run_two_agent(config: PipelineConfig) -> PipelineResult:
    """agents=2: Researcher (knowledge + plan, one call) -> 3 parallel stage directors."""
    _use_theme(config)
    clock = _Clock()
    check_dir = Path(config.out_dir) / "probe" if _use_checks(config) else None
    _log(config, f"[1/2] Researcher running (grounded={config.grounded}, "
                 f"checks={check_dir is not None}) ...")
    kp, plan = run_research(config, clock)
    clock.lap("research")
    _log(config, f"[1/2] Researcher done: topic={kp.topic!r} title={plan.title!r} "
                 f"scenes={[s.id for s in plan.scenes]} total={sum(s.duration_sec for s in plan.scenes)}s")
    _log(config, "[2/2] Stage directors running (S1, S2, S3 in parallel) ...")
    coded, rejected = _direct_scenes(config, kp, plan, clock, check_dir)
    clock.lap("stage")
    return _finish(config, kp, plan, coded, rejected, clock, agents=2)


# ---------------------------------------------------------------------------
# agents=1: one call for research, plan and all three scenes
# ---------------------------------------------------------------------------

_RESEARCH_RE = re.compile(r"<research>(.*?)</research>", re.S)
_SCENE_RE = re.compile(r'<scene\s+id\s*=\s*"?(S[123])"?\s*>(.*?)</scene>', re.S)


def parse_solo(content: str) -> tuple[Optional[str], dict[str, str]]:
    """Split a Solo reply into its research JSON text and per-scene beat documents.
    Missing blocks are simply absent (a repair reply sends only what changed)."""
    m = _RESEARCH_RE.search(content)
    research = m.group(1).strip() if m else None
    scenes = {}
    for sid, body in _SCENE_RE.findall(content):
        try:
            scenes[sid] = extract_beats(body)
        except ValidationError:
            scenes[sid] = ""  # present but broken: reported by the scene check
    return research, scenes


def _solo_examples(config: PipelineConfig) -> str:
    """No plan exists before the call, so take one example per genre (most general first)
    that passes the same-topic guard on the user prompt."""
    from .stage.examples import FALLBACK, MAX_EXAMPLES, examples_block, load_examples, overlaps

    allowed = [e for e in load_examples() if not overlaps(e, config.user_prompt)]
    rank = {g: i for i, g in enumerate((*FALLBACK, "chart", "cells", "world3d"))}
    picked, genres = [], set()
    for ex in sorted(allowed, key=lambda e: (rank.get(e.genre, 99), e.name)):
        if ex.genre not in genres and len(picked) < MAX_EXAMPLES:
            picked.append(ex)
            genres.add(ex.genre)
    return examples_block(picked)


def _scene_problems(sid: str, html: str, plan: ScenePlan, check_dir: Optional[Path],
                    prelude_html: Optional[str], cache: dict) -> list[str]:
    from .stage.check import check_runtime, check_static

    if not html:
        return ["no <beats>...</beats> document in this scene block"]
    scene = next(s for s in plan.scenes if s.id == sid)
    key = (sid, html, scene.model_dump_json(), prelude_html)
    if key not in cache:
        problems = check_static(html, scene)
        if check_dir is not None and not problems:
            problems += check_runtime(html, check_dir, sid, prelude_html=prelude_html)
        cache[key] = problems
    return cache[key]


def _reply_is_cut(content: str) -> bool:
    """A block was opened and never closed (the reply stopped mid-way)."""
    return (content.count("<research>") > content.count("</research>")
            or content.count("<scene") > content.count("</scene>"))


def _finish_cut_reply(agent: Any, content: str, config: PipelineConfig, tries: int = 4) -> str:
    """Some models (seen with claude-haiku) call a tool in the middle of writing the reply and then
    end their turn there, leaving it cut mid-JSON. Ask for the rest and join the pieces."""
    for _ in range(tries):
        if not _reply_is_cut(content):
            break
        _log(config, f"      Solo reply stopped mid-way at {len(content)} chars; asking for the rest")
        more = _agent_text(agent.run(
            "Your previous reply stopped in the middle. Its last lines were:\n\n"
            + content[-1500:]
            + "\n\nContinue it from exactly where it stopped: output only the rest, starting with "
              "the very next character, with no preamble and no tool calls."))
        content += more if isinstance(more, str) else str(more)
    return content


def run_one_agent(config: PipelineConfig) -> PipelineResult:
    """agents=1: Solo writes research + plan + 3 scenes; repairs resend only failing blocks."""
    _use_theme(config)
    clock = _Clock()
    out = Path(config.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    check_dir = out / "probe" if _use_checks(config) else None
    agent = _counting(_make("solo", config), clock)
    _log(config, f"[1/1] Solo running (grounded={config.grounded}, "
                 f"checks={check_dir is not None}) ...")
    _log(config, f"      model: {_model_label(agent)}")
    examples = _solo_examples(config)
    ask = (examples + "\n\n" if examples else "") + (
        f"NOW THE REAL TASK.\nUSER_PROMPT: {config.user_prompt}\nTarget duration: {config.duration_sec}\n"
        'Output <research>, then <scene id="S1">, <scene id="S2">, <scene id="S3">.')

    research: Optional[str] = None
    html: dict[str, str] = {}
    kp = plan = None
    cache: dict = {}
    problems: dict[str, list[str]] = {}
    for attempt in range(config.repair_rounds + 1):
        if attempt == 0:
            prompt = ask
        else:
            prompt = ask + "\n\nYOUR PREVIOUS REPLY WAS REJECTED. Here it is:\n" + _solo_reply(research, html) + \
                "\n\nProblems, by block:\n" + "\n\n".join(
                    f"[{block}]\n- " + "\n- ".join(p) for block, p in problems.items()) + \
                "\n\nOutput only the blocks that must change, each one complete."
        content = _agent_text(agent.run(prompt))
        content = content if isinstance(content, str) else str(content)
        content = _finish_cut_reply(agent, content, config)
        (out / f"solo-reply-{attempt + 1}.txt").write_text(content, encoding="utf-8")
        new_research, new_html = parse_solo(content)
        research = new_research or research
        html.update(new_html)

        problems = {}
        try:
            if research is None:
                raise ValidationError("no <research>...</research> block")
            kp, plan = validate_research(research, config)
        except ValidationError as e:
            problems["research"] = [str(e)]
        if plan is not None and "research" not in problems:
            for i, sid in enumerate(ORDER):
                prelude = html.get(ORDER[i - 1]) if i and check_dir is not None else None
                p = _scene_problems(sid, html.get(sid, ""), plan, check_dir, prelude, cache)
                if p:
                    problems[sid] = p
        if not problems:
            break
        feedback = "\n".join(f"[{b}] " + "; ".join(p) for b, p in problems.items())
        config.repair_log.append(("Solo", attempt + 1, feedback))
        if attempt < config.repair_rounds:
            _log(config, f"      Solo rejected (attempt {attempt + 1}): "
                         f"{', '.join(problems)} — {_short(feedback)}")
    clock.lap("solo")
    if kp is None or plan is None or "research" in problems:
        clock.write(out, agents=1)
        raise ValidationError("Solo: research/plan still rejected after repairs:\n"
                              + "\n".join(problems.get("research", [])))
    coded = [CodedScene(scene_id=sid, code=html.get(sid, ""),
                        vo_lines=list(next(s for s in plan.scenes if s.id == sid).vo_script)) for sid in ORDER]
    rejected = {sid: p for sid, p in problems.items() if sid in ORDER}
    for sid in rejected:
        _log(config, f"      {sid} STILL REJECTED after {config.repair_rounds} repairs "
                     f"({len(rejected[sid])} problems); keeping last attempt")
    return _finish(config, kp, plan, coded, rejected, clock, agents=1)


def _solo_reply(research: Optional[str], html: dict[str, str]) -> str:
    parts = [f"<research>\n{research}\n</research>"] if research else []
    parts += [f'<scene id="{sid}">\n{html[sid]}</scene>' for sid in ORDER if sid in html]
    return "\n".join(parts)


def run_lean(config: PipelineConfig, agents: AgentCount = 2) -> PipelineResult:
    return run_one_agent(config) if agents == 1 else run_two_agent(config)
