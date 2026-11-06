"""Explorer + Writer (the four-agent redesign's first two agents), standalone, on 3b1b's own topics.

PLAN_MODEL=claude-haiku-5-5 uv run python scripts/story_eval.py OUT_DIR [TOPIC ...]

Per topic: the Explorer (calc, run_python) returns findings keyed to the arc steps; the Writer
writes the whole spoken script from them; if it returns `needs`, the Explorer computes just those
once and the Writer writes the final script. OUT_DIR/<topic>.json holds all of it plus the checks;
OUT_DIR/cost.json the cost. Not wired into the pipeline.
"""
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.chdir(Path(__file__).resolve().parents[1])
load_dotenv()
os.environ["OPENCODE_MODEL_ID"] = os.environ["KONVEY_MODEL_ID"] = os.environ.get("PLAN_MODEL", "claude-haiku-5-5")

from agno.agent import Agent  # noqa: E402

from konvey.agents import resolve_model  # noqa: E402
from konvey.compute import ComputeLog, make_tools  # noqa: E402
from konvey.cost import CostLog, track  # noqa: E402
from konvey.validators import extract_json  # noqa: E402
from opening_eval import TOPICS  # noqa: E402

STEPS = ("hook", "why_care", "problem", "naive_attempt", "promise", "exploration", "key_insight",
         "why_it_holds", "objections", "lesson", "generalisation", "surprise", "closes_opening")
RANK = {s: i for i, s in enumerate(STEPS)} | {"why_care": 0}   # hook and why_care may swap
KIND_RULE = {"puzzle": "concrete", "phenomenon": "concrete", "tool": "matters",
             "famous_problem": "matters", "formula": "confusion", "misconception": "confusion"}
WORDS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve "
                                    "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}
WORDS |= {"thirty": 30, "forty": 40, "fifty": 50, "hundred": 100, "thousand": 1000, "million": 1e6,
          "billion": 1e9}
EXPLORER_CALLS = 24

EXPLORER = Path("prompts/shared/explorer.md").read_text()
opening = Path("prompts/shared/opening.md").read_text()
WRITER = Path("prompts/shared/writer.md").read_text() + opening[opening.index("## How 3Blue1Brown opens"):]

log = CostLog()


def ask(agent, message):
    """One run, parsed as JSON; one retry when the reply is not JSON."""
    raw = agent.run(message).content
    try:
        return extract_json(raw)
    except Exception as e:  # noqa: BLE001
        raw = agent.run(f"{message}\n\nYour last reply was not valid JSON ({e}). Output ONLY the JSON.").content
        return extract_json(raw)


def explorer(compute):
    return track(Agent(model=resolve_model(), instructions=EXPLORER, tools=make_tools(compute),
                       tool_call_limit=EXPLORER_CALLS, markdown=False), log, "explorer")


def writer():
    return track(Agent(model=resolve_model(), instructions=WRITER, markdown=False), log, "writer")


def numbers_in(text):
    vals = [float(m.replace(",", "")) for m in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]
    vals += [WORDS[w] for w in re.findall(r"[a-z]+", text.lower()) if w in WORDS]
    return vals


def flat(v):
    if isinstance(v, bool):
        return []
    if isinstance(v, (int, float)):
        return [float(v)]
    if isinstance(v, str):
        return numbers_in(v)
    if isinstance(v, dict):
        return [x for u in v.values() for x in flat(u)]
    if isinstance(v, list):
        return [x for u in v for x in flat(u)]
    return []


def same(a, b):
    if a == b:
        return True
    if b == 0 or a == 0:
        return False
    digits = len(str(a).split(".")[1]) if "." in str(a) else 0
    return round(b, digits) == a or abs(a - b) / abs(b) < 1e-3 or abs(a - 100 * b) < 0.5  # 0.25 said as 25%


