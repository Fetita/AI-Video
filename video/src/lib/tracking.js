// Camera + wrist tracking (vision scene): a head camera walks a loop around a workbench while an orbiting
// camera watches. Shared with scripts/render_tracking.py through video/tools/dump_shot_inputs.mjs, so the
// rendered rig, wrists and set sit exactly under the overlays. World: x right, y up, z forward (metres-ish).
import { prog, E, lerp } from '../engine.js';
import { v3, add, sub, mul, norm, cross, camera } from './three.js';

const LOOK = v3(0, 0.9, 0.2);
export const TRACK = {
  bench: { lo: [-0.9, 0, -0.5], hi: [0.9, 0.9, 0.9] },
  camPath(u) {
    const a = u * Math.PI * 1.6 - 0.6;
    return v3(Math.cos(a) * 2.4, 1.6 + Math.sin(u * 30) * 0.03, Math.sin(a) * 1.6 + 0.3);
  },
  wrist(side, u) {
    const c = this.camPath(u); const f = norm(sub(LOOK, c)); const r = norm(cross(f, v3(0, 1, 0)));
    return add(add(add(c, mul(f, 0.45)), mul(r, side * (0.24 + Math.sin(u * 17 + side) * 0.05))), v3(0, -0.55 + Math.sin(u * 23 + side * 2) * 0.06, 0));
  },
  /** progress along the walk at scene time t */
  progress: (t, c) => prog(t, c.cTrk - 0.1, c.cDs - c.cTrk + 0.6, E.linear) * 0.9 + 0.05,
  orbit(p) {
    const az = lerp(-0.75, -0.3, p);
    return { eye: v3(Math.sin(az) * 5.6, 3.6, -Math.cos(az) * 5.6), target: v3(0, 0.75, 0.3), f: 1500 };
  },
  camera(p) { const o = this.orbit(p); return camera(o.eye, o.target, { f: o.f, cx: 960, cy: 540 }); },
  /** the head camera's frame at progress U */
  head(U) {
    const c0 = this.camPath(U), c1 = this.camPath(Math.min(1, U + 0.01));
    const fw = norm(add(sub(LOOK, c0), mul(norm(sub(c1, c0)), 0.4)));
    const rt = norm(cross(fw, v3(0, 1, 0))), up = cross(rt, fw);
    return { c0, fw, rt, up };
  },
  pose(t, c) {
    const p = this.progress(t, c);
    return { t, p, ...this.orbit(p), ...this.head(p), wristL: this.wrist(-1, p), wristR: this.wrist(1, p) };
  },
};
