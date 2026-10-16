// 01 — Computer vision · Custom models · Robotics
// API call → full vision stack → hands → faces → camera & wrist tracking → dataset → train/benchmark → robot.
import { addScene, h, put, prog, E, clamp, lerp, env, makeCanvas, rng, rgba, C, keys, rrect, makeNoise } from '../engine.js';
import { makeHud, box, tag, recHud, brackets, FONT_MONO, FONT_UI } from '../lib/ui.js';
import { handPoints, basis, drawHand, drawPose, bbox, FINGER_COLORS } from '../lib/hand.js';
import { v3, add, sub, mul, norm, camera, lerp3, cross } from '../lib/three.js';
import { drawEgo } from '../lib/ego.js';

const FRAME = { x: 150, y: 118, w: 1620, h: 826 };
const STACK = [['Capture', 'Ego + fixed cameras'], ['Annotate', 'Hands · faces · wrists'], ['Dataset', 'Custom · versioned'], ['Train', 'Detection · pose'], ['Evaluate', 'Benchmarks'], ['Deploy', 'Robot data pipeline']];

// ------------------------------------------------------------ room with people (face detection)
function drawRoom(g, t, faceA, blurA) {
  const pan = Math.sin(t * 0.5) * 20;
  const x0 = FRAME.x, y0 = FRAME.y, W = FRAME.w, H = FRAME.h;
  const bg = g.createLinearGradient(0, y0, 0, y0 + H);
  bg.addColorStop(0, '#2b3036'); bg.addColorStop(1, '#171a1d');
  g.fillStyle = bg; g.fillRect(x0, y0, W, H);
  // window light + shelves
  const wg = g.createLinearGradient(x0 + 1100 + pan, 0, x0 + 1500 + pan, 0);
  wg.addColorStop(0, 'rgba(210,225,235,0.18)'); wg.addColorStop(1, 'rgba(210,225,235,0.05)');
  g.fillStyle = wg; g.fillRect(x0 + 1080 + pan, y0 + 60, 420, 420);
  g.strokeStyle = 'rgba(0,0,0,0.3)'; g.lineWidth = 8; g.strokeRect(x0 + 1080 + pan, y0 + 60, 420, 420); g.beginPath(); g.moveTo(x0 + 1290 + pan, y0 + 60); g.lineTo(x0 + 1290 + pan, y0 + 480); g.stroke();
  g.fillStyle = '#3a342f'; g.fillRect(x0 + 120 + pan, y0 + 150, 380, 14); g.fillRect(x0 + 120 + pan, y0 + 300, 380, 14);
  [[150, 96, '#6b7f8c'], [210, 120, '#8c6b5a'], [300, 80, '#5a6b58'], [380, 110, '#7a7160']].forEach(([x, hh, c]) => { g.fillStyle = c; g.fillRect(x0 + x + pan, y0 + 150 - hh * 0.5, 40, hh * 0.5); });
  // table edge in the foreground
  g.fillStyle = '#2a211b'; g.fillRect(x0, y0 + H - 170, W, 170);
  g.fillStyle = '#3a2e25'; g.fillRect(x0, y0 + H - 178, W, 10);
  const people = [
    { x: 420, y: 470, s: 1.25, c: '#3f5566', skin: '#b39580', blur: 0 },
    { x: 930, y: 420, s: 0.95, c: '#6b4f45', skin: '#8f6e5a', blur: 1.5 },
    { x: 1370, y: 440, s: 1.05, c: '#4d5a3f', skin: '#c7a38a', blur: 0.8 },
  ];
  const faces = [];
  people.forEach((p, i) => {
    const px = x0 + p.x + pan * (1 + i * 0.2), py = y0 + p.y + Math.sin(t * 1.4 + i) * 4;
    g.save();
    if (p.blur) g.filter = `blur(${p.blur}px)`;
    // shoulders
    g.fillStyle = p.c;
    g.beginPath(); g.moveTo(px - 190 * p.s, y0 + H); g.bezierCurveTo(px - 190 * p.s, py + 120 * p.s, px - 120 * p.s, py + 95 * p.s, px, py + 92 * p.s); g.bezierCurveTo(px + 120 * p.s, py + 95 * p.s, px + 190 * p.s, py + 120 * p.s, px + 190 * p.s, y0 + H); g.closePath(); g.fill();
    g.fillStyle = p.skin; g.fillRect(px - 26 * p.s, py + 40 * p.s, 52 * p.s, 60 * p.s);
    const hg = g.createRadialGradient(px - 18 * p.s, py - 22 * p.s, 5, px, py, 80 * p.s);
    hg.addColorStop(0, '#e2c9b5'); hg.addColorStop(0.35, p.skin); hg.addColorStop(1, '#4a3a31');
    g.fillStyle = hg; g.beginPath(); g.ellipse(px, py, 58 * p.s, 72 * p.s, 0, 0, Math.PI * 2); g.fill();
    g.fillStyle = '#2a211d'; g.beginPath(); g.ellipse(px, py - 42 * p.s, 60 * p.s, 36 * p.s, 0, Math.PI, Math.PI * 2); g.fill();
    g.restore();
    faces.push({ x: px - 66 * p.s, y: py - 84 * p.s, w: 132 * p.s, h: 164 * p.s, cx: px, cy: py, s: p.s });
  });
  // privacy blur on faces
  if (blurA > 0) {
    faces.forEach((f) => {
      g.save();
      g.globalAlpha = blurA;
      g.beginPath(); g.ellipse(f.cx, f.cy, f.w * 0.46, f.h * 0.46, 0, 0, Math.PI * 2); g.clip();
      const cell = 14;
      for (let yy = f.y; yy < f.y + f.h; yy += cell) for (let xx = f.x; xx < f.x + f.w; xx += cell) {
        const d = Math.hypot((xx - f.cx) / f.w, (yy - f.cy) / f.h);
        const v = 120 + Math.sin(xx * 0.13 + yy * 0.07) * 18 - d * 90;
        g.fillStyle = `rgb(${v + 30 | 0},${v + 10 | 0},${v | 0})`;
        g.fillRect(xx, yy, cell - 1, cell - 1);
      }
      g.restore();
    });
  }
  g.save(); g.globalCompositeOperation = 'multiply'; g.fillStyle = 'rgba(150,175,190,1)'; g.fillRect(x0, y0, W, H); g.restore();
  faces.forEach((f, i) => {
    const a = clamp(faceA * 3 - i * 0.5);
    box(g, f.x, f.y, f.w, f.h, { color: C.accent, a, lw: 1.6 });
    tag(g, f.x, f.y - 6, blurA > 0.5 ? `FACE ${i + 1} · ANONYMIZED` : `FACE ${i + 1}`, { a, size: 12 });
  });
}

