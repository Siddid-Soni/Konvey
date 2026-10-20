"""Build out/<EVAL>/compare.html: per topic, 3b1b's arc, v2 (DeepSeek), and the configs in that eval dir.

EVAL=story-eval-v4 uv run python scripts/build_story_compare.py [CONFIG ...]   (default EVAL: story-eval-v3)
"""
import html
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path("/home/siddid/Projects/Konvey/out")
V1, V2 = ROOT / "story-eval", ROOT / os.environ.get("EVAL", "story-eval-v3")
V2OLD = ROOT / "story-eval-v2"
TOPICS = ["clacks", "convolutions", "wordle", "taylor", "chessboard", "clt", "inscribed", "triples", "basel", "fractaldim"]
CONFIGS = [c for c in sys.argv[1:]] or ["ds", "ds-haiku"]
NAMES = {"haiku": "haiku", "muse": "muse", "ds": "DeepSeek", "ds-haiku": "DeepSeek explorer + haiku writer",
         "ds-haiku-all": "DeepSeek explorer + haiku writer"}
e = html.escape

arcs = {}
for m in re.finditer(r"\*\*(\w[\w ]*?)\*\* (.*?)(?=\n\n\*\*|\n\n## |\Z)", (V1 / "3b1b-arcs.md").read_text(), re.S):
    key = {"inscribed rectangle": "inscribed", "fractal dimension": "fractaldim"}.get(m.group(1), m.group(1))
    arcs[key] = m.group(2).replace("\n", " ")


def cost(dirpath):
    try:
        return json.loads((dirpath / "cost.json").read_text())["total"]["usd"]
    except Exception:  # noqa: BLE001
        return None


def v1_block(t):
    d = json.loads((V2OLD / "ds" / f"{t}.json").read_text())
    if "checks" not in d:
        return ""
    lines = "".join(f"<li><span class=step>{e('/'.join(m['steps']))}</span> " + " ".join(e(l['line']) for l in m['lines']) + "</li>"
                    for m in d["writer"]["moves"])
    return f"<details><summary>v2 · DeepSeek · {d['checks']['words']} words (before the two acts)</summary><ol start=0>{lines}</ol></details>"


def v2_block(c, t):
    p = V2 / c / f"{t}.json"
    if not p.exists():
        return f"<section class=cfg><h3>{e(NAMES.get(c, c))}</h3><p class=bad>missing</p></section>"
    d = json.loads(p.read_text())
    if "error" in d or not d.get("checks"):
        return (f"<section class=cfg><h3>{e(NAMES.get(c, c))}</h3><p class=bad>{e(str(d.get('error', 'invalid')))}"
                f"</p><pre>{e(json.dumps(d.get('writer_problems') or d.get('explorer_problems'), indent=1))}</pre></section>")
    x, w, k = d["explorer"], d["writer"], d["checks"]
    states = "".join(f"<li><b>{e(s['id'])}</b> {e(s['shows'])}</li>" for s in x["picture"]["states"])
    chaps = "".join(f"<li><b>{e(z['id'])}</b> {e(z['setting'])}: <i>reveals</i> {e(z['reveals'])}</li>" for z in x.get("deepening", []))
    core = "".join(f"<li>{e(z)}</li>" for z in x.get("topic_core", []))
    disc = "".join(f"<li><b>{e(z['id'])}</b> in {e(z['case'])}: <i>notice</i> {e(z['notice'])} → <i>step</i> {e(z['step'])}</li>"
                   for z in x["discovery"])
    moves = []
    for i, m in enumerate(w["moves"]):
        tags = " ".join(f"<span class=tag>{e(v)}</span>" for v in [f"act {m.get('act', 1)}", m.get("chapter"), m["picture"], m.get("discovery"), m.get("series")] if v)
        lines = "".join(f"<p>{e(ln['line'])}</p>" for ln in m["lines"])
        moves.append(f"<div class=move><div class=mh><span class=num>{i}</span> <span class=step>{e(' / '.join(m['steps']))}</span> {tags}"
                     f"<div class=thinks>viewer thinks: {e(m['viewer_thinks'])} → {e(m['changes_to'])}</div></div>{lines}</div>")
    left = d["writer_problems"]["left"]
    warn = k.get("warnings", []) + [f"left after repair: {p}" for p in left] + [f"check failing: {p}" for p in k.get("checks_failing", [])]
    return (f"<section class=cfg><h3>{e(NAMES.get(c, c))}</h3>"
            f"<p class=meta>{k['words']} words ≈ {k['minutes_at_2.2wps']} min · planned {k['planned_minutes']:g} min "
            f"· {k['moves']} moves · {k['montages']} montages · opening {k['opening_words']} words"
            + (f" · {k['findings_checked']}/{k['findings_computed']} findings checked" if 'findings_computed' in k else '') + "</p>"
            f"<p class=why>Length: {e(k['length_why'])}</p>"
            + (f"<ul class=warn>{''.join(f'<li>{e(z)}</li>' for z in warn)}</ul>" if warn else "")
            + f"<p class=q><b>Question:</b> {e(x['question'])}</p>"
            f"<details><summary>Picture: {e(x['picture']['object'])}</summary><ul>{states}</ul>"
            f"<p><b>Key change:</b> {e(x['picture']['key_change'])}</p></details>"
            f"<details><summary>Discovery links ({len(x['discovery'])})</summary><ul>{disc}</ul></details>"
            f"<details><summary>Topic core ({len(x.get('topic_core', []))})</summary><ul>{core}</ul></details>"
            f"<details open><summary>Chapters ({len(x.get('deepening', []))}) · played {e(', '.join(k.get('chapters_played', [])))} · Act 1 {k.get('act1_share', 0):.0%}</summary><ul>{chaps}</ul></details>"
            f"<div class=moves>{''.join(moves)}</div></section>")


