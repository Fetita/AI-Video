# Eagerworks AI Studio: promotional film

A premium B2B film positioning **Eagerworks AI Studio** as the partner that turns
AI capabilities into real products, workflows and measurable outcomes.

**Hero cut:** [`out/eagerworks-ai-studio-linkedin.mp4`](out/eagerworks-ai-studio-linkedin.mp4)
(1:32, 1920×1080, 30 fps, H.264 + AAC, −14 LUFS, burned-in captions; poster frame:
[`…-poster.jpg`](out/eagerworks-ai-studio-linkedin-poster.jpg)). The LinkedIn overview, rebuilt with the cinematic
pipeline described below: 3D shots, motion blur, a moving camera and a finishing grade.
**Full film:** [`out/eagerworks-ai-studio.mp4`](out/eagerworks-ai-studio.mp4) (3:08, same format, no captions), also on the
cinematic pipeline, with its own scene changes moved to camera fly-throughs (treatment §13) and every client case
shot in 3D: the tractor and its top-down feed, the pumpkin packing line, the story board and the tracking bench (treatment §14).
**Themed LinkedIn cuts** (same pipeline and 3D shots as the full film):
[`linkedin-cv`](out/eagerworks-ai-studio-linkedin-cv.mp4) (1:54, every computer-vision case) ·
[`linkedin-genai`](out/eagerworks-ai-studio-linkedin-genai.mp4) (1:47, generative and document AI)
**Creative treatment** (narrative, storyboard, timings, VO script, on-screen text, visual & sound direction, reference mapping):
[`docs/creative-treatment.md`](docs/creative-treatment.md)

Everything in the film is generated from code in this repository. Visuals are deterministic
HTML/Canvas/SVG scenes rendered frame by frame in headless Chromium. The voiceover comes from a
local open-weight TTS model, and the music and sound design are synthesized with numpy.
The photoreal material (the marketplace's location photos, the robot arm, the mannequin room, the 3D logo, and the
field, packing-line, story-board and tracking shots) is rendered with Blender Cycles from procedural scenes built in
Python, with procedural materials only (no scanned textures or HDRIs). No stock media is used,
and no client screenshots, names, logos or data appear. The external assets are the supplied Eagerworks logo,
the story character sheets, and a clip of Eagerworks' own packing-line vision product (`video/assets/inhouse/`).

### What the hero cut adds

- **3D shots rendered in Blender.** A photoreal robot arm picks and places a part while the camera dollies around
  it (`scripts/render_robot.py`); the film's overlays (trajectory, joint pose, telemetry) are drawn on top with the
  same camera and kinematics, so they sit exactly on the render. The finale is a logo sting: the Eagerworks icon as
  black glass with violet light tubes that turns white-hot and becomes the flat lockup (`scripts/render_logo.py`).
  The face-detection beat plays over a rendered room of display mannequins (`scripts/render_room.py`).
- **Every client case in 3D.** The field case opens on a tractor at golden hour driving its rows, its boom camera
  lighting the lettuce, and pushes into that camera's top-down feed (`scripts/render_field.py`). The packing line is a
  packhouse conveyor of pumpkins seen from the line camera (`scripts/render_packline.py`). The story case is a varnished
  walnut board where beech pieces printed with the characters drop into their slots (`scripts/render_board.py`), and the
  3D-tracking beat is a real workbench with the tracked head camera and wrist bands (`scripts/render_tracking.py`).
  Each shot is built from the film's own models (`video/tools/dump_shot_inputs.mjs` → `inputs.json`) and exports, per
  frame, where its objects land on screen (`video/src/shots/*.js`), so the film's boxes, IDs, trails, reticles and
  relation lines sit on the rendered plants, pumpkins and pieces (`video/src/lib/shot.js`).
- **Motion blur.** Every frame is the linear-light average of several sub-frames (`render.mjs --mb 6`, a 180° shutter).
- **A scene camera.** Each scene pushes in slowly; scene changes are fly-throughs (the outgoing scene rushes past,
  the next one settles from further back) with a band of light crossing the frame (`engine.js`, `lib/atmosphere.js`).