// ------------------------------------------------------------ 3D tracking view
function camPath(u) {
  // a person walking a loop around a workbench (world units = meters-ish)
  const a = u * Math.PI * 1.6 - 0.6;
  return v3(Math.cos(a) * 2.4, 1.6 + Math.sin(u * 30) * 0.03, Math.sin(a) * 1.6 + 0.3);
}
function drawTracking(g, t, p, a) {
  if (a <= 0.001) return;
  g.save();
  g.globalAlpha = a;
  const az = lerp(-0.75, -0.3, p);
  const eye = v3(Math.sin(az) * 5.6, 3.6, -Math.cos(az) * 5.6);
  const cam = camera(eye, v3(0, 0.75, 0.3), { f: 1500, cx: 960, cy: 540 });
  const P = (q) => cam.project(q);
  // floor grid
  g.lineWidth = 1;
  for (let i = -5; i <= 5; i++) {
    const s1 = P(v3(i, 0, -4)), s2 = P(v3(i, 0, 5)), s3 = P(v3(-5, 0, i)), s4 = P(v3(5, 0, i));
    g.strokeStyle = i === 0 ? 'rgba(255,255,255,0.16)' : 'rgba(255,255,255,0.06)';
    g.beginPath(); g.moveTo(s1.x, s1.y); g.lineTo(s2.x, s2.y); g.moveTo(s3.x, s3.y); g.lineTo(s4.x, s4.y); g.stroke();
  }
  // workbench block
  const bench = [v3(-0.9, 0, -0.5), v3(0.9, 0, -0.5), v3(0.9, 0, 0.9), v3(-0.9, 0, 0.9)];
  const top = bench.map((q) => P(add(q, v3(0, 0.9, 0))));
  g.fillStyle = 'rgba(255,255,255,0.05)'; g.strokeStyle = 'rgba(255,255,255,0.18)';
  g.beginPath(); top.forEach((q, i) => (i ? g.lineTo(q.x, q.y) : g.moveTo(q.x, q.y))); g.closePath(); g.fill(); g.stroke();
  bench.forEach((q, i) => { const b0 = P(q), b1 = top[i]; g.beginPath(); g.moveTo(b0.x, b0.y); g.lineTo(b1.x, b1.y); g.stroke(); });
  const U = p; // progress along the path
  // ground truth (dashed, full) and estimate (solid, up to now)
  g.setLineDash([6, 8]); g.strokeStyle = 'rgba(255,255,255,0.45)'; g.lineWidth = 1.5; g.beginPath();
  for (let k = 0; k <= 120; k++) { const q = P(camPath(k / 120)); k ? g.lineTo(q.x, q.y) : g.moveTo(q.x, q.y); } g.stroke(); g.setLineDash([]);
  g.strokeStyle = C.accent; g.lineWidth = 2.5; g.beginPath();
  for (let k = 0; k <= 120 * U; k++) { const u = k / 120; const q = P(add(camPath(u), v3(Math.sin(u * 40) * 0.025, Math.cos(u * 33) * 0.02, 0))); k ? g.lineTo(q.x, q.y) : g.moveTo(q.x, q.y); } g.stroke();
  // camera frustum at current pose
  const c0 = camPath(U), c1 = camPath(Math.min(1, U + 0.01));
  const fw = norm(add(sub(v3(0, 0.9, 0.2), c0), mul(norm(sub(c1, c0)), 0.4)));
  const rt = norm(cross(fw, v3(0, 1, 0))), up = cross(rt, fw);
  const corner = (sx, sy) => P(add(add(add(c0, mul(fw, 0.55)), mul(rt, sx * 0.36)), mul(up, sy * 0.22)));
  const cc = P(c0), k1 = corner(-1, 1), k2 = corner(1, 1), k3 = corner(1, -1), k4 = corner(-1, -1);
  g.fillStyle = 'rgba(130,52,254,0.12)'; g.strokeStyle = C.accent; g.lineWidth = 2;
  g.beginPath(); g.moveTo(k1.x, k1.y); g.lineTo(k2.x, k2.y); g.lineTo(k3.x, k3.y); g.lineTo(k4.x, k4.y); g.closePath(); g.fill(); g.stroke();
  [k1, k2, k3, k4].forEach((k) => { g.beginPath(); g.moveTo(cc.x, cc.y); g.lineTo(k.x, k.y); g.stroke(); });
  // wrists: positions relative to the head camera, with 3 s trails
  const wrist = (side, u) => { const c = camPath(u); const f = norm(sub(v3(0, 0.9, 0.2), c)); const r = norm(cross(f, v3(0, 1, 0))); return add(add(add(c, mul(f, 0.45)), mul(r, side * (0.24 + Math.sin(u * 17 + side) * 0.05))), v3(0, -0.55 + Math.sin(u * 23 + side * 2) * 0.06, 0)); };
  [[-1, C.sky], [1, C.coral]].forEach(([side, col]) => {
    g.strokeStyle = rgba(col, 0.9); g.lineWidth = 2; g.beginPath();
    const tail = 0.12;
    for (let k = 0; k <= 30; k++) { const u = Math.max(0, U - tail + (k / 30) * tail); const q = P(wrist(side, u)); k ? g.lineTo(q.x, q.y) : g.moveTo(q.x, q.y); }
    g.stroke();
    const q = P(wrist(side, U));
    g.fillStyle = col; g.beginPath(); g.arc(q.x, q.y, 7, 0, Math.PI * 2); g.fill();
    g.strokeStyle = '#0b0d10'; g.lineWidth = 2; g.stroke();
  });
  // axis gizmo at camera
  [[rt, C.coral], [up, C.accent], [fw, C.sky]].forEach(([d, col]) => { const e = P(add(c0, mul(d, 0.35))); g.strokeStyle = col; g.lineWidth = 2.5; g.beginPath(); g.moveTo(cc.x, cc.y); g.lineTo(e.x, e.y); g.stroke(); });
  g.restore();
  // legend
  const items = [['Camera · estimate', C.accent, false], ['Ground truth', 'rgba(255,255,255,0.6)', true], ['Left wrist', C.sky, false], ['Right wrist', C.coral, false]];
  let lx = 200;
  g.save(); g.globalAlpha = a; g.font = `500 14px ${FONT_MONO}`; g.textBaseline = 'middle';
  items.forEach(([label, col, dashed]) => {
    g.strokeStyle = col; g.lineWidth = 2.5; if (dashed) g.setLineDash([5, 5]);
    g.beginPath(); g.moveTo(lx, 900); g.lineTo(lx + 28, 900); g.stroke(); g.setLineDash([]);
    g.fillStyle = 'rgba(243,243,239,0.75)'; g.fillText(label.toUpperCase(), lx + 40, 901);
    lx += 70 + g.measureText(label.toUpperCase()).width;
  });
  g.restore();
}

