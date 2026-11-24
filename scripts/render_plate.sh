#!/usr/bin/env bash
# Two-stage Blender plate render, resumable at every step:
#   1. scripts/render_<script>.py with --exr: noisy scene-referred EXRs (+ denoising albedo/normal) on the GPU,
#      CHUNK frames per Blender process (a fresh process keeps peak memory flat on an 8 GB Mac)
#   2. scripts/denoise_frames.py: OIDN (accurate prefilter) + AgX in a separate process → 16-bit PNGs, after each chunk
# Frames already done are skipped in both stages, so a stopped render picks up where it left off.
#   scripts/render_plate.sh field tractor 200 --exposure -3.3 -- --res 1.0 --samples 512 --min-samples 64 --threshold 0.01
#   (script, shot, frame count; arguments before -- go to the denoise stage, after -- to the render script)
# Long renders: nohup caffeinate -dimsu scripts/render_plate.sh … > video/build/tractor.log 2>&1 &
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BLENDER="${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}"
CHUNK="${CHUNK:-2}"
SCRIPT="$1"; SHOT="$2"; NFR="$3"; shift 3
DEN=()
while [ $# -gt 0 ] && [ "$1" != "--" ]; do DEN+=("$1"); shift; done
[ "${1:-}" = "--" ] && shift
OUT="$ROOT/video/build/plates/$SHOT"
mkdir -p "$OUT/exr"
# the overlay export (video/src/shots/<shot>.js) once, then the frames
"$BLENDER" -b --factory-startup -P "$ROOT/scripts/render_$SCRIPT.py" -- --shot "$SHOT" --export-only --out "$OUT" "$@" > /dev/null
todo=()
for ((f = 0; f < NFR; f++)); do
  n=$(printf %04d "$f")
  [ -f "$OUT/$n.png" ] || [ -f "$OUT/exr/$n.exr" ] || todo+=("$f")
done
echo "$SHOT: ${#todo[@]} of $NFR frames to render"
for ((i = 0; i < ${#todo[@]}; i += CHUNK)); do
  chunk=("${todo[@]:i:CHUNK}")
  # Metal occasionally aborts while loading its kernel cache (an NSException before rendering starts):
  # retry the chunk, rendering only the frames it is still missing
  for attempt in 1 2 3; do
    missing=()
    for f in "${chunk[@]}"; do [ -f "$OUT/exr/$(printf %04d "$f").exr" ] || missing+=("$f"); done
    [ ${#missing[@]} -eq 0 ] && break
    [ "$attempt" -gt 1 ] && echo "retrying frames ${missing[*]} (attempt $attempt)"
    "$BLENDER" -b --factory-startup -P "$ROOT/scripts/render_$SCRIPT.py" -- --shot "$SHOT" --device "${DEVICE:-METAL}" --exr --no-export \
      --out "$OUT" --frames "${missing[@]}" "$@" 2>&1 | grep -E "^frame|Error|Traceback|rror:|Terminating" || true
  done
  # denoise the chunk right away (its own process, after the render's has exited): finished frames can be
  # reviewed while the rest render
  "$BLENDER" -b --factory-startup -P "$ROOT/scripts/denoise_frames.py" -- "$OUT" --frames "${chunk[@]}" ${DEN[@]+"${DEN[@]}"} 2>&1 | grep -E "denoised|rror" || true
done
"$BLENDER" -b --factory-startup -P "$ROOT/scripts/denoise_frames.py" -- "$OUT" ${DEN[@]+"${DEN[@]}"} 2>&1 | grep -E "denoised|frames to|rror" || true
echo "done: $(ls "$OUT"/[0-9]*.png 2>/dev/null | wc -l | tr -d ' ') of $NFR frames in $OUT"