def checks(story, findings):
    by_id = {f.get("id"): f for f in findings}
    every = [x for f in findings for x in flat([f.get("claim", ""), f.get("numbers", {})])]
    script = story.get("script", [])
    out = {"lines": len(script), "words": sum(len(s.get("line", "").split()) for s in script),
           "long_lines": [i for i, s in enumerate(script) if len(s.get("line", "").split()) > 20],
           "missing_steps": [s for s in STEPS if s not in {x.get("step") for x in script}],
           "unknown_steps": sorted({x.get("step") for x in script} - set(STEPS)),
           "out_of_order": [], "untraced": [], "wrong_finding": [], "missing_finding": []}
    top = -1
    for i, s in enumerate(script):
        r = RANK.get(s.get("step"), top)
        if r < top:
            out["out_of_order"].append(i)
        top = max(top, r)
        cited = [x for u in s.get("uses", []) for x in flat([by_id.get(u, {}).get("claim", ""),
                                                             by_id.get(u, {}).get("numbers", {})])]
        out["missing_finding"] += [f"{i}:{u}" for u in s.get("uses", []) if u not in by_id]
        for n in numbers_in(s.get("line", "")):
            if n in (0, 1, 2) and not re.search(r"\d", s.get("line", "")):
                continue  # "one", "two" as plain words
            if not any(same(n, c) for c in cited):
                (out["wrong_finding"] if any(same(n, c) for c in every) else out["untraced"]).append(f"{i}:{n:g}")
    kind = KIND_RULE.get(story.get("topic_type"))
    out["kind_by_rule"] = kind == story.get("opening_kind")
    out["bad_whys"] = [w.get("question") for w in story.get("whys", [])
                       if not w.get("answered_at") or any(a >= len(script) or a < w.get("asked_at", 0)
                                                           for a in w.get("answered_at", []))]
    out["whys"] = len(story.get("whys", []))
    return out


def one(key):
    compute = ComputeLog()
    try:
        exp = ask(explorer(compute), f"TOPIC REQUEST: {TOPICS[key]}\nWork it, then output the JSON.")
        findings = exp.get("findings", [])
        msg = f"TOPIC REQUEST: {TOPICS[key]}\n\nFINDINGS:\n{json.dumps(exp, ensure_ascii=False)}\n\nOutput the JSON."
        draft = ask(writer(), msg)
        story, extra = draft, []
        if draft.get("needs"):
            last = findings[-1]["id"] if findings else "F0"
            more = ask(explorer(compute), "NEEDS:\n" + "\n".join(f"- {n}" for n in draft["needs"])
                       + f"\n\nThe question: {exp.get('question', TOPICS[key])}\nLast finding id given: {last}")
            extra = more.get("findings", [])
            findings = findings + extra
            exp["findings"] = findings
            story = ask(writer(), f"TOPIC REQUEST: {TOPICS[key]}\n\nFINDINGS:\n{json.dumps(exp, ensure_ascii=False)}"
                                  f"\n\nYOUR DRAFT (it asked for {draft['needs']}; those findings are now in FINDINGS):\n"
                                  f"{json.dumps(draft, ensure_ascii=False)}\n\nWrite the final script. `needs` must be empty.")
        return key, {"explorer": exp, "draft": draft if story is not draft else None, "needs_findings": extra,
                     "writer": story, "checks": checks(story, findings), "tool_calls": len(compute.calls)}
    except Exception as e:  # noqa: BLE001
        return key, {"error": repr(e)}


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    keys = sys.argv[2:] or list(TOPICS)
    with ThreadPoolExecutor(10) as ex:
        for key, res in ex.map(one, keys):
            (out / f"{key}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
            print(key, "error" if "error" in res else res["checks"], flush=True)
    summary = log.summary()
    (out / "cost.json").write_text(json.dumps(summary, indent=1))
    print("cost", summary["total"]["usd"], {a: v["usd"] for a, v in summary["by_agent"].items()})