// ------------------------------------------------------------ robot arm
const ARM = { base: v3(0, 0, 0), h0: 0.55, l1: 0.95, l2: 0.85, grip: 0.28 };
function demoPath(u) {
  // pick at A → lift → place at B (world units)
  const A = v3(-1.05, 0.12, 0.75), B = v3(1.05, 0.12, 0.55);
  const p = lerp3(A, B, E.inOutSine(u));
  p.y += Math.sin(Math.PI * u) * 0.9;
  p.z += Math.sin(Math.PI * u) * 0.35;
  return p;
}
function armIK(T) {
  const yaw = Math.atan2(T.x, T.z);
  const wristT = add(T, v3(0, ARM.grip, 0));
  const d = Math.hypot(wristT.x, wristT.z), hgt = wristT.y - ARM.h0;
  const L = Math.min(Math.hypot(d, hgt), ARM.l1 + ARM.l2 - 1e-3);
  const a2 = Math.acos(clamp((ARM.l1 ** 2 + ARM.l2 ** 2 - L ** 2) / (2 * ARM.l1 * ARM.l2), -1, 1));
  const a1 = Math.atan2(hgt, d) + Math.acos(clamp((ARM.l1 ** 2 + L ** 2 - ARM.l2 ** 2) / (2 * ARM.l1 * L), -1, 1));
  const dir = v3(Math.sin(yaw), 0, Math.cos(yaw));
  const shoulder = v3(0, ARM.h0, 0);
  const elbow = add(shoulder, add(mul(dir, Math.cos(a1) * ARM.l1), v3(0, Math.sin(a1) * ARM.l1, 0)));
  const a3 = a1 - (Math.PI - a2);
  const wrist = add(elbow, add(mul(dir, Math.cos(a3) * ARM.l2), v3(0, Math.sin(a3) * ARM.l2, 0)));
  return { yaw, dir, shoulder, elbow, wrist, tip: add(wrist, v3(0, -ARM.grip, 0)) };
}
function drawRobot(g, t, a, U, hand) {
  if (a <= 0.001) return;
  g.save(); g.globalAlpha = a;
  const az = -0.55 + Math.sin(t * 0.25) * 0.08;
  const cam = camera(v3(Math.sin(az) * 4.3, 2.5, -Math.cos(az) * 4.3), v3(0, 0.62, 0.45), { f: 1450, cx: 960, cy: 560 });
  const P = (q) => cam.project(q);
  for (let i = -4; i <= 4; i++) {
    const s1 = P(v3(i * 0.5, 0, -2)), s2 = P(v3(i * 0.5, 0, 3)), s3 = P(v3(-2, 0, i * 0.5 + 0.5)), s4 = P(v3(2, 0, i * 0.5 + 0.5));
    g.strokeStyle = 'rgba(255,255,255,0.06)'; g.lineWidth = 1; g.beginPath(); g.moveTo(s1.x, s1.y); g.lineTo(s2.x, s2.y); g.moveTo(s3.x, s3.y); g.lineTo(s4.x, s4.y); g.stroke();
  }
  // demonstration path (dashed) + robot trail (violet)
  g.setLineDash([7, 8]); g.strokeStyle = 'rgba(124,198,255,0.8)'; g.lineWidth = 2; g.beginPath();
  for (let k = 0; k <= 80; k++) { const q = P(demoPath(k / 80)); k ? g.lineTo(q.x, q.y) : g.moveTo(q.x, q.y); } g.stroke(); g.setLineDash([]);
  if (U > 0) { g.strokeStyle = C.accent; g.lineWidth = 3.5; g.beginPath(); for (let k = 0; k <= 80 * U; k++) { const q = P(demoPath(k / 80)); k ? g.lineTo(q.x, q.y) : g.moveTo(q.x, q.y); } g.stroke(); }
  // pick/place markers
  [[demoPath(0), 'PICK'], [demoPath(1), 'PLACE']].forEach(([q0, label]) => { const q = P(v3(q0.x, 0.001, q0.z)); g.strokeStyle = 'rgba(255,255,255,0.35)'; g.lineWidth = 1.5; g.beginPath(); g.ellipse(q.x, q.y, 36, 12, 0, 0, Math.PI * 2); g.stroke(); tag(g, q.x + 42, q.y + 6, label, { bg: null, fg: 'rgba(255,255,255,0.55)', size: 12, anchor: 'bl', pad: 0 }); });
  // the part being moved
  const carry = U > 0.02 && U < 0.98;
  const partPos = U <= 0.02 ? demoPath(0) : U >= 0.98 ? demoPath(1) : demoPath(U);
  { const c = add(partPos, v3(0, -0.12, 0)); const s = 0.12; const pts = []; for (const dx of [-1, 1]) for (const dy of [0, 2]) for (const dz of [-1, 1]) pts.push(P(add(c, v3(dx * s, dy * s, dz * s))));
    const face = (idx, fill) => { g.fillStyle = fill; g.beginPath(); idx.forEach((i, k) => (k ? g.lineTo(pts[i].x, pts[i].y) : g.moveTo(pts[i].x, pts[i].y))); g.closePath(); g.fill(); };
    face([2, 3, 7, 6], '#ffc45c'); face([0, 1, 3, 2], '#d99a2b'); face([1, 3, 7, 5], '#b87d1c'); }
  // arm
  const T = demoPath(Math.max(0.0001, Math.min(0.9999, U)));
  const k = armIK(T);
  const seg = (A, B, w, col) => { const a1 = P(A), b1 = P(B); g.lineCap = 'round'; g.strokeStyle = '#1b1f24'; g.lineWidth = w * a1.s * 1.25; g.beginPath(); g.moveTo(a1.x, a1.y); g.lineTo(b1.x, b1.y); g.stroke(); g.strokeStyle = col; g.lineWidth = w * a1.s; g.beginPath(); g.moveTo(a1.x, a1.y); g.lineTo(b1.x, b1.y); g.stroke(); g.strokeStyle = 'rgba(255,255,255,0.35)'; g.lineWidth = w * a1.s * 0.25; g.beginPath(); g.moveTo(a1.x, a1.y - w * a1.s * 0.22); g.lineTo(b1.x, b1.y - w * a1.s * 0.22); g.stroke(); };
  const bp = P(v3(0, 0, 0));
  g.fillStyle = '#2a2f36'; g.beginPath(); g.ellipse(bp.x, bp.y, 0.34 * bp.s, 0.12 * bp.s, 0, 0, Math.PI * 2); g.fill();
  seg(v3(0, 0, 0), k.shoulder, 0.26, '#8d959e');
  seg(k.shoulder, k.elbow, 0.2, '#c3c9cf');
  seg(k.elbow, k.wrist, 0.16, '#d9dde1');
  seg(k.wrist, add(k.wrist, v3(0, -ARM.grip * 0.55, 0)), 0.12, '#8d959e');
  const open = carry ? 0.05 : 0.12;
  const gl = add(k.wrist, v3(0, -ARM.grip * 0.55, 0));
  const side = norm(cross(k.dir, v3(0, 1, 0)));
  [-1, 1].forEach((sgn) => seg(add(gl, mul(side, sgn * open)), add(add(gl, mul(side, sgn * open)), v3(0, -ARM.grip * 0.45, 0)), 0.05, '#e6e9ec'));
  [k.shoulder, k.elbow, k.wrist].forEach((j) => { const q = P(j); g.fillStyle = '#0d0f12'; g.beginPath(); g.arc(q.x, q.y, 0.1 * q.s, 0, Math.PI * 2); g.fill(); g.strokeStyle = C.accent; g.lineWidth = 2.5; g.beginPath(); g.arc(q.x, q.y, 0.1 * q.s, 0, Math.PI * 2); g.stroke(); });
  // ghost demonstrator hand (keypoints only) leading along the path
  if (hand.a > 0.001) {
    const hp = demoPath(hand.u);
    const b = basis(v3(0.2, -0.9, 0.3), v3(0, 0.3, -1));
    const pts = handPoints({ pos: add(hp, v3(0, 0.3, 0)), ...b, curl: [0.45, 0.45, 0.55, 0.6, 0.65], spread: 0.3, scale: 0.34 });
    drawPose(g, pts.map(P), { alpha: hand.a, r: 4.5, lw: 2.5 });
    const q = P(add(hp, v3(0, 0.55, 0)));
    tag(g, q.x - 60, q.y, 'HUMAN DEMONSTRATION', { a: hand.a, bg: '#0d0f12', fg: C.sky, stroke: rgba(C.sky, 0.6), size: 12 });
  }
  const eq = P(add(k.elbow, v3(0, 0.25, 0)));
  if (U > 0.05) tag(g, eq.x + 20, eq.y, 'ROBOT · REPLAYING', { a: clamp((U - 0.05) * 6), size: 12 });
  g.restore();
}

