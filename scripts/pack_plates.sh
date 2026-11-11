#!/usr/bin/env bash
# Pack the Blender plates (video/build/plates/<name>/*.png, from render_robot.py / render_logo.py) into the
# compact files that are committed under video/assets/renders/:
#   robot.mp4                 opaque plate, upscaled to 1920×1080
#   logo.mp4 + logo-alpha.mp4 colour and matte of the transparent logo sting
# scripts/extract_clips.sh turns them back into numbered frames for the renderer.
#   scripts/pack_plates.sh [robot|logo]   pack only one of them
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
P="$ROOT/video/build/plates"; OUT="$ROOT/video/assets/renders"; ONLY="${1:-all}"
mkdir -p "$OUT"
X264=(-c:v libx264 -preset slow -crf 14 -pix_fmt yuv420p -color_primaries bt709 -color_trc bt709 -colorspace bt709 -movflags +faststart)
if [ -d "$P/robot" ] && [ "$ONLY" != logo ]; then
  ffmpeg -hide_banner -loglevel error -y -framerate 30 -i "$P/robot/%04d.png" \
    -vf "scale=1920:1080:flags=lanczos,unsharp=5:5:0.35:5:5:0.0" "${X264[@]}" "$OUT/robot.mp4"
fi
if [ -d "$P/logo" ] && [ "$ONLY" != robot ]; then
  # straight-alpha PNGs → colour (unpremultiplied, bled over black) and matte
  ffmpeg -hide_banner -loglevel error -y -framerate 30 -i "$P/logo/%04d.png" \
    -filter_complex "[0:v]scale=1920:1080:flags=lanczos,format=rgba,split[a][b];[a]alphaextract[m];color=black:s=1920x1080:r=30[k];[k][b]overlay=shortest=1:format=auto[c]" \
    -map "[c]" "${X264[@]}" "$OUT/logo.mp4" -map "[m]" "${X264[@]}" "$OUT/logo-alpha.mp4"
fi
ls -lh "$OUT"
