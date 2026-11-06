"""Explorer + Writer v2 (konvey/story.py): discovery links, picture thread, moves; standalone.

PLAN_MODEL=claude-haiku-5-5 uv run python scripts/story_eval_v2.py OUT_DIR [TOPIC ...]
EXPLORER_MODEL / WRITER_MODEL override PLAN_MODEL for one agent; DURATION_SEC (default 600) is the
longest the video may be. The Writer chooses the length the story needs (`length`); only going
over the maximum is sent back for repair, the rest is reported in the soft checks.

Per topic: the Explorer (calc, run_python) returns an Exploration; problems in it go back once
for repair. The Writer returns a Script of moves; problems go back once. OUT_DIR/<topic>.json
holds both, the problems found before and after repair, and the soft checks; OUT_DIR/cost.json
the cost. Not wired into the pipeline.
"""
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # opening_eval, story_eval
os.chdir(Path(__file__).resolve().parents[1])
load_dotenv()
PLAN = os.environ.get("PLAN_MODEL", "claude-haiku-5-5")
EXPLORER_MODEL = os.environ.get("EXPLORER_MODEL", PLAN)
WRITER_MODEL = os.environ.get("WRITER_MODEL", PLAN)
os.environ["OPENCODE_MODEL_ID"] = os.environ["KONVEY_MODEL_ID"] = PLAN

from agno.agent import Agent  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from konvey.agents import resolve_model  # noqa: E402
from konvey.compute import ComputeLog, make_tools  # noqa: E402
from konvey.cost import CostLog, track  # noqa: E402
from konvey.story import STEPS, Exploration, Script  # noqa: E402
from konvey.validators import extract_json  # noqa: E402
from opening_eval import TOPICS  # noqa: E402
from story_eval import KIND_RULE, RANK, flat, same  # noqa: E402

DURATION = float(os.environ.get("DURATION_SEC", 600))
WORDS_PER_SEC = 2.2  # DramaBox on short lines, with room for held lines (3b1b himself: ~3)
TARGET = {"minutes": f"{DURATION / 60:g}", "words": int(round(DURATION * WORDS_PER_SEC, -1)),
          "opening_words": int(max(40, round(DURATION * WORDS_PER_SEC * 0.1, -1)))}  # maxima
