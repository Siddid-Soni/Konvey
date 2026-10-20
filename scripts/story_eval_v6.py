"""Explorer + Writer v6: v5 (scripts/story_eval_v5.py) without the Auditor, fixing the data instead.

Tracing v5's wrong sentences showed they mostly entered upstream of the Writer: Explorer claims
that were wrong in words while their checks only tested the numbers ("height is a logarithm of
the fanout"), two findings disagreeing, the argument stored as a numeric instance instead of a
reason, and the Writer reading each finding's check code and raw `numbers` (about 40% of its
input). So v6:
- the Writer sees only id, step, claim, `say`, `holds_for`, `assumption` of each finding (the
  checks still run on the full exploration);
- a claim that states a relation or bound needs a check over several cases (a loop);
- `why_it_holds` findings state the reason in words (Explorer prompt);
- numbers: at most 6 per 100 words over the script (hard); per move only a warning, so a worked
  trace keeps its labels;
- a chapter that replays Part 1's argument or is the first example with other numbers goes back
  to the Explorer: one model call judges every chapter (prompts/shared/chapter-judge-v6.md),
  because number overlap with Part 1 flags chapters that rightly reuse its numbers.

TOPICS_FILE=out/story-eval-v5/topics.json PLAN_MODEL=deepseek-v4.1-flash uv run python scripts/story_eval_v6.py OUT_DIR [TOPIC ...]
"""
import ast
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import story_eval_v5 as v5  # noqa: E402  (patches v4 → v3; chdirs to the repo)

from agno.agent import Agent  # noqa: E402

from konvey.story import Exploration, Script  # noqa: E402

v3, v4 = v5.v3, v5.v4
v3.EXPLORER = v3.fill(Path("prompts/shared/explorer-v6.md").read_text())
v3.WRITER = v3.fill(Path("prompts/shared/writer-v6.md").read_text()) + v5._opening[v5._opening.index("## How 3Blue1Brown opens"):]
v5.audit = lambda script, exp: ([], None)  # no Auditor
JUDGE = Path("prompts/shared/chapter-judge-v6.md").read_text()
PART1_ARGUMENT = ("key_insight", "why_it_holds")

DENSITY = 6  # numbers per 100 words, whole script (3Blue1Brown: about 1-4)
WRITER_FIELDS = ("id", "step", "claim", "say", "holds_for", "assumption")
RELATION = re.compile(r"proportional|logarithm|\blog\b|grows like|at most|at least|always|never|for every|"
                      r"for all|any number|the same for|doubles|halves|squares? of|square root", re.I)
MULTI = (ast.For, ast.While, ast.comprehension)


def writer_view(exp: Exploration):
    data = exp.model_dump()
    data["findings"] = [{k: f[k] for k in WRITER_FIELDS if f.get(k) not in (None, {}, "")} for f in data["findings"]]
    return json.dumps(data, ensure_ascii=False)


def tautologies(tree):
    """Asserts that compare a value with itself (`assert 10 == 10`) or assert a bare constant."""
    out = []
    for a in ast.walk(tree):
        if not isinstance(a, ast.Assert):
            continue
        c = a.test
        if isinstance(c, ast.Constant) or (isinstance(c, ast.Compare) and len({ast.dump(x) for x in [c.left, *c.comparators]}) == 1):
            out.append(ast.unparse(c))
    return out


_verdicts: dict = {}  # judge input → verdicts; repairs that leave the chapters alone cost nothing


def chapter_verdicts(exp: Exploration):
    claims = {f.id: f.claim for f in exp.findings}
    part1 = {"first_example": exp.chosen_example.model_dump(),
             "argument": [{"id": f.id, "claim": f.claim} for f in exp.findings if f.step in PART1_ARGUMENT]}
    chapters = [{"id": c.id, "setting": c.setting, "reveals": c.reveals,
                 "findings": [claims[i] for i in c.findings if i in claims]} for c in exp.deepening]
    msg = f"PART 1:\n{json.dumps(part1, ensure_ascii=False)}\n\nCHAPTERS:\n{json.dumps(chapters, ensure_ascii=False)}\n\nOutput the JSON."
    if msg not in _verdicts:
        agent = v3.track(Agent(model=v3.model(v5.AUDIT_MODEL), instructions=JUDGE, markdown=False), v3.log, "chapter_judge")
        try:
            data, _ = v3.ask(agent, msg)
            _verdicts[msg] = [c for c in data.get("chapters", []) if isinstance(c, dict)]
        except Exception:  # noqa: BLE001 - an unreadable verdict is skipped, not fatal
            _verdicts[msg] = []
    return _verdicts[msg]


def explorer_problems(exp: Exploration):
    out = v5.explorer_problems(exp)
    for v in chapter_verdicts(exp):
        if v.get("verdict") == "replays_argument":
            out.append(f"chapter {v.get('id')}: it tells Part 1's argument again ({v.get('why', '')}). Replace it with a "
                       "new setting that uses the idea; Part 1's proof stays in why_it_holds")
        elif v.get("verdict") == "same_example":
            out.append(f"chapter {v.get('id')}: it is the first example with other numbers ({v.get('why', '')}). "
                       "Replace it with a setting that changes what the idea is applied to, or one of its assumptions")
    for f in v4.computed(exp):
        try:
            taut = tautologies(ast.parse(f.check))
        except SyntaxError:
            continue
        if taut:
            out.append(f"finding {f.id}: `assert {taut[0]}` proves nothing; derive the claimed number from its definition")
    for f in v4.computed(exp):
        if not RELATION.search(f.claim) or not f.check.strip():
            continue
        try:
            tree = ast.parse(f.check)
        except SyntaxError:
            continue  # reported by the v4 check
        if not any(isinstance(n, MULTI) for n in ast.walk(tree)):
            word = RELATION.search(f.claim).group(0)
            out.append(f"finding {f.id}: the claim states a relation ({word!r}) but its check tests one case; "
                       "check it on at least three cases in a loop, so a wrong relation fails")
    return out


def numbers_said(text):
    """Every number said (digits or words), repeats included; 0, 1 and 2 are ordinary words."""
    return [n for n in v3.numbers_in(text) if n not in (0, 1, 2)]


PER_MOVE = re.compile(r"move \d+ says \d+ numbers")


def writer_problems(script: Script, exp: Exploration):
    out = [p for p in v5.writer_problems(script, exp) if not PER_MOVE.match(p)]  # per move: soft now
    text = " ".join(ln.line for m in script.moves for ln in m.lines)
    words = len(text.split()) or 1
    total = len(numbers_said(text))
    if 100 * total / words > DENSITY:
        dense = sorted(((len(numbers_said(" ".join(ln.line for ln in m.lines))), i)
                        for i, m in enumerate(script.moves)), reverse=True)[:4]
        out.append(f"{100 * total / words:.1f} numbers per 100 words; at most {DENSITY}. Say fewer numbers, "
                   f"starting with moves {', '.join(str(i) for _, i in dense)}: keep those that are the point")
    return out


def soft(script: Script, exp: Exploration):
    res = v5.soft(script, exp)
    res["warnings"] += [p for p in v5.writer_problems(script, exp) if PER_MOVE.match(p)]
    return res


v3.writer_view = writer_view
v3.explorer_problems, v3.writer_problems, v3.soft = explorer_problems, writer_problems, soft

if __name__ == "__main__":
    from concurrent.futures import ThreadPoolExecutor, as_completed
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    keys = sys.argv[2:] or list(v3.TOPICS)
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
