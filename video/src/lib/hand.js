// Procedural 21-keypoint hand: forward kinematics + a stylized "clay" render + pose overlay.
// Keypoint order follows the common hand-landmark convention:
// 0 wrist · 1-4 thumb · 5-8 index · 9-12 middle · 13-16 ring · 17-20 pinky.
import { v3, add, mul, norm, cross, rotAxis } from './three.js';
import { rgba, C } from '../engine.js';

const FINGERS = [
  // base (MCP) in hand-local coords (palm width ≈ 1; +y toward fingers, +z = back of hand), splay angle, segment lengths
  { base: v3(-0.34, 0.98, 0), splay: -0.12, L: [0.46, 0.28, 0.22] },
  { base: v3(-0.11, 1.03, 0.02), splay: -0.03, L: [0.5, 0.31, 0.24] },
  { base: v3(0.13, 0.99, 0.01), splay: 0.06, L: [0.46, 0.29, 0.22] },
  { base: v3(0.35, 0.9, 0), splay: 0.16, L: [0.36, 0.23, 0.19] },
];
export const BONES = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9], [9, 10], [10, 11], [11, 12], [9, 13], [13, 14], [14, 15], [15, 16], [13, 17], [0, 17], [17, 18], [18, 19], [19, 20]];
export const FINGER_COLORS = [C.coral, C.amber, C.accent, C.sky, C.violet];
const lerpN = (a, b, t) => a + (b - a) * t;
const boneFinger = (a, b) => (b <= 4 ? 0 : b <= 8 ? 1 : b <= 12 ? 2 : b <= 16 ? 3 : 4);

/**
 * Hand keypoints in camera space.
 * pose: { pos (wrist, camera space: x right, y down, z forward), right: basis vector for hand +x,
 *         fwd: basis for hand +y (toward fingers), back: basis for +z (back of hand),
 *         curl: [thumb, index, middle, ring, pinky] 0..1, spread: 0..1, scale }
 */
export function handPoints(pose) {
  const { pos, right: bx, fwd: by, back: bz, curl = [0, 0, 0, 0, 0], spread = 0.3, scale = 1, mirror = false } = pose;
  const toCam = (p) => add(pos, add(add(mul(bx, (mirror ? -p.x : p.x) * scale), mul(by, p.y * scale)), mul(bz, p.z * scale)));
  const pts = new Array(21);
  pts[0] = toCam(v3(0, 0, 0));
  // thumb
  {
    const c = curl[0];
    let p = v3(-0.28, 0.22, -0.05);
    pts[1] = toCam(p);
    let d = norm(v3(-0.42, 0.88, -0.22));
    const axis = norm(v3(-0.66, -0.51, -0.56)); // rotates the thumb across the palm
    const L = [0.3, 0.25, 0.2];
    const bend = [0.35 * c, 0.55 * c, 0.6 * c];
    for (let j = 0; j < 3; j++) {
      d = rotAxis(d, axis, bend[j] - 0.12 * spread * (j === 0 ? 1 : 0));
      p = add(p, mul(d, L[j]));
      pts[2 + j] = toCam(p);
    }
  }
  FINGERS.forEach((f, i) => {
    const c = curl[i + 1];
    const a = f.splay * (0.6 + spread * 1.4);
    let d = v3(Math.sin(a), Math.cos(a), 0);
    const lat = v3(Math.cos(a), -Math.sin(a), 0);
    let p = f.base;
    pts[5 + i * 4] = toCam(p);
    const bend = [0.9 * c, 1.25 * c, 0.95 * c];
    for (let j = 0; j < 3; j++) {
      d = rotAxis(d, lat, -bend[j]); // negative rotation around the lateral axis flexes toward -z (palm side)
      p = add(p, mul(d, f.L[j]));
      pts[6 + i * 4 + j] = toCam(p);
    }
  });
  return pts;
}

/** Orthonormal hand basis from a forward (fingers) direction and a "back of hand" hint. */
export function basis(fwd, backHint) {
  const f = norm(fwd);
  const r = norm(cross(backHint, f));
  const b = cross(f, r);
  return { fwd: f, right: r, back: b };
}

