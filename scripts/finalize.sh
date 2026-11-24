#!/usr/bin/env bash
# Delivery encode: lossless-ish frame intermediate + master mix → H.264/AAC MP4.
# The picture goes through the film's finishing grade first (scripts/grade.filter): a tight glow and a
# wider, slightly violet halation around the highlights, a gentle contrast curve, and a fine temporal
# grain that also hides gradient banding on the dark backgrounds.
#   GRADE=0 scripts/finalize.sh …   keeps only the grain (the look of the earlier cuts)
# The glow and halation are for the dark interface scenes: while the bright 3D plates are on screen (tractor,
# feed, packline, board) they fade out and back with the plates (video/tools/grade_windows.mjs computes when,
# from the cut's timeline and the plates' envelopes, and drives the two blends through an ffmpeg sendcmd script).
# The curve and the grain stay everywhere.
#   CUT=linkedin-cv scripts/finalize.sh …     the cut whose timeline the windows come from (default: full film)
# MIX may be a WAV (encoded to AAC) or an already-encoded .m4a/.aac/.mp4 soundtrack (stream-copied).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRAMES="${1:-$ROOT/video/build/frames.mkv}"
MIX="${2:-$ROOT/audio/build/mix.wav}"
OUT="${3:-$ROOT/out/eagerworks-ai-studio.mp4}"
CRF="${CRF:-20}"
if [ "${GRADE:-1}" = "0" ]; then
  FILTER="[0:v]noise=alls=2:allf=t+u,format=yuv420p[v]"
else
  FILTER="$(tr -d '\n' < "$ROOT/scripts/grade.filter")"
  CMDS="$(mktemp -t gradecmds).txt"
  (cd "$ROOT/video" && node tools/grade_windows.mjs ${CUT:-} --cmds "$CMDS")
  FILTER="[0:v]sendcmd=f=${CMDS},${FILTER#\[0:v\]}"
fi
case "$MIX" in
  *.m4a|*.aac|*.mp4) AUDIO=(-c:a copy) ;;
  *) AUDIO=(-c:a aac -b:a 256k -ar 48000) ;;
esac
mkdir -p "$(dirname "$OUT")"
ffmpeg -hide_banner -loglevel error -y -i "$FRAMES" -i "$MIX" \
  -filter_complex "$FILTER" \
  -map "[v]" -map 1:a:0 \
  -c:v libx264 -preset slow -crf "$CRF" -profile:v high -level 4.2 -pix_fmt yuv420p \
  -x264-params "keyint=60:min-keyint=30:aq-mode=3" \
  -color_primaries bt709 -color_trc bt709 -colorspace bt709 \
  "${AUDIO[@]}" \
  -movflags +faststart -shortest "$OUT"
ls -lh "$OUT"
