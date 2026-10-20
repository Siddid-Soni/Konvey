"""A story stage plan (story_eval_v7's <topic>.stage-plan.json) -> Director -> DramaBox -> video.

    DIRECTOR_MODEL=claude-haiku-5-5 uv run --group render --group layout --group speech \
        python scripts/story_render_v7.py out/story-eval-v7/ds-plan4/clacks.stage-plan.json out/story-render-v7/clacks
    ... --skip-direct     # voice + render the Director's saved scenes again
    ... --no-render       # Director only

Agent 3 (the Director) runs exactly as in konvey/pipeline.py (narration mode, examples, static +
runtime checks, repairs, scenes in parallel with each runtime check continuing the previous scene);
the plan comes from the story agents instead of Agent 2. Writes the usual run directory
(agent2-output.json, agent3-S*.html/.py, speech.json, audio/, video.mp4, cost.json).
"""
import json
import os
import re
import sys
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.chdir(Path(__file__).resolve().parents[1])
load_dotenv()
# before any konvey import: konvey.agents reads the model id when it is imported
os.environ["OPENCODE_MODEL_ID"] = os.environ["KONVEY_MODEL_ID"] = os.environ.get("DIRECTOR_MODEL", "claude-haiku-5-5")

from konvey import pipeline as P  # noqa: E402
from konvey.cost import fmt_usd  # noqa: E402
from konvey.schemas import CodedScene, ScenePlan  # noqa: E402
from konvey.speech.narrate import finish, narration_mode  # noqa: E402
from konvey.pipeline import CodeRejected  # noqa: E402


WORD_KINDS = {"text", "tex", "number"}   # as in story_eval_v7: a shot sets these as words


def pictures(objects: list) -> list:
    return [o for o in objects if o.get("kind") not in WORD_KINDS]


def load_plan(path: Path) -> ScenePlan:
    data = json.loads(path.read_text())
    for scene in data["scenes"]:
        for beat in scene["beats"]:
            beat.pop("trace_step", None)   # a label only: the step's state is in the beat's objects
            cam = beat.get("camera") or {}
            if cam.get("shot") == "compare" and len(pictures(beat["objects"])) < 2:
                cam["shot"] = None   # plans made before the planner checked this; the engine would reject it
    return ScenePlan.model_validate(data)


LAST_BEAT = re.compile(r"(<beat\b[^>]*>)(?![\s\S]*<beat\b)")
CAMERA_ATTR = re.compile(r'\s(?:view|zoom|focus)="[^"]*"')


def still_last_beat(html: str) -> str:
    """The next scene opens on this scene's last beat, and the engine then resolves that beat's
    camera against the next scene's ids (an error). Until the engine handles it, a scene ends
    with the camera at rest."""
    return LAST_BEAT.sub(lambda m: CAMERA_ATTR.sub("", m.group(1)), html, count=1)


def direct(config: P.PipelineConfig, plan: ScenePlan) -> dict[str, list[str]]:
    """Agent 3 on every scene; writes agent3-S*.html/.py. Returns the scenes still rejected."""
    from konvey.stage.check import wrapper_source
    from konvey.stage.examples import examples_block, select

    out = Path(config.out_dir)
    scenes = {s.id: s for s in plan.scenes}
    probe_dir = out / "probe" if config.probe and P._stage_check_available() else None
    topic_text = plan.model_dump_json()
    order = ["S1", "S2", "S3"]
    done: dict[str, Future] = {sid: Future() for sid in order}
    rejected: dict[str, list[str]] = {}

    def prelude(sid):
        i = order.index(sid)
        return None if i == 0 else (lambda: still_last_beat(done[order[i - 1]].result().code))

    def code(sid) -> CodedScene:
        picked = select(scenes[sid], topic_text, log=lambda m: P._log(config, m))
        P._log(config, f"      {sid} ({len(scenes[sid].beats)} beats) examples: {[e.name for e in picked] or 'none'}")
        block = examples_block(picked)
        try:
            return P._with_repair(config, "coding", sid, lambda agent, fb, prev: P.run_staging(
                scenes[sid], agent, check_dir=probe_dir, feedback=fb,
                previous_html=prev.code if prev else None, examples=block, prelude=prelude(sid)))
        except CodeRejected as e:
            rejected[sid] = e.problems
            P._log(config, f"      {sid} STILL REJECTED ({len(e.problems)} problems); keeping last attempt")
            return e.coded

    def run(sid) -> CodedScene:
        try:
            result = code(sid)
        except BaseException as e:
            done[sid].set_exception(e)
            raise
        done[sid].set_result(result)
        P._log(config, f"      {sid} done ({len(result.code.splitlines())} lines)")
        return result

    P.warm_cache(config)
    with ThreadPoolExecutor(max_workers=3) as pool:
        coded = list(pool.map(run, order))
    for scene in coded:
        html = out / f"agent3-{scene.scene_id}.html"
        html.write_text(still_last_beat(scene.code), encoding="utf-8")
        html.with_suffix(".py").write_text(wrapper_source(html), encoding="utf-8")
        report = out / f"agent3-{scene.scene_id}.problems.txt"
        if scene.scene_id in rejected:
            report.write_text("\n".join(rejected[scene.scene_id]) + "\n", encoding="utf-8")
        elif report.exists():
            report.unlink()
    if config.repair_log:
        (out / "repair-log.txt").write_text("\n\n".join(
            f"## {label} attempt {n}\n{text}" for label, n, text in config.repair_log) + "\n", encoding="utf-8")
    return rejected


def main(argv: list[str]) -> int:
    flags = {a for a in argv if a.startswith("--")}
    stage_plan, out_dir = [Path(a) for a in argv if not a.startswith("--")]
    sys.argv = sys.argv[:1]   # manimgl parses sys.argv when the runtime check imports it
    out_dir.mkdir(parents=True, exist_ok=True)
    if "--skip-direct" not in flags:
        plan = load_plan(stage_plan)
        (out_dir / "agent2-output.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
        config = P.PipelineConfig(user_prompt=plan.title, out_dir=str(out_dir), verbose=True, repair_rounds=3)
        P._use_theme(config)
        print(f"Director ({os.environ['OPENCODE_MODEL_ID']}) on {[len(s.beats) for s in plan.scenes]} beats ...", flush=True)
        with narration_mode():
            rejected = direct(config, plan)
        total = config.cost_log.summary()["total"]
        print(f"Director done: {fmt_usd(total['usd'])} for {total['requests']} requests"
              + (f"; rejected {sorted(rejected)}" if rejected else ""), flush=True)
    if "--no-render" not in flags:
        finish(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
