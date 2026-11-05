// Open — six small leaks flash by (three named by the VO, three on music hits), snap into a 3×2 grid and
// collapse into one line; "Impact isn't a promise." → "It's measured." (promise decodes into measured);
// the Eagerworks lockup and a ghost impact indicator (what changes × what it's worth); the line becomes
// the value chain, from seed to shelf, and shrinks into the chain map as the first chapter opens.
import { addScene, h, put, prog, E, clamp, lerp, env, makeCanvas, rgba, C, hash, rrect, W, H, FPS } from '../engine.js';
import { decode, tag, box } from '../lib/ui.js';
import { has, seg, lineStart, lineEnd } from '../lib/vo.js';
import { makeLockup } from '../lib/logo.js';
import { CHAIN, MAP, BIG, drawLine, neighbors, makeValueChain } from '../lib/chain.js';
import { STATIONS, stationIndex } from '../lib/impact-data.js';
import { exitLine } from '../lib/chapter.js';
import { seedlingSprite, traySprite, crateSprite, onionSprite } from '../lib/produce.js';
import { pumpkinSprite } from '../lib/field.js';
import { icon } from '../lib/icons.js';
import '../lib/impact-theme.js';

const GRID = [[-600, -190], [0, -190], [600, -190], [-600, 190], [0, 190], [600, 190]];

