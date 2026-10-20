"""Explorer + Writer v5: v4 (scripts/story_eval_v4.py) plus the fixes from the v4 runs.

Telling: at most 3 numbers in a move that is not a montage; the key_insight move's first line
uses its discovery's case; lesson moves say no numbers; Act 1 at most 55% (aim 40%, planned per
act in `length`); 2-3 chapters with room; hold lines. Explorer: a chapter has its own picture state
(not the first example's); data typed into a check is quoted, not computed; the argument is marked
`why_it_holds`. Accuracy: an Auditor (prompts/shared/auditor-v5.md) reads the script against the
findings and its problems join the writer's repair. Reliability: up to 2 repair rounds (the best
draft is kept), up to 3 tries for unreadable JSON. Prompts are scrubbed of the eval topics.

PLAN_MODEL=deepseek-v4.1-flash uv run python scripts/story_eval_v5.py OUT_DIR [TOPIC ...]
AUDIT_MODEL (default: the explorer's model); TOPICS_FILE as in v4.
"""
import ast
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import story_eval_v4 as v4  # noqa: E402  (patches story_eval_v3; chdirs to the repo)

from agno.agent import Agent  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from konvey.story import Exploration, Script  # noqa: E402

v3 = v4.v3
OPENING_SWAPS = {  # eval-topic examples in the shared opening guide, swapped for neutral ones
    '("Euler\n  found the answer to be pi squared over 6. What is pi doing here?")':
        '("the sum\n  comes out to exactly 2, every time. Why 2?")',
    '"used in image processing, in probability, in solving differential equations"':
        '"used in GPS, in weather forecasts, in pricing insurance"',
}
_opening = Path("prompts/shared/opening.md").read_text()
for a, b in OPENING_SWAPS.items():
    assert a in _opening, a
    _opening = _opening.replace(a, b)
v3.EXPLORER = v3.fill(Path("prompts/shared/explorer-v5.md").read_text())
v3.WRITER = v3.fill(Path("prompts/shared/writer-v5.md").read_text()) + _opening[_opening.index("## How 3Blue1Brown opens"):]
AUDITOR = Path("prompts/shared/auditor-v5.md").read_text()
AUDIT_MODEL = os.environ.get("AUDIT_MODEL", v3.EXPLORER_MODEL)

MOVE_NUMBERS = 3
ACT1_MAX = 0.55
TABLE_VALUES = 8  # a literal with this many numbers in a check is typed-in data


# --- Explorer -------------------------------------------------------------------------------

def typed_table(f):
    try:
        tree = ast.parse(f.check)
    except SyntaxError:
        return 0
    sizes = [sum(isinstance(e, ast.Constant) and isinstance(e.value, (int, float)) and not isinstance(e.value, bool)
                 for e in ast.walk(n))
             for stmt in tree.body if not isinstance(stmt, ast.Assert)  # expected values in an assert are fine
             for n in ast.walk(stmt) if isinstance(n, (ast.List, ast.Tuple, ast.Dict, ast.Set))]
    return max(sizes, default=0)


def explorer_problems(exp: Exploration):
    out = v4.explorer_problems(exp)
    for f in v4.computed(exp):
        n = typed_table(f)
        if n >= TABLE_VALUES and not f.assumption:
            out.append(f"finding {f.id}: its check types in a table of {n} values. If they are real-world data, "
                       "set source to 'known: <where they come from>'; if made up, say so in `assumption`; "
                       "if your program produced them, recompute them in the check instead")
    states = {s.id: s for s in exp.picture.states}
    for c in exp.deepening:
        s = states.get(c.picture)
        if s is not None and s.chapter != c.id:
            out.append(f"chapter {c.id}: picture {c.picture} is not its own (chapter {s.chapter!r}); "
                       "give the chapter a state of its own setting, with chapter set to its id")
    return out


# --- Writer ---------------------------------------------------------------------------------

def spoken_numbers(text):
    return {n for n in v3.numbers_in(text) if n not in (0, 1, 2)}


def audit(script: Script, exp: Exploration):
    agent = v3.track(Agent(model=v3.model(AUDIT_MODEL), instructions=AUDITOR, markdown=False), v3.log, "auditor")
    findings = [{"id": f.id, "step": f.step, "claim": f.claim, "holds_for": f.holds_for} for f in exp.findings]
    lines = [{"move": i, "line": j, "says": ln.line, "uses": ln.uses}
             for i, m in enumerate(script.moves) for j, ln in enumerate(m.lines)]
    msg = f"FINDINGS:\n{json.dumps(findings, ensure_ascii=False)}\n\nSCRIPT:\n{json.dumps(lines, ensure_ascii=False)}\n\nOutput the JSON."
    try:
        data, _ = v3.ask(agent, msg)
    except Exception as e:  # noqa: BLE001 - an unreadable audit is skipped, not fatal
        return [], f"audit unreadable: {e}"
    out = []
    for p in data.get("problems", []) if isinstance(data, dict) else []:
        where = f"move {p.get('move')}" + (f" line {p['line']}" if p.get("line", -1) not in (-1, None) else "")
        out.append(f"{where}: {p.get('kind', 'problem')}: says {p.get('says', '')!r}; the findings support: {p.get('should', '')}")
    return out, None


