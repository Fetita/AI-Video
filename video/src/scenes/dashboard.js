// 06 — Office · Dashboard & alerts (data platform + AI assistant; fictional data, no client names).
// Every station's data streams into one data foundation → a paper-style live dashboard rises out of it
// (KPIs, field map cell by cell, size distribution, size split by field, stock vs demand) → reports build
// themselves → an alert arrives in time → a plain-English question gets an answer from live data →
// formula: Reporting hours saved × Cost/hour.
import { addScene, h, put, prog, E, clamp, lerp, env, makeCanvas, rgba, C, hash, rrect, W, H, makeNoise } from '../engine.js';
import { makeHud, words, revealWords, typed } from '../lib/ui.js';
import { seg } from '../lib/vo.js';
import { EQUATIONS, STATIONS, stationIndex } from '../lib/impact-data.js';
import { makeEquation, eqTimes, dockStart } from '../lib/equation.js';
import { mapDot, drawLine, CHAIN } from '../lib/chain.js';
import { exitLine } from '../lib/chapter.js';
import { icon, drawIcon } from '../lib/icons.js';
import { BANDS, PAPER } from '../lib/impact-theme.js';

const P = { x: 230, y: 150, w: 1460, h: 700 };        // paper dashboard
const SLAB_Y0 = CHAIN.y, SLAB_Y1 = 912;
const FIELDS = ['North 4', 'Weir 2', 'Hill 7', 'Mill 3', 'Ridge 1', 'Vale 6'];
const SPLITS = [[0.22, 0.38, 0.3, 0.1], [0.18, 0.34, 0.36, 0.12], [0.1, 0.3, 0.42, 0.18], [0.08, 0.26, 0.44, 0.22], [0.06, 0.24, 0.46, 0.24], [0.12, 0.3, 0.4, 0.18]];
const Q = 'Which fields are furthest below target population?';
const A = 'North 4, Weir 2 and Hill 7. Filters: season 2026 · all fields · read-only.';

