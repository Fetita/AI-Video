// The robot-arm shot: a photoreal plate rendered in Blender (scripts/render_robot.py) with the film's
// overlays drawn on top. The kinematics and the camera here mirror that script exactly (same constants,
// same formulas), so every label, trail and keypoint sits on the rendered arm.
// World: x right, y up, z forward. tau = seconds since the first frame of the plate.
import { clamp, lerp, E, C, rgba, TAU, hash } from '../engine.js';
import { v3, add, camera } from './three.js';
import { tag, FONT_UI } from './ui.js';
import { handPoints, basis, drawPose } from './hand.js';

export const SHOT = { fps: 30, frames: 180, dur: 6.0 };
const H0 = 0.55, L1 = 0.95, L2 = 0.85, GRIP = 0.28;
const PICK = v3(-1.05, 0.10, 0.75), PLACE = v3(1.05, 0.10, 0.55);
const ios = E.inOutSine;

export function demoPath(u) {
  const e = ios(u), s = Math.sin(Math.PI * u);
  return v3(lerp(PICK.x, PLACE.x, e), PICK.y + s * 0.9, lerp(PICK.z, PLACE.z, e) + s * 0.35);
}
export const moveU = (tau) => ios(clamp((tau - 1.5) / 2.8));
const hover = (tau) => 0.30 * (1 - ios(clamp((tau - 0.25) / 0.85))) + 0.30 * ios(clamp((tau - 4.65) / 0.9));
export function tip(tau) { const p = demoPath(moveU(tau)); return v3(p.x, p.y + hover(tau), p.z); }
export function ik(T) {
  const yaw = Math.atan2(T.x, T.z);
  const wy = T.y + GRIP, d = Math.hypot(T.x, T.z), hgt = wy - H0;
  const L = Math.min(Math.hypot(d, hgt), L1 + L2 - 1e-3);
  const a2 = Math.acos(clamp((L1 ** 2 + L2 ** 2 - L ** 2) / (2 * L1 * L2), -1, 1));
  const a1 = Math.atan2(hgt, d) + Math.acos(clamp((L1 ** 2 + L ** 2 - L2 ** 2) / (2 * L1 * L), -1, 1));
  const dx = Math.sin(yaw), dz = Math.cos(yaw);
  const shoulder = v3(0, H0, 0);
  const elbow = v3(dx * Math.cos(a1) * L1, H0 + Math.sin(a1) * L1, dz * Math.cos(a1) * L1);
  const a3 = a1 - (Math.PI - a2);
  const wrist = v3(elbow.x + dx * Math.cos(a3) * L2, elbow.y + Math.sin(a3) * L2, elbow.z + dz * Math.cos(a3) * L2);
  return { yaw, a1, a2, shoulder, elbow, wrist };
}
export function shotCamera(tau) {
  const p = clamp(tau / SHOT.dur);
  const az = -0.62 + 0.22 * p, R = 3.75 - 0.30 * p;
  return camera(v3(Math.sin(az) * R, 1.95 - 0.12 * p, -Math.cos(az) * R), v3(0, 0.50, 0.45), { f: 1450, cx: 960, cy: 540 });
}

function polyline(g, pts) { g.beginPath(); pts.forEach((q, i) => (i ? g.lineTo(q.x, q.y) : g.moveTo(q.x, q.y))); g.stroke(); }

