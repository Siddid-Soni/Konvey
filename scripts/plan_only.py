"""Agents 1-2 only (narration mode), for comparing plans before any render.

PLAN_MODEL=claude-haiku-5-5 uv run --group render --group layout --group speech python scripts/plan_only.py OUT_DIR "PROMPT"
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.chdir(Path(__file__).resolve().parents[1])
load_dotenv()
# before any konvey import: konvey.agents reads the model id when it is imported
os.environ["OPENCODE_MODEL_ID"] = os.environ["KONVEY_MODEL_ID"] = os.environ.get("PLAN_MODEL", "claude-haiku-5-5")

from konvey import pipeline as P  # noqa: E402
from konvey.speech.checks import narration_problems  # noqa: E402
from konvey.speech.narrate import DURATION_TOLERANCE, narration_mode  # noqa: E402
from konvey.validators import computed_numbers, example_vo_lines_from_template  # noqa: E402

out, prompt = sys.argv[1], sys.argv[2]
config = P.PipelineConfig(user_prompt=prompt, duration_sec=120, out_dir=out, verbose=True, grounded=True,
                          probe=False, repair_rounds=2)
config.duration_tolerance = max(config.duration_tolerance, DURATION_TOLERANCE)
Path(out).mkdir(parents=True, exist_ok=True)
with narration_mode():
    knowledge = P._with_repair(config, "knowledge", "Agent 1", lambda agent, fb, prev: P.run_knowledge(
        config.user_prompt, agent, require_grounding=True, feedback=fb, previous=prev))
    (Path(out) / "agent1-output.json").write_text(knowledge.model_dump_json(indent=2))
    lines = example_vo_lines_from_template(P.build_agent_instructions(2, config.mode_agent2))
    plan = P._with_repair(config, "planning", "Agent 2", lambda agent, fb, prev: P.run_planning(
        knowledge=knowledge, planning_agent=agent, duration_sec=config.duration_sec,
        duration_tolerance=config.duration_tolerance, grounded=True, example_vo_lines=lines,
        feedback=fb, previous=prev, computed=computed_numbers(config.compute_log.calls),
        request=config.user_prompt))
    (Path(out) / "agent2-output.json").write_text(plan.model_dump_json(indent=2))
warnings = narration_problems(plan)[1]
(Path(out) / "narration-warnings.txt").write_text("\n".join(warnings) + "\n")
total = config.cost_log.summary()["total"]
print(f"DONE {out} usd={total['usd']} requests={total['requests']}")