// ------------------------------------------------------------ charts
function lossCurve(u, seed, floor) { return floor + (1 - floor) * Math.exp(-u * 4.2) + Math.sin(u * 60 + seed) * 0.012 * (1 - u) + Math.sin(u * 23 + seed * 3) * 0.01; }
function prCurve(r, q) { return clamp(1 - Math.pow(r, q) * 0.92 - 0.03, 0, 1); }
function drawCharts(g, t, a, p) {
  if (a <= 0.001) return;
  g.save(); g.globalAlpha = a;
  const panels = [{ x: 170, y: 190, w: 760, h: 620, title: 'TRAINING', xl: 'EPOCHS', yl: 'LOSS' }, { x: 990, y: 190, w: 760, h: 620, title: 'BENCHMARK', xl: 'RECALL', yl: 'PRECISION' }];
  const models = [{ name: 'Baseline', col: 'rgba(200,205,212,0.75)', floor: 0.42, q: 1.6 }, { name: 'Model B', col: C.sky, floor: 0.3, q: 2.6 }, { name: 'Custom model', col: C.accent, floor: 0.16, q: 4.4 }];
  panels.forEach((pn, pi) => {
    g.fillStyle = '#0f1115'; g.strokeStyle = 'rgba(255,255,255,0.13)'; g.lineWidth = 1;
    rrect(g, pn.x, pn.y, pn.w, pn.h, 18); g.fill(); g.stroke();
    g.font = `600 13px ${FONT_MONO}`; g.fillStyle = 'rgba(243,243,239,0.85)'; g.textBaseline = 'middle'; g.fillText(pn.title, pn.x + 28, pn.y + 34);
    const ax = { x: pn.x + 70, y: pn.y + 80, w: pn.w - 110, h: pn.h - 150 };
    g.strokeStyle = 'rgba(255,255,255,0.08)';
    for (let i = 0; i <= 4; i++) { const yy = ax.y + (i / 4) * ax.h; g.beginPath(); g.moveTo(ax.x, yy); g.lineTo(ax.x + ax.w, yy); g.stroke(); }
    g.strokeStyle = 'rgba(255,255,255,0.3)'; g.beginPath(); g.moveTo(ax.x, ax.y); g.lineTo(ax.x, ax.y + ax.h); g.lineTo(ax.x + ax.w, ax.y + ax.h); g.stroke();
    g.font = `500 12px ${FONT_MONO}`; g.fillStyle = 'rgba(168,172,179,0.8)';
    g.fillText(pn.xl, ax.x + ax.w - g.measureText(pn.xl).width, ax.y + ax.h + 26);
    g.save(); g.translate(ax.x - 26, ax.y + ax.h / 2); g.rotate(-Math.PI / 2); g.fillText(pn.yl, -g.measureText(pn.yl).width / 2, 0); g.restore();
    models.forEach((m, mi) => {
      const q = clamp(p * 1.25 - mi * 0.12);
      if (q <= 0) return;
      g.strokeStyle = m.col; g.lineWidth = mi === 2 ? 3.5 : 2.2;
      if (mi === 2) { g.shadowColor = 'rgba(130,52,254,0.5)'; g.shadowBlur = 12; }
      g.beginPath();
      const N = 140;
      for (let k = 0; k <= N * q; k++) {
        const u = k / N;
        const yv = pi === 0 ? lossCurve(u, mi * 5 + 1, m.floor) : prCurve(u, m.q);
        const xx = ax.x + u * ax.w, yy = ax.y + (1 - yv) * ax.h * (pi === 0 ? 1 : 1);
        const Y = pi === 0 ? ax.y + (1 - yv) * ax.h * 0.92 + ax.h * 0.04 : yy;
        k ? g.lineTo(xx, Y) : g.moveTo(xx, Y);
      }
      g.stroke();
      g.shadowBlur = 0;
    });
    // legend
    let lx = pn.x + 28;
    g.font = `500 12.5px ${FONT_UI}`;
    models.forEach((m) => { g.fillStyle = m.col; g.fillRect(lx, pn.y + pn.h - 38, 14, 3); g.fillStyle = 'rgba(243,243,239,0.8)'; g.fillText(m.name, lx + 22, pn.y + pn.h - 36); lx += 44 + g.measureText(m.name).width; });
  });
  // selected operating point on the benchmark
  const sp = clamp((p - 0.75) / 0.2);
  if (sp > 0) {
    const ax = { x: 990 + 70, y: 190 + 80, w: 760 - 110, h: 620 - 150 };
    const r = 0.72, yv = prCurve(r, 4.4);
    const X = ax.x + r * ax.w, Y = ax.y + (1 - yv) * ax.h;
    g.strokeStyle = C.accent; g.lineWidth = 2; g.beginPath(); g.arc(X, Y, 10 + (1 - sp) * 20, 0, Math.PI * 2); g.globalAlpha = a * sp; g.stroke();
    g.fillStyle = C.accent; g.beginPath(); g.arc(X, Y, 5, 0, Math.PI * 2); g.fill();
    tag(g, X + 16, Y - 14, 'SELECTED', { a: a * sp, size: 12 });
  }
  g.restore();
}

