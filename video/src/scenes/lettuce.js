// 02 — Field · Harvest forecast.
// The hand-off line becomes the horizon: the line-art tractor (from the AI Studio film) scans the crop;
// push into its camera → every head measured → the feed shrinks to an inset and its plants stream into a
// day-by-day harvest forecast; orders appear, surplus (waste) and shortfall (penalty) shrink as the plan
// matches supply to orders → gain: harvest cut to the order.
import { addScene, h, put, prog, E, clamp, lerp, env, makeCanvas, rgba, C, hash, rrect, W, H } from '../engine.js';
import { makeHud, box, tag, recHud } from '../lib/ui.js';
import { seg } from '../lib/vo.js';
import { GAINS, stationIndex } from '../lib/impact-data.js';
import { makeGain, gainTimes, dockStart } from '../lib/gain.js';
import { mapDot, drawLine, CHAIN } from '../lib/chain.js';
import { withFeed, lerpRect, exitLine, FEED } from '../lib/chapter.js';
import { plantSprite, soilTile, SPEED, ROWS, ROW_X0, ROW_DX } from '../lib/field.js';
import { drawTractor } from '../lib/tractor.js';

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const SUPPLY = [0.42, 0.6, 0.86, 1.0, 0.88, 0.6, 0.4];   // heads ready per day, from the scan (relative)
const ORDERS = [0.58, 0.66, 0.68, 0.74, 0.72, 0.66, 0.56];
const CH = { x: 760, y: 214, w: 960, h: 470 };           // chart plot area
const INSET = { x: 150, y: 214, w: 540, h: 470 };
const PITCH5 = 176;

