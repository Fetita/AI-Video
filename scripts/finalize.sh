#!/usr/bin/env bash
# Delivery encode: lossless-ish frame intermediate + master mix → H.264/AAC MP4.
# Adds a very fine temporal grain (hides gradient banding on dark backgrounds).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRAMES="${1:-$ROOT/video/build/frames.mkv}"
MIX="${2:-$ROOT/audio/build/mix.wav}"
OUT="${3:-$ROOT/out/eagerworks-ai-studio.mp4}"
CRF="${CRF:-18}"
mkdir -p "$(dirname "$OUT")"
ffmpeg -hide_banner -loglevel error -y -i "$FRAMES" -i "$MIX" \
  -filter_complex "[0:v]noise=alls=2:allf=t+u,format=yuv420p[v]" \
  -map "[v]" -map 1:a \
  -c:v libx264 -preset slow -crf "$CRF" -profile:v high -level 4.2 -pix_fmt yuv420p \
  -x264-params "keyint=60:min-keyint=30:aq-mode=3" \
  -color_primaries bt709 -color_trc bt709 -colorspace bt709 \
  -c:a aac -b:a 256k -ar 48000 \
  -movflags +faststart -shortest "$OUT"
ls -lh "$OUT"
