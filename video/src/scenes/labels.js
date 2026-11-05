// 05 — Dispatch · Crate labeling.
// First the leak, without AI: a crate carrying the wrong label reaches the wrong store and is REJECTED
// (fine + product + freight). Then with AI: a camera gantry recognizes every crate, checks it against the
// order, the applicator prints and applies the right label, each crate routes to its store dock and the
// one mismatch is held back → formula: Rejections avoided × (Fine + Product + Freight).
import { addScene, h, put, prog, E, clamp, lerp, env, makeCanvas, rgba, C, hash, rrect, W, H } from '../engine.js';
import { makeHud, box, tag } from '../lib/ui.js';
import { seg, cueOr } from '../lib/vo.js';
import { EQUATIONS, stationIndex } from '../lib/impact-data.js';
import { makeEquation, eqTimes, dockStart } from '../lib/equation.js';
import { mapDot, drawLine, CHAIN } from '../lib/chain.js';
import { makeOutcome, exitLine, fmt } from '../lib/chapter.js';
import { crateSprite } from '../lib/produce.js';
import { drawRollers } from '../lib/conveyor.js';
import { drawIcon } from '../lib/icons.js';

const Y = CHAIN.y;                     // conveyor centreline = the hand-off line
const X0 = 150, SORT_X = 1250, DOCK_X = 1600;
const CAM_X = 640, CHECK_X = 820, LABEL_X = 1010, HOLD_X = 1130;
const STORES = [
  { name: 'STORE A', col: '#6686f6', y: 300 },
  { name: 'STORE B', col: '#3ed6b8', y: 540 },
  { name: 'STORE C', col: '#ff8fc8', y: 780 },
];
const V = 230, CW = 250, CHh = 164;   // crate speed and drawn size
const PRODUCTS = [{ name: 'ICEBERG', n: 8, kind: 'iceberg' }, { name: 'ROMAINE', n: 6, kind: 'romaine' }];

// distance → position along a crate's route (straight to the sorter, diagonal to its dock, into the dock)
function routePos(s, store, held) {
  if (held) {
    if (s < HOLD_X - X0 + 200) return { x: X0 - 200 + s, y: Y, a: 0 };
    const u = clamp((s - (HOLD_X - X0 + 200)) / 230);
    return { x: HOLD_X, y: lerp(Y, Y + 230, E.inOutCubic(u)), a: 0 };
  }
  const L1 = SORT_X - X0 + 200;
  if (s < L1) return { x: X0 - 200 + s, y: Y, a: 0 };
  const yd = STORES[store].y;
  const dx = 220, dy = yd - Y, L2 = Math.hypot(dx, dy);
  if (s < L1 + L2) { const u = (s - L1) / L2; return { x: SORT_X + dx * u, y: Y + dy * u, a: Math.atan2(dy, dx) * 0.35 }; }
  return { x: SORT_X + dx + (s - L1 - L2), y: yd, a: 0 };
}

