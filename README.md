# Eagerworks AI Studio: promotional film

A 2:23 premium B2B film positioning **Eagerworks AI Studio** as the partner that turns
AI capabilities into real products, workflows and measurable outcomes.

**Deliverable:** [`out/eagerworks-ai-studio.mp4`](out/eagerworks-ai-studio.mp4) (1920×1080, 30 fps, H.264 + AAC, −14 LUFS)
**Creative treatment** (narrative, storyboard, timings, VO script, on-screen text, visual & sound direction, reference mapping):
[`docs/creative-treatment.md`](docs/creative-treatment.md)

Everything in the film is generated from code in this repository. Visuals are deterministic
HTML/Canvas/SVG scenes rendered frame by frame in headless Chromium. The voiceover comes from a
local open-weight TTS model, and the music and sound design are synthesized with numpy.
No stock media is used, and no client screenshots, names, logos or data appear. The Eagerworks logo
(vectorized from the supplied PNG) is the only external asset.

## Structure

```
audio/
  vo_script.json        narration (text + pronunciation spellings, per-scene pacing)
  tts.py                Kokoro TTS → build/vo/*.wav + clause timings
  build_timeline.py     VO durations → master timeline (scene cuts snapped to the 100 BPM grid)
  synth.py              DSP toolkit (oscillators, filters, drums, reverb, limiter)
  music.py              original score, arranged to the edit
  sfx.py                sound design cued to visual events
  mix.py                VO chain, ducking, master → build/mix.wav
  analyze.py            loudness / spectrogram QA plots
video/
  index.html, src/      the film: engine.js (seek(t) runtime), scenes/*.js, lib/*.js
  render.mjs            Playwright renderer (stills for review, or parallel video render)
  snap.mjs              screenshot helper for debug pages
  assets/               fonts (Google Fonts, OFL), vectorized logo, recap thumbnails
scripts/
  finalize.sh           delivery encode (grain, H.264 High, AAC, faststart)
  contact_sheet.py      stills → review sheet
docs/creative-treatment.md
out/eagerworks-ai-studio.mp4
```

## Rebuild

Requirements: Node 22 with Playwright 1.56 and Chromium, Python 3.11 with `numpy scipy soundfile pyloudnorm kokoro-onnx`, and ffmpeg.
Kokoro model files (`kokoro-v1.0.onnx`, `voices-v1.0.bin`) come from the
[kokoro-onnx release](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0); set `KOKORO_DIR` to their folder.

```bash
# 1. voiceover + timeline (only when the script changes)
cd audio && python3 tts.py && python3 build_timeline.py

# 2. picture (≈7 min on 4 cores); review stills with:  node render.mjs --stills 12.5,30 [--only search]
cd ../video && npm install && node render.mjs --video --workers 4 --out build/frames.mkv

# 3. sound
cd ../audio && python3 music.py && python3 sfx.py && python3 mix.py

# 4. delivery file
cd .. && scripts/finalize.sh
```

Editing a scene is safe: every animation is keyed to VO clause timestamps from `video/src/timeline.js`,
so changing the narration and re-running steps 1–4 keeps picture, music and effects in sync.