def writer_problems(script: Script, exp: Exploration):
    found = {f.id: f for f in exp.findings}
    out = []
    for p in v4.writer_problems(script, exp):  # raw decimals are fine where the finding's `say` keeps the digits
        m = re.match(r"move (\d+) line (\d+): say (\S+) as a person would", p)
        if m:
            i, j, x = int(m[1]), int(m[2]), m[3]
            ln = script.moves[i].lines[j] if i < len(script.moves) and j < len(script.moves[i].lines) else None
            if ln and any(x in s for u in ln.uses if u in found for s in found[u].say.values()):
                continue
        out.append(p)
    disc = {d.id: d for d in exp.discovery}
    series = {s.id: s for s in exp.series}
    for i, m in enumerate(script.moves):
        text = " ".join(ln.line for ln in m.lines)
        nums = spoken_numbers(text)
        if not m.series and len(nums) > MOVE_NUMBERS:
            out.append(f"move {i} says {len(nums)} numbers ({', '.join(f'{n:g}' for n in sorted(nums)[:8])}); "
                       f"keep at most {MOVE_NUMBERS}, the ones that are the point, and say the rest as what the picture shows")
        if set(m.steps) == {"lesson"} and nums:
            out.append(f"move {i}: the lesson says numbers ({', '.join(f'{n:g}' for n in sorted(nums)[:5])}); say what this was an example of, in words")
        if "key_insight" in m.steps and m.discovery in disc:
            d = disc[m.discovery]
            case = set(series[d.case].cases) | {d.case} if d.case in series else {d.case}
            if not set(m.lines[0].uses) & case:
                out.append(f"move {i}: the insight's first line must point at its discovery's case {d.case} "
                           f"(use {', '.join(sorted(case)[:4])}) and what is visible in it, before the idea is named")
    words = sum(len(ln.line.split()) for m in script.moves for ln in m.lines)
    act1 = sum(len(ln.line.split()) for m in script.moves if m.act == 1 for ln in m.lines)
    if words and act1 / words > ACT1_MAX:
        out.append(f"Act 1 is {act1 / words:.0%} of the script; at most {ACT1_MAX:.0%} (aim 40%): "
                   "tell the first example more briefly, or give the chapters more room")
    found_audit, err = audit(script, exp)
    return out + found_audit + ([err] if err else [])


def soft(script: Script, exp: Exploration):
    res = v4.soft(script, exp)
    text = " ".join(ln.line for m in script.moves for ln in m.lines)
    words = len(text.split()) or 1
    res["numbers_per_100w"] = round(100 * len([n for n in v3.numbers_in(text) if n not in (0, 1, 2)]) / words, 1)
    res["planned_act_words"] = [script.length.act1_words, script.length.act2_words]
    if len(res.get("chapters_played", [])) > 3:
        res["warnings"].append(f"{len(res['chapters_played'])} chapters played (aim 2–3, each with room)")
    if res["numbers_per_100w"] > 6:
        res["warnings"].append(f"{res['numbers_per_100w']} numbers per 100 words (3Blue1Brown: 1–4)")
    return res


# --- Reliability ----------------------------------------------------------------------------

REPAIR_ROUNDS = 2
_ask_v3 = v3.ask


def ask(agent, message):
    """v3's ask (one JSON retry), tried up to 3 times in all."""
    err = None
    for _ in range(3):
        try:
            return _ask_v3(agent, message)
        except Exception as e:  # noqa: BLE001
            err = e
    raise err


def validated(agent, message, schema, problems_of):
    """Ask, validate, then up to REPAIR_ROUNDS repairs; keeps the draft with the fewest problems."""
    data, _ = ask(agent, message)
    try:
        obj = schema.model_validate(data)
        probs = problems_of(obj)
    except ValidationError as e:
        obj, probs = None, [f"schema: {err['loc']}: {err['msg']}" for err in e.errors()][:20]
    first = probs
    for _ in range(REPAIR_ROUNDS):
        if not probs:
            break
        try:
            new_data, new_obj = v3.repair(agent, message, data, probs, schema)
            new_probs = problems_of(new_obj)
        except Exception as e:  # noqa: BLE001 - an unreadable or invalid repair keeps the best draft
            if obj is None:
                raise
            probs = probs + [f"repair failed ({type(e).__name__}); kept the best draft"]
            break
        if obj is None or len(new_probs) <= len(probs):
            data, obj, probs = new_data, new_obj, new_probs
        else:
            break
    return data, obj, first, probs


v3.explorer_problems, v3.writer_problems, v3.soft = explorer_problems, writer_problems, soft
v3.ask, v3.validated = ask, validated

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
