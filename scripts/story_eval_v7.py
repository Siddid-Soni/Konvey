"""Story agents v7: v6's Explorer + Writer, then the Voice and the Visual Planner.

- Explorer: a `simulate` tool runs the video's own simulations (konvey/story_sim.py), and a
  finding read off one stores its run (`sim`), rerun here before the Writer; worked runs come
  as `traces` (every step's state) so the picture can show each step exactly.
- Writer: sees which findings are simulations and the traces' steps; plays a simulation as a
  watching move.
- Visual Planner (prompts/shared/visual-planner-v7.md): the script in sections (Act 1, each
  chapter, the ending; Act 1 first, the rest in parallel given Act 1's last objects) → one
  beat per line with its voice prompt (`vo`, DramaBox: the line's words locked, no laughing;
  konvey/story_voice.py), its objects, simulations copied from the findings, trace steps and
  camera targets by name. Checked here, repaired up to twice; a `vo` still invalid after that
  gets a plain prompt.

OUT_DIR/<topic>.json holds everything; OUT_DIR/<topic>.stage-plan.json is the plan in the
existing StagePlan form (S1 = Act 1, S2 = chapters, S3 = the ending; vo_line = the DramaBox
prompt; camera kept beside it under `camera`), for the stage director.

TOPICS_FILE=out/story-eval-v5/topics.json PLAN_MODEL=deepseek-v4.1-flash uv run python scripts/story_eval_v7.py OUT_DIR [TOPIC ...]
REUSE_SCRIPT=<v6 or v7 run dir>: take the exploration and script from there; run the Voice and the planner only.
"""
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import story_eval_v6 as v6  # noqa: E402  (patches v5 → v4 → v3; chdirs to the repo)

from agno.agent import Agent  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from konvey import story_voice as voice  # noqa: E402
from konvey.compute import make_tools  # noqa: E402
from konvey.schemas import OBJECT_KINDS  # noqa: E402
from konvey.stage.displays import fill_plan  # noqa: E402
from konvey.story import Exploration, Script, VisualBeat  # noqa: E402
from konvey.story_sim import sim_problem, simulate  # noqa: E402

v3, v4, v5 = v6.v3, v6.v4, v6.v5
v3.EXPLORER = v3.fill(Path("prompts/shared/explorer-v7.md").read_text())
v3.WRITER = v3.fill(Path("prompts/shared/writer-v7.md").read_text()) + v5._opening[v5._opening.index("## How 3Blue1Brown opens"):]
PLANNER_MODEL = os.environ.get("VISUAL_MODEL", v3.WRITER_MODEL)
WORDS_PER_SEC = 2.2


def _objects_section():
    """The object kinds and how to pick them, from the stage planner's prompt (one source)."""
    text = Path("prompts/agent2-stage/plan.md").read_text()
    part = text[text.index("## Objects: kinds and data"):text.index("## Grounding")].split("\n", 1)[1]
    for a, b in (("walkthrough step", "trace step"), ("the walkthrough", "the trace"),
                 ("KNOWLEDGE_PACK", "the findings")):
        part = part.replace(a, b)
    return fill_plan(part).strip()


PLANNER = Path("prompts/shared/visual-planner-v7.md").read_text().replace("{{OBJECTS}}", _objects_section())


# --- Explorer: simulate tool, sim and trace checks ---------------------------------------------

def tools_v7(log=None):
    tools = make_tools(log)
    if log is None:
        return tools + [simulate]

    def simulate_logged(rule: str, settings: str, times: str = "end") -> str:
        return log.record("simulate", f"{rule} {settings} @ {times}", simulate(rule, settings, times))

    simulate_logged.__name__, simulate_logged.__doc__ = simulate.__name__, simulate.__doc__
    return tools + [simulate_logged]


v3.make_tools = tools_v7
_computed_v4 = v4.computed
v4.computed = lambda exp: [f for f in _computed_v4(exp) if not f.sim]  # a sim finding is checked by its rerun


def trace_problems(exp: Exploration):
    ids = {f.id for f in exp.findings}
    out = []
    for t in exp.traces:
        keys = [set(s.state) for s in t.steps]
        if len(t.steps) < 2:
            out.append(f"trace {t.id}: one step; a worked run has every step (3–12)")
        if len(t.steps) > 12:
            out.append(f"trace {t.id}: {len(t.steps)} steps; give at most 12 (the first ones, where something happens, the last)")
        if any(k != keys[0] for k in keys) or (t.start and set(t.start) != keys[0]):
            out.append(f"trace {t.id}: its states do not all have the same keys; give the full state at every step")
        if missing := [f for f in t.findings if f not in ids]:
            out.append(f"trace {t.id}: findings {missing} do not exist")
    return out


def explorer_problems(exp: Exploration):
    out = v6.explorer_problems(exp)
    out += [p for f in exp.findings if f.sim for p in [sim_problem(f.id, f.sim)] if p]
    return out + trace_problems(exp)


def writer_view(exp: Exploration):
    data = json.loads(v6.writer_view(exp))
    sims = {f.id: f.sim.get("rule") for f in exp.findings if f.sim}
    for f in data["findings"]:
        if f["id"] in sims:
            f["sim"] = sims[f["id"]]
    data["traces"] = [{"id": t.id, "of": t.of, "findings": t.findings, "steps": [s.action for s in t.steps]}
                      for t in exp.traces]
    return json.dumps(data, ensure_ascii=False)


v3.explorer_problems, v3.writer_view = explorer_problems, writer_view


# --- Visual planner --------------------------------------------------------------------------

class SectionOut(BaseModel):
    beats: list[VisualBeat] = Field(min_length=1)


def sections(script: Script):
    """[(id, [move index, …])]: Act 1, then each run of a chapter's moves, the rest as 'end'."""
    out = []
    for i, m in enumerate(script.moves):
        sid = "act1" if m.act == 1 else (m.chapter or "end")
        if out and out[-1][0] == sid:
            out[-1][1].append(i)
        else:
            out.append((sid, [i]))
    seen = {}
    for k, (sid, moves) in enumerate(out):  # a chapter or ending split in two keeps distinct ids
        seen[sid] = seen.get(sid, 0) + 1
        if seen[sid] > 1:
            out[k] = (f"{sid}-{seen[sid]}", moves)
    return out


def used_findings(script: Script, moves, exp: Exploration):
    want = set()
    for i in moves:
        m = script.moves[i]
        for ln in m.lines:
            want.update(ln.uses)
        for d in exp.discovery:
            if d.id == m.discovery:
                want.update([d.case, *d.pays_off])
        for s in exp.series:
            if s.id == m.series:
                want.update(s.cases)
    for c in exp.deepening:
        if any(script.moves[i].chapter == c.id for i in moves):
            want.update(c.findings)
    return [f for f in exp.findings if f.id in want]