/** Overlays for the plate at shot time tau (a = overall opacity). */
export function drawRobotOverlay(g, tau, a) {
  if (a <= 0.001) return;
  const cam = shotCamera(tau);
  const P = (q) => cam.project(q);
  const U = moveU(tau);
  g.save();
  g.globalAlpha = a;
  g.lineCap = 'round'; g.lineJoin = 'round';

  // ---- the human demonstration: a keypoint hand travels the arc first and leaves it behind as a dashed path
  const hu = ios(clamp((tau - 0.3) / 1.25));
  const handA = Math.min(clamp((tau - 0.25) / 0.3), 1 - clamp((tau - 1.55) / 0.45));
  const pathA = clamp((tau - 0.3) / 0.3);
  if (pathA > 0) {
    const pts = [];
    for (let k = 0; k <= 90 * hu; k++) pts.push(P(demoPath(k / 90)));
    g.save();
    g.globalAlpha = a * pathA * 0.9;
    g.setLineDash([3, 11]); g.strokeStyle = 'rgba(150,214,255,0.95)'; g.lineWidth = 2.6;
    polyline(g, pts);
    g.restore();
  }
  if (handA > 0.001) {
    const hp = demoPath(hu);
    const b = basis(v3(0.2, -0.9, 0.3), v3(0, 0.3, -1));
    const pts = handPoints({ pos: add(hp, v3(0, 0.3, 0)), ...b, curl: [0.45, 0.45, 0.55, 0.6, 0.65], spread: 0.3, scale: 0.34 });
    drawPose(g, pts.map(P), { alpha: a * handA, r: 5, lw: 2.8 });
    const q = P(add(hp, v3(0, 0.62, 0)));
    tag(g, q.x - 80, q.y, 'HUMAN DEMONSTRATION', { a: a * handA, bg: '#0d0f12', fg: C.sky, stroke: rgba(C.sky, 0.6), size: 14, pad: 9 });
  }

  // ---- the robot replays it: a glowing trail along the same arc
  if (U > 0) {
    const pts = [];
    for (let k = 0; k <= 90 * U; k++) pts.push(P(demoPath(k / 90)));
    pts.push(P(demoPath(U)));
    g.save();
    g.strokeStyle = rgba(C.accent, 0.35); g.lineWidth = 11; polyline(g, pts);
    g.shadowColor = 'rgba(130,52,254,0.9)'; g.shadowBlur = 18;
    g.strokeStyle = '#b89cff'; g.lineWidth = 3.4; polyline(g, pts);
    g.restore();
  }

  // ---- pose estimate on the arm: joints and links
  const k = ik(tip(tau));
  const poseA = clamp((tau - 1.0) / 0.5);
  if (poseA > 0) {
    const J = [v3(0, 0.02, 0), k.shoulder, k.elbow, k.wrist, add(k.wrist, v3(0, -GRIP, 0))].map(P);
    g.save();
    g.globalAlpha = a * poseA;
    g.strokeStyle = 'rgba(255,255,255,0.55)'; g.lineWidth = 1.6; g.setLineDash([2, 7]);
    polyline(g, J);
    g.setLineDash([]);
    J.slice(1, 4).forEach((q, i) => {
      const r = [15, 13, 10][i];
      g.fillStyle = 'rgba(8,8,12,0.55)'; g.beginPath(); g.arc(q.x, q.y, r, 0, TAU); g.fill();
      g.strokeStyle = '#b89cff'; g.lineWidth = 2.4; g.beginPath(); g.arc(q.x, q.y, r, 0, TAU); g.stroke();
      g.fillStyle = '#ffffff'; g.beginPath(); g.arc(q.x, q.y, 2.6, 0, TAU); g.fill();
    });
    g.restore();
    const eq = P(add(k.elbow, v3(0, 0.3, 0)));
    tag(g, eq.x + 26, eq.y, U >= 0.999 ? 'ROBOT · TASK COMPLETE' : 'ROBOT · REPLAYING', { a: a * clamp((tau - 1.35) / 0.3), size: 14, pad: 9 });
  }

  // ---- pick / place labels
  [[PICK, 'PICK', 0.2], [PLACE, 'PLACE', 0.45]].forEach(([p0, label, at]) => {
    const q = P(v3(p0.x, 0.0, p0.z));
    tag(g, q.x + 118, q.y + 14, label, { a: a * clamp((tau - at) / 0.4), bg: null, fg: 'rgba(255,255,255,0.72)', size: 14, pad: 0, track: 0.16 });
  });

  // ---- telemetry
  const ta = clamp((tau - 1.2) / 0.5);
  if (ta > 0) {
    const x0 = 1486, y0 = 196, w = 274, rowH = 30;
    const deg = (r) => `${(r * 180 / Math.PI).toFixed(1)}°`;
    const err = U > 0 && U < 0.999 ? 0.6 + 0.5 * hash(Math.floor(tau * 12), 3) : 0.4;
    const rows = [['J1', 'BASE', deg(k.yaw)], ['J2', 'SHOULDER', deg(k.a1)], ['J3', 'ELBOW', deg(Math.PI - k.a2)], ['TCP', 'ERROR', `${err.toFixed(1)} mm`]];
    g.save();
    g.globalAlpha = a * ta;
    g.textBaseline = 'middle';
    g.font = `600 13px ${FONT_UI}`; g.letterSpacing = '0.16em';
    g.fillStyle = '#b89cff'; g.fillText('REPLAY', x0, y0);
    g.fillStyle = 'rgba(255,255,255,0.55)'; g.textAlign = 'right'; g.fillText('30 HZ', x0 + w, y0); g.textAlign = 'left';
    g.fillStyle = 'rgba(255,255,255,0.22)'; g.fillRect(x0, y0 + 16, w, 1);
    g.fillStyle = C.accent; g.fillRect(x0, y0 + 16, w * U, 1.5);
    rows.forEach(([id, name, val], i) => {
      const y = y0 + 40 + i * rowH;
      g.font = `600 13px ${FONT_UI}`; g.letterSpacing = '0.12em';
      g.fillStyle = '#b89cff'; g.fillText(id, x0, y);
      g.fillStyle = 'rgba(255,255,255,0.6)'; g.fillText(name, x0 + 48, y);
      g.font = `600 17px ${FONT_UI}`; g.letterSpacing = '0em';
      g.fillStyle = '#ffffff';
      // right-aligned in fixed cells so the running digits don't jitter
      const cell = g.measureText('0').width + 0.5;
      let cx = x0 + w;
      for (let j = val.length - 1; j >= 0; j--) { const ch = val[j]; const cw = /\d/.test(ch) ? cell : g.measureText(ch).width; cx -= cw; g.fillText(ch, cx + (cw - g.measureText(ch).width) / 2, y); }
    });
    g.restore();
  }
  g.restore();
}