costs = " · ".join(f"{NAMES.get(c, c)} ${cost(V2 / c):.2f}" for c in CONFIGS if cost(V2 / c) is not None)
tabs = "".join(f"<button data-t={t}>{t}</button>" for t in TOPICS)
panes = "".join(
    f"<div class=pane id=p-{t}><div class=his><h2>3b1b · {t}</h2><p>{e(arcs.get(t, ''))}</p>{v1_block(t)}</div>"
    f"<div class=grid>{''.join(v2_block(c, t) for c in CONFIGS)}</div></div>" for t in TOPICS)

page = f"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Story eval {V2.name[len('story-eval-'):]}</title><style>
:root{{--bg:#f7f6f2;--fg:#1c1c1a;--mut:#6b6a64;--card:#fff;--line:#dedbd2;--acc:#2a6f97;--warn:#9a5b00;--bad:#a12a2a}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151514;--fg:#e8e6df;--mut:#9c998f;--card:#1f1f1d;--line:#34332f;--acc:#7fb8d8;--warn:#e0a640;--bad:#e07a7a}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}}
header{{padding:16px;border-bottom:1px solid var(--line)}} h1{{margin:0;font-size:20px}} .sub{{color:var(--mut);font-size:13px}}
nav{{display:flex;flex-wrap:wrap;gap:6px;padding:10px 16px;position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);z-index:1}}
nav button{{border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:6px;padding:5px 10px;cursor:pointer}}
nav button.on{{border-color:var(--acc);color:var(--acc);font-weight:600}}
.pane{{display:none;padding:16px}} .pane.on{{display:block}}
.his{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 16px;margin-bottom:16px}} .his h2{{margin:0 0 6px;font-size:16px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:14px}}
.cfg{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px;min-width:0}} .cfg h3{{margin:0 0 4px;font-size:15px;color:var(--acc)}}
.meta,.why{{color:var(--mut);font-size:13px;margin:2px 0}} .warn{{color:var(--warn);font-size:13px;margin:4px 0;padding-left:18px}} .bad{{color:var(--bad)}}
.q{{font-size:13px}} details{{font-size:13px;margin:4px 0}} summary{{cursor:pointer;color:var(--mut)}}
.move{{border-top:1px solid var(--line);padding:6px 0}} .move p{{margin:2px 0 2px 22px}}
.mh{{font-size:12px;color:var(--mut)}} .num{{display:inline-block;width:18px;color:var(--fg)}} .step{{font-weight:600;color:var(--fg)}}
.tag{{border:1px solid var(--line);border-radius:4px;padding:0 4px;margin-left:2px}} .thinks{{margin-left:22px;font-style:italic}}
ol{{padding-left:28px;font-size:13px}} ol .step{{font-weight:600;margin-right:4px;font-size:11px;color:var(--mut)}}
</style></head><body><header><h1>Story eval {V2.name[len('story-eval-'):]}: two acts, on ten 3b1b topics</h1>
<div class=sub>Max length 10 min; the Writer picks the length. Cost: {e(costs)}</div></header>
<nav>{tabs}</nav>{panes}
<script>
const bs=[...document.querySelectorAll('nav button')];
function show(t){{bs.forEach(b=>b.classList.toggle('on',b.dataset.t===t));document.querySelectorAll('.pane').forEach(p=>p.classList.toggle('on',p.id==='p-'+t));try{{localStorage.setItem('tab',t)}}catch(e){{}}}}
bs.forEach(b=>b.onclick=()=>show(b.dataset.t));let t0='clacks';try{{t0=localStorage.getItem('tab')||t0}}catch(e){{}}show(t0);
</script></body></html>"""
(V2 / "compare.html").write_text(page)
print("wrote", V2 / "compare.html")
