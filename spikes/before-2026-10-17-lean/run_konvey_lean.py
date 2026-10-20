"""CLI for the fewer-agent stage pipelines (konvey.lean); run_konvey.py stays the 3-agent one.

    uv run --group render --group layout python run_konvey_lean.py --agents 2 --prompt "..." --render
    uv run --group render --group layout python run_konvey_lean.py --agents 1 --prompt "..." \
        --out-dir out/lean-1 --model-id deepseek-v4.1-flash

Outputs match run_konvey.py (agent1/2-output.json, agent3-S*.html/.py), plus
timings.json (phase seconds, model calls) for comparing 3 vs 2 vs 1 agents.
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv


load_dotenv()


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Konvey 2-agent / 1-agent stage pipeline")
    p.add_argument("--agents", type=int, default=2, choices=[1, 2],
                   help="2 = Researcher -> 3 parallel stage directors; 1 = one Solo call (default: 2)")
    p.add_argument("--prompt", required=True, help="USER_PROMPT")
    p.add_argument("--duration", type=float, default=90.0, help="Target video duration in seconds")
    p.add_argument("--out-dir", default="out/lean-run")
    p.add_argument("--provider", default=None, choices=["opencode", "opencode-go", "minimax"])
    p.add_argument("--model-id", default=None, help="Model id for the active provider")
    p.add_argument("--theme", default="editorial", help="Visual theme (editorial, classic)")
    p.add_argument("--repair-rounds", type=int, default=2)
    p.add_argument("--no-grounding", action="store_true")
    p.add_argument("--no-probe", action="store_true", help="Skip the headless runtime check of each scene")
    p.add_argument("--render", action="store_true", help="Render <out-dir>/video.mp4 afterwards")
    p.add_argument("--quiet", action="store_true")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    from konvey.stage.theme import get_theme

    try:
        get_theme(args.theme)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.provider:
        os.environ["KONVEY_PROVIDER"] = args.provider
    if args.model_id:
        from konvey.agents import default_provider, model_id_env

        os.environ[model_id_env(default_provider())] = args.model_id

    from konvey.lean import run_lean
    from konvey.pipeline import PipelineConfig

    config = PipelineConfig(
        user_prompt=args.prompt, duration_sec=args.duration,
        out_dir=args.out_dir, verbose=not args.quiet, grounded=not args.no_grounding,
        probe=not args.no_probe, repair_rounds=args.repair_rounds, theme=args.theme,
    )
    result = run_lean(config, agents=args.agents)
    print(f"topic: {result.topic}")
    print(f"plan: {result.plan.title} ({len(result.plan.scenes)} scenes)")
    print(f"wrote: {result.out_dir} (timings.json, agent3-S*.html)")
    if args.render:
        from konvey.render import render_run

        print(f"video: {render_run(result.out_dir)}")
    for sid in sorted(result.rejected):
        print(f"REJECTED {sid}: see {result.out_dir}/agent3-{sid}.problems.txt", file=sys.stderr)
    return 1 if result.rejected else 0


if __name__ == "__main__":
    raise SystemExit(main())
