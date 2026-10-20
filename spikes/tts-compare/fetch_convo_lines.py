"""Downloads one hero's conversation lines (more natural than pings/select lines) with exact transcripts.

Transcripts and file names: deadlock.vlviewer.com/characters/<hero>.json and its conversations.
Audio and durations: deadlock.wiki (same file names, capitalised). Writes out/voice-lines/<hero>/
with the mp3s and lines.json.  Usage: fetch_convo_lines.py paige dynamo
"""

import json
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import ROOT  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130 Safari/537.36"}
VL = "https://deadlock.vlviewer.com"


def get(url, raw=False):
    with urllib.request.urlopen(urllib.request.Request(url, headers={**UA, "Referer": "https://deadlock.wiki/"}), timeout=60) as r:
        return r.read() if raw else json.load(r)


def wiki_name(filename):
    base = filename.split("/")[-1]
    return base[0].upper() + base[1:]


for hero in sys.argv[1:]:
    out = ROOT / "out" / "voice-lines" / hero
    out.mkdir(parents=True, exist_ok=True)
    char = get(f"{VL}/characters/{hero}.json")
    rows = {}
    for convo in char["conversations"]:
        lines = get(VL + convo["jsonPath"])["lines"]
        for i, line in enumerate(lines):
            if line["speakerKey"] == hero and line["filename"] not in rows:
                prev = lines[i - 1]["text"] if i else ""
                rows[line["filename"]] = {"file": wiki_name(line["filename"]), "text": line["text"],
                                          "convo": convo["conversationId"], "after": prev}
        time.sleep(0.1)
    rows = list(rows.values())
    for i in range(0, len(rows), 50):
        chunk = rows[i:i + 50]
        q = urllib.parse.urlencode({"action": "query", "prop": "imageinfo", "iiprop": "url", "format": "json",
                                    "titles": "|".join("File:" + r["file"] for r in chunk)})
        pages = get("https://deadlock.wiki/api.php?" + q)["query"]["pages"].values()
        urls = {p["title"].replace(" ", "_"): p.get("imageinfo", [{}])[0].get("url") for p in pages}
        for r in chunk:
            r["url"] = urls.get("File:" + r["file"])
        time.sleep(0.3)
    rows = [r for r in rows if r["url"]]

    def fetch(r):
        path = out / r["file"]
        if not path.exists():
            path.write_bytes(get(r["url"], raw=True))

    with ThreadPoolExecutor(4) as ex:
        list(ex.map(fetch, rows))
    (out / "lines.json").write_text(json.dumps(rows, indent=1))
    print(f"{hero}: {len(rows)} conversation lines -> {out}")
