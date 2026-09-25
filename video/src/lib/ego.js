// Egocentric workbench camera with two procedural hands (shared by the vision scene, hook and recap).
import { prog, E, clamp, lerp, rrect } from '../engine.js';
import { handPoints, basis, drawHand } from './hand.js';
import { v3, add, mul, camera, lerp3 } from './three.js';

export const FRAME = { x: 150, y: 118, w: 1620, h: 826 };

// ------------------------------------------------------------ ego-camera scene
export function egoCam(t) {
  const n = 0.02;
  const sway = v3(Math.sin(t * 1.3) * n * 6, Math.sin(t * 2.1) * n * 3, 0);
  return camera(add(v3(0, 4.3, -2.3), sway), add(v3(0, 0.2, 2.5), mul(sway, 0.4)), { f: 1150, cx: 960, cy: 520 });
}
export function handPose(which, t) {
  if (which === 'L') {
    const pos = v3(-2.0 + Math.sin(t * 1.1) * 0.05, 0.78, 0.7 + Math.sin(t * 0.9) * 0.04);
    const b = basis(v3(0.42, 0.02, 1), v3(0.18, 1, 0));
    return { pos, ...b, mirror: true, curl: [0.15, 0.22, 0.28, 0.34, 0.4], spread: 0.45, scale: 1 };
  }
  const reach = E.inOutCubic(clamp((t - 0.3) / 1.4));
  const pinch = E.inOutCubic(clamp((t - 1.5) / 0.6));
  const lift = E.inOutCubic(clamp((t - 2.2) / 0.8));
  const pos = add(lerp3(v3(2.1, 0.95, 0.1), v3(0.95, 0.7, 1.25), reach), v3(0, lift * 0.35, -lift * 0.2));
  const b = basis(v3(lerp(-0.25, -0.45, reach), -0.05 - lift * 0.1, 1), v3(-0.25, 1, 0));
  return { pos, ...b, curl: [lerp(0.1, 0.62, pinch), lerp(0.12, 0.58, pinch), lerp(0.1, 0.72, pinch), lerp(0.14, 0.8, pinch), lerp(0.18, 0.85, pinch)], spread: lerp(0.55, 0.25, pinch), scale: 1 };
}
export function drawEgo(g, t, overlay, FR = FRAME) {
  const cam = egoCam(t);
  const P = (p) => cam.project(p);
  // table / cutting mat
  g.fillStyle = '#161a1c';
  g.fillRect(FR.x, FR.y, FR.w, FR.h);
  const mat = [v3(-6, 0, -0.6), v3(6, 0, -0.6), v3(6, 0, 11), v3(-6, 0, 11)].map(P);
  g.fillStyle = '#1d2a27';
  g.beginPath(); mat.forEach((q, i) => (i ? g.lineTo(q.x, q.y) : g.moveTo(q.x, q.y))); g.closePath(); g.fill();
  g.strokeStyle = 'rgba(190,230,210,0.07)';
  g.lineWidth = 1;
  for (let x = -6; x <= 6.01; x += 0.5) { const a = P(v3(x, 0, -0.6)), b = P(v3(x, 0, 11)); g.beginPath(); g.moveTo(a.x, a.y); g.lineTo(b.x, b.y); g.stroke(); }
  for (let z = -0.5; z <= 11; z += 0.5) { const a = P(v3(-6, 0, z)), b = P(v3(6, 0, z)); g.beginPath(); g.moveTo(a.x, a.y); g.lineTo(b.x, b.y); g.stroke(); }
  { const fog = g.createLinearGradient(0, FR.y, 0, FR.y + FR.h * 0.55); fog.addColorStop(0, 'rgba(14,17,19,0.96)'); fog.addColorStop(1, 'rgba(14,17,19,0)'); g.fillStyle = fog; g.fillRect(FR.x, FR.y, FR.w, FR.h * 0.55); }
  // a small parts box (held by the left hand)
  const cube = (c, s, col) => {
    const pts = []; for (const dx of [-1, 1]) for (const dy of [0, 2]) for (const dz of [-1, 1]) pts.push(P(add(c, v3(dx * s, dy * s * 0.5, dz * s))));
    const face = (idx, fill) => { g.fillStyle = fill; g.beginPath(); idx.forEach((i, k) => (k ? g.lineTo(pts[i].x, pts[i].y) : g.moveTo(pts[i].x, pts[i].y))); g.closePath(); g.fill(); };
    face([0, 1, 5, 4], col[2]); face([4, 5, 7, 6], col[1]); face([1, 3, 7, 5], col[0]); face([2, 3, 7, 6], col[1]);
  };
  cube(v3(-1.05, 0, 2.1), 0.55, ['#5a6773', '#3d4750', '#2b333a']);
  // hex nuts
  [[0.5, 2.55], [0.95, 2.95], [1.45, 2.35], [0.2, 3.3]].forEach(([x, z], i) => {
    const q = P(v3(x, 0.02, z));
    const r = 0.13 * q.s;
    g.fillStyle = '#9aa3ab'; g.beginPath(); for (let k = 0; k < 6; k++) { const a = k / 6 * Math.PI * 2 + i; g.lineTo(q.x + Math.cos(a) * r, q.y + Math.sin(a) * r * 0.62); } g.closePath(); g.fill();
    g.fillStyle = '#1d2a27'; g.beginPath(); g.ellipse(q.x, q.y, r * 0.45, r * 0.28, 0, 0, Math.PI * 2); g.fill();
  });
  // screwdriver
  { const a = P(v3(2.3, 0.05, 2.9)), b = P(v3(3.6, 0.05, 2.0)); g.lineCap = 'round'; g.strokeStyle = '#c9d0d6'; g.lineWidth = 0.05 * a.s; g.beginPath(); g.moveTo(a.x, a.y); g.lineTo(lerp(a.x, b.x, 0.5), lerp(a.y, b.y, 0.5)); g.stroke(); g.strokeStyle = '#d9542f'; g.lineWidth = 0.16 * b.s; g.beginPath(); g.moveTo(lerp(a.x, b.x, 0.5), lerp(a.y, b.y, 0.5)); g.lineTo(b.x, b.y); g.stroke(); }
  // hands
  const hands = ['L', 'R'].map((w) => { const pts = handPoints(handPose(w, t)); return { w, pts, P: pts.map(P) }; });
  hands.forEach((hd) => drawHand(g, hd.P, { tone: '#b7aca3', shade: '#6d655f', light: '#efe6dc', sleeve: '#262d36' }));
  // sensor look: cool grade + vignette
  g.save();
  g.globalCompositeOperation = 'multiply';
  g.fillStyle = 'rgba(150,175,190,1)';
  g.fillRect(FR.x, FR.y, FR.w, FR.h);
  g.restore();
  if (overlay) overlay(hands, cam);
  return hands;
}

