#!/usr/bin/env bash
# Unpack the in-house product clips (video/assets/inhouse/*.mp4) into numbered JPEG frames
# under video/build/clips/<name>/, which the renderer shows frame-accurately (see video/src/lib/clip.js).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
for src in "$ROOT"/video/assets/inhouse/*.mp4; do
  name="$(basename "$src" .mp4)"
  out="$ROOT/video/build/clips/$name"
  rm -rf "$out" && mkdir -p "$out"
  ffmpeg -hide_banner -loglevel error -i "$src" -vf fps=30 -q:v 2 -start_number 0 "$out/%04d.jpg"
  echo "$name: $(ls "$out" | wc -l) frames"
done
