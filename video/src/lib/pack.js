// The packing line's model (agri scene, beat D), shared with scripts/render_packline.py through
// video/tools/dump_shot_inputs.mjs. Times are relative to the "a3" cue (cPack); x/y are feed pixels at the
// overhead line-camera view (FRAME coordinates, as the 2D version drew them).
import { hash } from '../engine.js';
import { FRAME } from './field.js';

const KINDS = ['orange', 'deep', 'orange', 'pale', 'orange', 'green', 'deep', 'orange'];
export const PACK = {
  N: 40,
  BV: 250,                         // belt speed, px/s
  LINE_X: FRAME.x + 1080,          // count line
  by0: FRAME.y + 200, bh: 420,     // belt top and width
  plateT0: -0.4,                   // the plate starts 0.4 s before the cue
  spawn: (k) => -2.6 + k * 0.62 + (hash(k, 4) - 0.5) * 0.2,
  lane: (k) => FRAME.y + 200 + 90 + hash(k, 8) * (420 - 180),
  radius: (k) => 70 + hash(k, 11) * 26,
  kind: (k) => KINDS[k % KINDS.length],
  table() {
    return Array.from({ length: this.N }, (_, k) => ({ k, spawn: this.spawn(k), y: this.lane(k), R: this.radius(k), rot0: hash(k, 5) * 6, kind: this.kind(k), seed: hash(k, 21) }));
  },
};