def _head(action: str) -> list[str]:
    """The words before a step's colon (or its first clause): "insert kim: slots 2, 9" -> [insert, kim]."""
    head = re.split(r"[:—,(=]", action, maxsplit=1)[0]
    return [w.lower() for w in re.findall(r"[A-Za-z][\w'-]{2,}", head)]


def item_words(t, j: int) -> list[str]:
    """What goes in at step j: its head words that are not verbs (a word that starts two or more steps,
    "insert", "query") and are its own (in no other step's head) or a name ("Kim leaves", "query Kim");
    capitalised first, else the last ("delete kim" -> kim). A single-step trace has no verb to tell apart."""
    heads = [_head(s.action) for s in t.steps]
    firsts = [h[0] for h in heads if h]
    verbs = {w for w in firsts if firsts.count(w) > 1}   # "query" starts two steps: a verb
    seen = {w: sum(w in h for h in heads) for h in heads for w in h}
    caps = {w.lower() for w in re.findall(r"\b[A-Z][\w'-]+", t.steps[j].action)}
    own = [w for w in heads[j] if w not in verbs and (seen[w] == 1 or w in caps or len(heads) == 1)]
    return sorted(own, key=lambda w: (w not in caps, -own.index(w)))


def _names_step(line: str, t, j: int) -> bool:
    """A spoken line names trace step j: what goes in ("Kim's land on two slots"), or two of its
    numbers, or all of them (0, 1 and 2 are ordinary words and never count alone)."""
    if any(re.search(rf"\b{re.escape(w)}(?:'s)?\b", line, re.I) for w in item_words(t, j)):
        return True
    want, said = set(v6.numbers_said(t.steps[j].action)), set(v3.numbers_in(line))
    return len(want & said) >= 2 or (bool(want) and want <= said)


def walked_steps(script: Script, t) -> dict[int, list[int]]:
    """{move index: [trace steps it names, a line each]} for trace ``t``."""
    out = {}
    for i, m in enumerate(script.moves):
        got = []
        for ln in m.lines:
            named = [j for j in range(len(t.steps)) if _names_step(ln.line, t, j)]
            if len(named) <= 2:   # a line naming three steps at once sums them up, it walks none
                got += named
        if got:
            out[i] = list(dict.fromkeys(got))
    return out


def walks(script: Script, exp: Exploration):
    """{move index: trace id}: the move that names most of a trace's steps walks through it; with none
    named, the move that uses the trace's findings most."""
    out = {}
    for t in exp.traces:
        named = walked_steps(script, t)
        if named:
            out.setdefault(max(named, key=lambda i: len(named[i])), t.id)
            continue
        uses = [sum(len(set(ln.uses) & set(t.findings)) for ln in m.lines) for m in script.moves]
        if uses and max(uses) > 0:
            out.setdefault(uses.index(max(uses)), t.id)
    return out


WALK_STEPS = 2   # steps of a used trace the story walks a line each before it summarises the rest


def trace_walk_problems(script: Script, exp: Exploration) -> list[str]:
    """A worked trace the story leans on, said in one summary line ("five guests each flip three, ten
    end up lit"): the viewer never sees one step happen, so never sees why the state is what it is. Its
    first steps get a line each, naming what goes in and where it lands; the rest may be summarised."""
    out = []
    for t in exp.traces:
        if len(t.steps) < 2 or not any(set(ln.uses) & set(t.findings) for m in script.moves for ln in m.lines):
            continue
        named = walked_steps(script, t)
        best = max((len(v) for v in named.values()), default=0)
        need = min(WALK_STEPS, len(t.steps))
        if best < need:
            first = "; ".join(f"{s.action!r}" for s in t.steps[:need])
            out.append(f"trace {t.id} ({t.of}) is used but its steps are never walked: the viewer never sees one "
                       f"happen. In one move, give its first {need} steps a line each in order, naming what goes in "
                       f"and where it lands ({first}), then summarise the rest")
    return out


_writer_v6 = v3.writer_problems


def writer_problems(script: Script, exp: Exploration):
    return _writer_v6(script, exp) + trace_walk_problems(script, exp)


v3.writer_problems = writer_problems


def planner_message(script: Script, exp: Exploration, sid, moves, before):
    disc = {d.id: d.model_dump() for d in exp.discovery}
    walk = walks(script, exp)
    sec = [{"move": i, "walks_trace": walk.get(i), "act": m.act, "chapter": m.chapter, "steps": m.steps, "picture": m.picture,
            "change": m.change, "discovery": disc.get(m.discovery), "series": m.series,
            "introduces": m.introduces, "changes_to": m.changes_to,
            "lines": [{"line": j, "says": ln.line, "uses": ln.uses} for j, ln in enumerate(m.lines)]}
           for i, m in ((i, script.moves[i]) for i in moves)]
    finds = [{k: v for k, v in f.model_dump().items() if k in ("id", "claim", "numbers", "say", "sim") and v}
             for f in used_findings(script, moves, exp)]
    series = [s.model_dump() for s in exp.series if any(script.moves[i].series == s.id for i in moves)]
    return (f"TOPIC REQUEST: {v3.TOPICS.get(script_key(script), '')}\n\nSECTION {sid}:\n{json.dumps(sec, ensure_ascii=False)}\n\n"
            f"PICTURE:\n{exp.picture.model_dump_json()}\n\nFINDINGS:\n{json.dumps(finds, ensure_ascii=False)}\n\n"
            f"SERIES:\n{json.dumps(series, ensure_ascii=False)}\n\nTRACES:\n{json.dumps([t.model_dump() for t in exp.traces], ensure_ascii=False)}\n\n"
            f"BEFORE:\n{json.dumps(before, ensure_ascii=False)}\n\nOutput the JSON.")


_keys = {}


def script_key(script):
    return _keys.get(id(script), "")


ID = re.compile(r"^[a-z][a-z0-9_]*$")
SHOTS = {"full", "question", "derive", "compare", "title"}
WORD_KINDS = {"text", "tex", "number"}   # set as words by a shot; every other kind is a picture


def _mark_kinds() -> set[str]:
    from konvey.stage import displays
    return {d.kind for d in displays.all_displays() if d.kind and not d.picture} - WORD_KINDS


MARK_KINDS = _mark_kinds()   # drawn on a picture (dots, a note, a brace): not a picture of their own


def pictures(objects: list) -> list:
    return [o for o in objects if o.get("kind") not in WORD_KINDS | MARK_KINDS]


