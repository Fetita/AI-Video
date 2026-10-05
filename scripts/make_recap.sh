#!/usr/bin/env bash
# Regenerate the finale's recap-wall thumbnails from the film itself (run after visual changes,
# before the final render): each tile is a frame of its chapter, scaled to 768×432.
set -euo pipefail
cd "$(dirname "$0")/../video"
TILES=(
  parse:26.45 search:27.95 recommend:37.95 physical:50.05 generative:53.65
  hands:64.85 faces:66.45 tracking3d:67.65 dataset:69.75 benchmark:72.45
  robot:74.85 field:87.05 conveyor:94.65 documents:105.75 readiness:111.05
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
