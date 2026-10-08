#!/usr/bin/env bash
# Regenerate the finale's recap-wall thumbnails from the film itself (run after visual changes,
# before the final render): each tile is a frame of its chapter, scaled to 768×432.
# Times are offsets from the start of the tile's scene, so reordering scenes keeps them valid.
set -euo pipefail
cd "$(dirname "$0")/../video"
TILES=(
  hands:vision:6.05 faces:vision:7.65 tracking3d:vision:8.85 dataset:vision:10.95 benchmark:vision:13.65 robot:vision:16.05
  field:agri:9.05 conveyor:agri:16.65
  parse:search:7.25 search:search:8.75 recommend:search:18.75
  physical:story:10.45 generative:story:14.05
  documents:docs:8.55 readiness:docs:13.85
)
starts=$(node -e "import('./src/timeline.js').then(({default: t}) => console.log(t.scenes.map((s) => s.id + '=' + s.start).join(' ')))")
abs=()
for tile in "${TILES[@]}"; do
  IFS=: read -r name scene off <<<"$tile"
  start=$(tr ' ' '\n' <<<"$starts" | sed -n "s/^$scene=//p")
  abs+=("$name:$(awk -v a="$start" -v b="$off" 'BEGIN { printf "%.2f", a + b }')")
done
times=$(printf '%s\n' "${abs[@]}" | cut -d: -f2 | paste -sd, -)
rm -rf build/recap
node render.mjs --stills "$times" --outdir build/recap
for tile in "${abs[@]}"; do
  name=${tile%%:*}; t=${tile##*:}
  src=build/recap/$(printf 'still_%07.2f.png' "$t")
  ffmpeg -loglevel error -y -i "$src" -vf scale=768:432:flags=lanczos -q:v 4 "assets/recap/$name.jpg"
done
echo "recap thumbnails updated"