// ------------------------------------------------------------ dataset atlas
function buildAtlas() {
  const TW = 200, TH = 124, COLS = 10, ROWS = 6;
  const { c, ctx: g } = makeCanvas(null, TW * COLS, TH * ROWS, '');
  const r = rng(5);
  for (let j = 0; j < ROWS; j++) for (let i = 0; i < COLS; i++) {
    const x = i * TW, y = j * TH;
    g.save();
    g.beginPath(); g.rect(x + 4, y + 4, TW - 8, TH - 8); g.clip();
    const kind = r();
    g.fillStyle = kind < 0.75 ? '#1b2522' : '#262a2f'; g.fillRect(x, y, TW, TH);
    if (kind < 0.75) {
      const cam = camera(v3(0, 5, -3.3), v3((r() - 0.5) * 1.5, 0.3, 2.8), { f: 170, cx: x + TW / 2, cy: y + TH / 2 + 10 });
      g.strokeStyle = 'rgba(190,230,210,0.08)';
      for (let k = -4; k <= 4; k++) { const a = cam.project(v3(k, 0, -0.5)), b = cam.project(v3(k, 0, 6)); g.beginPath(); g.moveTo(a.x, a.y); g.lineTo(b.x, b.y); g.stroke(); }
      const nh = r() < 0.6 ? 2 : 1;
      for (let hh = 0; hh < nh; hh++) {
        const side = nh === 1 ? (r() < 0.5 ? -1 : 1) : hh ? 1 : -1;
        const b = basis(v3(-side * (0.1 + r() * 0.5), -0.1 + r() * 0.2, 1), v3(side * -0.2, 1, 0));
        const pts = handPoints({ pos: v3(side * (1 + r() * 1.2), 0.7 + r() * 0.4, 0.4 + r() * 1.2), ...b, mirror: side < 0, curl: [r(), r(), r(), r(), r()].map((v) => v * 0.9), spread: r(), scale: 1 });
        const P = pts.map((q) => cam.project(q));
        drawHand(g, P, { tone: '#9e958d', shade: '#5c554f', light: '#d7cec5', forearm: true, sleeve: '#232a31' });
        drawPose(g, P, { r: 1.6, lw: 1.1 });
        const bb = bbox(P, 5);
        g.strokeStyle = side < 0 ? C.sky : C.coral; g.lineWidth = 1; g.strokeRect(bb.x, bb.y, bb.w, bb.h);
      }
    } else {
      for (let k = 0; k < 2; k++) {
        const fx = x + 40 + k * 90 + r() * 20, fy = y + 50 + r() * 16;
        g.fillStyle = '#6b5a50'; g.beginPath(); g.ellipse(fx, fy, 16, 20, 0, 0, Math.PI * 2); g.fill();
        g.fillStyle = '#39424c'; g.beginPath(); g.ellipse(fx, fy + 60, 40, 34, 0, 0, Math.PI * 2); g.fill();
        g.strokeStyle = C.accent; g.lineWidth = 1.2; g.strokeRect(fx - 20, fy - 25, 40, 50);
      }
    }
    g.restore();
  }
  return { c, TW, TH, COLS, ROWS };
}

