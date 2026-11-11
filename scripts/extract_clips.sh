#!/usr/bin/env bash
# Unpack every clip the film plays into numbered frames under video/build/clips/<name>/, which the renderer
# shows frame-accurately (see video/src/lib/clip.js):
#   video/assets/inhouse/*.mp4   product footage            → JPEG frames at the clip's own frame rate
#   video/assets/renders/*.mp4   Blender plates (30 fps)    → JPEG frames; a clip with a <name>-alpha.mp4
#                                                             matte becomes PNG frames with transparency
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
for src in "$ROOT"/video/assets/inhouse/*.mp4 "$ROOT"/video/assets/renders/*.mp4; do
  [ -f "$src" ] || continue
  name="$(basename "$src" .mp4)"
  case "$name" in *-alpha) continue ;; esac
  out="$ROOT/video/build/clips/$name"
  rm -rf "$out" && mkdir -p "$out"
  matte="$(dirname "$src")/$name-alpha.mp4"
  if [ -f "$matte" ]; then
    # the colour was stored over black (premultiplied): divide it back out by the matte
    ffmpeg -hide_banner -loglevel error -i "$src" -i "$matte" \
      -filter_complex "[0:v]format=gbrp[c];[1:v]format=gray[m];[c][m]alphamerge,unpremultiply=inplace=1,format=rgba" \
      -fps_mode passthrough -start_number 0 "$out/%04d.png"
  else
    ffmpeg -hide_banner -loglevel error -i "$src" -fps_mode passthrough -q:v 2 -start_number 0 "$out/%04d.jpg"
  fi
  echo "$name: $(ls "$out" | wc -l) frames"
done
