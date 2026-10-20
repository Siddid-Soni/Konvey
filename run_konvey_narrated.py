"""CLI for narration mode (konvey.speech): the 3-agent stage pipeline, voiced by DramaBox.

    uv run --group render --group layout --group speech python run_konvey_narrated.py --prompt "..." \
        --out-dir out/speech-monty [--model-id claude-haiku-5-5] [--max-sec 300]
    uv run --group render --group layout --group speech python run_konvey_narrated.py --out-dir out/speech-monty \
        --skip-generate        # re-voice + re-render a run (reads agent3-S*.tagged.html)

DramaBox runs in process (--group speech; voice: Paige, assets/voices/paige/). TTS runs
before manimgl and frees the GPU, since both need it. Writes speech.json, audio/, video.mp4 next to the usual outputs.
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Konvey narrated explainer video (stage + DramaBox)")
    p.add_argument("--prompt", default="", help="USER_PROMPT (not needed with --skip-generate)")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--max-sec", type=float, default=300,
                   help="longest the video may be (a limit, not a target)")
    p.add_argument("--provider", default=None, choices=["opencode", "opencode-go", "minimax"])
    p.add_argument("--model-id", default="claude-haiku-5-5", help="Model id for the active provider")
    p.add_argument("--theme", default="editorial", help="Visual theme (editorial, classic)")
    p.add_argument("--highlight", default=None,
                   help="Highlight colour for the video: a theme colour (c1..c5, ink) or a hex; default the theme's accent (a re-render keeps the recorded one)")
    p.add_argument("--repair-rounds", type=int, default=2)
    p.add_argument("--no-grounding", action="store_true")
    p.add_argument("--no-probe", action="store_true", help="Skip the headless runtime check of each scene")
    p.add_argument("--no-render", action="store_true", help="Voice and wire only; no video.mp4")
    p.add_argument("--no-voice", action="store_true",
                   help="Stop after the agents; voice and render later with --skip-generate")
    p.add_argument("--skip-generate", action="store_true", help="reuse the agent outputs in --out-dir")
    p.add_argument("--quiet", action="store_true")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    from konvey.speech.narrate import finish, run_narrated

    from konvey.stage.theme import use

    try:
        use(args.theme, args.highlight)   # checks the colour now, not after the model calls
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.skip_generate:
        finish(args.out_dir, render=not args.no_render, highlight=args.highlight)
        return 0
    if not args.prompt.strip():
        print("error: --prompt is required (or --skip-generate)", file=sys.stderr)
        return 2
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
    from konvey.pipeline import PipelineConfig

    config = PipelineConfig(
        user_prompt=args.prompt, duration_sec=args.max_sec,
        out_dir=args.out_dir, verbose=not args.quiet, grounded=not args.no_grounding,
        probe=not args.no_probe, repair_rounds=args.repair_rounds, theme=args.theme,
    )
    result = run_narrated(config, render=not args.no_render, highlight=args.highlight,
                          voice=not args.no_voice)
    print(f"topic: {result.topic}")
    print(f"plan: {result.plan.title} ({len(result.plan.scenes)} scenes)")
    for sid in sorted(result.rejected):
        print(f"REJECTED {sid}: see {result.out_dir}/agent3-{sid}.problems.txt "
              "(voiced and rendered as written)", file=sys.stderr)
    return 1 if result.rejected else 0


if __name__ == "__main__":
    raise SystemExit(main())