addScene({
  id: 'labels',
  pre: 0.3,
  post: 0.5,
  setup(ctx) {
    const R = ctx.root;
    this.cv = makeCanvas(R);
    this.g = this.cv.ctx;
    this.crates = { iceberg: [crateSprite('iceberg', 61), crateSprite('iceberg', 62)], romaine: [crateSprite('romaine', 63), crateSprite('romaine', 64)] };
    const def = EQUATIONS.labels;
    this.times = eqTimes(ctx, def);
    this.dockAt = dockStart(def) - ctx.start;
    this.dock = mapDot(stationIndex('labels'));
    this.cWrong = seg(ctx, 'b1', 1);
    this.cFine = seg(ctx, 'b1', 2);
    this.cAI = seg(ctx, 'b2', 0);
    this.cCheck = seg(ctx, 'b2', 1);
    this.cLabel = seg(ctx, 'b2', 2);
    this.cHold = seg(ctx, 'b2', 3);
    this.cOut = cueOr(ctx, 'b3', () => this.times[0] - 2.2);
    this.cReject = this.cWrong + 1.45;
    this.aiAt = this.cAI - 0.4;
    // crates in the AI pass: index k, spawn time, product, store; one mismatch reaches the hold pusher on cue
    this.crate = (k) => {
      const prod = hash(k, 3) < 0.55 ? 0 : 1;
      const store = Math.floor(hash(k, 5) * 3);
      return { k, prod, store, t0: this.aiAt - 3.2 + k * 1.25, held: false, v: k % 2 };
    };
    const holdDist = HOLD_X - X0 + 200;
    this.heldK = Math.round((this.cHold + 0.2 - holdDist / V - (this.aiAt - 3.2)) / 1.25);
    this.hud = makeHud(ctx, {
      num: '05', title: 'Dispatch · Crate labeling', badge: 'Vision + automation',
      steps: [
        { label: 'Recognize', at: this.cAI + 0.2 },
        { label: 'Check', at: this.cCheck },
        { label: 'Label', at: this.cLabel },
        { label: 'Route', at: this.cHold },
      ],
    });
    // the cost of one rejection (stays as a reference card; the formula's bracket flies out of it)
    this.cost = h('div', { class: 'panel', style: { left: '150px', top: '128px', padding: '16px 20px', background: 'rgba(20,10,9,0.9)', borderColor: 'rgba(255,107,87,0.45)', zIndex: '20' } },
      h('div', { class: 'kicker', style: { fontSize: '11px', color: 'var(--coral)', marginBottom: '12px' } }, 'One rejection costs'),
      h('div', { style: { display: 'flex', gap: '10px', alignItems: 'center' } }, ...['Fine', 'Product', 'Freight'].map((x, i) => h('span', { class: 'ix-chip', style: { background: 'rgba(255,107,87,0.16)', color: '#ffb3a8', border: '1px solid rgba(255,107,87,0.45)' } }, x))));
    this.costChips = [...this.cost.querySelectorAll('.ix-chip')];
    R.append(this.cost);
    this.stats = h('div', { class: 'panel', style: { left: '560px', top: '128px', display: 'flex', gap: '34px', alignItems: 'center', padding: '14px 26px', background: 'rgba(12,14,17,0.92)', zIndex: '20' } });
    const st = (k, col) => { const v = h('span', { class: 'tnum', style: { fontSize: '22px', color: col || 'var(--text)' } }, '0'); return { el: h('div', { style: { display: 'flex', flexDirection: 'column', gap: '4px' } }, h('span', { class: 'kicker', style: { fontSize: '10.5px' } }, k), v), v, last: '' }; };
    this.sLab = st('Labeled', 'var(--accent-text)');
    this.sChk = st('Order checks', 'var(--accent-text)');
    this.sHeld = st('Held back', 'var(--coral)');
    this.sRej = st('Rejections');
    this.stats.append(h('div', { style: { fontSize: '16px', fontWeight: '600', width: '110px', lineHeight: '1.3' } }, 'Dispatch', h('br'), h('span', { class: 'kicker', style: { fontSize: '10.5px', color: 'var(--coral)' } }, '● Live')), this.sLab.el, this.sChk.el, this.sHeld.el, this.sRej.el);
    R.append(this.stats);
    this.outcome = makeOutcome(R, [
      { text: 'Fewer rejections', dir: 'down' },
      { text: 'Fewer returns', dir: 'down' },
      { text: 'Less product lost', dir: 'down' },
    ], { y: 806 });
    this.eq = makeEquation(R, def);
  },

  drawStage(g, t, a, ghost) {
    g.save(); g.globalAlpha *= a;
    drawRollers(g, t, X0 - 40, SORT_X + 30, Y - 105, 210, { speed: ghost ? 120 : 160 });
    // sorter lanes to the docks
    STORES.forEach((s) => {
      // lane: a dark roller strip with thin guide rails
      g.save();
      g.strokeStyle = '#0f1216'; g.lineWidth = 186; g.lineJoin = 'round';
      g.beginPath(); g.moveTo(SORT_X - 10, Y); g.lineTo(SORT_X + 220, s.y); g.lineTo(DOCK_X, s.y); g.stroke();
      g.strokeStyle = 'rgba(255,255,255,0.05)'; g.lineWidth = 1.5; g.setLineDash([2, 14]);
      g.beginPath(); g.moveTo(SORT_X - 10, Y); g.lineTo(SORT_X + 220, s.y); g.lineTo(DOCK_X, s.y); g.stroke(); g.setLineDash([]);
      g.restore();
      // dock door
      g.fillStyle = '#0d1014'; g.strokeStyle = 'rgba(255,255,255,0.18)'; g.lineWidth = 1.5;
      rrect(g, DOCK_X, s.y - 95, 170, 190, 14); g.fill(); g.stroke();
      g.fillStyle = s.col; rrect(g, DOCK_X, s.y - 95, 170, 10, 4); g.fill();
      for (let i = 0; i < 6; i++) { g.fillStyle = 'rgba(255,255,255,0.05)'; g.fillRect(DOCK_X + 14, s.y - 70 + i * 26, 142, 14); }
      drawIcon(g, 'truck', DOCK_X + 85, s.y + 6, 54, { color: rgba(s.col, 0.9), lw: 1.6 });
      tag(g, DOCK_X + 85, s.y + 66, s.name, { bg: null, fg: s.col, size: 13, anchor: 'c', pad: 0, track: 0.16 });
    });
    g.restore();
  },

  drawCrate(g, x, y, ang, kind, v, label, a = 1) {
    g.save(); g.globalAlpha *= a; g.translate(x, y); g.rotate(ang);
    g.drawImage(this.crates[kind][v], -CW / 2, -CHh / 2, CW, CHh);
    if (label) {
      const s = STORES[label.store];
      const lw = 58, lh = 96, lx = CW / 2 - lw - 4, ly = -lh / 2 + (label.drop || 0);
      g.globalAlpha *= label.a ?? 1;
      g.fillStyle = '#f6f6f2'; rrect(g, lx, ly, lw, lh, 4); g.fill();
      g.fillStyle = label.wrong ? '#ff6b57' : s.col; g.fillRect(lx, ly, lw, 14);
      g.fillStyle = '#16181c';
      for (let i = 0; i < 16; i++) g.fillRect(lx + 7 + i * 2.8, ly + 52, i % 3 === 0 ? 1.8 : 1, 30);
      g.font = '800 26px Manrope, sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle';
      g.fillText(s.name.slice(-1), lx + lw / 2, ly + 33);
    }
    g.restore();
  },

  render(t, ctx) {
    const g = this.g;
    g.clearRect(0, 0, W, H);
    const D = ctx.dur;
    const eqLevel = this.eq.level(t, { times: this.times, dockAt: this.dockAt });
    this.hud(t, { hideSteps: eqLevel > 0.25 });

    // ================= A: without AI (ghost): the wrong crate reaches the wrong store
    const ghostA = env(t, 0.0, this.aiAt + 0.2, 0.5, 0.6);
    if (ghostA > 0.001) {
      g.save(); g.filter = 'saturate(0.35) brightness(0.8)';
      this.drawStage(g, t, ghostA * 0.9, true);
      g.restore();
      const s = 700 + Math.max(0, t) * 330;
      const p = routePos(s, 1, false);
      const arrived = p.x > DOCK_X - 20;
      const x = Math.min(p.x, DOCK_X - 20);
      g.save(); g.filter = 'saturate(0.5)';
      this.drawCrate(g, x, p.y, p.a, 'romaine', 0, { store: 1, wrong: false }, ghostA);
      g.restore();
      const rej = prog(t, this.cReject, 0.35, E.outBack);
      if (rej > 0) {
        g.save(); g.globalAlpha = ghostA; g.translate(x, p.y); g.rotate(-0.14); g.scale(lerp(1.8, 1, Math.min(1, rej)), lerp(1.8, 1, Math.min(1, rej)));
        g.strokeStyle = C.coral; g.lineWidth = 5; rrect(g, -150, -40, 300, 80, 10); g.stroke();
        g.fillStyle = rgba(C.coral, 0.18); rrect(g, -150, -40, 300, 80, 10); g.fill();
        g.font = '800 46px Archivo, sans-serif'; g.letterSpacing = '0.12em'; g.fillStyle = C.coral; g.textAlign = 'center'; g.textBaseline = 'middle';
        g.fillText('REJECTED', 0, 3);
        g.restore();
        tag(g, x - 120, p.y + 130, 'ROMAINE FOR STORE C · LABELED STORE B', { bg: '#0b0d10', fg: '#ffb3a8', stroke: rgba(C.coral, 0.6), a: ghostA * prog(t, this.cReject + 0.3, 0.4), size: 11.5 });
      }
      tag(g, 150, 250, 'WITHOUT AI', { bg: 'rgba(255,255,255,0.1)', fg: 'rgba(255,255,255,0.8)', a: ghostA * prog(t, 0.3, 0.4), size: 12, track: 0.18 });
      if (t >= 0) drawLine(g, CHAIN.x0, CHAIN.x1, CHAIN.y, { a: 1 - prog(t, 0.05, 0.5) });
    }
    // cost card: appears with "…and a fine", stays as the reference until the formula takes its chips
    const costA = env(t, this.cFine - 0.1, this.dockAt - 0.2, 0.35, 0.5);
    put(this.cost, { y: (1 - prog(t, this.cFine - 0.1, 0.45, E.outCubic)) * 14, o: costA });
    this.costChips.forEach((c, i) => { const q = prog(t, this.cFine + i * 0.18, 0.35, E.outBack); c.style.opacity = clamp(q * 2).toFixed(3); c.style.transform = `scale(${lerp(0.7, 1, Math.min(1.06, q)).toFixed(3)})`; });

    // ================= B: with AI
    const aiA = prog(t, this.aiAt, 0.6) * (1 - prog(t, this.dockAt - 0.7, 1.0, E.inOutSine));
    let labeled = 0, checked = 0;
    if (aiA > 0.001) {
      this.drawStage(g, t, aiA, false);
      // camera gantry + labeler
      g.save(); g.globalAlpha = aiA;
      const bm = g.createLinearGradient(CAM_X - 14, 0, CAM_X + 14, 0);
      bm.addColorStop(0, '#2a2f35'); bm.addColorStop(0.5, '#6b737b'); bm.addColorStop(1, '#23272c');
      g.fillStyle = bm; g.fillRect(CAM_X - 14, Y - 190, 28, 380);
      const sb = g.createLinearGradient(CAM_X, 0, CAM_X + 80, 0);
      sb.addColorStop(0, rgba(C.accent, 0.3)); sb.addColorStop(1, rgba(C.accent, 0));
      g.fillStyle = sb; g.fillRect(CAM_X + 14, Y - 105, 80, 210);
      g.fillStyle = '#0d0f12'; g.strokeStyle = C.accent; g.lineWidth = 2; rrect(g, CAM_X - 30, Y - 214, 60, 44, 8); g.fill(); g.stroke();
      g.fillStyle = C.accent; g.beginPath(); g.arc(CAM_X, Y - 192, 7, 0, Math.PI * 2); g.fill();
      tag(g, CAM_X + 40, Y - 192, 'CAMERA', { bg: null, fg: 'rgba(255,255,255,0.75)', size: 11, anchor: 'c', pad: 0 });
      // print-and-apply labeler (arm comes down when a crate passes)
      g.fillStyle = '#1a1e23'; g.strokeStyle = 'rgba(255,255,255,0.22)'; g.lineWidth = 1.5;
      rrect(g, LABEL_X + 60, Y - 250, 120, 92, 10); g.fill(); g.stroke();
      tag(g, LABEL_X + 120, Y - 270, 'PRINT & APPLY', { bg: null, fg: 'rgba(255,255,255,0.75)', size: 11, anchor: 'c', pad: 0 });
      g.restore();
      // crates
      let armDown = 0;
      for (let k = 0; k < 16; k++) {
        const c = this.crate(k);
        const held = k === this.heldK;
        const s = (t - c.t0) * V;
        if (s < 0) continue;
        const p = routePos(s, c.store, held);
        if (p.x > DOCK_X + 30) continue;
        const pr = PRODUCTS[c.prod];
        const pastCam = p.x > CAM_X + 10, pastCheck = p.x > CHECK_X, pastLabel = p.x > LABEL_X + 120;
        if (pastCheck) checked++;
        if (pastLabel && !held) labeled++;
        const near = clamp(1 - Math.abs(p.x - (LABEL_X + 120)) / 70);
        armDown = Math.max(armDown, near);
        const drop = pastLabel ? 0 : -120 * (1 - near);
        const lab = (p.x > LABEL_X + 50 && !held) ? { store: c.store, a: clamp((p.x - LABEL_X - 50) / 70), drop: pastLabel ? 0 : drop * 0.4 } : null;
        const intoDock = clamp((p.x - DOCK_X + 60) / 80);
        this.drawCrate(g, p.x, p.y, p.a, pr.kind, c.v, lab, aiA * (1 - intoDock));
        // recognition + order check overlays
        if (pastCam && p.x < DOCK_X - 40) {
          const oa = aiA * prog(t, this.cAI - 0.1, 0.4) * clamp((p.x - CAM_X) / 60);
          const col = held && pastCheck ? C.coral : C.accent;
          box(g, p.x - CW / 2 - 6, p.y - CHh / 2 - 6, CW + 12, CHh + 12, { color: col, a: oa, lw: 1.6, fill: 0.03 });
          tag(g, p.x - CW / 2 - 6, p.y - CHh / 2 - 9, `${pr.name} · ${pr.n} HEADS`, { bg: rgba(col, 0.92), fg: held && pastCheck ? '#1d0905' : '#fff', a: oa, size: 11 });
          if (pastCheck && t > this.cCheck - 0.2) {
            const ca = oa * prog(p.x, CHECK_X, 60);
            const txt = held ? 'MISMATCH · HELD' : `ORDER ${4460 + k} · ${STORES[c.store].name} ✓`;
            tag(g, p.x - CW / 2 - 6, p.y + CHh / 2 + 34, txt, { bg: held ? C.coral : '#0b0d10', fg: held ? '#1d0905' : STORES[c.store].col, stroke: held ? null : rgba(STORES[c.store].col, 0.6), a: ca, size: 11.5 });
          }
        }
      }
      // labeler arm
      g.save(); g.globalAlpha = aiA;
      g.fillStyle = '#7a828a'; g.fillRect(LABEL_X + 112, Y - 160, 16, 40 + armDown * 60);
      g.fillStyle = '#0d0f12'; g.strokeStyle = C.accent; g.lineWidth = 2; rrect(g, LABEL_X + 92, Y - 124 + armDown * 60, 56, 30, 6); g.fill(); g.stroke();
      g.restore();
      // hold lane marker
      const ha = aiA * prog(t, this.cHold - 0.4, 0.4);
      if (ha > 0) {
        g.save(); g.globalAlpha = ha; g.strokeStyle = rgba(C.coral, 0.75); g.setLineDash([8, 6]); g.lineWidth = 2;
        rrect(g, HOLD_X - CW / 2 - 20, Y + 230 - CHh / 2 - 20, CW + 40, CHh + 40, 14); g.stroke(); g.setLineDash([]); g.restore();
        tag(g, HOLD_X - CW / 2 - 20, Y + 230 + CHh / 2 + 44, 'HOLD · CHECK BEFORE DISPATCH', { bg: null, fg: C.coral, size: 11, pad: 0, a: ha, anchor: 'bl' });
      }
      tag(g, 150, 250, 'WITH AI', { bg: rgba(C.accent, 0.9), a: aiA * prog(t, this.aiAt + 0.3, 0.4), size: 12, track: 0.18 });
    }
    const sA = env(t, this.cCheck, this.dockAt - 0.3, 0.45, 0.6);
    put(this.stats, { y: (1 - prog(t, this.cCheck, 0.5, E.outCubic)) * -14, o: sA });
    const setv = (s, v) => { if (s.last !== v) { s.v.textContent = v; s.last = v; } };
    setv(this.sLab, fmt(3120 + labeled)); setv(this.sChk, fmt(3121 + checked)); setv(this.sHeld, t > this.cHold + 0.6 ? '1' : '0'); setv(this.sRej, '0');

    this.outcome.render(t, this.cOut - 0.1, this.times[0] - 0.5);
    const chipSrc = (i) => () => ({ x: 150 + 20 + 44 + i * 108, y: 128 + 62, w: 90 });
    this.eq.render(t, {
      times: this.times, dockAt: this.dockAt, dock: this.dock,
      from: { 0: () => ({ x: HOLD_X, y: Y + 230, w: 260 }), 3: chipSrc(0), 5: chipSrc(1), 7: chipSrc(2) },
    });
    exitLine(g, t, D);
  },
});