LINE_LIMIT = 20
EXPLORER_CALLS = max(24, int(DURATION / 15))
UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                    "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
BIG = {"thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12}



def fill(text):
    for k, v in TARGET.items():  # the prompts hold JSON braces, so no str.format
        text = text.replace("{" + k + "}", str(v))
    return text


EXPLORER = fill(Path("prompts/shared/explorer-v2.md").read_text())
opening = Path("prompts/shared/opening.md").read_text()
WRITER = fill(Path("prompts/shared/writer-v2.md").read_text()) + opening[opening.index("## How 3Blue1Brown opens"):]

log = CostLog()
_env = threading.Lock()


REQUEST_TIMEOUT = 600  # s per request; a hung request fails the topic instead of the whole run
T0 = time.time()


def progress(key, what):
    print(f"[{(time.time() - T0) / 60:5.1f} min] {key}: {what}", flush=True)


def model(model_id):
    with _env:  # resolve_model reads the id from the environment
        os.environ["OPENCODE_MODEL_ID"] = model_id
        m = resolve_model()
    if hasattr(m, "timeout"):
        m.timeout = REQUEST_TIMEOUT
    return m


def ask(agent, message):
    raw = agent.run(message).content
    try:
        return extract_json(raw), raw
    except Exception as e:  # noqa: BLE001
        raw = agent.run(f"{message}\n\nYour last reply was not valid JSON ({e}). Output ONLY the JSON.").content
        return extract_json(raw), raw


def numbers_in(text):
    """Digits and spoken numbers ("thirty-one", "three hundred fourteen", "a million")."""
    vals = [float(m.replace(",", "")) for m in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]
    total, cur = 0.0, None
    for t in re.findall(r"[a-z]+|[^a-z\s]", text.lower().replace("-", " ")) + ["."]:  # punctuation ends a number
        if t in UNITS or t in TENS:
            cur = (cur or 0) + UNITS.get(t, TENS.get(t, 0))
        elif t == "hundred":
            cur = (cur or 1) * 100
        elif t in BIG:
            total, cur = total + (cur or 1) * BIG[t], 0
        elif t == "and" and (cur or total):
            continue
        else:
            if cur is not None or total:
                vals.append(total + (cur or 0))
            total, cur = 0.0, None
    return vals


def explorer_problems(exp: Exploration):
    ids = [f.id for f in exp.findings]
    found, series = set(ids), {s.id for s in exp.series}
    states = {s.id for s in exp.picture.states}
    out = [f"finding id {i} is used twice" for i in sorted({i for i in ids if ids.count(i) > 1})]
    out += [f"finding {f.id}: step {f.step!r} is not an arc step" for f in exp.findings
            if f.step not in STEPS + ("worked_run",)]
    for s in exp.series:
        out += [f"series {s.id}: case {c} is not a finding" for c in s.cases if c not in found]
    for d in exp.discovery:
        if d.case not in found | series:
            out.append(f"discovery {d.id}: case {d.case} is not a finding or series")
        out += [f"discovery {d.id}: pays_off {p} is not a finding" for p in d.pays_off if p not in found]
    out += [f"term {t.term!r}: picture {t.picture} is not a picture state" for t in exp.introduces
            if t.picture not in states]
    return out


def mentions(term, text):
    return re.search(rf"\b{re.escape(term.lower())}\b", text.lower()) is not None


def writer_problems(script: Script, exp: Exploration):
    """Hard problems (go back to the Writer once)."""
    found = {f.id: f for f in exp.findings}
    states, series, disc = {s.id for s in exp.picture.states}, {s.id for s in exp.series}, {d.id for d in exp.discovery}
    moves, out = script.moves, []
    covered = [s for m in moves for s in m.steps]
    out += [f"step {s!r} is not covered by any move" for s in STEPS if s not in covered]
    out += [f"step {s!r} is not an arc step" for s in sorted(set(covered) - set(STEPS))]
    top = -1
    for i, m in enumerate(moves):
        for s in m.steps:
            r = RANK.get(s, top)
            if r < top:
                out.append(f"move {i}: step {s!r} comes after a later step")
            top = max(top, r)
        if m.picture not in states:
            out.append(f"move {i}: picture {m.picture!r} is not a picture state ({', '.join(sorted(states))})")
        if m.series and m.series not in series:
            out.append(f"move {i}: series {m.series!r} does not exist")
        if m.discovery and m.discovery not in disc:
            out.append(f"move {i}: discovery {m.discovery!r} does not exist")
        if not i <= m.answered_in < len(moves):
            out.append(f"move {i}: answered_in {m.answered_in} must be this move or a later one")
        for j, ln in enumerate(m.lines):
            if len(ln.line.split()) > LINE_LIMIT:
                out.append(f"move {i} line {j}: {len(ln.line.split())} words, at most {LINE_LIMIT}")
            out += [f"move {i} line {j}: uses {u}, which is not a finding" for u in ln.uses if u not in found]
            raw = [x for x in re.findall(r"\d[\d,]*\.\d+", ln.line) if len(x.replace(".", "").replace(",", "").lstrip("0")) > 3]
            out += [f"move {i} line {j}: say {x} as a person would (its finding's `say` form, rounded)" for x in raw]
            for u in ln.uses:
                a = found.get(u) and found[u].assumption
                keys = [w for w in re.findall(r"[a-z]{5,}", (a or "").lower())]
                text = " ".join(x.line for x in m.lines).lower()
                if a and keys and not any(k in text for k in keys):
                    out.append(f"move {i} line {j}: {u} rests on '{a}'; say that in this move, or drop it")
    insight = [m for m in moves if "key_insight" in m.steps]
    if insight and not any(m.discovery for m in insight):
        out.append("the key_insight move names no discovery; name the one it makes visible and point at its case")
    for t in exp.introduces:
        first = next((i for i, m in enumerate(moves) if any(mentions(t.term, ln.line) for ln in m.lines)), None)
        if first is not None and not any(t.term.lower() == x.lower() for x in moves[first].introduces):
            out.append(f"move {first}: uses the term {t.term!r} first; list it in that move's introduces and say it in plain words")
    words = sum(len(ln.line.split()) for m in moves for ln in m.lines)
    if words > TARGET["words"]:
        out.append(f"{words} words; the video may be at most {TARGET['minutes']} minutes, {TARGET['words']} words: "
                   "cut what the story does not need")
    if script.length.minutes * 60 > DURATION:
        out.append(f"length {script.length.minutes} minutes; at most {TARGET['minutes']}")
    if KIND_RULE.get(script.topic_type) != script.opening_kind:
        out.append(f"opening_kind {script.opening_kind!r} does not follow from topic_type {script.topic_type!r}")
    return out


def soft(script: Script, exp: Exploration):
    found = {f.id: f for f in exp.findings}
    every = [x for f in exp.findings for x in flat([f.claim, f.numbers, f.say])]
    untraced, wrong = [], []
    for i, m in enumerate(script.moves):
        for j, ln in enumerate(m.lines):
            cited = [x for u in ln.uses if u in found for x in flat([found[u].claim, found[u].numbers, found[u].say])]
            for n in numbers_in(ln.line):
                if n in (0, 1, 2) and not re.search(r"\d", ln.line):
                    continue
                if not any(same(n, c) for c in cited):
                    (wrong if any(same(n, c) for c in every) else untraced).append(f"{i}.{j}:{n:g}")
    words = sum(len(ln.line.split()) for m in script.moves for ln in m.lines)
    lead = 0
    for m in script.moves:
        if not set(m.steps) <= {"hook", "why_care"}:
            break
        lead += sum(len(ln.line.split()) for ln in m.lines)
    planned = script.length.minutes * 60 * WORDS_PER_SEC
    warnings = []
    if abs(words - planned) > 0.25 * planned:
        warnings.append(f"{words} words for a planned {script.length.minutes:g} min (~{planned:.0f} words)")
    if lead > min(TARGET["opening_words"], 0.15 * words):
        warnings.append(f"opening {lead} words (aim: about a tenth, at most {TARGET['opening_words']})")
    return {"planned_minutes": script.length.minutes, "length_why": script.length.why,
            "moves": len(script.moves), "words": words,
            "minutes_at_2.2wps": round(words / WORDS_PER_SEC / 60, 1), "opening_words": lead,
            "warnings": warnings, "untraced": untraced, "wrong_finding": wrong,
            "montages": sum(1 for m in script.moves if m.series), "insight_discovery":
            [m.discovery for m in script.moves if "key_insight" in m.steps]}


def repair(agent, message, data, problems, schema):
    msg = (f"{message}\n\nYOUR OUTPUT:\n{json.dumps(data, ensure_ascii=False)}\n\nPROBLEMS:\n"
           + "\n".join(f"- {p}" for p in problems) + "\n\nFix every problem; change nothing else. Output the full JSON.")
    data, _ = ask(agent, msg)
    return data, schema.model_validate(data)


def validated(agent, message, schema, problems_of):
    """Ask, validate, and repair once (schema errors and check problems alike)."""
    data, _ = ask(agent, message)
    try:
        obj = schema.model_validate(data)
        first = problems_of(obj)
    except ValidationError as e:
        obj, first = None, [f"schema: {err['loc']}: {err['msg']}" for err in e.errors()][:20]
    if first:
        try:
            data, obj = repair(agent, message, data, first, schema)
        except ValidationError as e:
            return data, None, first, [f"schema: {err['loc']}: {err['msg']}" for err in e.errors()][:20]
    return data, obj, first, problems_of(obj) if first else []


def one(key):
    compute = ComputeLog()
    try:
        exp_agent = track(Agent(model=model(EXPLORER_MODEL), instructions=EXPLORER, tools=make_tools(compute),
                                tool_call_limit=EXPLORER_CALLS, markdown=False), log, "explorer")
        progress(key, "explorer started")
        exp_data, exp, e_first, e_left = validated(
            exp_agent, f"TOPIC REQUEST: {TOPICS[key]}\nWork it, then output the JSON.", Exploration, explorer_problems)
        progress(key, f"explorer done ({len(compute.calls)} tool calls, {len(e_first)} problems before repair)")
        if exp is None:
            return key, {"explorer": exp_data, "explorer_problems": e_left, "error": "explorer output invalid"}
        wr_agent = track(Agent(model=model(WRITER_MODEL), instructions=WRITER, markdown=False), log, "writer")
        msg = (f"TOPIC REQUEST: {TOPICS[key]}\n\nEXPLORATION:\n{exp.model_dump_json()}\n\nOutput the JSON.")
        wr_data, script, w_first, w_left = validated(wr_agent, msg, Script, lambda s: writer_problems(s, exp))
        progress(key, f"writer done ({len(w_first)} problems before repair, {len(w_left)} left)")
        res = {"explorer": exp.model_dump(), "explorer_problems": {"first": e_first, "left": e_left},
               "writer": wr_data, "writer_problems": {"first": w_first, "left": w_left},
               "tool_calls": len(compute.calls)}
        if script is not None:
            res["checks"] = soft(script, exp)
        return key, res
    except Exception as e:  # noqa: BLE001
        return key, {"error": repr(e)}


if __name__ == "__main__":
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    keys = sys.argv[2:] or list(TOPICS)
    with ThreadPoolExecutor(10) as ex:
        for fut in as_completed([ex.submit(one, k) for k in keys]):  # write each topic as it finishes
            key, res = fut.result()
            (out / f"{key}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
            left = (res.get("writer_problems") or {}).get("left")
            print(key, "error: " + res["error"] if "error" in res else
                  {"left": left, **res.get("checks", {})}, flush=True)
    summary = log.summary()
    (out / "cost.json").write_text(json.dumps(summary, indent=1))
    print("cost", summary["total"]["usd"], {a: v["usd"] for a, v in summary["by_agent"].items()})
