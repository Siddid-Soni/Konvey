"""Re-run the stage check (layout, runtime, frame audit) over scenes that models already
generated, without calling a model. Use it after a renderer or checker change: past outputs
are the regression corpus where new generations break, and the unit tests never see them.

    uv run --group render --group layout python scripts/recheck.py out/heldout-3d-run3 [more runs…]
        [--agents a3]  [--summary]

Prints each scene's problems (or nothing) and a count per problem type.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from konvey.stage.check import check_runtime  # noqa: E402

PREV = {"S2": "S1", "S3": "S2"}


def kind(problem: str) -> str:
    """A short problem type, for the tally ('drawn over', 'label lands on', …)."""
    for key in ("is drawn over", "lands on", "labels of", "pieces of text", "has no focus",
                "sticks out", "too small to read", "needs <", "runtime error", "BeatError"):
        if key in problem:
            return key
    return re.sub(r"\d+", "#", problem)[:60]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("runs", nargs="+", help="output roots (…/<topic>/<aN>/agent3-S*.html)")
    p.add_argument("--agents", default="a*", help="which pipeline dirs, e.g. a3 (default all)")
    p.add_argument("--summary", action="store_true", help="only the tally")
    args = p.parse_args()
    tally, scenes, bad = Counter(), 0, 0
    work = REPO / "out" / ".recheck"
    for run in args.runs:
        for html in sorted(Path(run).glob(f"*/{args.agents}/agent3-S[123].html")):
            sid = html.stem.split("-")[-1]
            prev = html.with_name(f"agent3-{PREV[sid]}.html") if sid in PREV else None
            prelude = prev.read_text() if prev and prev.exists() else None
            found = [x for x in check_runtime(html.read_text(), work / html.parent.parent.name, sid,
                                              prelude_html=prelude) if not x.startswith("note:")]
            lines = [ln.strip("- ") for f in found for ln in f.splitlines()
                     if ln.strip() and not ln.startswith(("frame errors", "layout errors"))]
            scenes += 1
            bad += bool(lines)
            tally.update(kind(ln) for ln in lines)
            if not args.summary:
                print(f"## {html.relative_to(REPO) if html.is_relative_to(REPO) else html}  ({len(lines)})",
                      flush=True)
                for ln in lines:
                    print("   " + ln[:400], flush=True)
    print(f"\n{bad}/{scenes} scenes with problems")
    for k, n in tally.most_common():
        print(f"  {n:4}  {k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