- **Atmosphere.** Two slow brand-coloured lights, drifting dust at several depths and a dithered gradient replace the flat background.
- **A finishing grade** in the delivery encode: glow, a slightly violet halation, a contrast curve and grain (`scripts/grade.filter`).
- **Captions** whose words brighten as they are spoken, on a blurred glass plate.
- A bigger hook (every input plays full-frame with its own push-in) and sound design for the new moments.

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
  index.html, src/      the film: engine.js (seek(t) runtime + scene camera), scenes/*.js, lib/*.js
  render.mjs            Playwright renderer (stills for review, or parallel video render with motion blur)
  snap.mjs              screenshot helper for debug pages
  tools/dump_shot_inputs.mjs  the film's models (plants, pumpkins, board, tracking poses) → build/shots/inputs.json for Blender
  src/shots/*.js        generated by the Blender scripts: per-frame screen positions the overlays follow
  extract_characters.mjs  cuts the supplied character sheets into one PNG per character
  assets/               fonts (Google Fonts, OFL), logo, characters, location photos, recap thumbnails, in-house product clips,
                        renders/ (the packed Blender plates)
scripts/
  render_locations.py   procedural Blender (Cycles) scenes → video/assets/places/*.jpg
  render_robot.py       the robot-arm shot (180 frames) → video/build/plates/robot/
  render_logo.py        the 3D logo sting (90 frames, transparent) → video/build/plates/logo/
  render_room.py        the mannequin room still → video/assets/renders/room.jpg
  blender_common.py     shared bpy helpers for the shots below: materials, physical sky, haze, camera, keying,
                        Cycles settings, the resumable frame loop, and the per-frame overlay export
  render_field.py       --shot tractor (200 frames) and --shot feed (120 frames, orthographic) → video/build/plates/
  render_plate.sh       two-stage plate render on the Mac's GPU (Metal): noisy EXRs, then denoise_frames.py; resumable
  denoise_frames.py     stage 2: OIDN (accurate prefilter) + AgX/exposure in its own process → 16-bit PNG frames
  render_packline.py    the packing line (230 frames) → video/build/plates/packline/
  render_board.py       the story board and pieces (214 frames) → video/build/plates/board/
  render_tracking.py    the camera + wrist tracking set (60 frames) → video/build/plates/tracking/
  pack_plates.sh        Blender frames → video/assets/renders/*.mp4 (the files that are committed)
  extract_clips.sh      product clip + Blender plates → numbered frames in video/build/clips/ (needed before rendering)
  make_recap.sh         film frames → the finale's recap-wall thumbnails
  grade.filter          the finishing grade (ffmpeg filter graph) used by finalize.sh
  finalize.sh           delivery encode (grade, grain, H.264 High, AAC, faststart); glow/halation fade out while the
                        bright 3D plates are on screen (windows from video/tools/grade_windows.mjs <cut>)
  contact_sheet.py      stills → review sheet
docs/creative-treatment.md
out/                    delivery files (one per cut) and the hero cut's poster frame
```

## Rebuild

Requirements: Node 22 with Playwright 1.56 and Chromium, Python with `numpy scipy soundfile pyloudnorm kokoro-onnx`, ffmpeg, and (for the Blender renders only) a Python 3.11 venv with `bpy==5.0.1`.
Kokoro model files (`kokoro-v1.0.onnx`, `voices-v1.0.bin`) come from the
[kokoro-onnx release](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0); set `KOKORO_DIR` to their folder.

```bash
# 1. voiceover + timeline (only when the script changes)
cd audio && python3 tts.py && python3 build_timeline.py

# 2. assets (only when they change): Blender renders (`pip install bpy==5.0.1` in a Python 3.11 venv), characters;
#    then unpack the clips and plates (always needed before rendering) and refresh the recap wall
python3 ../scripts/render_locations.py      # slow: a few minutes per photo on CPU
python3 ../scripts/render_robot.py --samples 28 --res 0.6667 --exposure -0.25   # ≈1 h on 4 cores
python3 ../scripts/render_logo.py --samples 36 --res 0.75                       # ≈30 min
python3 ../scripts/render_room.py
node ../video/tools/dump_shot_inputs.mjs                                        # inputs for the four shots below
# the field plates: Blender.app (5.x) on the Apple GPU, two-stage (see scripts/render_plate.sh), 1080p native;
#   long: run detached, e.g.  nohup caffeinate -dimsu ../scripts/render_plate.sh … > build/tractor.log 2>&1 &
../scripts/render_plate.sh field tractor 200 --exposure -3.3 -- --res 1.0 --samples 256 --min-samples 64 --threshold 0.01   # ≈40 h on an M1 (≈11–17 min/frame)
../scripts/render_plate.sh field feed 120 --exposure -3.3 -- --res 1.0 --samples 256 --min-samples 64 --threshold 0.01      # ≈8 h
python3 ../scripts/render_packline.py --res 0.5 --samples 10                    # ≈1 h
python3 ../scripts/render_board.py --res 0.45 --samples 10                      # ≈45 min
python3 ../scripts/render_tracking.py --res 0.5 --samples 10                    # ≈10 min
../scripts/pack_plates.sh
cd ../video && npm install && node extract_characters.mjs && ../scripts/extract_clips.sh && ../scripts/make_recap.sh

# 3. picture (--mb 6 = motion blur from 6 sub-frames per frame, ≈6× the render time; omit it for a fast draft)
#    review stills with:  node render.mjs --stills 12.5,30 [--only search]
#    if this Playwright version has no browser download, point PW_CHROMIUM at a Chromium binary
node render.mjs --video --workers 4 --mb 6 --out build/frames.mkv

# 4. sound
cd ../audio && python3 music.py && python3 sfx.py && python3 mix.py

# 5. delivery file
cd .. && scripts/finalize.sh
```

Editing a scene is safe: every animation is keyed to VO clause timestamps from `video/src/timeline.js`,
so changing the narration and re-running steps 1–5 keeps picture, music and effects in sync.

### Alternate cuts (LinkedIn)

A cut is a second narration script, `audio/vo_script.<cut>.json`, listing the scenes it keeps (in order) and their lines.
It can also burn in captions (`"captions": true`, with `"caption": false` on lines whose words are already on screen)
and renumber the chapters it keeps (`"chapters"`). Every step takes `CUT=<cut>` and writes `*-<cut>` files next to the
full film's, so the two never overwrite each other:

```bash
cd audio && export CUT=linkedin
python3 tts.py && python3 build_timeline.py          # → build/vo-linkedin/, video/src/timeline-linkedin.js
python3 music.py && python3 sfx.py && python3 mix.py # → build/mix-linkedin.wav
cd ../video && node render.mjs --video --workers 4 --mb 6 --query cut=linkedin --out build/frames-linkedin.mkv
cd .. && scripts/finalize.sh video/build/frames-linkedin.mkv audio/build/mix-linkedin.wav out/eagerworks-ai-studio-linkedin.mp4
```

Review stills for a cut with `node render.mjs --stills 12.5 --query cut=linkedin`. The same steps build
`linkedin-cv` and `linkedin-genai` (swap the cut name).
