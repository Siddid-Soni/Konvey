"""CLI for the Konvey Agno pipeline.

Agent 3 writes <beat> HTML; konvey.stage lays it out with Chromium and renders it with
Manim. Needs OPENCODE_API_KEY or MINIMAX_API_KEY in .env; --group render --group layout
enables the headless runtime check and --render:
    uv run --group render --group layout run_konvey.py --prompt "Where do facts live in an LLM?" \
        --render --out-dir out/facts
"""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

from konvey.pipeline import PipelineConfig, run_pipeline

load_dotenv()

MODES = ["few-shot", "zero-shot", "cot"]


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Konvey 3-agent explainer-video pipeline (Agno)")
    p.add_argument("--prompt", default="", help="USER_PROMPT, e.g. 'Where do facts live in an LLM?'")
    p.add_argument("--mode", default="few-shot", choices=MODES,
                   help="Prompt mode for all three agents (default: few-shot; CoT is auto-retried on validation failure)")
    p.add_argument("--duration", type=float, default=90.0, help="Target video duration in seconds")
    p.add_argument("--out-dir", default="out/konvey-run", help="Where agent{1,2}-output.json + agent3-S*.html go")
    p.add_argument("--provider", default=None, choices=["opencode", "opencode-go", "minimax", "inception"],
                   help="Override KONVEY_PROVIDER (default: opencode if OPENCODE_API_KEY is set, else minimax)")
    p.add_argument("--model-id", default=None,
                   help="Model id for the active provider (default: glm-5.3 on opencode, muse-spark-1.3-contributor on opencode-go, MiniMax-M3 on minimax, mercury-3 on inception)")
    p.add_argument("--quiet", action="store_true", help="Suppress progress output")
    p.add_argument("--no-grounding", action="store_true",
                   help="Skip worked_examples / typed objects / no-invented-numbers checks")
    p.add_argument("--no-probe", action="store_true",
                   help="Skip the headless runtime check of each scene (needs uv run --group render --group layout)")
    p.add_argument("--repair-rounds", type=int, default=2,
                   help="Extra attempts per agent with validator errors fed back (default: 2)")
    p.add_argument("--theme", default="editorial", help="Visual theme (editorial, classic)")
    p.add_argument("--highlight", default=None,
                   help="Highlight colour for the video: a theme colour (c1..c5, ink) or a hex; default the theme's accent (a re-render keeps the recorded one)")
    p.add_argument("--render", action="store_true",
                   help="After the run, render every scene with manimgl and join them into <out-dir>/video.mp4")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    from konvey.stage.theme import get_theme

    try:
        from konvey.stage.theme import use

        get_theme(args.theme)
        use(args.theme, args.highlight)   # checks the colour now, not after the model calls
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not args.prompt.strip():
        print("error: --prompt is required", file=sys.stderr)
        return 2
    import os

    if args.provider:
        os.environ["KONVEY_PROVIDER"] = args.provider
    if args.model_id:
        from konvey.agents import default_provider, model_id_env

        os.environ[model_id_env(default_provider())] = args.model_id
    config = PipelineConfig(
        user_prompt=args.prompt,
        mode_agent1=args.mode,  # type: ignore[arg-type]
        mode_agent2=args.mode,  # type: ignore[arg-type]
        mode_agent3=args.mode,  # type: ignore[arg-type]
        duration_sec=args.duration,
        out_dir=args.out_dir,
        verbose=not args.quiet,
        grounded=not args.no_grounding,
        probe=not args.no_probe,
        repair_rounds=args.repair_rounds,
        theme=args.theme,
    )
    result = run_pipeline(config)
    print(f"topic: {result.topic}")
    print(f"plan: {result.plan.title} ({len(result.plan.scenes)} scenes)")
    print(f"wrote: {result.out_dir}/agent1-output.json, agent2-output.json, "
          + ", ".join(f"agent3-{s.scene_id}.html" for s in result.scenes))
    if args.render:
        from konvey.render import render_run

        print(f"video: {render_run(result.out_dir, highlight=args.highlight)}")
    if result.rejected:
        for scene_id, problems in sorted(result.rejected.items()):
            print(f"REJECTED {scene_id}: see {result.out_dir}/agent3-{scene_id}.problems.txt", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
