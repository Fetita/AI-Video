#!/usr/bin/env bash
# Regenerate the finale's recap-wall thumbnails from the film itself (run after visual changes,
# before the final render): each tile is a frame of its chapter, scaled to 768×432.
set -euo pipefail
cd "$(dirname "$0")/../video"
TILES=(
  parse:40.85 search:42.35 recommend:52.35 physical:64.45 generative:68.05
  hands:79.25 faces:80.85 tracking3d:82.05 dataset:84.15 benchmark:86.85
  robot:89.25 field:101.45 conveyor:109.05 documents:120.15 readiness:125.45
)
times=$(printf '%s\n' "${TILES[@]}" | cut -d: -f2 | paste -sd, -)
rm -rf build/recap
node render.mjs --stills "$times" --outdir build/recap
for tile in "${TILES[@]}"; do
  name=${tile%%:*}; t=${tile##*:}
  src=build/recap/$(printf 'still_%07.2f.png' "$t")
  ffmpeg -loglevel error -y -i "$src" -vf scale=768:432:flags=lanczos -q:v 4 "assets/recap/$name.jpg"
done
echo "recap thumbnails updated"
