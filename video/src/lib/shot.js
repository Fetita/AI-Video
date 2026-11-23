// Blender plates (scripts/render_*.py) played under the film's overlays.
// A plate is a numbered image sequence (scripts/extract_clips.sh) that starts at a scene-relative time t0,
// shown frame-accurately through lib/clip.js. Overlays that follow objects in the plate read the plate's
// own export (src/shots/<name>.js: per frame, the camera and the screen position of each tracked object),
// at the same frame the plate is showing, so they never lead or lag it.
import { h, clamp, FPS } from '../engine.js';
import { makeClip } from './clip.js';
import { camera, v3 } from './three.js';
import { FRAME } from './field.js';

/** Every plate: length, size it is shown at (plate pixels = film pixels), and its start in its scene. */
export const PLATES = {
  tractor: { frames: 200, w: 1920, h: 1080, t0: () => -0.3 },                 // agri: tractor establishing shot
  feed: { frames: 120, w: FRAME.w, h: FRAME.h, t0: (c) => c.cTr + 0.6 },     // agri: top-down crop feed (orthographic)
  packline: { frames: 230, w: FRAME.w, h: FRAME.h, t0: (c) => c.cPack - 0.4 }, // agri: packing line
  board: { frames: 214, w: 1920, h: 1080, t0: () => -0.2 },                  // story: board and pieces
  tracking: { frames: 60, w: 1920, h: 1080, t0: (c) => c.cTrk - 0.1 },        // vision: camera + wrist tracking
};

/** Plate frame index shown at scene time t (held at both ends). */
export const plateFrame = (name, t, t0) => clamp(Math.floor((t - t0) * FPS + 1e-6), 0, PLATES[name].frames - 1);
/** Scene time of the frame the plate is showing (overlays computed from formulas use this). */
export const plateTime = (name, t, t0) => t0 + plateFrame(name, t, t0) / FPS;

/**
 * A plate in its own layer: rect = {x, y, w, h, radius} in film pixels (defaults to the full frame).
 * show(t, t0) returns the decode promise the engine waits for.
 */
export function makePlate(parent, name, rect = {}) {
  const P = PLATES[name];
  const r = { x: 0, y: 0, w: P.w, h: P.h, radius: 0, ...rect };
  const el = h('div', { class: 'abs', style: { left: `${r.x}px`, top: `${r.y}px`, width: `${r.w}px`, height: `${r.h}px`, borderRadius: `${r.radius}px`, overflow: 'hidden', transformOrigin: '50% 50%' } });
  parent.append(el);
  const clip = makeClip(el, { name, frames: P.frames, fps: FPS });
  return {
    el,
    show(t, t0) { return clip.show(plateFrame(name, t, t0) / FPS); },
  };
}

/** Export data at the frame shown: data.pts[key][frame] (or null), and the frame's camera. */
export function shotAt(data, name, t, t0) {
  const i = plateFrame(name, t, t0);
  return {
    i,
    pt: (key, j = undefined) => { const a = data.pts[key]; if (!a) return null; const row = a[i]; return j === undefined ? row : row && row[j]; },
    cam: () => { const c = data.cam[i]; return camera(v3(c[0], c[1], c[2]), v3(c[3], c[4], c[5]), { f: c[6], cx: data.w / 2, cy: data.h / 2 }); },
  };
}