MAX_PICTURES = 2


def crowd_problems(beats) -> list[str]:
    """3b1b's frame holds one picture, or two that are linked (blocks and their phase circle);
    three or four small pictures side by side read as a dashboard, each too small to watch."""
    out = []
    for b in beats:
        pics = pictures(b.objects)
        if len(pics) > MAX_PICTURES:
            out.append(f"move {b.move} line {b.line}: {len(pics)} pictures on screen "
                       f"({', '.join(str(o.get('id')) for o in pics)}); at most {MAX_PICTURES}. Keep the main picture and "
                       "the one this line is about; drop the others (a word or number can say the rest)")
    return out[:4]


def renamed_axes_problems(beats) -> list[str]:
    """One plot id keeps its axis names (the engine draws the first ones), so a different graph
    under an old id shows the wrong axis names: a different graph is a new picture with its own id."""
    first, out = {}, []
    for b in beats:
        for o in b.objects:
            d = o.get("data") or {}
            if o.get("kind") != "plot":
                continue
            names = first.setdefault(o.get("id"), {})
            for k in ("xlabel", "ylabel"):
                if d.get(k):
                    if k in names and str(names[k]) != str(d[k]):
                        out.append(f"move {b.move} line {b.line}: plot {o.get('id')} renames its {k} "
                                   f"{names[k]!r} -> {d[k]!r}; a different graph needs its own id")
                    names.setdefault(k, d[k])
    return out[:3]
SKIP_KEYS = {"until", "seed", "zoom", "at", "r", "size", "w", "h", "x", "y", "z", "index", "pointers",
             "highlight", "highlight_cols", "built_from", "period", "views"}


def _numbers(v, key=""):
    if key in SKIP_KEYS:
        return []
    if isinstance(v, dict):
        return [n for k, x in v.items() for n in _numbers(x, k)]
    if isinstance(v, list):
        return [n for x in v for n in _numbers(x, key)]
    return v3.flat(v)


