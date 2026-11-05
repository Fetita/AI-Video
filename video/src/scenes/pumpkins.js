// 04 — Packhouse · Count & quality.
// The hand-off line opens into the two rails of the pumpkin packing line (the AI Studio film's conveyor):
// every pumpkin gets an ID and is counted at the line, then a quality scan grades it (Class I / Class II /
// Out-grade, with the defect and an estimated weight) and the belt splits into three lanes by class →
// formula: Hours saved × Cost/hour + Kg graded right × Price difference.
import { addScene, h, put, prog, E, clamp, lerp, env, makeCanvas, rgba, C, hash, rrect, W, H } from '../engine.js';
import { makeHud, box, tag } from '../lib/ui.js';
import { seg, cueOr } from '../lib/vo.js';
import { EQUATIONS, stationIndex } from '../lib/impact-data.js';
import { makeEquation, eqTimes, dockStart } from '../lib/equation.js';
import { mapDot, drawLine, CHAIN } from '../lib/chain.js';
import { makeOutcome, withFeed, exitLine, FEED, fmt } from '../lib/chapter.js';
import { pumpkinSprite } from '../lib/field.js';
import { drawDefect } from '../lib/produce.js';
import { beltTexture, drawRail, drawBelt } from '../lib/conveyor.js';

const BV = 250;
const BY0 = CHAIN.y - 210, BH = 420;          // belt centred on the hand-off line
const LINE_X = FEED.x + 520, GRADE_X = FEED.x + 860, SPLIT_X = FEED.x + 1180;
const LANES = [BY0 + 70, BY0 + 210, BY0 + 350];
const GRADES = [
  { name: 'CLASS I', col: C.accent, fg: '#fff' },
  { name: 'CLASS II', col: C.amber, fg: '#1a1205' },
  { name: 'OUT-GRADE', col: C.coral, fg: '#1d0905' },
];
const pk = (k) => {
  const r = hash(k, 21);
  const grade = r < 0.68 ? 0 : r < 0.88 ? 1 : 2;
  const R = 50 + hash(k, 11) * 16;
  return { k, grade, R, defect: grade === 1 ? (hash(k, 23) < 0.6 ? 'scar' : 'color') : grade === 2 ? 'shape' : null, y0: BY0 + 80 + hash(k, 8) * (BH - 160), rot: hash(k, 5) * 6, kg: (R / 58) ** 3 * 4.6 };
};