/** Draw the stylized hand (clay material) given projected points. */
export function drawHand(g, P, { tone = '#b9ada2', shade = '#6f655d', light = '#e7ddd2', alpha = 1, forearm = true, sleeve = '#20262e' } = {}) {
  g.save();
  g.globalAlpha = alpha;
  g.lineCap = 'round';
  g.lineJoin = 'round';
  const pal = P[0].s; // px per hand unit at wrist depth
  // forearm / sleeve toward the bottom of the frame
  if (forearm) {
    const w = P[0];
    const dx = w.x - P[9].x, dy = w.y - P[9].y;
    const L = Math.hypot(dx, dy) || 1, ux = dx / L, uy = dy / L, nx = -uy, ny = ux;
    const len = pal * 3.4, w0 = pal * 0.3, w1 = pal * 0.46;
    const quad = (a0, a1, b0, b1, t0, t1) => {
      const x0 = w.x + ux * len * t0, y0 = w.y + uy * len * t0, x1 = w.x + ux * len * t1, y1 = w.y + uy * len * t1;
      g.beginPath(); g.moveTo(x0 + nx * a0, y0 + ny * a0); g.lineTo(x0 - nx * a1, y0 - ny * a1); g.lineTo(x1 - nx * b1, y1 - ny * b1); g.lineTo(x1 + nx * b0, y1 + ny * b0); g.closePath(); g.fill();
    };
    const gr = g.createLinearGradient(w.x + nx * w1, w.y + ny * w1, w.x - nx * w1, w.y - ny * w1);
    gr.addColorStop(0, shade); gr.addColorStop(0.45, tone); gr.addColorStop(1, shade);
    g.fillStyle = gr;
    quad(w0, w0, lerpN(w0, w1, 0.5), lerpN(w0, w1, 0.5), -0.05, 0.5);
    const sg = g.createLinearGradient(w.x + nx * w1, w.y + ny * w1, w.x - nx * w1, w.y - ny * w1);
    sg.addColorStop(0, '#12161b'); sg.addColorStop(0.5, sleeve); sg.addColorStop(1, '#12161b');
    g.fillStyle = sg;
    quad(lerpN(w0, w1, 0.45) * 1.25, lerpN(w0, w1, 0.45) * 1.25, w1 * 1.35, w1 * 1.35, 0.45, 1.6);
  }
  // segments sorted far → near
  const segs = [];
  const R = (i) => (i === 0 ? 0.3 : i <= 4 ? 0.12 - (i - 1) * 0.012 : 0.1 - ((i - 5) % 4) * 0.01);
  for (const [a, b] of BONES) {
    if ((a === 5 && b === 9) || (a === 9 && b === 13) || (a === 13 && b === 17) || (a === 0 && b === 17) || (a === 0 && b === 5)) continue;

    segs.push({ a, b, z: (P[a].z + P[b].z) / 2 });
  }
  // palm polygon
  const palm = [P[0], P[1], P[5], P[9], P[13], P[17]];
  const drawPalm = () => {
    g.fillStyle = tone;
    g.strokeStyle = tone;
    g.lineWidth = pal * 0.18;
    g.beginPath();
    palm.forEach((p, i) => (i ? g.lineTo(p.x, p.y) : g.moveTo(p.x, p.y)));
    g.closePath();
    g.fill();
    g.stroke();
    const cxp = (P[0].x + P[9].x) / 2, cyp = (P[0].y + P[9].y) / 2;
    const gr = g.createRadialGradient(cxp - pal * 0.1, cyp - pal * 0.15, 0, cxp, cyp, pal * 0.7);
    gr.addColorStop(0, rgba(light, 0.55)); gr.addColorStop(1, rgba(light, 0));
    g.fillStyle = gr;
    g.fill();
  };
  const palmZ = (P[0].z + P[9].z) / 2;
  segs.sort((s1, s2) => s2.z - s1.z);
  let palmDrawn = false;
  for (const s of segs) {
    if (!palmDrawn && s.z < palmZ - 0.02 * pal / 100) { drawPalm(); palmDrawn = true; }
    const A = P[s.a], B = P[s.b];
    const r = ((R(s.a) + R(s.b)) / 2) * pal;
    g.strokeStyle = shade;
    g.lineWidth = r * 2.1;
    g.beginPath(); g.moveTo(A.x, A.y); g.lineTo(B.x, B.y); g.stroke();
    g.strokeStyle = tone;
    g.lineWidth = r * 1.7;
    g.beginPath(); g.moveTo(A.x, A.y - r * 0.12); g.lineTo(B.x, B.y - r * 0.12); g.stroke();
    g.strokeStyle = rgba(light, 0.55);
    g.lineWidth = r * 0.55;
    g.beginPath(); g.moveTo(A.x - r * 0.1, A.y - r * 0.45); g.lineTo(B.x - r * 0.1, B.y - r * 0.45); g.stroke();
  }
  if (!palmDrawn) drawPalm();
  g.restore();
}

/** Keypoint + skeleton overlay (per-finger colors). */
export function drawPose(g, P, { alpha = 1, r = 5, lw = 2.5, p = 1 } = {}) {
  if (alpha <= 0.001) return;
  g.save();
  g.globalAlpha = alpha;
  g.lineCap = 'round';
  BONES.forEach(([a, b], k) => {
    const q = Math.min(1, Math.max(0, p * BONES.length - k * 0.6));
    if (q <= 0) return;
    g.strokeStyle = FINGER_COLORS[boneFinger(a, b)];
    g.lineWidth = lw;
    g.beginPath();
    g.moveTo(P[a].x, P[a].y);
    g.lineTo(P[a].x + (P[b].x - P[a].x) * q, P[a].y + (P[b].y - P[a].y) * q);
    g.stroke();
  });
  P.forEach((pt, i) => {
    if (i / 21 > p * 1.05) return;
    g.fillStyle = '#0b0d10';
    g.beginPath(); g.arc(pt.x, pt.y, r + 1.6, 0, Math.PI * 2); g.fill();
    g.fillStyle = i === 0 ? '#ffffff' : FINGER_COLORS[i <= 4 ? 0 : Math.floor((i - 5) / 4) + 1];
    g.beginPath(); g.arc(pt.x, pt.y, r, 0, Math.PI * 2); g.fill();
  });
  g.restore();
}

/** Axis-aligned bounding box of projected points (with padding). */
export function bbox(P, pad = 18) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const p of P) { x0 = Math.min(x0, p.x); y0 = Math.min(y0, p.y); x1 = Math.max(x1, p.x); y1 = Math.max(y1, p.y); }
  return { x: x0 - pad, y: y0 - pad, w: x1 - x0 + pad * 2, h: y1 - y0 + pad * 2 };
}
