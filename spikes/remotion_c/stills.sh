#!/usr/bin/env bash
# Render one still per beat (or the frames given as args) into out/stills/ for visual checks.
set -euo pipefail
cd "$(dirname "$0")"
npx remotion bundle src/index.ts --out-dir=build >/dev/null
frames=${*:-"60 250 420 640 700 760 850 900 1010 1180 1270 1330 1420 1490 1570 1640"}
for f in $frames; do
  npx remotion still build CubeShadow "out/stills/f$f.png" --frame="$f" --browser-executable=/usr/bin/chromium --gl=angle --log=error
done