addScene({
  id: 'vision',
  pre: 0.3,
  post: 0.5,
  setup(ctx) {
    const R = ctx.root;
    this.hud = makeHud(ctx, {
      num: '01', title: 'Computer vision · Custom models · Robotics', badge: 'Client project',
      steps: [
        { label: 'Detect', at: ctx.cue('v2', 0) + 0.2 },
        { label: 'Track', at: ctx.cue('v2', 2) },
        { label: 'Dataset', at: ctx.cue('v2', 3) },
        { label: 'Train', at: ctx.cue('v3', 0) },
        { label: 'Benchmark', at: ctx.cue('v3', 0) + 1.0 },
        { label: 'Robotics', at: ctx.cue('v3', 1) },
      ],
    });
    const cv = makeCanvas(R);
    this.g = cv.ctx;
    this.atlas = buildAtlas();
    // ---- API call → the vision stack (DOM typography)
    this.api = h('div', { class: 'abs', style: { left: '0', top: '0', width: '1920px', display: 'flex', justifyContent: 'center' } });
    this.apiPill = h('div', { class: 'panel', style: { position: 'relative', padding: '22px 34px', display: 'flex', alignItems: 'center', gap: '22px' } },
      h('span', { class: 'kicker', style: { color: 'var(--text3)' } }, 'API call'),
      h('span', { class: 'mono', style: { fontSize: '40px', color: 'var(--text)' } }, h('span', { style: { color: 'var(--sky)' } }, 'vision'), '.detect(', h('span', { style: { color: 'var(--amber)' } }, 'frame'), ')'));
    this.strike = h('div', { style: { position: 'absolute', left: '24px', right: '24px', top: '50%', height: '2px', background: 'var(--coral)', transformOrigin: '0 50%' } });
    this.apiPill.append(this.strike);
    this.api.append(this.apiPill);
    R.append(this.api);
    // incoming hand-off: the intro's violet line (same position) contracts and opens the API call card
    this.handIn = h('div', { class: 'abs', style: { left: '460px', top: '483px', width: '1000px', height: '2px', background: 'var(--accent)', transformOrigin: '50% 50%', boxShadow: '0 0 16px rgba(130,52,254,0.6)' } });
    R.insertBefore(this.handIn, this.api); // behind the card, so the card covers it as it opens
    this.stack = STACK.map(([k, v], i) => {
      const el = h('div', { class: 'panel', style: { left: '560px', top: '0', width: '800px', height: '74px', display: 'flex', alignItems: 'center', padding: '0 30px', gap: '20px', borderRadius: '14px' } },
        h('span', { class: 'mono', style: { color: 'var(--accent-text)', fontSize: '14px', width: '30px' } }, `0${i + 1}`),
        h('span', { class: 'display', style: { fontSize: '30px', fontWeight: 600, flex: 1, letterSpacing: '-0.01em' } }, k),
        h('span', { class: 'kicker', style: { color: 'var(--text2)' } }, v));
      R.append(el);
      return el;
    });
    this.stackLabel = h('div', { class: 'abs kicker', style: { left: '560px', top: '0', color: 'var(--text2)', fontSize: '14px' } }, 'The vision stack we build');
    R.append(this.stackLabel);
    // dataset side panel
    this.dsPanel = h('div', { class: 'panel', style: { left: '1330px', top: '300px', width: '430px', padding: '26px 28px' } },
      h('div', { class: 'kicker', style: { marginBottom: '10px' } }, 'Custom dataset'),
      h('div', { style: { fontSize: '28px', fontWeight: 600, marginBottom: '20px', letterSpacing: '-0.01em' } }, 'Annotated frames'),
      h('div', { style: { display: 'flex', flexWrap: 'wrap', gap: '10px', marginBottom: '26px' } }, ...['Hands · 21 keypoints', 'Faces', 'Wrist pose', 'Camera pose'].map((x) => h('span', { class: 'chip ai' }, x))),
      h('div', { class: 'kicker', style: { marginBottom: '10px' } }, 'Splits'),
      h('div', { style: { display: 'flex', height: '12px', borderRadius: '6px', overflow: 'hidden', gap: '3px' } },
        h('i', { style: { display: 'block', flex: 7, background: 'var(--accent)' } }), h('i', { style: { display: 'block', flex: 2, background: 'var(--sky)' } }), h('i', { style: { display: 'block', flex: 1, background: 'var(--violet)' } })),
      h('div', { style: { display: 'flex', justifyContent: 'space-between', marginTop: '10px' } }, ...['Train', 'Validation', 'Test'].map((x) => h('span', { class: 'kicker', style: { fontSize: '11px' } }, x))));
    R.append(this.dsPanel);
  },

  render(t, ctx) {
    const g = this.g;
    g.clearRect(0, 0, 1920, 1080);
    this.hud(t);
    const D = ctx.dur;
    const cStack = ctx.cue('v1', 1), cVS = ctx.cue('v2', 0), cDet = ctx.cue('v2', 1), cTrk = ctx.cue('v2', 2), cDs = ctx.cue('v2', 3), cTr = ctx.cue('v3', 0), cRb = ctx.cue('v3', 1);

    // ---------- A: API call → stack
    const apiIn = prog(t, 0.05, 0.5, E.outCubic);
    const stackIn = prog(t, cStack - 0.05, 0.9, E.outCubic);
    const stackOut = prog(t, cVS - 0.35, 0.55, E.inOutCubic);
    // the card opens out of the hand-off line (its vertical centre sits on the line at y = 483)
    if (!this.pillH) { const r = this.apiPill.getBoundingClientRect(); if (r.height > 10) { this.pillH = r.height; this.pillW = r.width; } }
    const pillH = this.pillH || 96, pillW = this.pillW || 560;
    put(this.api, { y: lerp(483 - pillH / 2, 150, stackIn) - stackOut * 40, o: (apiIn > 0 ? 1 : 0) * (1 - stackOut) });
    this.apiPill.style.clipPath = `inset(${((1 - apiIn) * 50).toFixed(2)}% 0 ${((1 - apiIn) * 50).toFixed(2)}% 0 round 18px)`;
    const shrink = prog(t, -0.3, 0.45, E.inOutCubic);
    put(this.handIn, { sx: lerp(1, pillW / 1000, shrink), o: (1 - prog(t, 0.2, 0.3)) * (t < 0.6 ? 1 : 0) });
    this.strike.style.transform = `scaleX(${prog(t, cStack + 0.35, 0.45, E.inOutCubic).toFixed(3)})`;
    this.apiPill.style.opacity = (1 - 0.45 * prog(t, cStack + 0.4, 0.5)).toFixed(3);
    this.stack.forEach((el, i) => {
      const q = prog(t, cStack + 0.12 + i * 0.1, 0.5, E.outCubic);
      const collapse = stackOut;
      put(el, { x: 0, y: lerp(300 + i * 86 + 40, 300 + i * 86, q) + collapse * (i - 2.5) * -60, s: lerp(0.96, 1, q) * (1 - collapse * 0.15), o: q * (1 - collapse) });
    });
    put(this.stackLabel, { y: 262, o: prog(t, cStack + 0.1, 0.4) * (1 - stackOut) });

    // ---------- feed frame timing
    const egoA = env(t, cVS - 0.3, cDet + 0.05, 0.45, 0.12);
    const roomA = env(t, cDet - 0.05, cTrk + 0.08, 0.12, 0.2);
    const trkA = env(t, cTrk - 0.05, cDs + 0.25, 0.2, 0.35);
    const dsA = env(t, cDs - 0.1, cTr + 0.25, 0.3, 0.35);
    const chA = env(t, cTr - 0.05, cRb + 0.2, 0.3, 0.35);
    const rbA = env(t, cRb - 0.1, D + 1, 0.4, 0.01) * (1 - prog(t, D - 0.55, 0.5, E.inCubic));
    const frameClip = (a, punch) => {
      g.save();
      g.globalAlpha = a;
      const s = 1 + punch * 0.03;
      g.translate(960, 531); g.scale(s, s); g.translate(-960, -531);
      rrect(g, FRAME.x, FRAME.y, FRAME.w, FRAME.h, 18); g.clip();
    };
    if (egoA > 0.001) {
      frameClip(egoA, 1 - prog(t, cVS - 0.3, 0.6, E.outCubic));
      const lt = t - cVS + 0.3;
      drawEgo(g, lt, (hands) => {
        const ov = prog(t, cVS + 0.35, 0.9, E.outCubic);
        hands.forEach((hd, i) => {
          const bb = bbox(hd.P, 26);
          const col = hd.w === 'L' ? C.sky : C.coral;
          box(g, bb.x, bb.y, bb.w, bb.h, { color: col, a: clamp(ov * 3 - i * 0.4), lw: 1.6 });
          tag(g, bb.x, bb.y - 6, hd.w === 'L' ? 'HAND · LEFT' : 'HAND · RIGHT', { bg: col, a: clamp(ov * 3 - i * 0.4), size: 12 });
          drawPose(g, hd.P, { alpha: clamp(ov * 2), p: clamp(ov * 1.3 - i * 0.2), r: 5.5, lw: 2.8 });
        });
      });
      g.restore();
      g.save(); g.globalAlpha = egoA;
      recHud(g, FRAME.x + 28, FRAME.y + 24, 'EGO CAM', t - cVS + 4.2);
      tag(g, FRAME.x + FRAME.w - 28, FRAME.y + 48, 'HAND DETECTION · 21 KEYPOINTS', { bg: null, fg: 'rgba(255,255,255,0.7)', size: 12, anchor: 'br', pad: 0 });
      brackets(g, FRAME.x + 16, FRAME.y + 16, FRAME.w - 32, FRAME.h - 32, { a: 0.35, len: 30 });
      g.restore();
    }
    if (roomA > 0.001) {
      frameClip(roomA, 1 - prog(t, cDet - 0.05, 0.5, E.outCubic));
      const fa = prog(t, cDet + 0.15, 0.7, E.outCubic);
      drawRoom(g, t, fa, prog(t, cDet + 0.8, 0.35, E.inOutCubic));
      g.restore();
      g.save(); g.globalAlpha = roomA; recHud(g, FRAME.x + 28, FRAME.y + 24, 'EGO CAM', t - cVS + 4.2); tag(g, FRAME.x + FRAME.w - 28, FRAME.y + 48, 'FACE DETECTION · PRIVACY FILTER', { bg: null, fg: 'rgba(255,255,255,0.7)', size: 12, anchor: 'br', pad: 0 }); g.restore();
    }
    // frame border
    const anyFeed = Math.max(egoA, roomA);
    if (anyFeed > 0.001) { g.save(); g.globalAlpha = anyFeed; g.strokeStyle = 'rgba(255,255,255,0.14)'; g.lineWidth = 1; rrect(g, FRAME.x + 0.5, FRAME.y + 0.5, FRAME.w, FRAME.h, 18); g.stroke(); g.restore(); }

    // ---------- D: camera + wrist tracking
    drawTracking(g, t, prog(t, cTrk - 0.1, cDs - cTrk + 0.6, E.linear) * 0.9 + 0.05, trkA);
    if (trkA > 0.001) tag(g, 200, 200, 'CAMERA + WRIST TRACKING · 3D', { a: trkA, bg: null, fg: 'rgba(255,255,255,0.7)', size: 13, anchor: 'bl', pad: 0 });

    // ---------- E: dataset wall
    if (dsA > 0.001) {
      const A = this.atlas;
      const zoom = lerp(1.9, 0.62, prog(t, cDs - 0.1, cTr - cDs + 0.3, E.inOutCubic));
      g.save(); g.globalAlpha = dsA;
      const tw = A.TW * zoom, th = A.TH * zoom;
      const cols = Math.ceil(1920 / tw) + 2, rows = Math.ceil(1080 / th) + 2;
      const ox = 960 - (cols / 2) * tw, oy = 540 - (rows / 2) * th;
      for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++) {
        const k = (i * 7 + j * 3) % (A.COLS * A.ROWS);
        const sx = (k % A.COLS) * A.TW, sy = Math.floor(k / A.COLS) * A.TH;
        const appear = clamp((t - cDs + 0.1) * 4 - ((i + j * 1.7) % 9) * 0.12);
        if (appear <= 0) continue;
        g.globalAlpha = dsA * appear * (0.45 + 0.55 * (1 - Math.abs((i + 0.5) / cols - 0.45)));
        g.drawImage(A.c, sx, sy, A.TW, A.TH, ox + i * tw, oy + j * th, tw, th);
      }
      g.restore();
      const vg = g.createLinearGradient(0, 0, 1920, 0);
      vg.addColorStop(0, 'rgba(7,8,10,0.2)'); vg.addColorStop(0.62, 'rgba(7,8,10,0.35)'); vg.addColorStop(0.72, 'rgba(7,8,10,0.92)'); vg.addColorStop(1, 'rgba(7,8,10,0.96)');
      g.save(); g.globalAlpha = dsA; g.fillStyle = vg; g.fillRect(0, 0, 1920, 1080); g.restore();
    }
    put(this.dsPanel, { x: (1 - prog(t, cDs + 0.05, 0.5, E.outCubic)) * 40, o: dsA * prog(t, cDs + 0.05, 0.5) });

    // ---------- F: training + benchmark
    if (chA > 0.001) { g.save(); g.fillStyle = `rgba(7,8,10,${(0.85 * chA).toFixed(3)})`; g.fillRect(0, 0, 1920, 1080); g.restore(); }
    drawCharts(g, t, chA, prog(t, cTr, cRb - cTr - 0.2, E.inOutSine));

    // ---------- G: robot replays the human demonstration
    const hand = { a: env(t, cRb - 0.1, cRb + 1.6, 0.3, 0.4), u: prog(t, cRb, 1.3, E.inOutSine) };
    drawRobot(g, t, rbA, prog(t, cRb + 1.1, 2.6, E.inOutSine), hand);
    if (rbA > 0.001) tag(g, 200, 200, 'DATA PIPELINES FOR ROBOTICS', { a: rbA, bg: null, fg: 'rgba(255,255,255,0.7)', size: 13, anchor: 'bl', pad: 0 });
  },
});
