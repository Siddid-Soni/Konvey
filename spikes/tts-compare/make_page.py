"""Writes out/tts-compare/index.html: one player per sample, grouped by model, Paige's reference first."""

import html
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import LINES, OUT, PAIGE_REF  # noqa: E402

GROUPS = [
    ("Paige (old reference)", "paige-ref", "The earlier reference clip (punkgoat + happy + forge lines)."),
    ("Kokoro-82M", "kokoro-", "Preset voices only: no cloning. 82M params, about 50x faster than real time."),
    ("Qwen3-TTS 1.7B CustomVoice", "qwen-custom-", "Preset speakers; \"styled\" adds a cheerful-teacher instruction. Ryan and Aiden are the native English ones."),
    ("Qwen3-TTS 1.7B Base (cloning)", "qwen-base-", "Clones Paige from her reference clip and its transcript."),
    ("KittenTTS 2", "kitten-", "1.7B. Presets (Bella, Luna, Rosie female; Jasper, Bruno, Hugo, Victor male) and clones from the mono references "
     "(it clones from 5-30 s). Has [emotion] tags and a <pause> event. Free commercial use under USD 1M revenue."),
    ("Higgs TTS 3", "higgs-", "4B, run 8-bit to fit 8 GB. Clones from the mono references; \"styled\" adds <|emotion:enthusiasm|> "
     "<|prosody:expressive_high|>. Has real pause tokens. Research/non-commercial license with a free creator grant (credit Boson AI)."),
    ("Fully tagged (one take)", "tagged", "Every tag that suits a cheerful explainer, per sentence (scripts below). Found: '...' next to Higgs tags "
     "makes it stop early or loop (removed); even without it Higgs Dynamo stopped early or looped on 2 of 4 seeds (seed 2 kept), so "
     "tagged takes need a completeness check and retry. Kitten reads some events aloud (<laugh> as 'laugh', Dynamo's <gasp> as 'gasp')."),
    ("One take, cut into lines", "onetake", "All four lines voiced in ONE take (mono references), then cut at word-timestamp line boundaries "
     "and rejoined with the usual gaps (\"-cut\"). Compare with the line-by-line clones above for cohesion."),
]

shutil.copy(PAIGE_REF, OUT / "paige-ref.wav")
wavs = sorted(p.name for p in OUT.glob("*.wav"))
parts = []
for title, prefix, note in GROUPS:
    if prefix == "tagged":
        rows = [w for w in wavs if "tagged" in w]
    elif prefix == "onetake":
        rows = [w for w in wavs if "onetake" in w and "tagged" not in w]
    else:
        rows = [w for w in wavs if w.startswith(prefix) and "onetake" not in w]
    if not rows:
        continue
    items = "".join(f'<div class="row"><span>{html.escape((w[:-4].removeprefix(prefix) if prefix not in ("onetake", "tagged") else w[:-4]) or w[:-4])}</span>'
                    f'<audio controls preload="none" src="{w}"></audio></div>' for w in rows)
    if prefix == "tagged":
        scripts = json.loads((Path(__file__).parent / "tagged.json").read_text())
        items += "".join(f'<p class="t" style="margin-left:0"><b>{k}:</b> {html.escape(" ".join(v))}</p>'
                         for k, v in scripts.items() if k[0] != "_")
    parts.append(f"<section><h2>{title}</h2><p>{html.escape(note)}</p>{items}</section>")
refs = "".join(f'<div class="row"><span>{w.stem}</span><audio controls preload="none" src="refs/{w.name}"></audio></div>'
               f'<p class="t">{html.escape(w.with_suffix(".txt").read_text())}</p>' for w in sorted((OUT / "refs").glob("*.wav")))
if refs:
    parts.insert(1, f"<section><h2>New references (conversation lines)</h2><p>Conversation lines picked by ear, with exact transcripts. Paige: all = six picks (44 s), mono = breakfast-book line, short = picks 3, 6, 17. Dynamo: all = eight picks (68 s), mono = the Patrons line, short = picks 1, 2.</p>{refs}</section>")
marks = "".join(f'<div class="row"><span>{w.stem}</span><audio controls preload="none" src="marks/{w.name}"></audio></div>'
                for w in sorted((OUT / "marks").glob("*.wav")))
if marks:
    parts.append("<section><h2>Line-end marks (one take, paige-mono)</h2><p>Each line end marked with a space, newline, blank line, "
                 "' ...', '—', ' —', or a model's pause tag before joining. Neither tokenizer has a pause token. Measured: Qwen ignores all marks (line-end pauses "
                 "~0.3 s, same as inside lines). Kitten's <pause> tag: line ends 0.93 -> 1.57 s. Higgs: 0.44 s -> 0.81 s with <|prosody:pause|>, 2.35 s with <|prosody:long_pause|>; inside-line pauses unchanged for both.</p>"
                 f"{marks}</section>")
lines = "".join(f"<li>{html.escape(t)}</li>" for t in LINES)
(OUT / "index.html").write_text(f"""<!doctype html><meta charset="utf-8"><title>TTS comparison</title>
<style>body{{background:#111;color:#ddd;font:15px system-ui;max-width:760px;margin:24px auto;padding:0 16px}}
h2{{margin:28px 0 4px;color:#fff}}p{{margin:0 0 10px;color:#999}}.row{{display:flex;align-items:center;gap:12px;margin:6px 0}}
.row span{{width:190px;flex:none}}audio{{flex:1}}ol{{color:#aaa}}.t{{font-size:13px;margin:0 0 8px 202px}}</style>
<h1>Narration voice trial</h1><p>Every sample reads the same four lines:</p><ol>{lines}</ol>{''.join(parts)}
<script>document.addEventListener('play',e=>document.querySelectorAll('audio').forEach(a=>a!==e.target&&a.pause()),true)</script>""")
print(OUT / "index.html")
