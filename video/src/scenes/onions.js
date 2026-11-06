// 03 — Harvest · Onion sizing (proposal).
// Need → Solution panels, with the proof-of-concept photo (an off-the-shelf model misses onions) →
// the windrower's rod belt: a custom model gives every onion an ID, counts it once at the line, measures it
// and sorts it into a size band; the field's size split builds live and lands on the field map →
// gain: every field planned on its real sizes.
import { addScene, h, put, prog, E, clamp, lerp, env, makeCanvas, rgba, C, hash, rrect, W, H } from '../engine.js';
import { makeHud, box, tag } from '../lib/ui.js';
import { seg } from '../lib/vo.js';
import { GAINS, stationIndex } from '../lib/impact-data.js';
import { makeGain, gainTimes, dockStart } from '../lib/gain.js';
import { mapDot } from '../lib/chain.js';
import { makeProposalCard } from '../lib/proposal.js';
import { withFeed, lerpRect, exitLine, fmt } from '../lib/chapter.js';
import { onionSprite, foliageSprite } from '../lib/produce.js';
import { drawRodBelt } from '../lib/conveyor.js';
import { BANDS } from '../lib/impact-theme.js';

const RB = { x: 150, y: 118, w: 1250, h: 826 };
const V = 165;               // belt speed (px/s, upward)
const SPAWN = 0.16;          // one onion every SPAWN seconds
const LINE_Y = RB.y + RB.h * 0.4;
const bandOf = (mm) => (mm < 45 ? 0 : mm < 60 ? 1 : mm < 75 ? 2 : 3);
// onion k: lane position, size, rotation (deterministic)
const onion = (k) => {
  const mm = 36 + Math.pow(hash(k, 3), 0.9) * 52;
  return { k, mm, band: bandOf(mm), x: RB.x + 90 + hash(k, 1) * (RB.w - 180), jy: (hash(k, 2) - 0.5) * 40, rot: hash(k, 4) * 6.28, spr: Math.floor(hash(k, 5) * 12), t0: k * SPAWN };
};
// missed onions in the proposal's proof-of-concept photo (image coordinates)
const POC_MISSED = [{ x: 541, y: 92, r: 26 }, { x: 588, y: 95, r: 15 }, { x: 614, y: 132, r: 15 }, { x: 540, y: 166, r: 13 }, { x: 659, y: 289, r: 15 }, { x: 255, y: 177, r: 15 }];