addScene({
  id: 'lettuce',
  pre: 0.3,
  post: 0.5,
  setup(ctx) {
    const R = ctx.root;
    this.cv = makeCanvas(R);
    this.g = this.cv.ctx;
    this.heads = Array.from({ length: 10 }, (_, i) => plantSprite(1200 + i, 160));
    this.soil = soilTile(FEED.w, 1200);
    const def = GAINS.lettuce;
    this.times = gainTimes(ctx, def);
    this.dockAt = dockStart(def) - ctx.start;
    this.dock = mapDot(stationIndex('lettuce'));
    this.cCam = seg(ctx, 'l1', 1);
    this.cFc = seg(ctx, 'l2', 0);
    this.cMatch = seg(ctx, 'l2', 1);
    this.cPush = this.cCam + 0.55;
    this.hud = makeHud(ctx, {
      num: '02', title: 'Field · Harvest forecast', badge: 'Vision + forecasting',
      steps: [
        { label: 'Detect', at: this.cPush + 0.5 },
        { label: 'Measure', at: this.cPush + 1.2 },
        { label: 'Forecast', at: this.cFc + 0.2 },
        { label: 'Match', at: this.cMatch },
      ],
    });
    // chart chrome (DOM): title, legend, day labels
    this.chart = h('div', { class: 'panel', style: { left: `${CH.x - 40}px`, top: `${CH.y - 96}px`, width: `${CH.w + 80}px`, height: `${CH.h + 170}px`, background: 'rgba(12,14,17,0.82)' } });
    this.chart.append(
      h('div', { style: { position: 'absolute', left: '40px', top: '28px', fontSize: '20px', fontWeight: '600' } }, 'Harvest forecast'),
      h('div', { class: 'kicker', style: { position: 'absolute', left: '40px', top: '62px', fontSize: '11px' } }, 'Boxes ready per day · Block 7'),
    );
    this.legend = h('div', { style: { position: 'absolute', right: '40px', top: '32px', display: 'flex', gap: '22px', alignItems: 'center', fontSize: '13px', color: 'var(--text2)', fontWeight: '600', letterSpacing: '0.04em' } });
    const lg = (sw, txt) => h('span', { style: { display: 'flex', alignItems: 'center', gap: '8px' } }, sw, txt);
    this.legItems = [
      lg(h('i', { style: { width: '14px', height: '14px', borderRadius: '3px', background: 'var(--accent)', display: 'block' } }), 'Forecast'),
      lg(h('i', { style: { width: '18px', height: '0', borderTop: '2px dashed #f3f3ef', display: 'block' } }), 'Orders'),
      lg(h('i', { style: { width: '14px', height: '14px', borderRadius: '3px', background: 'rgba(255,107,87,0.55)', display: 'block' } }), 'Surplus · Short'),
    ];
    this.legItems.forEach((x) => this.legend.append(x));
    this.chart.append(this.legend);
    this.dayEls = DAYS.map((d, i) => { const el = h('div', { class: 'kicker', style: { position: 'absolute', top: `${CH.h + 116}px`, left: `${40 + (i + 0.5) * (CH.w / 7) - 40}px`, width: '80px', textAlign: 'center', fontSize: '12px' } }, d); this.chart.append(el); return el; });
    R.append(this.chart);
    this.gain = makeGain(R, def);
  },

  render(t, ctx) {
    const g = this.g;
    g.clearRect(0, 0, W, H);
    const D = ctx.dur;
    const gainLevel = this.gain.level(t, { times: this.times, dockAt: this.dockAt });
    this.hud(t, { hideSteps: gainLevel > 0.25 });
    const cPush = this.cPush;

    // ================= A: horizon + tractor (the hand-off line becomes the horizon)
    const trA = env(t, -0.3, cPush + 0.95, 0.01, 0.35);
    if (trA > 0.001) {
      const push = prog(t, cPush, 0.9, E.inCubic);
      const S0 = 1.25, gy0 = CHAIN.y;
      const S = lerp(S0, 3.6, push);
      const ox = lerp(560, 960 - 535 * 3.6, push);
      const oy = lerp(gy0 - 95 * S0, 540 - 95 * 3.6, push);
      const gy = oy + 95 * S;
      const land = prog(t, 0.0, 0.7, E.outCubic);
      g.save(); g.globalAlpha = trA;
      const sky = g.createLinearGradient(0, gy - 360, 0, gy);
      sky.addColorStop(0, 'rgba(20,24,30,0)'); sky.addColorStop(1, `rgba(40,46,52,${0.35 * land})`);
      g.fillStyle = sky; g.fillRect(0, gy - 360, 1920, 360);
      g.fillStyle = `rgba(12,14,16,${land})`; g.fillRect(0, gy, 1920, 1080 - gy);
      g.strokeStyle = `rgba(255,255,255,${0.18 * land})`; g.lineWidth = 1.5; g.beginPath(); g.moveTo(0, gy); g.lineTo(1920, gy); g.stroke();
      for (let i = -14; i <= 14; i++) {
        const grd = g.createLinearGradient(0, gy, 0, 1080);
        grd.addColorStop(0, 'rgba(111,174,85,0)'); grd.addColorStop(1, `rgba(111,174,85,${0.16 * land})`);
        g.strokeStyle = grd; g.lineWidth = 1;
        g.beginPath(); g.moveTo(960 + i * 20, gy); g.lineTo(960 + i * 90 * S, 1080 + 200); g.stroke();
      }
      for (let i = 0; i < 70; i++) {
        const x = ((i * 64 - t * SPEED * 0.9 * (S / 1.25)) % (70 * 64) + 70 * 64) % (70 * 64) - 200;
        const hh = 15 * S * land;
        if (hh < 0.5) continue;
        g.fillStyle = '#4f8a3f'; g.beginPath(); g.ellipse(x, gy - hh * 0.35, hh * 0.9, hh * 0.45, 0, Math.PI, Math.PI * 2); g.fill();
        g.fillStyle = '#6fae55'; g.beginPath(); g.ellipse(x - hh * 0.3, gy - hh * 0.4, hh * 0.35, hh * 0.3, -0.5, 0, Math.PI * 2); g.fill();
      }
      g.restore();
      // the incoming violet line settles into the horizon
      if (t >= 0) drawLine(g, CHAIN.x0, CHAIN.x1, CHAIN.y, { a: 1 - prog(t, 0.1, 0.6) });
      const tin = prog(t, 0.15, 0.9, E.outCubic);
      drawTractor(g, t, ox - (1 - tin) * 700, oy, S, env(t, this.cCam - 0.1, this.cCam + 1.2, 0.2, 0.8) * (1 - push), trA * tin);
      if (t > this.cCam && push < 0.5) tag(g, ox + 560 * S, oy - 150 * S, 'CAMERA', { a: trA * prog(t, this.cCam, 0.4) * (1 - push * 2), size: 12 });
    }

    // ================= B: top-down feed of mature heads, measured; shrinks to an inset for the forecast
    const feedA = prog(t, cPush + 0.7, 0.35) * (1 - prog(t, this.times[0] + 0.6, 0.6));
    const toInset = prog(t, this.cFc + 0.45, 0.9, E.inOutCubic);
    const fr = lerpRect(FEED, INSET, toInset);
    const scroll = t * SPEED * 0.8;
    const headPos = [];
    if (feedA > 0.001) {
      withFeed(g, fr, () => {
        const sx = fr.w / FEED.w, sy = fr.h / FEED.h;
        g.save();
        g.translate(fr.x, fr.y); g.scale(sx, sx); g.translate(-FEED.x, -FEED.y + (FEED.h - fr.h / sx) / 2);
        const zoomIn = 1 + (1 - prog(t, cPush + 0.7, 0.8, E.outCubic)) * 0.25;
        g.translate(960, 531); g.scale(zoomIn, zoomIn); g.translate(-960, -531);
        const sh = this.soil.height, oy = ((scroll % sh) + sh) % sh;
        g.drawImage(this.soil, FEED.x, FEED.y + oy - sh);
        g.drawImage(this.soil, FEED.x, FEED.y + oy);
        const ovA = prog(t, cPush + 0.7, 0.45);
        const kMin = Math.floor((scroll - 300) / PITCH5), kMax = Math.ceil((scroll + FEED.h + 300) / PITCH5);
        for (let r = 0; r < ROWS; r++) for (let k = kMin; k <= kMax; k++) {
          const x = ROW_X0 + r * ROW_DX + (hash(r, k, 7) - 0.5) * 16;
          const py = FEED.y + FEED.h + 140 - (k * PITCH5 - scroll + (hash(r, k, 9) - 0.5) * 30);
          if (py < FEED.y - 120 || py > FEED.y + FEED.h + 120) continue;
          const s = 0.85 + hash(r, k, 13) * 0.35;
          const sz = 150 * s;
          g.drawImage(this.heads[Math.floor(hash(r, k, 17) * 10)], x - sz / 2, py - sz / 2, sz, sz);
          const vis = clamp((py - FEED.y - 30) / 60) * clamp((FEED.y + FEED.h - py) / 60);
          const a = ovA * vis;
          if (a > 0.01) {
            const ready = hash(r, k, 21);
            const day = 1 + Math.floor(ready * 6);
            const col = day <= 2 ? C.accent : C.accent2;
            const bw = sz * 0.74;
            box(g, x - bw / 2, py - bw / 2, bw, bw, { color: col, a, lw: 1.6, fill: 0.05 });
            tag(g, x - bw / 2, py - bw / 2 - 3, `Ø ${Math.round(14 + s * 6)} cm`, { bg: rgba(col, 0.92), a: a * 0.95, size: 11, pad: 5 });
            if ((r + k) % 2 === 0) tag(g, x - bw / 2, py + bw / 2 + 22, `READY · ${DAYS[(day + 2) % 7].toUpperCase()}`, { bg: '#0b0d10', fg: '#fff', a: a * 0.9, size: 10.5, stroke: 'rgba(255,255,255,0.25)', anchor: 'bl' });
            headPos.push({ x, y: py, day: (day + 2) % 7, a });
          }
        }
        g.restore();
      }, { a: feedA, label: toInset < 0.5 ? 'TRACTOR CAM · BLOCK 7' : null, t: t + 31.2 });
      if (toInset > 0.6) tag(g, fr.x + 18, fr.y + 30, 'FIELD SCAN', { bg: 'rgba(130,52,254,0.92)', a: feedA * prog(toInset, 0.6, 0.4), size: 12 });
    }

    // ================= C: forecast chart: supply bars, orders, surplus / shortfall shrink as the plan matches
    const chA = prog(t, this.cFc + 0.7, 0.6, E.outCubic) * (1 - prog(t, this.dockAt - 0.7, 0.9));
    put(this.chart, { y: (1 - prog(t, this.cFc + 0.7, 0.6, E.outCubic)) * 24, o: chA });
    this.legItems.forEach((el, i) => { el.style.opacity = i === 0 ? '1' : prog(t, this.cMatch - 0.1, 0.4).toFixed(3); });
    const surplusAt = [], shortAt = [];
    if (chA > 0.001) {
      g.save(); g.globalAlpha = chA;
      const cw = CH.w / 7, bw = 84;
      const grow = prog(t, this.cFc + 0.9, 1.6, E.outCubic);
      const ordA = prog(t, this.cMatch - 0.1, 0.5);
      const match = prog(t, this.cMatch + 0.8, 2.6, E.inOutCubic);
      const yOf = (v) => CH.y + CH.h - v * CH.h * 0.82;
      // grid
      g.strokeStyle = 'rgba(255,255,255,0.06)'; g.lineWidth = 1;
      for (let k = 1; k <= 4; k++) { const yy = CH.y + CH.h - (k / 4) * CH.h * 0.82; g.beginPath(); g.moveTo(CH.x, yy); g.lineTo(CH.x + CH.w, yy); g.stroke(); }
      g.strokeStyle = 'rgba(255,255,255,0.22)'; g.beginPath(); g.moveTo(CH.x, CH.y + CH.h); g.lineTo(CH.x + CH.w, CH.y + CH.h); g.stroke();
      for (let i = 0; i < 7; i++) {
        const cx = CH.x + (i + 0.5) * cw;
        const sv = SUPPLY[i] * clamp(grow * 1.4 - i * 0.06);
        const v = lerp(sv, ORDERS[i] + (SUPPLY[i] - ORDERS[i]) * 0.06, match);
        const y = yOf(v), y0 = CH.y + CH.h;
        const bg = g.createLinearGradient(0, y, 0, y0);
        bg.addColorStop(0, '#9b63ff'); bg.addColorStop(1, rgba(C.accent2, 0.55));
        g.fillStyle = bg; rrect(g, cx - bw / 2, y, bw, y0 - y, 6); g.fill();
        // confidence whisker
        const ww = 0.05 * (1 - match * 0.5) * CH.h;
        g.strokeStyle = 'rgba(255,255,255,0.55)'; g.lineWidth = 1.5;
        g.beginPath(); g.moveTo(cx, y - ww); g.lineTo(cx, y + ww); g.moveTo(cx - 8, y - ww); g.lineTo(cx + 8, y - ww); g.moveTo(cx - 8, y + ww); g.lineTo(cx + 8, y + ww); g.stroke();
        if (ordA > 0) {
          const yo = yOf(ORDERS[i]);
          // surplus (above orders) and short (below orders)
          if (v > ORDERS[i] + 0.004) {
            g.fillStyle = rgba(C.coral, 0.55 * ordA); g.fillRect(cx - bw / 2, y, bw, yo - y);
            g.strokeStyle = rgba(C.coral, 0.9 * ordA); g.setLineDash([4, 3]); g.strokeRect(cx - bw / 2 + 0.5, y + 0.5, bw - 1, yo - y); g.setLineDash([]);
            surplusAt.push({ x: cx, y: (y + yo) / 2, w: bw, d: yo - y });
          } else if (v < ORDERS[i] - 0.004) {
            g.strokeStyle = rgba(C.coral, 0.95 * ordA); g.lineWidth = 2; g.setLineDash([5, 4]);
            g.strokeRect(cx - bw / 2 + 0.5, yo + 0.5, bw - 1, y - yo); g.setLineDash([]);
            g.fillStyle = rgba(C.coral, 0.12 * ordA); g.fillRect(cx - bw / 2, yo, bw, y - yo);
            shortAt.push({ x: cx, y: (y + yo) / 2, w: bw, d: y - yo });
          }
          // orders tick (dashed)
          g.strokeStyle = `rgba(243,243,239,${0.95 * ordA})`; g.lineWidth = 2.5; g.setLineDash([8, 6]);
          g.beginPath(); g.moveTo(cx - cw / 2 + 10, yo); g.lineTo(cx + cw / 2 - 10, yo); g.stroke(); g.setLineDash([]);
        }
      }
      // labels on the mismatch while it's large
      const lblA = ordA * (1 - match);
      if (lblA > 0.02) {
        tag(g, CH.x + 3.5 * cw + bw / 2 + 10, yOf(1.0) + 8, 'SURPLUS → WASTE', { bg: C.coral, fg: '#1d0905', a: lblA, size: 11.5 });
        tag(g, CH.x + 0.5 * cw - bw / 2, yOf(ORDERS[0]) - 14, 'SHORT → PENALTY', { bg: '#0b0d10', fg: C.coral, stroke: rgba(C.coral, 0.7), a: lblA, size: 11.5 });
      }
      // boxes moved from surplus days to short days while matching
      if (match > 0 && match < 1) {
        for (let k = 0; k < 14; k++) {
          const from = [2, 3, 4][k % 3], to = [0, 1, 5, 6][k % 4];
          const u = clamp(match * 1.6 - (k / 14) * 0.6);
          if (u <= 0 || u >= 1) continue;
          const x = lerp(CH.x + (from + 0.5) * cw, CH.x + (to + 0.5) * cw, E.inOutSine(u));
          const y = lerp(yOf(SUPPLY[from]) + 20, yOf(ORDERS[to]) + 10, u) - Math.sin(u * Math.PI) * 90;
          g.fillStyle = rgba('#c4adff', Math.sin(u * Math.PI));
          g.fillRect(x - 5, y - 5, 10, 10);
        }
      }
      // plants stream from the inset into the bars (field scan → forecast)
      const st = prog(t, this.cFc + 0.9, 2.2, E.linear);
      if (st > 0 && st < 1 && headPos.length) {
        for (let k = 0; k < 26; k++) {
          const hp = headPos[k % headPos.length];
          const u = clamp(st * 1.6 - (k / 26) * 0.6);
          if (u <= 0 || u >= 1) continue;
          const sx = fr.x + (hp.x - FEED.x) * (fr.w / FEED.w), sy = fr.y + (hp.y - FEED.y) * (fr.w / FEED.w);
          const tx = CH.x + (hp.day + 0.5) * cw, ty = yOf(SUPPLY[hp.day] * 0.5);
          const x = lerp(sx, tx, E.inOutSine(u)), y = lerp(sy, ty, E.inOutSine(u)) - Math.sin(u * Math.PI) * 60;
          g.fillStyle = rgba(C.accent, Math.sin(u * Math.PI)); g.beginPath(); g.arc(x, y, 4, 0, Math.PI * 2); g.fill();
        }
      }
      g.restore();
    }
    this.surplusAt = surplusAt; this.shortAt = shortAt;

    // ================= gain → dock (the coral surplus and shortfall fly into their chips)
    const surplusSrc = () => ({ x: CH.x + 3.5 * (CH.w / 7), y: CH.y + CH.h * 0.18, w: 160 });
    const shortSrc = () => ({ x: CH.x + 0.5 * (CH.w / 7), y: CH.y + CH.h * 0.5, w: 160 });
    this.gain.render(t, { times: this.times, dockAt: this.dockAt, dock: this.dock, from: { 1: surplusSrc, 2: shortSrc } });
    exitLine(g, t, D);
  },
});
