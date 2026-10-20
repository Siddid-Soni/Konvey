#!/usr/bin/env bash
# Render spike A. ./render.sh preview  (480p)  |  ./render.sh  (1080p)
set -euo pipefail
cd "$(dirname "$0")"
if [[ "${1:-}" == preview ]]; then
  args=(-r 854x480 --file_name preview)
else
  args=(--hd --file_name cube-shadow)
fi
uv run --project ../.. --group render --group layout \
  manimgl cube_shadow.py CubeShadow -w --video_dir out "${args[@]}"