addScene({
  id: 'impact-open',
  pre: 0,
  post: 0.4,
  setup(ctx) {
    const R = ctx.root;
    this.cv = makeCanvas(R);
    this.g = this.cv.ctx;
    this.tray = traySprite(6, 4, 130, 21);
    this.seed = Array.from({ length: 8 }, (_, i) => seedlingSprite(500 + i, 150, 0.9 + hash(i, 2) * 0.3));
    this.crate = crateSprite('romaine', 71);
    this.onion = onionSprite(733, 360);
    this.pumpkin = [pumpkinSprite('orange', 3), pumpkinSprite('deep', 5), pumpkinSprite('orange', 8)];
    // cues
    this.c1 = seg(ctx, 'x1', 0); this.c2 = seg(ctx, 'x2', 0); this.c3 = seg(ctx, 'x3', 0);
    this.e3 = lineEnd(ctx, 'x3');
    this.cNot = seg(ctx, 'x4', 0); this.cFormula = seg(ctx, 'x4', 1);
    this.hasX5 = has('x5');
    this.cEw = this.hasX5 ? seg(ctx, 'x5', 0) : null;
    this.cMeasure = this.hasX5 ? seg(ctx, 'x5', 1) : null;
    this.cSeason = seg(ctx, 'x6', 0); this.cShelf = seg(ctx, 'x6', 1);
    const gap = this.cNot - this.e3;
    this.fl = [0, 1, 2].map((i) => this.e3 + 0.05 + i * Math.min(0.32, (gap - 0.9) / 3));
    this.gridAt = this.fl[2] + 0.3;
    this.collapseAt = this.gridAt + 0.32;
    // next station (nursery in the film, field in the teaser)
    const { next } = neighbors(ctx);
    this.nextIdx = Math.max(0, stationIndex(next));

    // ---- typography
    this.t1 = h('div', { class: 'abs display', style: { left: '0', width: '1920px', top: '392px', textAlign: 'center', fontSize: '112px', fontWeight: '600', letterSpacing: '-0.02em', lineHeight: '1', whiteSpace: 'nowrap' } });
    this.t1a = h('span', {}, 'Impact isn’t ');
    this.t1b = h('span', { style: { position: 'relative', display: 'inline-block', color: 'var(--text2)' } }, 'a promise');
    this.u1 = h('i', { style: { position: 'absolute', left: '-4px', right: '-4px', top: '108%', height: '6px', background: 'var(--text2)', transformOrigin: '0 50%', display: 'block', borderRadius: '3px' } });
    this.t1b.append(this.u1);
    this.t1.append(this.t1a, this.t1b, h('span', {}, '.'));
    this.t2 = h('div', { class: 'abs display', style: { left: '0', width: '1920px', top: '560px', textAlign: 'center', fontSize: '112px', fontWeight: '600', letterSpacing: '-0.02em', lineHeight: '1', whiteSpace: 'nowrap' } });
    this.t2a = h('span', {}, 'It’s ');
    this.t2b = h('span', { style: { position: 'relative', display: 'inline-block', color: 'var(--accent)' } }, 'measured');
    this.u2 = h('i', { style: { position: 'absolute', left: '-4px', right: '-4px', top: '108%', height: '6px', background: 'var(--accent)', boxShadow: '0 0 18px rgba(130,52,254,0.6)', transformOrigin: '0 50%', display: 'block', borderRadius: '3px' } });
    this.t2b.append(this.u2);
    this.t2.append(this.t2a, this.t2b, h('span', {}, '.'));
    R.append(this.t1, this.t2);
    // ---- ghost impact indicator: what changes × what it's worth
    this.ghost = h('div', { class: 'abs', style: { left: '0', width: '1920px', top: '706px', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '20px' } });
    const slot = (txt, ai) => h('div', { style: { display: 'flex', alignItems: 'center', height: '66px', padding: '0 28px', borderRadius: '16px', border: `1.5px dashed ${ai ? 'rgba(160,120,255,0.75)' : 'rgba(255,255,255,0.35)'}`, color: ai ? '#d9caff' : 'var(--text2)', fontFamily: 'var(--font-ui)', fontWeight: '600', fontSize: '26px', minWidth: '210px', justifyContent: 'center' } }, h('span', {}, txt));
    this.gSlots = [slot('What changes', true), slot('What it’s worth', false)];
    const op = (s) => h('div', { style: { fontFamily: 'var(--font-ui)', fontWeight: '300', fontSize: '44px', color: 'var(--text2)' } }, s);
    this.gItems = [this.gSlots[0], op('×'), this.gSlots[1]];
    this.gItems.forEach((x) => this.ghost.append(x));
    this.gKick = h('div', { class: 'abs ix-kicker', style: { left: '0', width: '1920px', textAlign: 'center', top: '672px', fontSize: '14px' } }, 'Impact indicator');
    R.append(this.gKick);
    R.append(this.ghost);
    // ---- lockup (static here; the build is saved for the close)
    this.lock = makeLockup({ height: 70 });
    this.lock.set({ strokes: 1, outline: 1, fill: 1, letters: 1, studio: 1 });
    this.lock.el.style.position = 'relative';
    this.lockWrap = h('div', { class: 'abs', style: { left: '0', top: '0' } }, this.lock.el);
    R.append(this.lockWrap);
    this.kickEw = h('div', { class: 'abs kicker', style: { left: '0', width: '1920px', textAlign: 'center', top: '548px', fontSize: '15px', letterSpacing: '0.24em', color: 'var(--text2)' } }, 'Every AI project starts with how impact is measured');
    R.append(this.kickEw);
    // ---- value chain
    this.chain = makeValueChain(R);
    this.kickChain = h('div', { class: 'abs kicker', style: { left: '0', width: '1920px', textAlign: 'center', top: '400px', fontSize: '16px', letterSpacing: '0.3em', color: 'var(--accent-text)' } }, 'From seed to shelf');
    this.kickSub = h('div', { class: 'abs', style: { left: '0', width: '1920px', textAlign: 'center', top: '700px', fontSize: '22px', fontWeight: '500', color: 'var(--text2)' } }, 'One grower · one season · six indicators');
    R.append(this.kickChain, this.kickSub);
  },

  // vignette k drawn in full-frame coordinates (the slot transform scales it)
  vignette(g, k, t) {
    if (k === 0) { // a seedling that never comes up
      const tw = this.tray.w, th = this.tray.h;
      const s = lerp(1.0, 1.06, prog(t, this.c1 - 0.2, 2.2, E.linear));
      g.save(); g.translate(960, 540); g.scale(s, s); g.translate(-tw / 2, -th / 2);
      g.drawImage(this.tray.c, 0, 0);
      for (let j = 0; j < 4; j++) for (let i = 0; i < 6; i++) {
        if (i === 3 && j === 1) continue;
        const cx = this.tray.m + (i + 0.5) * 130, cy = this.tray.m + (j + 0.5) * 130;
        g.drawImage(this.seed[(i + j * 3) % 8], cx - 75, cy - 75, 150, 150);
      }
      const ex = this.tray.m + 3.5 * 130, ey = this.tray.m + 1.5 * 130;
      const pulse = 0.5 + 0.5 * Math.sin(t * 7);
      g.strokeStyle = rgba(C.coral, 0.9); g.lineWidth = 4; g.setLineDash([10, 8]);
      g.beginPath(); g.arc(ex, ey, 52 + pulse * 6, 0, Math.PI * 2); g.stroke(); g.setLineDash([]);
      g.restore();
      tag(g, 960 - tw / 2 * s + this.tray.m * s + 3.5 * 130 * s + 70, 540 - th / 2 * s + (this.tray.m + 1.5 * 130) * s - 40, 'NEVER CAME UP', { bg: C.coral, fg: '#1d0905', size: 18, pad: 10 });
    } else if (k === 1) { // a harvest that misses the order
      const x0 = 420, x1 = 1500, yb = 760, hgt = 420;
      const sup = [0.5, 0.62, 0.48, 0.3, 0.44, 0.7, 0.86], ord = [0.56, 0.6, 0.64, 0.66, 0.62, 0.6, 0.58];
      const p = prog(t, this.c2 - 0.15, 1.1, E.outCubic);
      const X = (i) => lerp(x0, x1, i / 6);
      g.strokeStyle = 'rgba(255,255,255,0.18)'; g.lineWidth = 2; g.beginPath(); g.moveTo(x0, yb); g.lineTo(x1, yb); g.stroke();
      for (let i = 0; i < 7; i++) {
        const v = ord[i];
        g.strokeStyle = 'rgba(243,243,239,0.85)'; g.lineWidth = 3; g.setLineDash([12, 8]);
        g.beginPath(); g.moveTo(X(i) - 60, yb - v * hgt); g.lineTo(X(i) + 60, yb - v * hgt); g.stroke(); g.setLineDash([]);
        const sv = sup[i] * p;
        if (sv < v && p > 0.6) { g.fillStyle = rgba(C.coral, 0.35); g.fillRect(X(i) - 44, yb - v * hgt, 88, (v - sv) * hgt); }
        if (sv > v && p > 0.6) { g.fillStyle = rgba(C.coral, 0.2); g.fillRect(X(i) - 44, yb - sv * hgt, 88, (sv - v) * hgt); }
        g.fillStyle = rgba(C.accent, 0.85); g.fillRect(X(i) - 44, yb - Math.min(sv, v) * hgt, 88, Math.min(sv, v) * hgt);
      }
      tag(g, X(3) - 44, yb - 0.66 * hgt - 14, 'SHORT DELIVERY', { bg: C.coral, fg: '#1d0905', size: 18, pad: 10, a: prog(t, this.c2 + 0.6, 0.3) });
      tag(g, X(6) - 44, yb - 0.86 * hgt - 14, 'WASTE', { bg: '#0b0d10', fg: C.coral, stroke: rgba(C.coral, 0.7), size: 18, pad: 10, a: prog(t, this.c2 + 0.8, 0.3) });
    } else if (k === 2) { // a crate at the wrong store
      const p = prog(t, this.c3 - 0.15, 1.0, E.outCubic);
      const x = lerp(520, 1060, p);
      g.fillStyle = '#0d1014'; g.strokeStyle = 'rgba(255,255,255,0.25)'; g.lineWidth = 2; rrect(g, 1280, 330, 260, 420, 18); g.fill(); g.stroke();
      g.fillStyle = '#3ed6b8'; rrect(g, 1280, 330, 260, 14, 6); g.fill();
      tag(g, 1410, 790, 'STORE B', { bg: null, fg: '#3ed6b8', size: 22, anchor: 'c', pad: 0, track: 0.16 });
      g.save(); g.translate(x, 540); g.drawImage(this.crate, -260, -170, 520, 340); g.restore();
      const rej = prog(t, this.c3 + 0.8, 0.3, E.outBack);
      if (rej > 0) {
        g.save(); g.translate(x, 540); g.rotate(-0.14); const sc = lerp(1.7, 1, Math.min(1, rej)); g.scale(sc, sc);
        g.strokeStyle = C.coral; g.lineWidth = 8; rrect(g, -250, -62, 500, 124, 14); g.stroke();
        g.font = '800 76px Archivo, sans-serif'; g.letterSpacing = '0.12em'; g.fillStyle = C.coral; g.textAlign = 'center'; g.textBaseline = 'middle';
        g.fillText('REJECTED', 0, 4); g.restore();
      }
    } else if (k === 3) { // counted by hand
      this.pumpkin.forEach((sp, i) => g.drawImage(sp, 420 + i * 260, 360, 300, 300));
      g.strokeStyle = C.coral; g.lineWidth = 9; g.lineCap = 'round';
      for (let gI = 0; gI < 3; gI++) for (let s = 0; s < 5; s++) {
        const bx = 1180 + gI * 150, x = bx + s * 24;
        if (s < 4) { g.beginPath(); g.moveTo(x, 430); g.lineTo(x + 4, 590); g.stroke(); } else { g.beginPath(); g.moveTo(bx - 14, 560); g.lineTo(bx + 100, 450); g.stroke(); }
      }
      tag(g, 1180, 680, 'COUNTED BY HAND', { bg: C.coral, fg: '#1d0905', size: 18, pad: 10, anchor: 'tl' });
    } else if (k === 4) { // size unknown
      g.drawImage(this.onion, 960 - 300, 540 - 300, 600, 600);
      g.strokeStyle = 'rgba(243,243,239,0.85)'; g.lineWidth = 5;
      g.beginPath(); g.moveTo(740, 330); g.lineTo(740, 760); g.moveTo(1180, 330); g.lineTo(1180, 760); g.moveTo(740, 360); g.lineTo(1180, 360); g.stroke();
      tag(g, 960, 300, 'Ø ?', { bg: C.coral, fg: '#1d0905', size: 34, pad: 16, anchor: 'c' });
    } else { // a report rebuilt by hand
      g.fillStyle = '#e9e7df'; rrect(g, 560, 300, 800, 480, 14); g.fill();
      g.strokeStyle = 'rgba(28,29,25,0.18)'; g.lineWidth = 2;
      for (let r = 1; r < 9; r++) { g.beginPath(); g.moveTo(560, 300 + r * 53); g.lineTo(1360, 300 + r * 53); g.stroke(); }
      for (let c = 1; c < 6; c++) { g.beginPath(); g.moveTo(560 + c * 133, 300); g.lineTo(560 + c * 133, 780); g.stroke(); }
      tag(g, 560, 280, 'report_v7_FINAL.xlsx', { bg: '#0b0d10', fg: '#f3f3ef', stroke: 'rgba(255,255,255,0.3)', size: 20, pad: 12 });
      tag(g, 1360, 830, 'REBUILT BY HAND', { bg: C.coral, fg: '#1d0905', size: 18, pad: 10, anchor: 'br' });
    }
  },

  render(t, ctx, T) {
    const g = this.g;
    g.clearRect(0, 0, W, H);
    const D = ctx.dur;
    const grid = prog(t, this.gridAt - 0.2, 0.3, E.outCubic);
    const collapse = prog(t, this.collapseAt, 0.3, E.inCubic);

    // ---------------- opening signal line
    const lp = prog(t, 0.25, 0.7, E.inOutCubic), lo = prog(t, 0.95, 0.25);
    if (lp > 0 && lo < 1) drawLine(g, 960 - 450 * lp * (1 - lo), 960 + 450 * lp * (1 - lo), CHAIN.y, { a: 1 - lo });

    // ---------------- vignettes: solo → 3×2 grid → one line
    const solo = [
      env(t, this.c1 - 0.12, this.c2 - 0.08, 0.15, 0.12),
      env(t, this.c2 - 0.1, this.c3 - 0.08, 0.12, 0.12),
      env(t, this.c3 - 0.1, this.fl[0], 0.12, 0.1),
      env(t, this.fl[0], this.fl[1], 0.06, 0.06),
      env(t, this.fl[1], this.fl[2], 0.06, 0.06),
      env(t, this.fl[2], this.gridAt, 0.06, 0.06),
    ];
    for (let k = 0; k < 6; k++) {
      const s = lerp(1, 0.3, grid);
      const x = lerp(0, GRID[k][0], grid) * (1 - collapse), y = lerp(0, GRID[k][1], grid) * (1 - collapse);
      const a = Math.max(solo[k], grid) * (1 - collapse);
      if (a <= 0.001) continue;
      g.save(); g.globalAlpha = a;
      g.translate(960 + x, 540 + y); g.scale(s * (1 + collapse * 0.4), s * (1 - collapse * 0.97)); g.translate(-960, -540);
      if (grid > 0.01) { g.fillStyle = '#0c0e11'; g.strokeStyle = rgba(C.coral, 0.6); g.lineWidth = 4 / s; rrect(g, 0, 0, 1920, 1080, 40); g.fill(); g.stroke(); }
      this.vignette(g, k, t);
      g.restore();
    }
    // collapse → the line (music hit)
    if (collapse > 0 && t < this.cNot + 0.6) {
      const lp2 = prog(t, this.collapseAt + 0.3, 0.35, E.inOutCubic);
      const w = lerp(1600, 960, lp2) * (1 - prog(t, this.cNot - 0.05, 0.35));
      drawLine(g, 960 - w / 2, 960 + w / 2, 529, { a: collapse });
    }

    // ---------------- thesis
    const tIn = prog(t, this.cNot + 0.02, 0.5, E.outCubic);
    const tOut = prog(t, (this.hasX5 ? this.cEw : this.cSeason) - 0.7, 0.5, E.inCubic);
    this.t1.style.clipPath = `inset(${((1 - tIn) * 50).toFixed(2)}% -10% ${((1 - tIn) * 50 - tIn * 40).toFixed(2)}% -10%)`;
    put(this.t1, { y: -prog(t, this.cFormula - 0.1, 0.5, E.inOutCubic) * 50, o: tIn * (1 - tOut) * lerp(1, 0.45, prog(t, this.cFormula, 0.5)) });
    this.u1.style.transform = `scaleX(${prog(t, this.cNot + 0.4, 0.45, E.inOutCubic).toFixed(3)})`;
    const f2 = prog(t, this.cFormula - 0.1, 0.45, E.outCubic);
    put(this.t2, { y: (1 - f2) * 30 - prog(t, this.cFormula - 0.1, 0.5, E.inOutCubic) * 50, o: f2 * (1 - tOut) });
    const dp = prog(t, this.cFormula - 0.05, 0.6, E.linear);
    const frame = Math.round(T * FPS);
    this.t2b.firstChild.textContent = dp <= 0 ? 'promise' : dp >= 1 ? 'measured' : decode('promise', 'measured', dp, 11, frame);
    this.u2.style.transform = `scaleX(${prog(t, this.cFormula + 0.45, 0.5, E.inOutCubic).toFixed(3)})`;

    // ---------------- ghost formula + Eagerworks (x5); in the teaser the formula rides the thesis
    const gIn = prog(t, this.cFormula + 0.7, 0.5, E.outCubic);
    const gOut = prog(t, this.cSeason - 0.6, 0.45, E.inCubic);
    const gY = this.hasX5 ? lerp(0, -40, prog(t, this.cEw - 0.6, 0.6, E.inOutCubic)) : 0;
    put(this.ghost, { y: gY, o: gIn * (1 - gOut) });
    put(this.gKick, { y: gY, o: prog(t, this.cFormula + 0.6, 0.5) * (1 - gOut) });
    this.gItems.forEach((el, i) => { const q = prog(t, this.cFormula + 0.7 + i * 0.12, 0.4, E.outBack); el.style.opacity = clamp(q * 2).toFixed(3); el.style.transform = `scale(${lerp(0.7, 1, Math.min(1.05, q)).toFixed(3)})`; });
    if (this.hasX5) {
      if (!this.lockW) { const r = this.lock.el.getBoundingClientRect(); if (r.width > 10) this.lockW = r.width; }
      const lw = this.lockW || 900;
      const la = prog(t, this.cEw - 0.25, 0.5, E.outCubic) * (1 - gOut);
      put(this.lockWrap, { x: (1920 - lw) / 2, y: 410 + (1 - la) * 16, o: la });
      put(this.kickEw, { o: prog(t, this.cMeasure + 1.6, 0.5) * (1 - gOut), y: (1 - prog(t, this.cMeasure + 1.6, 0.5, E.outCubic)) * 10 });
      // the slots fill in as the VO says "measured"
      const fillP = prog(t, this.cMeasure + 2.4, 0.5);
      this.gSlots.forEach((s) => { s.style.borderStyle = fillP > 0.5 ? 'solid' : 'dashed'; s.style.background = fillP > 0.5 ? 'rgba(255,255,255,0.04)' : 'transparent'; });
    } else { put(this.lockWrap, { o: 0 }); put(this.kickEw, { o: 0 }); }

    // ---------------- value chain: the line returns and becomes six stations
    const cIn = prog(t, this.cSeason - 0.25, 0.7, E.inOutCubic);
    const shrink = prog(t, D - 1.55, 0.95, E.inOutCubic);
    const focus = env(t, this.cShelf + 1.0, D - 0.9, 0.3, 0.4);
    const s = lerp(1, (MAP.x1 - MAP.x0) / (BIG.x1 - BIG.x0), shrink);
    const tx = lerp(0, MAP.x0 - BIG.x0 * s, shrink), ty = lerp(0, MAP.y - BIG.y * s, shrink);
    this.chain.set({
      draw: cIn,
      node: (i) => prog(t, this.cSeason + 0.2 + i * 0.14, 0.45),
      lit: () => 0,
      labels: 1 - shrink,
      a: cIn > 0 ? 1 - prog(t, D - 0.75, 0.3) : 0,
      x: tx, y: ty, s,
    });
    // focus on the next station
    const n = this.chain.nodes[this.nextIdx];
    if (n) n.ring.style.boxShadow = focus > 0 ? `0 0 0 ${(6 + 4 * Math.sin(t * 6)).toFixed(1)}px rgba(255,255,255,${(0.12 * focus).toFixed(3)}), 0 20px 50px -20px rgba(0,0,0,0.9)` : '0 20px 50px -20px rgba(0,0,0,0.9)';
    const kq = prog(t, this.cShelf - 0.1, 0.5, E.outCubic) * (1 - shrink);
    put(this.kickChain, { o: kq, y: (1 - kq) * 10 });
    put(this.kickSub, { o: prog(t, this.cShelf + 0.5, 0.5) * (1 - shrink), y: (1 - prog(t, this.cShelf + 0.5, 0.5, E.outCubic)) * 10 });
    exitLine(g, t, D);
  },
});
