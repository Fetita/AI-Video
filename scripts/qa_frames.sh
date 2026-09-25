#!/usr/bin/env bash
# Sample the delivery video every N seconds into contact sheets for review.
set -euo pipefail
VIDEO="${1:-out/eagerworks-ai-studio.mp4}"; OUTDIR="${2:-/tmp/qa}"; STEP="${3:-1}"
mkdir -p "$OUTDIR/frames"; rm -f "$OUTDIR"/frames/*.png
ffmpeg -hide_banner -loglevel error -i "$VIDEO" -vf "fps=1/$STEP,scale=480:-1" "$OUTDIR/frames/f_%04d.png"
ls "$OUTDIR"/frames/*.png | split -l 32 - "$OUTDIR/chunk_"
i=0; for c in "$OUTDIR"/chunk_*; do python3 "$(dirname "$0")/contact_sheet.py" "$OUTDIR/sheet_$i.png" 8 240 $(cat "$c") >/dev/null; i=$((i+1)); rm "$c"; done
ls "$OUTDIR"/sheet_*.png
