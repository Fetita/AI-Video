// Writes video/build/shots/inputs.json: everything the Blender shots (scripts/render_*.py) need from the film's
// own JS models, so the 3D scenes are built from the same data the overlays are drawn from:
//   feed      the crop field: every plant from plantAt() (gaps, off-row offsets, jitter, size), scroll speed, layout
//   packline  the pumpkins' spawn table and lanes (scenes/agri.js PACK), relative to the "a3" cue
//   board     the story board's slots, piece size and drop times (scenes/story.js BOARD)
//   tracking  per plate frame: the orbit camera, the head-camera pose and both wrists (scenes/vision.js TRACK)
// Run from anywhere:  node video/tools/dump_shot_inputs.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

globalThis.location = { search: '' };           // engine.js reads ?cut= at import; the full film's timeline
const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const { TIMELINE, FPS } = await import('../src/engine.js');
const field = await import('../src/lib/field.js');
const { PLATES } = await import('../src/lib/shot.js');
const { PACK } = await import('../src/lib/pack.js');
const { BOARD } = await import('../src/lib/board.js');
const { TRACK } = await import('../src/lib/tracking.js');

const scene = (id) => TIMELINE.scenes.find((s) => s.id === id);
const cue = (id, seg = 0) => { const l = TIMELINE.lines[id]; return l.segs[seg][0] - scene(l.scene).start; };

// ---- crop field
const plants = [];
for (let r = 0; r < field.ROWS; r++) for (let k = -2; k <= 34; k++) { const p = field.plantAt(r, k); plants.push({ r, k, ...p }); }

// ---- tracking: per plate frame, at the quantised time the plate shows
const tr = PLATES.tracking;
const trCue = { cTrk: cue('v2', 2), cDs: cue('v2', 3) };
const trFrames = [];
for (let i = 0; i < tr.frames; i++) trFrames.push(TRACK.pose(tr.t0(trCue) + i / FPS, trCue));

const out = {
  fps: FPS,
  plates: Object.fromEntries(Object.entries(PLATES).map(([k, v]) => [k, { frames: v.frames, w: v.w, h: v.h }])),
  tractor: { t0: PLATES.tractor.t0({}), cCam: cue('a1', 1), cData: cue('a1', 2), cTr: cue('a2', 0) },
  feed: { t0: PLATES.feed.t0({ cTr: cue('a2', 0) }), FRAME: field.FRAME, ROWS: field.ROWS, ROW_X0: field.ROW_X0, ROW_DX: field.ROW_DX, PITCH: field.PITCH, SPEED: field.SPEED, plants },
  packline: { t0: PACK.plateT0, cID: cue('a3', 1) - cue('a3', 0), BV: PACK.BV, FRAME: field.FRAME, LINE_X: PACK.LINE_X, by0: PACK.by0, bh: PACK.bh, pumpkins: PACK.table() },
  board: BOARD.inputs(cue('t2', 0)),
  tracking: { t0: tr.t0(trCue), frames: trFrames, bench: TRACK.bench },
};
const file = path.join(ROOT, 'build', 'shots', 'inputs.json');
fs.mkdirSync(path.dirname(file), { recursive: true });
fs.writeFileSync(file, JSON.stringify(out, null, 1));
console.log('wrote', path.relative(process.cwd(), file), `(${plants.length} plants, ${out.packline.pumpkins.length} pumpkins, ${trFrames.length} tracking frames)`);