def _bits(v):
    """A string of 0s and 1s (a bit array, "10010") as its bits: read as one number it is 1e+31,
    which no picture of the bits shows."""
    if isinstance(v, str) and re.fullmatch(r"[01]{2,}", v.strip()):
        return [int(c) for c in v.strip()]
    if isinstance(v, dict):
        return {k: _bits(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_bits(x) for x in v]
    return v


def planner_problems(out: SectionOut, script: Script, exp: Exploration, moves):
    probs, warns = [], []
    want = [(i, j) for i in moves for j in range(len(script.moves[i].lines))]
    got = [(b.move, b.line) for b in out.beats]
    if got != want:
        miss = [w for w in want if w not in got][:6]
        extra = [g for g in got if g not in want][:6]
        probs.append(f"beats must be exactly one per line in order: (move, line) {want[:3]}…; "
                     f"missing {miss}, not in this section or repeated {extra}" if miss or extra else
                     "beats are out of order: one per line, in the order of SECTION")
    finds = {f.id: f for f in exp.findings}
    traces = {t.id: t for t in exp.traces}
    known = v3.flat([[f.claim, f.numbers, list(f.say.values()), (f.sim or {}).get("values"), (f.sim or {}).get("settings")]
                     for f in exp.findings])
    known += v3.flat([[t.start, [[s.action, s.state] for s in t.steps]] for t in traces.values()])
    known += v3.flat([s.shows for s in exp.picture.states])
    last_until, sim_settings = {}, {}
    camera_beats = 0
    for b in out.beats:
        where = f"move {b.move} line {b.line}"
        if not (0 <= b.move < len(script.moves) and 0 <= b.line < len(script.moves[b.move].lines)):
            continue
        line = script.moves[b.move].lines[b.line]
        probs += [f"{where} vo: {p}: {b.vo!r} (line: {line.line!r})" for p in voice.problems(line.line, b.vo)]
        ids = set()
        for o in b.objects:
            oid, kind = str(o.get("id", "")), o.get("kind")
            ids.add(oid)
            if not ID.match(oid):
                probs.append(f"{where}: object id {oid!r} is not snake_case")
            if kind not in OBJECT_KINDS:
                probs.append(f"{where}: kind {kind!r} is not one of {', '.join(OBJECT_KINDS)}")
            if not isinstance(o.get("data", {}), dict):
                probs.append(f"{where}: {oid}'s data is not an object")
                continue
            if kind == "simulation":
                setup = {k: v for k, v in o.get("data", {}).items() if k not in ("until", "views")}
                if sim_settings.setdefault(oid, setup) != setup:
                    probs.append(f"{where}: {oid} changes its settings ({sim_settings[oid]} → {setup}); a different run is "
                                 "a new simulation with its own id")
                u = o.get("data", {}).get("until")
                if isinstance(u, (int, float)):
                    if u < last_until.get(oid, 0):
                        probs.append(f"{where}: {oid} until={u} goes back in time (was {last_until[oid]}); raise it beat by beat")
                    last_until[oid] = u
                continue  # its numbers are settings, checked against the finding below
            if o.get("source") == "visual":
                continue
            local = known + v3.flat(line.line)
            bad = [n for n in _numbers(o.get("data", {})) if abs(n) > 10 and not any(v3.same(n, k) or v3.same(k, n) for k in local)]
            if bad:
                probs.append(f"{where}: {oid} shows {sorted(set(bad))[:4]}, which no finding, trace, picture state or "
                             "the line has; use the findings' numbers or leave them out")
        for fid in line.uses:
            f = finds.get(fid)
            if not (f and f.sim):
                continue
            sims = [o for o in b.objects if o.get("kind") == "simulation" and o.get("data", {}).get("rule") == f.sim.get("rule")]
            if not sims:
                probs.append(f"{where}: the line uses {fid}, read off a {f.sim.get('rule')} simulation; show that run "
                             f"(a simulation object with rule {f.sim.get('rule')!r} and its settings {f.sim.get('settings')})")
                continue
            def diff(o):
                return {k: v for k, v in (f.sim.get("settings") or {}).items() if str(o["data"].get(k)) != str(v)}
            if all(diff(o) for o in sims):
                probs.append(f"{where}: no {f.sim.get('rule')} simulation here has {fid}'s settings "
                             f"{f.sim.get('settings')} ({sims[0].get('id')} differs in {diff(sims[0])}); copy them exactly")
        if b.trace_step:
            m = re.match(r"^(T\w+)\.(start|\d+)$", b.trace_step)
            t = traces.get(m.group(1)) if m else None
            if not t or (m.group(2) != "start" and int(m.group(2)) >= len(t.steps)):
                probs.append(f"{where}: trace_step {b.trace_step!r} is not a step of any trace (T1.start, T1.0, …)")
            elif not any(o.get("kind") == "simulation" for o in b.objects):  # a simulation shows its run's state live
                state = _bits(t.start if m.group(2) == "start" else t.steps[int(m.group(2))].state)
                shown = _numbers(_bits([o.get("data", {}) for o in b.objects]))
                missing = [n for n in v3.flat(state) if not any(v3.same(n, s) or v3.same(s, n) for s in shown)]
                if missing:
                    probs.append(f"{where}: shows {b.trace_step} but not its values {missing[:5]}; show the step's state exactly")
        if b.camera and (b.camera.view or b.camera.focus or b.camera.shot):
            camera_beats += 1
            for ref in [b.camera.view, *b.camera.focus]:
                if ref and ref != "page" and ref.split(">")[0].strip() not in ids:
                    probs.append(f"{where}: camera target {ref!r} is not an object of this beat ({', '.join(sorted(ids))})")
            if b.camera.shot and b.camera.shot not in SHOTS:
                probs.append(f"{where}: shot {b.camera.shot!r} is not one of {', '.join(sorted(SHOTS))}")
            elif b.camera.shot == "compare" and len(pictures(b.objects)) < 2:
                probs.append(f"{where}: shot 'compare' sets two pictures side by side, and this beat has "
                             f"{len(pictures(b.objects))}; give it two pictures or drop the shot")
    for i in moves:  # a run that reaches its end on the first of several lines is over before they watch it
        runs = {}
        for b in (b for b in out.beats if b.move == i):
            for o in b.objects:
                if o.get("kind") == "simulation" and isinstance(o.get("data"), dict):
                    runs.setdefault(o.get("id"), []).append(o["data"].get("until"))
        for oid, us in runs.items():
            if len(us) >= 3 and len(set(map(str, us))) == 1:
                probs.append(f"move {i}: {oid} has until={us[0]!r} on all {len(us)} of its beats, so the whole run plays "
                             "during the first line; raise until line by line and reach its end at the line that states the result")
    for i, tid in walks(script, exp).items():
        if i not in moves:
            continue
        steps = [b.trace_step for b in out.beats if b.move == i and (b.trace_step or "").startswith(tid + ".")]
        need = min(2, len(script.moves[i].lines))
        order = [-1 if x.endswith(".start") else int(x.rsplit(".", 1)[1]) for x in steps if re.match(r".*\.(start|\d+)$", x)]
        if len(steps) < need:
            probs.append(f"move {i} walks through trace {tid}: show its steps, one beat per step or two, with "
                         f"trace_step {tid}.start, {tid}.0, … and each step's state ({len(steps)} beats do now)")
        elif order != sorted(order):
            probs.append(f"move {i}: the steps of trace {tid} are out of order ({steps}); show them in order")
    heads = [voice.opening(b.vo) for b in out.beats]
    for k in range(2, len(heads)):
        if heads[k] and heads[k] == heads[k - 1] == heads[k - 2]:
            probs.append(f"beats {k - 2}–{k} of this section all open with {heads[k]!r}; vary the delivery")
            break
    for i in moves:
        if script.moves[i].discovery and not any(b.move == i and b.camera and (b.camera.view or b.camera.focus) for b in out.beats):
            probs.append(f"move {i} is the discovery ({script.moves[i].discovery}): at the line where the viewer should "
                         "notice, give a camera view or focus on the exact part the notice is about")
    warns += picture_warnings(out.beats)
    probs += state_problems(out.beats)
    probs += pile_problems(out.beats)
    probs += flat_problems(out.beats)
    probs += lopsided_problems(out.beats)
    p, w = slide_problems(out.beats)
    probs, warns = probs + p + listed_problems(out.beats) + terms_problems(out.beats), warns + w
    probs += crowd_problems(out.beats) + kind_problems(out.beats) + cause_problems(out.beats, exp, script)
    probs += renamed_axes_problems(out.beats)
    if out.beats and camera_beats > 0.5 * len(out.beats):
        warns.append(f"the camera moves on {camera_beats} of {len(out.beats)} beats; about a third reads calmer")
    return probs, warns


STATE_KINDS = {"plane", "plot"}   # where a run's state gets redrawn by hand instead of shown as its view


def picture_warnings(beats) -> list[str]:
    """Soft rules (from a few runs, not measured on 3b1b yet): the main picture stays on screen,
    and a simulated run's state is its view, not a hand-drawn plane beside or instead of it."""
    warns = []
    seen = [{o.get("id") for o in pictures(b.objects)} for b in beats]
    counts = {}
    for ids in seen:
        for i in ids:
            counts[i] = counts.get(i, 0) + 1
    if counts and len(beats) >= 6:
        main = max(counts, key=counts.get)
        if counts[main] < 0.6 * len(beats):
            switches = sum(1 for a, b in zip(seen, seen[1:]) if a and b and not a & b)
            warns.append(f"the main picture {main!r} is on {counts[main]} of {len(beats)} beats and the picture "
                         f"is swapped {switches} times; add new pictures beside it instead of replacing it")
    return warns


def _fns(o) -> dict[str, str]:
    fns = (o.get("data") or {}).get("fns")
    return {str(k): str(v) for k, v in fns.items()} if isinstance(fns, dict) else {}


def pile_problems(beats) -> list[str]:
    """A plot that gains a curve which is one of its curves plus more terms (P2, then P4 beside
    it): 3b1b bends the one curve into the next while the line is spoken, and its formula gains
    the term. A pile of partial sums reads as a chart, not as a curve being built."""
    squash = lambda e: re.sub(r"\s+", "", e.split("|")[-1])  # noqa: E731 - a curve's last step
    prev: dict[str, dict[str, str]] = {}
    out = []
    for b in beats:
        for o in b.objects:
            if o.get("kind") != "plot":
                continue
            oid, now = o.get("id"), _fns(o)
            before = prev.get(oid, {})
            for label, expr in now.items():
                if label in before:
                    continue
                grown = [k for k, e in before.items() if k in now and len(squash(expr)) > len(squash(e))
                         and squash(expr).startswith(squash(e))]
                if grown:
                    k = grown[0]
                    out.append(f"move {b.move} line {b.line}: plot {oid} adds {label!r} beside {k!r}, which it extends "
                               f"by more terms. Grow the one curve instead: \"{k.split('|')[-1].strip()} | {label}\": "
                               f"\"{before[k].split('|')[-1].strip()} | {expr}\" (it bends while the line is spoken; "
                               f"one label per step), drop the separate {label!r}, and give the formula the same "
                               "stages (tex \"a || b\", follow the plot)")
            prev[oid] = now
    return out[:4]


def flat_problems(beats) -> list[str]:
    """A plot's y range many times the height of its first (main) curve flattens that curve into
    a line: the range was stretched to keep the approximations inside the box. 3b1b sizes y to
    the function and lets a diverging approximation leave at the top or bottom edge."""
    import numpy as np
    from konvey.stage.displays.plot import spec as PS
    out, seen = [], set()
    for b in beats:
        for o in b.objects:
            d = o.get("data") or {}
            if o.get("kind") != "plot" or o.get("id") in seen or not d.get("y"):
                continue
            fns = _fns(o)
            if not fns:
                continue
            label, expr = next(iter(fns.items()))
            try:
                x, y = PS.pair(d["x"], "x"), PS.pair(d["y"], "y")
                ys = PS.fn_of(expr.split("|")[0])(np.linspace(*x, 400))
            except Exception:  # noqa: BLE001 - malformed data is reported by the plot checks
                continue
            ys = ys[np.isfinite(ys)]
            if not len(ys):
                continue
            lo, hi = np.percentile(ys, 2), np.percentile(ys, 98)
            span = max(hi - lo, 1e-9)
            if (y[1] - y[0]) > 5 * span and lo >= y[0] and hi <= y[1]:
                seen.add(o.get("id"))
                pad = 0.25 * span
                out.append(f"move {b.move} line {b.line}: plot {o.get('id')} has y={list(d['y'])}, "
                           f"{(y[1] - y[0]) / span:.0f}x the height of its main curve {label!r} "
                           f"({lo:.3g} to {hi:.3g}), so {label!r} reads as a flat line. Size y to it "
                           f"(about [{lo - pad:.2g}, {hi + pad:.2g}]); an approximation that grows "
                           "leaves at the top or bottom edge, as in 3b1b's graphs")
    return out


def lopsided_problems(beats) -> list[str]:
    """A function symmetric about 0 (even or odd) on an x range that is not shows half of
    itself: x from -1 to 5.5 cut a cosine-shaped curve off on the left."""
    import numpy as np
    from konvey.stage.displays.plot import spec as PS
    out, seen = [], set()
    for b in beats:
        for o in b.objects:
            d = o.get("data") or {}
            fns = _fns(o)
            if o.get("kind") != "plot" or o.get("id") in seen or not fns or not d.get("x"):
                continue
            label, expr = next(iter(fns.items()))
            try:
                x0, x1 = PS.pair(d["x"], "x")
                f = PS.fn_of(expr.split("|")[0])
            except Exception:  # noqa: BLE001 - malformed data is reported by the plot checks
                continue
            r = max(abs(x0), abs(x1))
            xs = np.linspace(0.05 * r, r, 60)
            a, b_ = f(xs), f(-xs)
            ok = np.isfinite(a) & np.isfinite(b_)
            if ok.sum() < 30:
                continue
            scale = max(float(np.max(np.abs(a[ok]))), 1e-9)
            even = np.max(np.abs(a[ok] - b_[ok])) < 1e-6 * scale
            odd = np.max(np.abs(a[ok] + b_[ok])) < 1e-6 * scale
            if (even or odd) and abs(x0 + x1) > 0.25 * (x1 - x0):
                seen.add(o.get("id"))
                out.append(f"move {b.move} line {b.line}: plot {o.get('id')} has x={list(d['x'])}, but its main curve "
                           f"{label!r} is {'even' if even else 'odd'} (the same on both sides of 0), so half of it is cut "
                           f"off; use x=[-{r:g}, {r:g}]")
    return out


GAP_AT = re.compile(r"^\s*([^,@]+),([^,@]+)@x=([^:]+)(?::(.*))?$")
CARD_AT = re.compile(r"\bx\s*=\s*(-?\d+(?:\.\d+)?)\b")


def _gap(plot):
    """A plot's planned gap at an x: (curve a, curve b, x, label), or None."""
    m = GAP_AT.match(str((plot.get("data") or {}).get("gap") or ""))
    try:
        return (m.group(1).strip(), m.group(2).strip(), float(m.group(3)), (m.group(4) or "").strip()) if m else None
    except ValueError:
        return None


def _mark_xs(b, pid) -> set[float]:
    """Every x the beat reads plot ``pid`` at: its `points`, `dots` on it, its gap's x, and a
    number card naming an x ("error at x = 5")."""
    xs = set()
    for o in b.objects:
        d = o.get("data") or {}
        at = []
        if o.get("kind") == "plot" and o.get("id") == pid:
            at = list(d["points"].values()) if isinstance(d.get("points"), dict) else []
            if _gap(o):
                at.append([_gap(o)[2]])
        elif o.get("kind") == "dots" and d.get("on") == pid:
            at = d.get("at") or []
        elif o.get("kind") == "number" and CARD_AT.search(str(d.get("label") or "")):
            at = [[CARD_AT.search(str(d["label"])).group(1)]]
        for p in at:
            try:
                xs.add(round(float(p[0]), 3))
            except (TypeError, ValueError, IndexError):
                continue
    return xs


def _quantity(label) -> str:
    """The first word of a number card's label: what it reads ("gap at x = 2" -> "gap")."""
    m = re.search(r"[A-Za-z]{3,}", str(label or ""))
    return m.group(0).lower() if m else ""


def _readings(plot, x: float) -> dict[tuple, float]:
    """What a plot can read live at x: each curve's height ({y}) and the distance between each
    pair of curves ({gap}), keyed by curve position (labels change: P, then P4)."""
    import numpy as np
    from konvey.stage.displays.plot import spec as PS
    ys = []
    for expr in _fns(plot).values():
        try:
            ys.append(float(PS.fn_of(expr.split("|")[-1])(np.array([x]))[0]))
        except Exception:  # noqa: BLE001 - malformed data is reported by the plot checks
            ys.append(float("nan"))
    out = {("y", i): v for i, v in enumerate(ys)}
    out |= {("gap", i, j): abs(ys[i] - ys[j]) for i in range(len(ys)) for j in range(i + 1, len(ys))}
    return {k: v for k, v in out.items() if np.isfinite(v)}


def _reads(value, x, plot, key) -> bool:
    try:
        v = abs(float(value))
    except (TypeError, ValueError):
        return False
    r = _readings(plot, x).get(key)
    return r is not None and abs(abs(r) - v) <= 0.03 * max(abs(r), v) + 1e-12


def _curve(plot, name) -> int | None:
    """The position of the curve a gap names: its label, or one of its steps' labels ("y=1 | P2")."""
    for i, k in enumerate(_fns(plot)):
        if name.strip() in {k.strip(), *(p.strip() for p in k.split("|"))}:
            return i
    return None


def _live_key(plot):
    """The reading a plot's own gap counts: ("gap", i, j) by curve position."""
    g = _gap(plot)
    ij = g and sorted(i for i in (_curve(plot, g[0]), _curve(plot, g[1])) if i is not None)
    return ("gap", *ij) if ij and len(ij) == 2 and ij[0] != ij[1] else None


def slide_problems(beats) -> tuple[list[str], list[str]]:
    """The same reading at a new x, line after line (the gap at 0.5, then at 2, then at 5), drawn
    as a new dot and a new number card each time: 3b1b slides the one point there while the
    line is spoken and the number counts as it goes. A problem when the cards read what the plot
    can count itself (a curve's height, the gap between two curves); a warning otherwise."""
    from konvey.stage.displays.plot import spec as PS
    probs, warns = [], []
    pids = list(dict.fromkeys(o.get("id") for b in beats for o in b.objects if o.get("kind") == "plot"))
    for pid in pids:
        spots, cur = [], None   # a spot: the beats where the plot's dots stay at the same x's
        for b in beats:
            plot = next((o for o in b.objects if o.get("kind") == "plot" and o.get("id") == pid), None)
            if plot is None:
                cur = None
                continue
            xs = _mark_xs(b, pid)
            if xs and (cur is None or not xs <= cur["xs"]):
                cur = {"b": b, "plot": plot, "xs": xs, "from": cur["xs"] if cur else None, "cards": []}
                spots.append(cur)
            if cur:
                cur["cards"] += [(_quantity((o.get("data") or {}).get("label")), (o.get("data") or {}).get("value"), plot)
                                 for o in b.objects if o.get("kind") == "number"]
                if _gap(plot):   # the plot's own live gap readout: it reads "gap" whatever its label
                    cur["cards"] += [(w, "live", plot) for w in {_quantity(_gap(plot)[3]), "gap"} - {""}]
        for a, c in zip(spots, spots[1:]):
            d = c["plot"].get("data") or {}
            same = {w for w, _, _ in a["cards"]} & {w for w, _, _ in c["cards"]} - {""}
            if c["from"] is None or c["from"] is not a["xs"] or d.get("slide") is not None or not same:
                continue
            new = sorted(c["xs"] - a["xs"])[0]
            old = min(a["xs"], key=lambda x: abs(x - new))
            try:
                x0, x1 = PS.pair(d.get("x"), "x")
            except Exception:  # noqa: BLE001 - malformed data is reported by the plot checks
                continue
            if abs(new - old) < 0.05 * (x1 - x0):
                continue
            word = sorted(same)[0]

            def reads(cards, x, k):
                return any(_live_key(plot) == k if v == "live" else _reads(v, x, plot, k)
                           for w, v, plot in cards if w in same)
            key = next((k for k in _readings(c["plot"], new) if reads(a["cards"], old, k) and reads(c["cards"], new, k)),
                       None)
            fns = [k.split("|")[-1].strip() for k in _fns(c["plot"])]
            where = (f"move {c['b'].move} line {c['b'].line}: on {pid} the {word!r} reading jumps from x={old:g} "
                     f"to x={new:g} (drawn again at the new x, a still picture per x)")
            if key is None:
                warns.append(f"{where}; if the plot can show that value (a curve's height, the gap between two "
                             f"curves), slide the point there instead: \"slide\": [{old:g}, {new:g}]")
                continue
            if key[0] == "gap":
                read = (f'"points": {{"x = {{x}}": [{old:g}, "{fns[key[1]]}"]}}, '
                        f'"gap": "{fns[key[1]]},{fns[key[2]]}@x={old:g}: {word} {{gap}}"')
            else:
                read = f'"points": {{"{word} {{y}}": [{old:g}, "{fns[key[1]]}"]}}'
            probs.append(f"{where}. Slide it: on the line that goes there, give {pid} {read}, \"slide\": "
                         f"[{old:g}, {new:g}] (the dot rides the curve and the number counts as it goes); drop "
                         f"the {word!r} number cards, and write the point at x={new:g} on the lines after")
    return probs[:4], warns[:3]


LISTED_AT = re.compile(r"\bx\s*=\s*(-?\d+(?:\.\d+)?)\s*[:=,]\s*(-?\d+(?:\.\d+)?(?:e-?\d+)?)")


def _listed(o) -> list[tuple[float, object]]:
    """(x, value) pairs a bars or array picture lists by x: bars labelled "x = 2", array items "x=2: 0.083"."""
    d = o.get("data") or {}
    out = []
    if o.get("kind") == "bars":
        for label, v in zip(d.get("labels") or [], d.get("values") or []):
            m = CARD_AT.search(str(label))
            if m:
                out.append((float(m.group(1)), v))
    elif o.get("kind") == "array":
        out = [(float(m.group(1)), m.group(2)) for m in (LISTED_AT.search(str(v)) for v in d.get("values") or []) if m]
    return out


def listed_problems(beats) -> list[str]:
    """A plot's reading at several x's set out as bars or an array of values beside it (the error at 1, 2, 3, 5):
    a chart of what the plot can show itself. 3b1b slides the point along the curve with the number counting."""
    out, done = [], set()
    for b in beats:
        plots = [o for o in b.objects if o.get("kind") == "plot"]
        for o in b.objects:
            pairs = _listed(o)
            if o.get("id") in done or len({x for x, _ in pairs}) < 2:
                continue
            for plot in plots:
                hits = {}
                for key in _readings(plot, pairs[0][0]):
                    xs = sorted({x for x, v in pairs if _reads(v, x, plot, key)})
                    if len(xs) >= 2:
                        hits[key] = xs
                if not hits:
                    continue
                key, xs = max(hits.items(), key=lambda kv: len(kv[1]))
                fns = [k.split("|")[-1].strip() for k in _fns(plot)]
                read = (f'"points": {{"x = {{x}}": [{xs[0]:g}, "{fns[key[1]]}"]}}, '
                        f'"gap": "{fns[key[1]]},{fns[key[2]]}@x={xs[0]:g}: gap {{gap}}"' if key[0] == "gap"
                        else f'"points": {{"{{y}}": [{xs[0]:g}, "{fns[key[1]]}"]}}')
                done.add(o.get("id"))
                out.append(f"move {b.move} line {b.line}: {o.get('kind')} {o.get('id')} lists {plot.get('id')}'s "
                           f"{'gap between ' + fns[key[1]] + ' and ' + fns[key[2]] if key[0] == 'gap' else 'height'} "
                           f"at x = {', '.join(f'{x:g}' for x in xs)}: values the plot shows itself. Slide instead: on "
                           f"the line that walks out, give {plot.get('id')} {read}, \"slide\": [{xs[0]:g}, {xs[-1]:g}] "
                           f"(the dot rides the curve and the number counts as it goes), and drop {o.get('id')}")
                break
    return out[:3]


def cause_problems(beats, exp: Exploration, script: Script | None = None) -> list[str]:
    """Trace steps on the screen: a step's first beat is a line that walks that step (a step put on a
    line about something else makes the picture change for no reason the viewer hears), and a step
    whose action names what goes in ("insert kim: slots 2, 9") shows that name in a note with an
    arrow to each place it lands, not only the new state."""
    traces, out, seen = {t.id: t for t in exp.traces}, [], set()
    for b in beats:
        m = re.match(r"^(T\w+)\.(\d+)$", b.trace_step or "")
        t = traces.get(m.group(1)) if m else None
        if not t or int(m.group(2)) >= len(t.steps) or b.trace_step in seen:
            continue   # the first beat that shows a step shows its cause; later ones talk about it
        seen.add(b.trace_step)
        j = int(m.group(2))
        action = t.steps[j].action
        line = script.moves[b.move].lines[b.line].line if script is not None else None
        if line is not None and not _names_step(line, t, j):
            out.append(f"move {b.move} line {b.line}: trace_step {b.trace_step} ({action!r}) is on a line about "
                       f"something else ({line[:60]!r}); put it on the line that says that step, or leave this "
                       "beat without trace_step")
            continue
        said = [w for w in item_words(t, j) if line is None or re.search(rf"\b{re.escape(w)}", line, re.I)]
        name = said[0] if said else None   # the item the line says goes in ("kim"), if it says one
        if not name or not re.search(r"\d", action):
            continue
        text = " ".join(str((o.get("data") or {}).get("text", "")) for o in b.objects if o.get("kind") == "note").lower()
        if name.lower() not in text:
            out.append(f"move {b.move} line {b.line}: shows {b.trace_step} ({action!r}) as its new state only; add a "
                       f"note with the text {name!r} on the picture, \"at\" each place it lands (one arrow "
                       f"each), with those places highlighted, so the viewer sees why they change")
    return out[:4]


def kind_problems(beats) -> list[str]:
    """Plans the Director cannot draw: one id that changes kind (a grid, then a drawing, then an
    array: an id keeps one tag, so each switch is rejected) and a one-row grid wider than a row fits
    (an array of that many wraps into rows itself)."""
    out, kinds, wide = [], {}, set()
    for b in beats:
        for o in b.objects:
            oid, kind, d = o.get("id"), o.get("kind"), o.get("data") or {}
            first = kinds.setdefault(oid, (kind, b))
            if first[0] != kind and len(out) < 3:
                out.append(f"move {b.move} line {b.line}: {oid} was a {first[0]} (move {first[1].move} line "
                           f"{first[1].line}) and is a {kind} here; one id keeps one kind. Keep the {first[0]} and "
                           f"change its data, or give the {kind} its own id")
                kinds[oid] = (kind, b)
            try:
                rows, cols = int(d.get("rows") or 0), int(d.get("cols") or 0)
            except (TypeError, ValueError):
                rows = cols = 0
            if kind == "grid" and rows == 1 and cols > 16 and oid not in wide:
                wide.add(oid)
                out.append(f"move {b.move} line {b.line}: grid {oid} is one row of {cols} cells, wider than the "
                           f"stage; plan it as an array (values in order, \"highlight\": [indices]): it wraps into "
                           "rows and keeps each cell's index")
    return out[:5]


MIN_TERMS = 3  # stages a sum built term by term shows at least (the user: 3 or 4 terms on screen)


def _terms(expr: str):
    """An expression's top-level terms, each as its values at a few x's (so 0.5*x^2 is x^2/2)."""
    import numpy as np
    from konvey.stage.displays.plot import spec as PS
    xs, parts, depth, cur = np.linspace(-1.3, 1.7, 7), [], 0, ""
    for i, ch in enumerate(expr.replace(" ", "")):
        depth += ch in "([{"
        depth -= ch in ")]}"
        if ch in "+-" and depth == 0 and cur and cur[-1] not in "*/^eE(":
            parts.append(cur)
            cur = ""
        cur += ch
    parts.append(cur)
    try:
        vals = [PS.fn_of(t)(xs) for t in parts if t not in "+-"]
    except Exception:  # noqa: BLE001 - malformed data is reported by the plot checks
        return None
    return [np.broadcast_to(v, xs.shape) for v in vals]


def _within(small, big) -> bool:
    """Every term of ``small`` is a term of ``big`` (matched one to one)."""
    import numpy as np
    left = list(big)
    for t in small:
        k = next((i for i, u in enumerate(left) if np.allclose(t, u, rtol=1e-4, atol=1e-9)), None)
        if k is None:
            return False
        left.pop(k)
    return True


def terms_problems(beats) -> list[str]:
    """A curve that grows by a term (a sum built up: each expression the one before plus more) shown
    at only two stages: the viewer sees one bend, not the sum closing in. Build it through 3-4 stages.
    A knob turned (terms dropped as well as added) is not a sum built up."""
    out = []
    pids = list(dict.fromkeys(o.get("id") for b in beats for o in b.objects if o.get("kind") == "plot"))
    for pid in pids:
        exprs, where = [], {}   # the plot's distinct expressions in order; the beat each first appears on
        for b in beats:
            for o in b.objects:
                if o.get("kind") == "plot" and o.get("id") == pid:
                    for expr in _fns(o).values():
                        for e in (p.strip() for p in str(expr).split("|") if p.strip()):
                            key = re.sub(r"\s+", "", e)
                            if key not in where:
                                where[key] = b
                                exprs.append(e)
        terms = [_terms(e) for e in exprs]
        chain, grew, knob = [1] * len(exprs), None, False
        for j, tj in enumerate(terms):
            for i in range(j):
                ti = terms[i]
                if ti is None or tj is None:
                    continue
                if len(tj) > len(ti) and _within(ti, tj):
                    chain[j] = max(chain[j], chain[i] + 1)
                    grew = grew or (exprs[i], exprs[j])
                elif len(tj) < len(ti) and _within(tj, ti):
                    knob = True
        if grew and not knob and max(chain) < MIN_TERMS:
            b = where[re.sub(r"\s+", "", grew[1])]
            out.append(f"move {b.move} line {b.line}: {pid}'s curve grows by a term only once ({grew[0]} -> {grew[1]}): "
                       f"one bend. A sum built term by term shows at least {MIN_TERMS}-4 stages: start it from its "
                       f"first term or two and step through them on one line (\"S\": \"a | a + b | a + b + c | ...\"), "
                       f"the formula gaining each term as the curve bends")
    return out[:2]


def state_problems(beats) -> list[str]:
    """A plane or plot drawn while the section's simulation is off screen: a run's state (its
    speeds, its phase) is the run's own view, moving in step beside it (3b1b's blocks and their
    velocity circle), not a still picture instead of it."""
    sims = set()
    for b in beats:
        kinds = {o.get("kind") for o in b.objects}
        sims |= {o.get("id") for o in b.objects if o.get("kind") == "simulation"}
        if sims and kinds & STATE_KINDS and "simulation" not in kinds:
            return [f"move {b.move} line {b.line}: a {'/'.join(sorted(kinds & STATE_KINDS))} with the simulation "
                    f"({', '.join(sorted(sims))}) off screen. If it shows the run's state (its speeds, energy, phase, "
                    "a count over time), make it the simulation's `views` and keep the run on screen; otherwise keep "
                    "the run beside it"]
    return []


def plan_section(script, exp, sid, moves, before):
    agent = v3.track(Agent(model=v3.model(PLANNER_MODEL), instructions=PLANNER, markdown=False), v3.log, "visual_planner")
    msg = planner_message(script, exp, sid, moves, before)
    warns = []

    def problems_of(o):
        p, w = planner_problems(o, script, exp, moves)
        warns[:] = w
        return p
    data, obj, first, left = v3.validated(agent, msg, SectionOut, problems_of)
    return {"id": sid, "moves": moves, "beats": [b.model_dump() for b in obj.beats] if obj else None,
            "problems": {"first": first, "left": left}, "warnings": warns}


def run_planner(script: Script, exp: Exploration, key: str):
    _keys[id(script)] = key
    secs = sections(script)
    first = plan_section(script, exp, *secs[0], before=[])
    before = (first["beats"] or [{}])[-1].get("objects", [])
    with ThreadPoolExecutor(6) as ex:
        rest = list(ex.map(lambda s: plan_section(script, exp, *s, before=before), secs[1:]))
    return [first, *rest]


def final_vo(script: Script, b: dict) -> str:
    """The beat's voice prompt, or the plain one where it is still invalid."""
    line = script.moves[b["move"]].lines[b["line"]].line
    return b["vo"] if not voice.problems(line, b.get("vo", "")) else voice.plain(line)


def stage_plan(script: Script, plan: list[dict], title: str):
    """The plan as a StagePlan dict (S1 Act 1, S2 chapters, S3 the ending), camera alongside."""
    groups = {"S1": [], "S2": [], "S3": []}
    for sec in plan:
        sid = "S1" if sec["id"] == "act1" else "S3" if sec["id"].startswith("end") else "S2"
        groups[sid] += sec["beats"] or []
    scenes = []
    for sid, purpose, nxt in (("S1", "hook", "S2"), ("S2", "build", "S3"), ("S3", "payoff", None)):
        beats = [{"vo_line": final_vo(script, b), "objects": b["objects"], "walkthrough_step": None,
                  "camera": b.get("camera"), "trace_step": b.get("trace_step")} for b in groups[sid]]
        words = sum(len(script.moves[b["move"]].lines[b["line"]].line.split()) for b in groups[sid])
        scenes.append({"id": sid, "purpose": purpose, "precedes": nxt, "vo_script": [b["vo_line"] for b in beats],
                       "duration_sec": round(words / WORDS_PER_SEC, 1), "beats": beats})
    return {"title": title, "scenes": scenes}


def after_writer(key, res):
    """Voice + planner on a finished exploration and script (in res); adds their results."""
    exp = Exploration.model_validate(res["explorer"])
    script = Script.model_validate(res["writer"])
    v3.progress(key, "visual planner started")
    plan = run_planner(script, exp, key)
    res["visual_plan"] = plan
    beats = sum(len(s["beats"] or []) for s in plan)
    res["visual_checks"] = {"sections": len(plan), "beats": beats,
                            "left": {s["id"]: s["problems"]["left"] for s in plan if s["problems"]["left"]},
                            "warnings": {s["id"]: s["warnings"] for s in plan if s["warnings"]},
                            "camera_beats": sum(1 for s in plan for b in s["beats"] or [] if b.get("camera")),
                            "sim_objects": sorted({o["id"] for s in plan for b in s["beats"] or [] for o in b["objects"]
                                                   if o.get("kind") == "simulation"}),
                            "trace_beats": sum(1 for s in plan for b in s["beats"] or [] if b.get("trace_step")),
                            "vo_fallbacks": sum(1 for s in plan for b in s["beats"] or [] if final_vo(script, b) != b.get("vo"))}
    if all(s["beats"] for s in plan):
        res["stage_plan"] = stage_plan(script, plan, script.explains[:80])
    v3.progress(key, f"planner ({beats} beats, {res['visual_checks']['vo_fallbacks']} plain voice fallbacks, "
                     f"{sum(len(x) for x in res['visual_checks']['left'].values())} problems left) done")
    return res


REUSE_SCRIPT = os.environ.get("REUSE_SCRIPT")


def one(key):
    if REUSE_SCRIPT:
        res = json.loads(Path(REUSE_SCRIPT, f"{key}.json").read_text())
    else:
        key, res = v3.one(key)
    if "error" in res or not res.get("writer"):
        return key, res
    try:
        return key, after_writer(key, res)
    except Exception as e:  # noqa: BLE001 - keep the exploration and script
        res["error"] = f"after writer: {e!r}"
        return key, res


if __name__ == "__main__":
    from concurrent.futures import as_completed
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    keys = sys.argv[2:] or list(v3.TOPICS)
    with ThreadPoolExecutor(10) as ex:
        for fut in as_completed([ex.submit(one, k) for k in keys]):
            key, res = fut.result()
            (out / f"{key}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
            if res.get("stage_plan"):
                (out / f"{key}.stage-plan.json").write_text(json.dumps(res["stage_plan"], indent=1, ensure_ascii=False))
            print(key, "error: " + res["error"] if "error" in res else
                  {"writer_left": (res.get("writer_problems") or {}).get("left"), **res.get("visual_checks", {})}, flush=True)
    summary = v3.log.summary()
    (out / "cost.json").write_text(json.dumps(summary, indent=1))
    print("cost", summary["total"]["usd"], {a: v["usd"] for a, v in summary["by_agent"].items()})
