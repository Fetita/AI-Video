#!/usr/bin/env bash
# Pack the Blender plates (video/build/plates/<name>/*.png, from scripts/render_*.py) into the compact files that are
# committed under video/assets/renders/, at the size the film shows them (video/src/lib/shot.js PLATES):
#   robot, tractor, board, tracking   opaque, 1920×1080
#   feed, packline                    opaque, 1620×826 (they play inside the feed frame)
#   logo                              logo.mp4 + logo-alpha.mp4: colour and matte of the transparent logo sting
# scripts/extract_clips.sh turns them back into numbered frames for the renderer.
#   scripts/pack_plates.sh                 pack every plate that has frames
#   scripts/pack_plates.sh feed packline   pack only these
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
P="$ROOT/video/build/plates"; OUT="$ROOT/video/assets/renders"
mkdir -p "$OUT"
X264=(-c:v libx264 -preset slow -crf 14 -pix_fmt yuv420p -color_primaries bt709 -color_trc bt709 -colorspace bt709 -movflags +faststart)
declare -A SIZE=([robot]=1920:1080 [tractor]=1920:1080 [board]=1920:1080 [tracking]=1920:1080 [feed]=1620:826 [packline]=1620:826)
NAMES=("$@"); [ ${#NAMES[@]} -eq 0 ] && NAMES=(robot logo tractor feed packline board tracking)
for name in "${NAMES[@]}"; do
  [ -d "$P/$name" ] || { echo "skip $name (no frames)"; continue; }
  if [ "$name" = logo ]; then
    # straight-alpha PNGs → colour (unpremultiplied, bled over black) and matte
    ffmpeg -hide_banner -loglevel error -y -framerate 30 -i "$P/logo/%04d.png" \
      -filter_complex "[0:v]scale=1920:1080:flags=lanczos,format=rgba,split[a][b];[a]alphaextract[m];color=black:s=1920x1080:r=30[k];[k][b]overlay=shortest=1:format=auto[c]" \
      -map "[c]" "${X264[@]}" "$OUT/logo.mp4" -map "[m]" "${X264[@]}" "$OUT/logo-alpha.mp4"
  else
    ffmpeg -hide_banner -loglevel error -y -framerate 30 -i "$P/$name/%04d.png" \
      -vf "scale=${SIZE[$name]}:flags=lanczos,unsharp=5:5:0.35:5:5:0.0" "${X264[@]}" "$OUT/$name.mp4"
  fi
  echo "$name: $(ls "$P/$name" | wc -l) frames"
done
ls -lh "$OUT"
