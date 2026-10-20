"""Writes out/voice-lines/index.html: every conversation line per hero (1.5 s or longer, longest first)
with a player, so references are picked by ear. Ticking lines builds a "hero: n, n, n" list in click order."""

import html
import json
import sys
from pathlib import Path

import librosa

sys.path.insert(0, str(Path(__file__).parent))
from common import ROOT  # noqa: E402

BASE = ROOT / "out" / "voice-lines"
sections = []
for folder in sorted(p for p in BASE.iterdir() if (p / "lines.json").exists()):
    rows = json.loads((folder / "lines.json").read_text())
    for r in rows:
        r["dur"] = librosa.get_duration(path=folder / r["file"])
    rows = sorted((r for r in rows if r["dur"] >= 1.5), key=lambda r: -r["dur"])
    numbered = []
    for i, r in enumerate(rows, 1):
        r["n"] = i
        numbered.append(f'<div class="row"><label><input type="checkbox" data-hero="{folder.name}" data-n="{i}"> <b>{i}</b></label>'
                        f'<span class="d">{r["dur"]:.1f}s</span><audio controls preload="none" src="{folder.name}/{r["file"]}"></audio>'
                        f'<span class="t">{html.escape(r["text"])}</span></div>')
    (folder / "numbered.json").write_text(json.dumps(rows, indent=1))
    sections.append(f'<h2>{folder.name.title()} ({len(rows)} lines)</h2>' + "".join(numbered))
(BASE / "index.html").write_text(f"""<!doctype html><meta charset="utf-8"><title>Reference line picker</title>
<style>body{{background:#111;color:#ddd;font:14px system-ui;max-width:1000px;margin:20px auto;padding:0 16px 120px}}
.row{{display:grid;grid-template-columns:70px 44px 300px 1fr;gap:10px;align-items:center;margin:3px 0}}
audio{{width:300px;height:32px}}.d{{color:#888}}h2{{color:#fff;margin-top:30px}}
#picks{{position:fixed;bottom:0;left:0;right:0;background:#222;padding:12px 16px;font:15px monospace;border-top:1px solid #444}}</style>
<h1>Pick reference lines by ear</h1><p>Tick lines in the order you want them (the first shapes delivery most), then send me the list at the bottom.</p>
{''.join(sections)}<div id="picks">picks: none yet</div>
<script>
const order=[];
document.addEventListener('change',e=>{{const c=e.target;const k=c.dataset.hero+':'+c.dataset.n;
 if(c.checked)order.push(k);else order.splice(order.indexOf(k),1);
 const by={{}};order.forEach(x=>{{const[h,n]=x.split(':');(by[h]=by[h]||[]).push(n)}});
 document.getElementById('picks').textContent='picks: '+(Object.entries(by).map(([h,ns])=>h+': '+ns.join(', ')).join('  |  ')||'none yet')}});
document.addEventListener('play',e=>document.querySelectorAll('audio').forEach(a=>a!==e.target&&a.pause()),true);
</script>""")
print(BASE / "index.html")
