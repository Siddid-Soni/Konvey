"""Explorer + Writer v4: v3 (scripts/story_eval_v3.py) plus executable checks on findings.

Every computed finding carries a `check`, a restricted-Python program whose asserts state the
claim as its sentence says it. All checks run between Explorer and Writer; failures (with their
output) go back to the Explorer in the existing repair round, so no extra model calls. Also: the
units rule in both prompts, the stand-in caveat as a hard check (at most 2 lines), Act 1 nudged
to about 40%. Standalone, same usage as v3:

PLAN_MODEL=claude-haiku-5-5 EXPLORER_MODEL=deepseek-v4.1-flash uv run python scripts/story_eval_v4.py OUT_DIR [TOPIC ...]
TOPICS_FILE=topics.json adds topics ({"key": "request"}) to the ten 3b1b ones.
"""
import ast
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import story_eval_v3 as v3  # noqa: E402  (chdirs to the repo, loads .env, resolves models)

from konvey.compute import run_python  # noqa: E402
from konvey.story import Exploration, Script  # noqa: E402

v3.EXPLORER = v3.fill(Path("prompts/shared/explorer-v4.md").read_text())
_opening = Path("prompts/shared/opening.md").read_text()
v3.WRITER = v3.fill(Path("prompts/shared/writer-v4.md").read_text()) + _opening[_opening.index("## How 3Blue1Brown opens"):]

CAVEAT_LINES = 2
# a spoken number is never more precise than 3 digits, so tolerances below 0.1% only catch pasted digits
APPROX = ("def approx(a, b, rel=0.01, abs_tol=0):\n"
          "    return abs(a - b) <= max(max(rel, 1e-3) * max(abs(a), abs(b)), abs_tol)\n")
WORK = (ast.Call, ast.BinOp, ast.comprehension, ast.For, ast.While, ast.FunctionDef)


def check_problem(f):
    """None if the finding's check passes; else what to send back."""
    if not f.check.strip():
        return f"finding {f.id}: computed, but no `check`; add asserts that restate the claim"
    try:
        tree = ast.parse(f.check)
    except SyntaxError as e:
        return f"finding {f.id}: check has a syntax error (line {e.lineno}: {e.msg})"
    if not any(isinstance(n, ast.Assert) for n in ast.walk(tree)):
        return f"finding {f.id}: check has no assert"
    if not any(isinstance(n, WORK) for n in ast.walk(tree)):
        return f"finding {f.id}: check only compares pasted values; recompute them"
    out = run_python(APPROX + with_values(tree))
    if "ERROR" in out or out.startswith("REJECTED"):
        return f"finding {f.id}: check FAILED, so the claim does not say what was computed: {out.strip()[-300:]}"
    return None


def computed(exp: Exploration):
    """Findings with a computed number: these need a check."""
    return [f for f in exp.findings if f.source == "computed" and v3.flat([f.claim, f.numbers])]


def with_values(tree):
    """The check's source, each bare assert given its test and operand values as the message."""
    for a in ast.walk(tree):
        if isinstance(a, ast.Assert) and a.msg is None:
            t = a.test
            parts = ([t.left, *t.comparators] if isinstance(t, ast.Compare) else
                     list(t.args) if isinstance(t, ast.Call) else [])
            a.msg = ast.Tuple([ast.Constant(ast.unparse(t)), *parts], ast.Load())
    return ast.unparse(ast.fix_missing_locations(tree))


def run_checks(exp: Exploration):
    with ThreadPoolExecutor(8) as ex:
        return [p for p in ex.map(check_problem, computed(exp)) if p]


_explorer_v3, _writer_v3, _soft_v3 = v3.explorer_problems, v3.writer_problems, v3.soft


def explorer_problems(exp: Exploration):
    return _explorer_v3(exp) + run_checks(exp)


def caveat_lines(script: Script, exp: Exploration):
    """{assumption: [move.line, …]} for lines that mention a stand-in."""
    out = {}
    for a in {f.assumption for f in exp.findings if f.assumption}:
        keys = set(re.findall(r"[a-z]{5,}", a.lower()))
        need = max(1, min(2, len(keys)), len(keys) // 2)  # one shared word ("count") is not a mention
        nums = re.findall(r"\d+", a)  # "a 4-word toy set": the 4 is what names it, not the word "answer"
        out[a] = [f"{i}.{j}" for i, m in enumerate(script.moves) for j, ln in enumerate(m.lines)
                  if keys and sum(k in ln.line.lower() for k in keys) >= need
                  and all(re.search(rf"\b{n}\b", ln.line) for n in nums)]
    return out


def writer_problems(script: Script, exp: Exploration):
    out = _writer_v3(script, exp)
    for a, where in caveat_lines(script, exp).items():
        if len(where) > CAVEAT_LINES:
            out.append(f"the stand-in '{a[:60]}' is mentioned in {len(where)} lines ({', '.join(where)}); "
                       f"say it once where first used, at most one short reminder")
    return out


def soft(script: Script, exp: Exploration):
    res = _soft_v3(script, exp)
    res["warnings"] = [w for w in res["warnings"] if not w.startswith("the caveat")]  # now a hard check
    if not 0.3 <= res["act1_share"] <= 0.5:
        res["warnings"] = [w for w in res["warnings"] if not w.startswith("Act 1 is")] + \
            [f"Act 1 is {res['act1_share']:.0%} of the script (aim about 40%)"]
    res["checks_failing"] = run_checks(exp)
    res["findings_checked"] = sum(1 for f in computed(exp) if f.check.strip())
    res["findings_computed"] = len(computed(exp))
    return res


v3.explorer_problems, v3.writer_problems, v3.soft = explorer_problems, writer_problems, soft
if os.environ.get("TOPICS_FILE"):  # extra topics, {"key": "request"}: out-of-sample runs
    v3.TOPICS.update(json.loads(Path(os.environ["TOPICS_FILE"]).read_text()))

if __name__ == "__main__":
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    keys = sys.argv[2:] or list(v3.TOPICS)
    from concurrent.futures import as_completed
    with ThreadPoolExecutor(10) as ex:
        for fut in as_completed([ex.submit(v3.one, k) for k in keys]):
            key, res = fut.result()
            (out / f"{key}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
            left = (res.get("writer_problems") or {}).get("left")
            print(key, "error: " + res["error"] if "error" in res else
                  {"left": left, **{k: v for k, v in res.get("checks", {}).items() if k != "length_why"}}, flush=True)
    summary = v3.log.summary()
    (out / "cost.json").write_text(json.dumps(summary, indent=1))
    print("cost", summary["total"]["usd"], {a: v["usd"] for a, v in summary["by_agent"].items()})