addScene({
  id: 'onions',
  pre: 0.3,
  post: 0.5,
  setup(ctx) {
    const R = ctx.root;
    this.cv = makeCanvas(R);
    this.g = this.cv.ctx;
    this.sprites = Array.from({ length: 12 }, (_, i) => onionSprite(700 + i, 160));
    this.leaves = Array.from({ length: 5 }, (_, i) => foliageSprite(800 + i, 260, 180));
    const def = GAINS.onions;
    this.times = gainTimes(ctx, def);
    this.dockAt = dockStart(def) - ctx.start;
    this.dock = mapDot(stationIndex('onions'));
    this.cSplit = seg(ctx, 'u1', 1);
    this.cMiss = seg(ctx, 'u2', 0);
    this.cCustom = seg(ctx, 'u2', 1);
    this.cSort = seg(ctx, 'u2', 2);
    this.liveAt = seg(ctx, 'u2', 0, 1) - 0.05;
    this.hud = makeHud(ctx, {
      num: '03', title: 'Harvest · Onion sizing', badge: 'Custom model',
      steps: [
        { label: 'Detect', at: this.liveAt + 0.4 },
        { label: 'Track', at: this.cCustom + 0.6 },
        { label: 'Size', at: this.cSort - 0.4 },
        { label: 'Split', at: this.cSort + 0.3 },
      ],
    });
    this.card = makeProposalCard(R, {
      need: 'Know <b>each field’s size split</b> during harvest, to plan sales and logistics.',
      solution: 'A camera over the windrower and <b>a custom model</b> count every onion, measure it and sort it into size bands.',
      photo: 'assets/proposals/onion-poc.png', caption: 'Off-the-shelf model', marks: POC_MISSED, markLabel: 'Missed onions',
      h: 540, solH: 300,
    });
    // live panel: count, manual samples, size split by band
    this.panel = h('div', { class: 'panel', style: { left: '1430px', top: '118px', width: '340px', padding: '18px 22px 20px', background: 'rgba(12,14,17,0.9)', zIndex: '20' } });
    this.count = h('span', { class: 'tnum', style: { fontSize: '30px', color: 'var(--accent-text)' } }, '0');
    this.samples = h('span', { class: 'tnum', style: { fontSize: '22px' } }, '0');
    this.panel.append(
      h('div', { style: { display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' } }, h('span', { style: { width: '8px', height: '8px', borderRadius: '50%', background: 'var(--coral)' } }), h('span', { style: { fontSize: '17px', fontWeight: '600' } }, 'Field 12 · lifting')),
      h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', height: '50px', borderBottom: '1px solid var(--line)' } }, h('span', { class: 'kicker', style: { fontSize: '11px' } }, 'Onions counted'), this.count),
      h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', height: '44px', borderBottom: '1px solid var(--line)' } }, h('span', { class: 'kicker', style: { fontSize: '11px' } }, 'Hand samples needed'), this.samples),
      h('div', { class: 'kicker', style: { fontSize: '11px', margin: '16px 0 10px' } }, 'Size split'));
    this.bands = BANDS.map((b) => {
      const bar = h('i', { style: { display: 'block', height: '100%', width: '0%', background: b.col, borderRadius: '4px' } });
      const val = h('span', { class: 'tnum', style: { fontSize: '14px', color: 'var(--text2)', width: '58px', textAlign: 'right' } }, '0');
      const row = h('div', { style: { display: 'flex', alignItems: 'center', gap: '10px', height: '30px' } },
        h('span', { style: { fontSize: '13px', fontWeight: '600', color: 'var(--text2)', width: '70px' } }, b.label),
        h('div', { style: { flex: '1', height: '12px', background: 'rgba(255,255,255,0.06)', borderRadius: '4px', overflow: 'hidden' } }, bar), val);
      this.panel.append(row);
      return { bar, val, last: '' };
    });
    R.append(this.panel);
    this.mapPanel = h('div', { class: 'panel', style: { left: '1430px', top: '560px', width: '340px', height: '384px', padding: '18px 22px', background: 'rgba(12,14,17,0.9)', zIndex: '20' } },
      h('div', { style: { fontSize: '17px', fontWeight: '600' } }, 'Field map'),
      h('div', { class: 'kicker', style: { fontSize: '11px', marginTop: '4px' } }, 'Predominant size band'));
    R.append(this.mapPanel);
    this.mapCv = makeCanvas(this.mapPanel, 300, 270, '');
    Object.assign(this.mapCv.c.style, { position: 'absolute', left: '20px', top: '92px', width: '300px', height: '270px' });
    this.gain = makeGain(R, def);
    this.lastCount = '';
  },

  render(t, ctx) {
    const g = this.g;
    g.clearRect(0, 0, W, H);
    const D = ctx.dur;
    const gainLevel = this.gain.level(t, { times: this.times, dockAt: this.dockAt });
    this.hud(t, { hideSteps: gainLevel > 0.25 });

    // ---------------- need → solution (with the proof-of-concept photo)
    this.card.render(t, {
      open: prog(t, 0.05, 1.0, E.linear),
      need: prog(t, 0.7, 1.4, E.linear),
      sol: prog(t, this.cSplit - 0.1, 1.2, E.linear),
      marks: prog(t, this.cMiss + 0.1, 1.1, E.linear),
      out: prog(t, this.liveAt, 0.55, E.linear),
    });

    // ---------------- live view: rod belt + custom model overlays
    const grow = prog(t, this.liveAt - 0.05, 0.85, E.inOutCubic);
    const fade = 1 - prog(t, this.dockAt - 0.7, 1.0, E.inOutSine);
    // onions counted so far (crossed the line): deterministic from t
    const crossT = (o) => o.t0 + (RB.y + RB.h + 80 + o.jy - LINE_Y) / V;
    const kNow = Math.floor((t + 12) / SPAWN);
    let counted = 0;
    const bandN = [0, 0, 0, 0];
    for (let k = 0; k <= kNow; k++) { const o = onion(k); if (crossT(o) - 12 <= t) { counted++; bandN[o.band]++; } }
    if (grow > 0 && fade > 0.001) {
      const rect = lerpRect(this.card.solutionRect(), RB, grow);
      const ovA = prog(t, this.liveAt + 0.5, 0.5);
      const sizeA = prog(t, this.cSort - 0.5, 0.5);
      withFeed(g, rect, () => {
        drawRodBelt(g, t, RB, V);
        const items = [];
        for (let k = kNow - 60; k <= kNow + 2; k++) {
          if (k < 0) continue;
          const o = onion(k);
          const y = RB.y + RB.h + 80 + o.jy - (t + 12 - o.t0) * V;
          if (y < RB.y - 120 || y > RB.y + RB.h + 120) continue;
          items.push({ o, y });
        }
        // foliage tangles under the onions
        for (let k = Math.floor((t + 12) / 0.9) - 9; k <= Math.floor((t + 12) / 0.9) + 1; k++) {
          const y = RB.y + RB.h + 120 - (t + 12 - k * 0.9) * V;
          if (y < RB.y - 200 || y > RB.y + RB.h + 200) continue;
          const x = RB.x + 120 + hash(k, 31) * (RB.w - 240);
          g.save(); g.translate(x, y); g.rotate(hash(k, 32) * 6.28); g.drawImage(this.leaves[k % 5], -130, -90); g.restore();
        }
        items.forEach(({ o, y }) => {
          const s = o.mm * 1.95;
          g.save(); g.translate(o.x, y); g.rotate(o.rot + Math.sin(t * 2 + o.k) * 0.05); g.drawImage(this.sprites[o.spr], -s / 2, -s / 2, s, s); g.restore();
        });
        if (ovA > 0) {
          // count line
          g.strokeStyle = `rgba(255,255,255,${0.8 * ovA})`; g.lineWidth = 2; g.setLineDash([10, 8]);
          g.beginPath(); g.moveTo(RB.x, LINE_Y); g.lineTo(RB.x + RB.w, LINE_Y); g.stroke(); g.setLineDash([]);
          tag(g, RB.x + 24, LINE_Y - 8, 'COUNT LINE · EACH ONION ONCE', { bg: null, fg: 'rgba(255,255,255,0.8)', size: 11, anchor: 'bl', pad: 0, a: ovA });
          items.forEach(({ o, y }) => {
            const vis = clamp((RB.y + RB.h - y) / 80) * clamp((y - RB.y) / 60) * ovA;
            if (vis <= 0.01) return;
            const r = o.mm * 0.62;
            const passed = y < LINE_Y;
            const flash = passed ? clamp(1 - (LINE_Y - y) / 70) : 0;
            const col = sizeA > 0.5 ? BANDS[o.band].col : C.accent;
            // short track below (moving up)
            g.strokeStyle = rgba(C.sky, 0.6 * vis); g.lineWidth = 2;
            g.beginPath(); g.moveTo(o.x, y + r * 0.6); g.lineTo(o.x, y + r * 0.6 + 46); g.stroke();
            box(g, o.x - r, y - r, r * 2, r * 2, { color: col, a: vis, lw: 1.4 + flash * 1.4, fill: 0.04 + flash * 0.16 });
            tag(g, o.x - r, y - r - 3, `#${2400 + o.k}${passed ? ' ✓' : ''}`, { bg: rgba(col, 0.92), fg: sizeA > 0.5 && o.band >= 2 ? '#1a1205' : '#fff', a: vis, size: 10, pad: 4 });
            if (sizeA > 0.01 && o.k % 2 === 0) tag(g, o.x - r, y + r + 18, `Ø ${Math.round(o.mm)} MM`, { bg: '#0b0d10', fg: '#fff', a: vis * sizeA, size: 10, stroke: 'rgba(255,255,255,0.25)', anchor: 'bl' });
          });
        }
        tag(g, RB.x + RB.w - 24, RB.y + 24, 'MODEL · CUSTOM V1', { bg: 'rgba(130,52,254,0.9)', a: ovA, size: 11, anchor: 'tr' });
      }, { a: fade, label: grow > 0.9 ? 'WINDROWER CAM · FIELD 12' : null, t: t + 53.4 });
    }

    // ---------------- panels: count, hand samples (none), size split, field map
    const pA = env(t, this.liveAt + 0.6, this.dockAt - 0.3, 0.45, 0.6);
    put(this.panel, { x: (1 - prog(t, this.liveAt + 0.6, 0.5, E.outCubic)) * 30, o: pA });
    const cs = fmt(18240 + counted);
    if (cs !== this.lastCount) { this.count.textContent = cs; this.lastCount = cs; }
    this.samples.textContent = '0';
    const tot = bandN.reduce((a, b) => a + b, 0) || 1;
    const fill = prog(t, this.cSort - 0.2, 0.8, E.outCubic);
    this.bands.forEach((b, i) => {
      const share = (bandN[i] + [120, 410, 520, 190][i]) / (tot + 1240);
      b.bar.style.width = `${(share * 100 * fill * 1.6).toFixed(1)}%`;
      const v = fmt((bandN[i] + [120, 410, 520, 190][i]) * fill);
      if (v !== b.last) { b.val.textContent = v; b.last = v; }
    });
    const mA = env(t, this.cSort + 0.4, this.dockAt - 0.3, 0.45, 0.6);
    put(this.mapPanel, { x: (1 - prog(t, this.cSort + 0.4, 0.5, E.outCubic)) * 30, o: mA });
    if (mA > 0.001) {
      const mg = this.mapCv.ctx;
      mg.clearRect(0, 0, 300, 270);
      mg.fillStyle = '#0d1012'; rrect(mg, 0, 0, 300, 270, 10); mg.fill();
      const fields = [
        [[18, 20], [128, 14], [136, 96], [24, 108], 2], [[146, 18], [282, 26], [276, 110], [150, 100], 1],
        [[22, 122], [118, 116], [112, 250], [16, 244], 2], [[128, 112], [214, 118], [208, 196], [124, 190], 3],
        [[224, 122], [284, 128], [280, 250], [220, 246], 1], [[124, 204], [208, 208], [204, 254], [120, 250], 0],
      ];
      fields.forEach((f, i) => {
        const q = clamp((t - this.cSort - 0.6) * 2.2 - i * 0.25);
        if (q <= 0) return;
        mg.globalAlpha = q;
        mg.fillStyle = BANDS[f[4]].col;
        mg.beginPath(); f.slice(0, 4).forEach(([x, y], j) => (j ? mg.lineTo(x, y) : mg.moveTo(x, y))); mg.closePath(); mg.fill();
        mg.globalAlpha = q * 0.35; mg.strokeStyle = '#000'; mg.lineWidth = 1.5; mg.stroke();
        mg.globalAlpha = 1;
        if (i === 3) {
          const pulse = 0.5 + 0.5 * Math.sin(t * 5);
          mg.strokeStyle = rgba(C.accent, 0.9 * q); mg.lineWidth = 3; mg.stroke();
          mg.strokeStyle = rgba(C.accent, 0.35 * pulse * q); mg.lineWidth = 8; mg.stroke();
        }
      });
      const lq = clamp((t - this.cSort - 1.5) * 2);
      if (lq > 0) tag(mg, 128, 108, 'FIELD 12 · LIFTING', { bg: C.accent, a: lq, size: 10, anchor: 'bl' });
    }

    // ---------------- gain → dock
    this.gain.render(t, {
      times: this.times, dockAt: this.dockAt, dock: this.dock,
      from: { 1: () => ({ x: 1600, y: 118 + 108, w: 300 }), 3: () => ({ x: 1600, y: 118 + 270, w: 300 }) },
    });
    exitLine(g, t, D);
  },
});
