"""CLI for the Konvey Agno pipeline.

Live run (needs MiniMax credentials in .env: MINIMAX_API_KEY):
    uv run run_konvey.py --prompt "Where do facts live in an LLM?" --set set-01-mlp-facts

Offline validation of a worked example (no API key):
    uv run run_konvey.py --dry-run-example examples/example-01-mlp-facts --out-dir out/dry-run-01

Agno Workflow view (same DAG, AgentOS/streaming friendly):
    uv run run_konvey.py --prompt "..." --workflow
"""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

from konvey.pipeline import PipelineConfig, build_workflow, run_dry_run, run_pipeline
from konvey.prompts import PROMPT_SET_GUIDE

load_dotenv()

SETS = ["generic", *PROMPT_SET_GUIDE]
MODES = ["few-shot", "zero-shot", "cot"]


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Konvey 3-agent explainer-video pipeline (Agno)")
    p.add_argument("--prompt", default="", help="USER_PROMPT, e.g. 'Where do facts live in an LLM?'")
    p.add_argument("--set", dest="prompt_set", default="set-01-mlp-facts",
                   choices=SETS, help="Per-video prompt set (default: set-01-mlp-facts)")
    p.add_argument("--mode", default="few-shot", choices=MODES,
                   help="Prompt mode for all three agents (default: few-shot; CoT is auto-retried on validation failure)")
    p.add_argument("--duration", type=float, default=90.0, help="Target video duration in seconds")
    p.add_argument("--out-dir", default="out/konvey-run", help="Where agent{1,2}-output.json + agent3-S*.py go")
    p.add_argument("--model-id", default=None, help="Override KONVEY_MODEL_ID (default: MiniMax-M3)")
    p.add_argument("--quiet", action="store_true", help="Suppress progress output")
    p.add_argument("--workflow", action="store_true", help="Run via Agno Workflow instead of direct orchestration")
    p.add_argument("--dry-run-example", default=None,
                   help="Offline: validate examples/<example>/ without any LLM call")
    p.add_argument("--list-sets", action="store_true", help="Show prompt sets and exit")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.list_sets:
        for name in SETS:
            print(f"{name}: {PROMPT_SET_GUIDE.get(name, 'generic style-first prompts')}")
        return 0
    if args.dry_run_example:
        result = run_dry_run(args.dry_run_example, args.out_dir)
        print(f"dry-run OK: topic={result.topic!r} scenes={[s.scene_id for s in result.scenes]} -> {result.out_dir}")
        return 0
    if not args.prompt.strip():
        print("error: --prompt is required (or use --dry-run-example)", file=sys.stderr)
        return 2
    import os

    if args.model_id:
        os.environ["KONVEY_MODEL_ID"] = args.model_id
    config = PipelineConfig(
        user_prompt=args.prompt,
        prompt_set=args.prompt_set,
        mode_agent1=args.mode,  # type: ignore[arg-type]
        mode_agent2=args.mode,  # type: ignore[arg-type]
        mode_agent3=args.mode,  # type: ignore[arg-type]
        duration_sec=args.duration,
        out_dir=args.out_dir,
        verbose=not args.quiet,
    )
    if args.workflow:
        print("Building Agno workflow: Knowledge -> Planning -> Parallel(S1,S2,S3) -> Assemble ...", flush=True)
        workflow = build_workflow(config)
        print("Running workflow ...", flush=True)
        response = workflow.run(config.user_prompt)
        print(response.content)
    else:
        result = run_pipeline(config)
        print(f"topic: {result.topic}")
        print(f"plan: {result.plan.title} ({len(result.plan.scenes)} scenes)")
        print(f"wrote: {result.out_dir}/agent1-output.json, agent2-output.json, "
              + ", ".join(f"agent3-{s.scene_id}.py" for s in result.scenes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