addScene({
  id: 'dashboard',
  pre: 0.3,
  post: 0.5,
  setup(ctx) {
    const R = ctx.root;
    this.cv = makeCanvas(R);
    this.g = this.cv.ctx;
    const def = EQUATIONS.dashboard;
    this.times = eqTimes(ctx, def);
    this.dockAt = dockStart(def) - ctx.start;
    this.dock = mapDot(stationIndex('dashboard'));
    this.cLand = seg(ctx, 'g1', 1);
    this.cDash = seg(ctx, 'g2', 0);
    this.cRep = seg(ctx, 'g2', 1);
    this.cAlert = seg(ctx, 'g2', 2);
    this.cAsk = seg(ctx, 'g3', 0);
    this.cAns = seg(ctx, 'g3', 1);
    this.hud = makeHud(ctx, {
      num: '06', title: 'Office · Dashboard & alerts', badge: 'Data + AI assistant',
      steps: [
        { label: 'Connect', at: 0.9 },
        { label: 'Report', at: this.cRep },
        { label: 'Alert', at: this.cAlert },
        { label: 'Ask', at: this.cAsk },
      ],
    });
    // ---- data foundation slab
    this.slab = h('div', { class: 'abs', style: { left: `${CHAIN.x0}px`, top: '0', width: `${CHAIN.x1 - CHAIN.x0}px`, height: '58px', borderRadius: '14px', background: 'linear-gradient(90deg, rgba(130,52,254,0.22), rgba(102,134,246,0.22))', border: '1px solid rgba(160,120,255,0.6)', boxShadow: '0 0 40px rgba(130,52,254,0.35)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '14px', color: '#e8defe', fontFamily: 'var(--font-ui)', fontWeight: '600', fontSize: '16px', letterSpacing: '0.24em', textTransform: 'uppercase', transformOrigin: '50% 50%', zIndex: '5' } },
      icon('database', { size: 24, stroke: 1.8 }), h('span', {}, 'One data foundation'));
    R.append(this.slab);
    // ---- paper dashboard
    this.paper = h('div', { class: 'ix-paper', style: { left: `${P.x}px`, top: `${P.y}px`, width: `${P.w}px`, height: `${P.h}px`, transformOrigin: '50% 100%', zIndex: '6' } });
    const head = h('div', { style: { position: 'absolute', left: '34px', top: '26px' } }, h('div', { class: 'h', style: { fontSize: '24px' } }, 'Season overview'), h('div', { class: 's', style: { marginTop: '4px', fontSize: '13px' } }, 'All fields · week 32 · updated live'));
    const chips = h('div', { style: { position: 'absolute', right: '30px', top: '30px', display: 'flex', gap: '10px' } },
      ...['Season 2026', 'All growers', 'PDF', 'CSV'].map((x, i) => h('span', { class: 'ix-chip', style: { background: i < 2 ? 'rgba(28,29,25,0.06)' : '#1c1d19', color: i < 2 ? PAPER.ink : '#f4f1e8', fontSize: '12px', letterSpacing: '0.08em' } }, x)));
    this.kpis = [['Fields', '27'], ['Hectares', '236'], ['On target', '19'], ['Alerts', '3'], ['Next report', 'Mon 07:00']].map(([k, v], i) => {
      const el = h('div', { style: { position: 'absolute', left: `${34 + i * 282}px`, top: '96px', width: '262px', height: '86px', borderRadius: '12px', background: '#fbfaf5', border: `1px solid ${PAPER.line}`, padding: '14px 18px' } },
        h('div', { class: 'k' }, k), h('div', { class: 'v', style: { marginTop: '6px', fontSize: i === 4 ? '24px' : '30px', color: i === 3 ? '#c4462f' : PAPER.ink } }, v));
      return el;
    });
    this.paper.append(head, chips, ...this.kpis);
    this.pc = makeCanvas(this.paper, P.w, P.h, '');
    Object.assign(this.pc.c.style, { position: 'absolute', left: '0', top: '0', width: `${P.w}px`, height: `${P.h}px` });
    R.append(this.paper);
    // field map heat (procedural cells), built once
    const noise = makeNoise(41);
    this.heat = (fx, fy, i) => clamp(0.55 + noise.fbm(fx * 0.09 + i * 3.1, fy * 0.09 + i * 1.7, 3) * 0.7 - (i === 0 ? 0.28 * Math.exp(-((fx - 6) ** 2 + (fy - 5) ** 2) / 18) : 0));
    // ---- report pages
    this.pages = [0, 1, 2].map((i) => {
      const lines = Array.from({ length: 9 }, (_, k) => h('div', { style: { height: '7px', borderRadius: '3px', margin: '0 0 11px', width: `${[86, 70, 92, 64, 80, 58, 88, 72, 50][k]}%`, background: k === 2 || k === 6 ? 'rgba(130,52,254,0.45)' : 'rgba(28,29,25,0.14)' } }));
      const pg = h('div', { class: 'abs', style: { left: '0', top: '0', width: '250px', height: '340px', borderRadius: '10px', background: '#fbfaf5', padding: '24px 22px', boxShadow: '0 30px 70px -20px rgba(0,0,0,0.75)', transformOrigin: '50% 100%', zIndex: '8' } },
        h('div', { style: { fontFamily: 'var(--font-ui)', fontWeight: '700', fontSize: '15px', color: PAPER.ink } }, ['Weekly stock report', 'Field report', 'Season summary'][i]),
        h('div', { style: { fontFamily: 'var(--font-ui)', fontWeight: '600', fontSize: '11px', color: PAPER.mute, margin: '4px 0 18px', letterSpacing: '0.06em' } }, 'AUTO · MON 07:00'),
        h('div', { style: { height: '70px', borderRadius: '6px', background: 'linear-gradient(90deg, #7f9fd8 0 18%, #5fb07e 18% 46%, #e3b34f 46% 82%, #e0804a 82%)', opacity: '0.75', marginBottom: '18px' } }), ...lines);
      R.append(pg);
      return pg;
    });
    this.fileChips = h('div', { class: 'abs', style: { left: '1450px', top: '700px', display: 'flex', gap: '10px', zIndex: '9' } },
      ...['PDF', 'CSV'].map((x) => h('span', { class: 'ix-chip', style: { background: 'rgba(130,52,254,0.9)', color: '#fff' } }, x)));
    R.append(this.fileChips);
    // ---- alert toast
    this.toast = h('div', { class: 'abs', style: { left: '1170px', top: '214px', width: '470px', display: 'flex', gap: '14px', alignItems: 'flex-start', padding: '16px 18px', borderRadius: '14px', background: '#1c1d19', color: '#f4f1e8', boxShadow: '0 24px 60px -16px rgba(0,0,0,0.8)', border: '1px solid rgba(255,107,87,0.6)', zIndex: '9' } },
      h('span', { style: { width: '38px', height: '38px', borderRadius: '10px', background: 'rgba(255,107,87,0.18)', color: '#ff6b57', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' } }, icon('alert', { size: 22, stroke: 2 })),
      h('div', {}, h('div', { style: { fontFamily: 'var(--font-ui)', fontWeight: '700', fontSize: '17px' } }, 'North 4 is below target population'), h('div', { style: { fontFamily: 'var(--font-ui)', fontWeight: '500', fontSize: '14px', color: '#b9b7aa', marginTop: '4px' } }, 'Review before Friday’s lift plan.')));
    R.append(this.toast);
    // ---- assistant
    this.chat = h('div', { class: 'panel', style: { left: '1120px', top: '300px', width: '600px', height: '520px', padding: '0', background: 'rgba(15,17,21,0.97)', zIndex: '10' } });
    this.chat.append(h('div', { class: 'panel-head' }, h('span', { style: { width: '9px', height: '9px', borderRadius: '50%', background: 'var(--accent)', boxShadow: '0 0 10px rgba(130,52,254,0.8)' } }), h('span', { class: 'title' }, 'Ask the data'), h('span', { class: 'spacer' }), h('span', { class: 'kicker', style: { fontSize: '11px' } }, 'Live · read-only')));
    this.qBubble = h('div', { style: { position: 'absolute', right: '24px', top: '82px', maxWidth: '470px', padding: '14px 18px', borderRadius: '16px 16px 4px 16px', background: 'rgba(255,255,255,0.08)', fontSize: '19px', lineHeight: '1.4', color: 'var(--text)' } });
    this.aBubble = h('div', { style: { position: 'absolute', left: '24px', top: '196px', width: '520px', padding: '16px 18px', borderRadius: '16px 16px 16px 4px', background: 'rgba(130,52,254,0.14)', border: '1px solid rgba(130,52,254,0.4)', fontSize: '18px', lineHeight: '1.45', color: '#ece6ff' } });
    this.aSpans = words(this.aBubble, A);
    this.bars = h('div', { style: { position: 'absolute', left: '24px', top: '330px', width: '552px', height: '160px' } });
    this.barEls = ['North 4', 'Weir 2', 'Hill 7'].map((n, i) => {
      const fill = h('i', { style: { display: 'block', height: '100%', width: '0%', borderRadius: '6px', background: 'linear-gradient(90deg, #ff6b57, #ff9a7a)' } });
      const row = h('div', { style: { display: 'flex', alignItems: 'center', gap: '14px', height: '40px', marginBottom: '10px' } },
        h('span', { style: { width: '84px', fontSize: '15px', fontWeight: '600', color: 'var(--text2)' } }, n),
        h('div', { style: { flex: '1', height: '22px', background: 'rgba(255,255,255,0.05)', borderRadius: '6px', position: 'relative', overflow: 'hidden' } }, fill));
      this.bars.append(row);
      return fill;
    });
    this.target = h('div', { style: { position: 'absolute', left: `${98 + 0.86 * 454}px`, top: '-6px', height: '150px', borderLeft: '2px dashed rgba(243,243,239,0.7)' } });
    this.bars.append(this.target, h('div', { class: 'kicker', style: { position: 'absolute', left: `${98 + 0.86 * 454 - 40}px`, top: '-26px', fontSize: '10.5px' } }, 'Target'));
    this.chat.append(this.qBubble, this.aBubble, this.bars);
    R.append(this.chat);
    this.eq = makeEquation(R, def);
    this.lastQ = '';
  },

  drawPaper(t, rise) {
    const g = this.pc.ctx;
    g.clearRect(0, 0, P.w, P.h);
    const b = (at, d = 0.8) => prog(t, this.cDash + at, d, E.outCubic);
    // field map (dark tile)
    const M = { x: 34, y: 206, w: 560, h: 460 };
    g.fillStyle = '#1d211c'; rrect(g, M.x, M.y, M.w, M.h, 12); g.fill();
    g.font = '700 13px Manrope, sans-serif'; g.fillStyle = 'rgba(244,241,232,0.85)'; g.textBaseline = 'top';
    g.fillText('Field map · plant population, cell by cell', M.x + 18, M.y + 16);
    const fieldsDef = [[70, 70, 13, 10], [270, 60, 10, 8], [420, 90, 8, 11], [80, 270, 11, 8], [260, 230, 12, 10], [430, 300, 7, 7]];
    fieldsDef.forEach(([fx, fy, cw, chh], i) => {
      const q = clamp(b(0.3 + i * 0.12, 1.0) * 1.2);
      if (q <= 0) return;
      const cs = 11;
      for (let yy = 0; yy < chh; yy++) for (let xx = 0; xx < cw; xx++) {
        if ((xx + yy * cw) / (cw * chh) > q) continue;
        const v = this.heat(xx, yy, i);
        g.fillStyle = `rgb(${Math.round(lerp(64, 150, v))},${Math.round(lerp(110, 205, v))},${Math.round(lerp(48, 90, v))})`;
        g.fillRect(M.x + fx + xx * cs, M.y + fy + yy * cs, cs - 1, cs - 1);
      }
      g.fillStyle = 'rgba(244,241,232,0.8)'; g.font = '600 11px Manrope, sans-serif';
      g.fillText(FIELDS[i].toUpperCase(), M.x + fx, M.y + fy + chh * cs + 6);
    });
    // alert pulse on North 4
    const al = env(t, this.cAlert, this.dockAt, 0.3, 0.5);
    if (al > 0) {
      const pulse = 0.5 + 0.5 * Math.sin(t * 6);
      g.strokeStyle = rgba('#e0573e', al * (0.6 + 0.4 * pulse)); g.lineWidth = 3;
      rrect(g, M.x + 70 - 6, M.y + 70 - 6, 13 * 11 + 12, 10 * 11 + 12, 6); g.stroke();
    }
    // size distribution curve with bands
    const S = { x: 620, y: 206, w: 400, h: 220 };
    g.fillStyle = '#fbfaf5'; g.strokeStyle = PAPER.line; g.lineWidth = 1; rrect(g, S.x, S.y, S.w, S.h, 12); g.fill(); g.stroke();
    g.fillStyle = PAPER.ink; g.font = '700 13px Manrope, sans-serif'; g.fillText('Size distribution', S.x + 16, S.y + 14);
    const cp = b(0.5, 1.2);
    const x0 = S.x + 20, x1 = S.x + S.w - 20, yb = S.y + S.h - 30, ht = 140;
    const f = (u) => Math.exp(-((u - 0.56) ** 2) / 0.035);
    const edges = [0, 0.3, 0.5, 0.72, 1];
    for (let bi = 0; bi < 4; bi++) {
      g.fillStyle = BANDS[bi].col;
      g.beginPath(); g.moveTo(lerp(x0, x1, edges[bi]), yb);
      for (let u = edges[bi]; u <= Math.min(edges[bi + 1], cp) + 1e-6; u += 0.01) g.lineTo(lerp(x0, x1, u), yb - f(u) * ht);
      g.lineTo(lerp(x0, x1, Math.min(edges[bi + 1], cp)), yb); g.closePath();
      if (cp > edges[bi]) g.fill();
    }
    g.strokeStyle = 'rgba(28,29,25,0.35)'; g.beginPath(); g.moveTo(x0, yb); g.lineTo(x1, yb); g.stroke();
    g.fillStyle = PAPER.mute; g.font = '600 10px Manrope, sans-serif';
    ['45', '60', '75'].forEach((lb, i) => g.fillText(`${lb} mm`, lerp(x0, x1, edges[i + 1]) - 14, yb + 8));
    // size split by field (stacked bars)
    const SS = { x: 1040, y: 206, w: 386, h: 220 };
    g.fillStyle = '#fbfaf5'; rrect(g, SS.x, SS.y, SS.w, SS.h, 12); g.fill(); g.stroke();
    g.fillStyle = PAPER.ink; g.font = '700 13px Manrope, sans-serif'; g.fillText('Size split by field', SS.x + 16, SS.y + 14);
    SPLITS.forEach((sp, i) => {
      const y = SS.y + 46 + i * 27, bx = SS.x + 86, bw = SS.w - 106;
      g.fillStyle = PAPER.mute; g.font = '600 11px Manrope, sans-serif'; g.fillText(FIELDS[i], SS.x + 16, y + 3);
      let acc = 0;
      const q = b(0.7 + i * 0.08, 0.7);
      sp.forEach((v, bi) => { g.fillStyle = BANDS[bi].col; g.fillRect(bx + acc * bw * q, y, v * bw * q, 15); acc += v; });
    });
    // stock vs demand
    const SD = { x: 620, y: 446, w: 806, h: 220 };
    g.fillStyle = '#fbfaf5'; rrect(g, SD.x, SD.y, SD.w, SD.h, 12); g.fill(); g.stroke();
    g.fillStyle = PAPER.ink; g.font = '700 13px Manrope, sans-serif'; g.fillText('Stock vs weekly demand', SD.x + 16, SD.y + 14);
    const stock = [0.82, 0.78, 0.74, 0.7, 0.62, 0.56, 0.5, 0.46], dem = [0.6, 0.62, 0.66, 0.64, 0.68, 0.7, 0.66, 0.64];
    const bw2 = 52, gx0 = SD.x + 40, gy0 = SD.y + SD.h - 34, gh = 140;
    stock.forEach((v, i) => {
      const q = b(0.9 + i * 0.05, 0.6);
      const x = gx0 + i * 94;
      g.fillStyle = 'rgba(28,29,25,0.16)'; g.fillRect(x, gy0 - v * gh * q, bw2, v * gh * q);
      g.fillStyle = PAPER.mute; g.font = '600 10px Manrope, sans-serif'; g.fillText(`WK ${30 + i}`, x + 8, gy0 + 8);
    });
    const dq = b(1.3, 0.8);
    g.strokeStyle = rgba(C.accent, 0.95); g.lineWidth = 3; g.beginPath();
    dem.forEach((v, i) => { const x = gx0 + i * 94 + bw2 / 2; const y = gy0 - v * gh; if (i / (dem.length - 1) > dq) return; i ? g.lineTo(x, y) : g.moveTo(x, y); });
    g.stroke();
    g.fillStyle = rgba(C.accent, 0.9); g.font = '700 11px Manrope, sans-serif'; g.fillText('DEMAND', gx0 + 7 * 94 + bw2 + 6, gy0 - dem[7] * gh - 6);
  },

  render(t, ctx) {
    const g = this.g;
    g.clearRect(0, 0, W, H);
    const D = ctx.dur;
    const eqLevel = this.eq.level(t, { times: this.times, dockAt: this.dockAt });
    this.hud(t, { hideSteps: eqLevel > 0.25 });
    const gone = prog(t, this.dockAt - 0.7, 1.0, E.inOutSine);

    // ---------------- stations stream into the line, which becomes the data foundation
    const icA = env(t, 0.1, this.cDash + 0.4, 0.4, 0.4);
    const slabP = prog(t, this.cLand - 0.2, 0.7, E.inOutCubic);
    const slabDown = prog(t, this.cDash - 0.1, 0.9, E.inOutCubic);
    if (t >= 0) drawLine(g, CHAIN.x0, CHAIN.x1, CHAIN.y, { a: 1 - slabP });
    const st = STATIONS.slice(0, 5);
    st.forEach((s, i) => {
      const x = lerp(420, 1500, i / 4), y = 360;
      const q = prog(t, 0.15 + i * 0.1, 0.4, E.outBack);
      if (icA * q <= 0.001) return;
      g.save(); g.globalAlpha = icA * clamp(q * 2);
      g.fillStyle = '#0c0e12'; g.strokeStyle = rgba(C.accent, 0.8); g.lineWidth = 2;
      g.beginPath(); g.arc(x, y, 36 * Math.min(1.08, q), 0, Math.PI * 2); g.fill(); g.stroke();
      drawIcon(g, s.icon, x, y, 32, { color: '#f3f3ef' });
      g.font = '600 13px Manrope, sans-serif'; g.letterSpacing = '0.18em'; g.fillStyle = 'rgba(243,243,239,0.7)'; g.textAlign = 'center';
      g.fillText(s.label.toUpperCase(), x, y + 62);
      g.restore();
      // data particles down into the line
      for (let k = 0; k < 7; k++) {
        const u = ((t - 0.4) * 0.9 + k / 7 + i * 0.13) % 1;
        if (t < 0.4 + i * 0.1) continue;
        const py = lerp(y + 40, CHAIN.y, u), px = x + Math.sin(u * 6 + k) * 6;
        g.fillStyle = rgba(C.accent, icA * Math.sin(u * Math.PI));
        g.fillRect(px - 3, py - 3, 6, 6);
      }
    });
    const sy = lerp(SLAB_Y0, SLAB_Y1, slabDown);
    put(this.slab, { y: sy - 29, sx: lerp(0.02, 1, slabP), sy: lerp(0.06, 1, slabP), o: slabP > 0.01 ? (1 - gone) : 0 });

    // ---------------- the paper dashboard rises out of the slab
    const rise = prog(t, this.cDash + 0.2, 1.0, E.inOutCubic);
    if (rise > 0.001) this.drawPaper(t, rise);
    put(this.paper, { y: (1 - rise) * 380, sy: lerp(0.05, 1, rise), o: clamp(rise * 3) * (1 - gone) });
    this.kpis.forEach((el, i) => { const q = prog(t, this.cDash + 0.7 + i * 0.1, 0.5, E.outCubic); el.style.opacity = q.toFixed(3); el.style.transform = `translateY(${((1 - q) * 12).toFixed(1)}px)`; });

    // ---------------- reports build themselves
    const rp = env(t, this.cRep - 0.1, this.cAlert + 0.9, 0.5, 0.5);
    this.pages.forEach((pg, i) => {
      const q = prog(t, this.cRep - 0.1 + i * 0.16, 0.55, E.outCubic);
      put(pg, { x: lerp(1000, 1360 + i * 60, q), y: lerp(560, 330 + i * 26, q), r: lerp(0, -6 + i * 6, q), s: lerp(0.5, 1, q), o: rp * clamp(q * 2) });
    });
    put(this.fileChips, { y: (1 - prog(t, this.cRep + 0.5, 0.4, E.outCubic)) * 12, o: rp * prog(t, this.cRep + 0.5, 0.4) });

    // ---------------- an alert, in time
    const ta = env(t, this.cAlert, this.cAsk + 0.2, 0.4, 0.4) * (1 - gone);
    put(this.toast, { x: (1 - prog(t, this.cAlert, 0.5, E.outCubic)) * 40, o: ta });

    // ---------------- ask the data
    const ca = env(t, this.cAsk - 0.3, this.dockAt - 0.2, 0.5, 0.5) * (1 - gone);
    put(this.chat, { x: (1 - prog(t, this.cAsk - 0.3, 0.6, E.outCubic)) * 60, o: ca });
    const qt = typed(Q, prog(t, this.cAsk, 1.2, E.linear));
    if (qt !== this.lastQ) { this.qBubble.textContent = qt || ' '; this.lastQ = qt; }
    this.qBubble.style.opacity = qt ? '1' : '0';
    revealWords(this.aSpans, prog(t, this.cAns - 0.1, 1.6, E.linear), { rise: 6, soft: 2 });
    this.aBubble.style.opacity = t > this.cAns - 0.2 ? '1' : '0';
    this.barEls.forEach((b, i) => { const q = prog(t, this.cAns + 0.9 + i * 0.15, 0.6, E.outCubic); b.style.width = `${(q * [62, 68, 73][i]).toFixed(1)}%`; });

    // ---------------- formula
    const pagesSrc = () => ({ x: 1420, y: 480, w: 240 });
    this.eq.render(t, { times: this.times, dockAt: this.dockAt, dock: this.dock, from: { 0: pagesSrc } });
    exitLine(g, t, D);
  },
});