addScene({
  id: 'pumpkins',
  pre: 0.3,
  post: 0.5,
  setup(ctx) {
    const R = ctx.root;
    this.cv = makeCanvas(R);
    this.g = this.cv.ctx;
    this.sprites = [['orange', 1], ['deep', 2], ['orange', 3], ['pale', 4], ['orange', 5], ['deep', 7], ['orange', 8]].map(([kd, s]) => pumpkinSprite(kd, s));
    this.belt = beltTexture();
    const def = EQUATIONS.pumpkins;
    this.times = eqTimes(ctx, def);
    this.dockAt = dockStart(def) - ctx.start;
    this.dock = mapDot(stationIndex('pumpkins'));
    this.cCount = seg(ctx, 'k1', 1);
    this.cNoHand = seg(ctx, 'k1', 2);
    this.cOut = cueOr(ctx, 'k2', () => this.times[0] - 2.4);
    this.cGrade = this.cCount + 1.2;
    this.hud = makeHud(ctx, {
      num: '04', title: 'Packhouse · Count & quality', badge: 'Computer vision',
      steps: [
        { label: 'Detect', at: 0.9 },
        { label: 'Count', at: this.cCount },
        { label: 'Grade', at: this.cGrade },
        { label: 'Sort', at: this.cGrade + 1.0 },
      ],
    });
    // live packhouse panel (top of the feed)
    this.panel = h('div', { class: 'panel', style: { left: '470px', top: '150px', display: 'flex', alignItems: 'center', gap: '38px', padding: '14px 30px', background: 'rgba(12,14,17,0.92)', zIndex: '20' } });
    const stat = (k, col) => { const v = h('span', { class: 'tnum', style: { fontSize: '23px', color: col || 'var(--text)' } }, '0'); return { el: h('div', { style: { display: 'flex', flexDirection: 'column', gap: '4px' } }, h('span', { class: 'kicker', style: { fontSize: '10.5px' } }, k), v), v, last: '' }; };
    this.sCount = stat('Counted', 'var(--accent-text)');
    this.sK = [stat('Class I · kg', 'var(--accent-text)'), stat('Class II · kg', 'var(--amber)'), stat('Out-grade · kg', 'var(--coral)')];
    this.sHand = stat('Hand counts');
    this.panel.append(h('div', { style: { fontSize: '16px', fontWeight: '600', width: '120px', lineHeight: '1.3' } }, 'Packing line', h('br'), h('span', { class: 'kicker', style: { fontSize: '10.5px', color: 'var(--coral)' } }, '● Live')), this.sCount.el, ...this.sK.map((s) => s.el), this.sHand.el);
    R.append(this.panel);
    this.outcome = makeOutcome(R, [
      { text: 'Right class', dir: 'up' },
      { text: 'Right price', dir: 'up' },
      { text: 'No hand counting', dir: 'down' },
    ]);
    this.eq = makeEquation(R, def);
  },

  render(t, ctx) {
    const g = this.g;
    g.clearRect(0, 0, W, H);
    const D = ctx.dur;
    const eqLevel = this.eq.level(t, { times: this.times, dockAt: this.dockAt });
    this.hud(t, { hideSteps: eqLevel > 0.25 });
    const fade = 1 - prog(t, this.dockAt - 0.7, 1.0, E.inOutSine);
    const open = prog(t, 0.05, 0.75, E.inOutCubic);      // the line splits into the two rails
    let counted = 0;
    const kg = [0, 0, 0];
    const spawn = (k) => -2.6 + k * 0.6 + (hash(k, 4) - 0.5) * 0.2;
    const xAt = (k, tt) => FEED.x - 110 + (tt - spawn(k)) * BV;
    for (let k = 0; k < 60; k++) {
      if (xAt(k, t) > LINE_X) counted++;
      if (xAt(k, t) > GRADE_X) { const p = pk(k); kg[p.grade] += p.kg; }
    }
    if (fade > 0.001) {
      withFeed(g, FEED, () => {
        g.fillStyle = '#121417'; g.fillRect(FEED.x, FEED.y, FEED.w, FEED.h);
        // belt revealed between the opening rails
        const half = (BH / 2 + 40) * open;
        g.save(); g.beginPath(); g.rect(FEED.x, CHAIN.y - half, FEED.w, half * 2); g.clip();
        drawBelt(g, this.belt, t, BV, FEED.x, FEED.x + FEED.w, BY0, BH);
        g.fillStyle = 'rgba(0,0,0,0.35)'; g.fillRect(FEED.x, BY0, FEED.w, 16);
        // lane guides after the split
        const laneA = prog(t, this.cGrade + 0.6, 0.6);
        if (laneA > 0) {
          [BY0 + 140, BY0 + 280].forEach((ly) => {
            g.fillStyle = rgba('#9aa2aa', laneA); g.fillRect(SPLIT_X + 70, ly - 4, FEED.x + FEED.w - SPLIT_X - 70, 8);
            g.beginPath(); g.moveTo(SPLIT_X, ly); g.lineTo(SPLIT_X + 70, ly - 4); g.lineTo(SPLIT_X + 70, ly + 4); g.closePath(); g.fill();
          });
        }
        // pumpkins
        const items = [];
        for (let k = 0; k < 60; k++) {
          const x = xAt(k, t);
          if (x < FEED.x - 140 || x > FEED.x + FEED.w + 140) continue;
          const p = pk(k);
          const sp = clamp((x - SPLIT_X) / 260);
          const y = lerp(p.y0, LANES[p.grade], E.inOutSine(sp * laneA)) + Math.sin((t - spawn(k)) * 1.7 + k) * 4;
          items.push({ p, x, y });
        }
        const trA = prog(t, 0.8, 0.5) * open;
        if (trA > 0) items.forEach(({ p, x, y }) => {
          const seen = clamp((x - FEED.x - 20) / 60) * trA;
          if (seen <= 0) return;
          g.strokeStyle = rgba(C.sky, 0.55 * seen); g.lineWidth = 2.5; g.beginPath();
          g.moveTo(x - p.R * 0.6, y); g.lineTo(Math.max(FEED.x, x - p.R * 0.6 - 170), y); g.stroke();
        });
        items.forEach(({ p, x, y }) => {
          g.save(); g.translate(x, y); g.rotate(p.rot + (t - spawn(p.k)) * 0.12);
          const sx = p.defect === 'shape' ? 1.22 : 1, sy = p.defect === 'shape' ? 0.78 : 1;
          g.scale(sx, sy);
          g.drawImage(this.sprites[p.k % this.sprites.length], -p.R * 1.19, -p.R * 1.19, p.R * 2.38, p.R * 2.38);
          g.restore();
          if (p.defect === 'scar' || p.defect === 'color') drawDefect(g, x, y, p.R, p.defect, p.rot);
        });
        g.restore();
        // rails (they start together on the line and part)
        drawRail(g, FEED.x, FEED.x + FEED.w, CHAIN.y - 20 - (BH / 2 + 20) * open, 40);
        drawRail(g, FEED.x, FEED.x + FEED.w, CHAIN.y - 20 + (BH / 2 + 20) * open, 40);
        // count line + quality scan
        const ovA = prog(t, 0.8, 0.5) * open;
        if (ovA > 0) {
          g.strokeStyle = `rgba(255,255,255,${0.8 * ovA})`; g.lineWidth = 2; g.setLineDash([10, 8]);
          g.beginPath(); g.moveTo(LINE_X, BY0 - 40); g.lineTo(LINE_X, BY0 + BH + 40); g.stroke(); g.setLineDash([]);
          tag(g, LINE_X + 10, BY0 - 50, 'COUNT LINE', { bg: null, fg: 'rgba(255,255,255,0.8)', size: 11, anchor: 'bl', pad: 0, a: ovA });
          const qa = prog(t, this.cGrade - 0.3, 0.5) * ovA;
          if (qa > 0) {
            const sb = g.createLinearGradient(GRADE_X - 50, 0, GRADE_X + 10, 0);
            sb.addColorStop(0, rgba(C.accent, 0)); sb.addColorStop(1, rgba(C.accent, 0.3 * qa));
            g.fillStyle = sb; g.fillRect(GRADE_X - 50, BY0, 60, BH);
            g.fillStyle = rgba(C.accent, 0.95 * qa); g.fillRect(GRADE_X + 8, BY0 - 40, 2, BH + 80);
            tag(g, GRADE_X + 16, BY0 - 50, 'QUALITY SCAN', { bg: null, fg: C.accentText, size: 11, anchor: 'bl', pad: 0, a: qa });
          }
          items.forEach(({ p, x, y }) => {
            const seen = clamp((x - FEED.x - 20) / 60) * ovA;
            if (seen <= 0) return;
            const counted2 = x > LINE_X, graded = x > GRADE_X && qa > 0.5;
            const flash = counted2 ? clamp(1 - (x - LINE_X) / 90) : 0;
            const gr = GRADES[p.grade];
            const col = graded ? gr.col : counted2 ? C.accent : C.sky;
            const rr = p.R * (p.defect === 'shape' ? 1.18 : 1.02);
            box(g, x - rr, y - rr, rr * 2, rr * 2, { color: col, a: seen, lw: 1.6 + flash * 1.5, fill: 0.03 + flash * 0.16 });
            const lab = graded ? `${gr.name}${p.grade === 1 ? ' · ' + (p.defect === 'scar' ? 'SCAR' : 'COLOR') : p.grade === 2 ? ' · SHAPE' : ''}` : `ID ${1240 + p.k}${counted2 ? '  ✓' : ''}`;
            tag(g, x - rr, y - rr - 4, lab, { bg: col, fg: graded ? gr.fg : '#fff', a: seen, size: 11 });
            if (graded) tag(g, x - rr, y + rr + 22, `EST. ${p.kg.toFixed(1)} KG`, { bg: '#0b0d10', fg: '#fff', a: seen * prog(t, this.cGrade, 0.4), size: 10.5, anchor: 'bl', stroke: 'rgba(255,255,255,0.25)' });
          });
          if (laneA > 0) GRADES.forEach((gr, i) => tag(g, FEED.x + FEED.w - 20, LANES[i] - 46, gr.name, { bg: rgba(gr.col, 0.95), fg: gr.fg, a: laneA * ovA, size: 12, anchor: 'tr' }));
        }
      }, { a: fade * prog(t, 0.0, 0.5), label: 'LINE CAM 02 · PACKHOUSE', t: t + 40 });
    }
    // the incoming hand-off line hands over to the rails
    if (t >= 0) drawLine(g, CHAIN.x0, CHAIN.x1, CHAIN.y, { a: 1 - prog(t, 0.1, 0.45) });
    // panel
    const pA = env(t, this.cCount - 0.2, this.dockAt - 0.3, 0.45, 0.6);
    put(this.panel, { y: (1 - prog(t, this.cCount - 0.2, 0.5, E.outCubic)) * -16, o: pA });
    const setv = (s, v) => { if (s.last !== v) { s.v.textContent = v; s.last = v; } };
    setv(this.sCount, fmt(1238 + counted));
    this.sK.forEach((s, i) => setv(s, fmt([5210, 1460, 380][i] + kg[i])));
    setv(this.sHand, '0');

    this.outcome.render(t, this.cOut - 0.1, this.times[0] - 0.5);
    this.eq.render(t, {
      times: this.times, dockAt: this.dockAt, dock: this.dock,
      from: { 0: () => ({ x: 1380, y: 186, w: 120 }), 4: () => ({ x: 860, y: 186, w: 140 }) },
    });
    exitLine(g, t, D);
  },
});
