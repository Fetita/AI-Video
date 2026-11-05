// 01 — Nursery · Seedling survival (proposal).
// Need → Solution panels → two lanes of trays roll under a camera gantry: every cell counted and sized,
// a weak tray flagged early → impact (outcome chips) → impact indicator: Seedlings saved × Cost per seedling.
import { addScene, h, put, prog, E, clamp, lerp, env, makeCanvas, rgba, C, hash, rrect, W, H } from '../engine.js';
import { makeHud, box, tag } from '../lib/ui.js';
import { seg, cueOr } from '../lib/vo.js';
import { EQUATIONS, stationIndex } from '../lib/impact-data.js';
import { makeEquation, eqTimes, dockStart } from '../lib/equation.js';
import { mapDot } from '../lib/chain.js';
import { makeProposalCard } from '../lib/proposal.js';
import { makeOutcome, withFeed, lerpRect, exitLine, makeStatPanel, fmt } from '../lib/chapter.js';
import { seedlingSprite, traySprite } from '../lib/produce.js';

const COLS = 10, ROWS = 5, CELL = 60;
const V = 190;                                   // tray speed (px/s)
const FEEDN = { x: 150, y: 118, w: 1250, h: 826 }; // camera feed (left) + audit column (right)
const GX = 640;                                  // gantry line
const LANES = [FEEDN.y + FEEDN.h * 0.27, FEEDN.y + FEEDN.h * 0.73];

addScene({
  id: 'nursery',
  pre: 0.3,
  post: 0.5,
  setup(ctx) {
    const R = ctx.root;
    this.cv = makeCanvas(R);
    this.g = this.cv.ctx;
    this.tray = traySprite(COLS, ROWS, CELL, 11);
    this.healthy = Array.from({ length: 14 }, (_, i) => seedlingSprite(300 + i, 72, 0.88 + hash(i, 3) * 0.34));
    this.small = Array.from({ length: 6 }, (_, i) => seedlingSprite(400 + i, 72, 0.4 + hash(i, 5) * 0.12));
    this.TW = this.tray.w; this.TH = this.tray.h;
    this.spacing = this.TW + 70;
    // cell state per (lane, tray, i, j): 0 ok, 1 small, 2 empty. Lane 0 / tray 0 is the weak one.
    this.cell = (L, k, i, j) => {
      const hh = hash(L * 3.3 + k * 7.13 + 1, i * 1.37 + 2, j * 2.71 + 3);
      const weak = L === 0 && k === 0;
      const st = hh < (weak ? 0.12 : 0.014) ? 2 : hh < (weak ? 0.28 : 0.055) ? 1 : 0;
      return { st, v: Math.floor(hash(L, k, i, j, 9) * 14) };
    };
    this.tot = (L, k) => { let ok = 0, sm = 0, em = 0; for (let j = 0; j < ROWS; j++) for (let i = 0; i < COLS; i++) { const s = this.cell(L, k, i, j).st; if (s === 0) ok++; else if (s === 1) sm++; else em++; } return { ok, sm, em }; };

    // cue times (scene-relative)
    this.cN2 = seg(ctx, 'n2', 0);
    this.cCount = seg(ctx, 'n2', 1);
    this.cFlag = seg(ctx, 'n2', 2);
    const def = EQUATIONS.nursery;
    this.times = eqTimes(ctx, def);
    this.cOut = cueOr(ctx, 'n3', () => this.times[0] - 3.2);
    this.dockAt = dockStart(def) - ctx.start;
    this.dock = mapDot(stationIndex('nursery'));
    this.liveAt = this.cN2 + 1.25;
    // tray k of lane L: its right edge reaches the gantry at tk(L, k)
    this.tk = (L, k) => this.cCount - 0.6 + (k * this.spacing) / V + L * 1.55;

    this.hud = makeHud(ctx, {
      num: '01', title: 'Nursery · Seedling survival', badge: 'Computer vision',
      steps: [
        { label: 'Scan', at: this.liveAt + 0.2 },
        { label: 'Count', at: this.cCount },
        { label: 'Size', at: this.cCount + 0.75 },
        { label: 'Flag', at: this.cFlag },
      ],
    });
    this.card = makeProposalCard(R, {
      need: 'Know how many seedlings survive in <b>every tray</b>, and catch weak trays early.',
      solution: 'Cameras over moving trays <b>count and size every seedling</b>, cell by cell, with a custom model.',
      h: 300,
    });
    this.panel = makeStatPanel(R, {
      title: 'Tray audit', x: 1430, y: 118, w: 340,
      rows: [['Seedlings counted', '0', C.accentText], ['Undersized', '0', C.amber], ['Empty cells', '0', C.coral], ['Trays flagged', '0', C.coral]],
    });
    // seedling size distribution (area), small bins in amber
    this.hist = h('div', { style: { display: 'flex', alignItems: 'flex-end', gap: '4px', height: '70px', marginTop: '16px' } });
    this.histBars = Array.from({ length: 14 }, (_, i) => { const b = h('i', { style: { display: 'block', flex: '1', background: i < 3 ? 'var(--amber)' : 'var(--accent)', opacity: i < 3 ? '0.85' : '1', borderRadius: '2px 2px 0 0' } }); this.hist.append(b); return b; });
    this.panel.el.append(h('div', { class: 'kicker', style: { fontSize: '11px', marginTop: '14px' } }, 'Seedling size'), this.hist);
    // flagged trays list
    this.flagCard = h('div', { class: 'panel', style: { left: '1430px', top: '640px', width: '340px', padding: '18px 22px', background: 'rgba(12,14,17,0.9)', zIndex: '20' } },
      h('div', { class: 'kicker', style: { fontSize: '11px', marginBottom: '12px' } }, 'Needs attention'),
      h('div', { style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px' } },
        h('span', { style: { fontSize: '19px', fontWeight: '600' } }, 'Tray 0412'),
        h('span', { class: 'badge bad', style: { background: '#2a1411' } }, 'Early intervention')),
      h('div', { style: { fontSize: '15px', color: 'var(--text2)', marginTop: '10px', lineHeight: '1.45' } }, 'Weak cells caught before transplant.'));
    R.append(this.flagCard);
    this.outcome = makeOutcome(R, [
      { text: 'More seedlings survive', dir: 'up' },
      { text: 'Less replanting', dir: 'down' },
      { text: 'Fewer empty-field days', dir: 'down' },
    ]);
    this.eq = makeEquation(R, def);
  },

  render(t, ctx) {
    const g = this.g;
    g.clearRect(0, 0, W, H);
    const D = ctx.dur;
    const eqLevel = this.eq.level(t, { times: this.times, dockAt: this.dockAt });
    this.hud(t, { hideSteps: eqLevel > 0.25 });

    // ---------------- need → solution: unfolds out of the hand-off line, then dissolves into the live view
    this.card.render(t, {
      open: prog(t, 0.05, 1.0, E.linear),
      need: prog(t, 0.75, 1.3, E.linear),
      sol: prog(t, this.cN2 - 0.15, 1.2, E.linear),
      out: prog(t, this.cN2 + 1.2, 0.55, E.linear),
    });

    // ---------------- live view: the gantry feed grows out of the solution column
    const grow = prog(t, this.liveAt - 0.05, 0.85, E.inOutCubic);
    const fade = 1 - prog(t, this.dockAt - 0.7, 1.0, E.inOutSine);
    let counts = { ok: 0, sm: 0, em: 0 };
    if (grow > 0 && fade > 0.001) {
      const rect = lerpRect(this.card.solutionRect(), FEEDN, grow);
      const ovA = prog(t, this.cCount - 0.35, 0.5);
      const summaries = [];
      withFeed(g, rect, () => {
        g.fillStyle = '#111317'; g.fillRect(rect.x, rect.y, rect.w, rect.h);
        LANES.forEach((ly, L) => {
          // bench rails
          g.fillStyle = '#1a1e23'; g.fillRect(FEEDN.x, ly - this.TH / 2 - 16, FEEDN.w, this.TH + 32);
          for (let x = FEEDN.x + ((t * V) % 64) - 64; x < FEEDN.x + FEEDN.w; x += 64) { g.fillStyle = 'rgba(255,255,255,0.035)'; g.fillRect(x, ly - this.TH / 2 - 16, 3, this.TH + 32); }
          const ty = ly - this.TH / 2;
          for (let k = 0; k < 6; k++) {
            const right = GX + (t - this.tk(L, k)) * V;
            const tx = right - this.TW;
            if (tx > FEEDN.x + FEEDN.w + 20 || right < FEEDN.x - 20) continue;
            g.drawImage(this.tray.c, tx, ty);
            let scanned = 0;
            for (let j = 0; j < ROWS; j++) for (let i = 0; i < COLS; i++) {
              const c = this.cell(L, k, i, j);
              const cx = tx + this.tray.m + (i + 0.5) * CELL, cy = ty + this.tray.m + (j + 0.5) * CELL;
              if (c.st !== 2) {
                const spr = c.st === 1 ? this.small[c.v % this.small.length] : this.healthy[c.v];
                const s = c.st === 1 ? 54 : 66;
                g.drawImage(spr, cx - s / 2, cy - s / 2, s, s);
              }
              if (cx <= GX + 6) continue;
              scanned++;
              if (c.st === 0) counts.ok++; else if (c.st === 1) counts.sm++; else counts.em++;
              if (ovA <= 0) continue;
              const flash = clamp(1 - (cx - GX) / 90);
              if (c.st === 0) {
                const rr = 13 + hash(L, k, i, j, 4) * 6;
                g.strokeStyle = rgba(C.accent, ovA * (0.55 + flash * 0.45)); g.lineWidth = 1.6 + flash;
                g.beginPath(); g.arc(cx, cy, rr, 0, Math.PI * 2); g.stroke();
                g.fillStyle = rgba(C.accent, ovA * 0.9); g.beginPath(); g.arc(cx, cy, 2.4, 0, Math.PI * 2); g.fill();
              } else if (c.st === 1) {
                box(g, cx - CELL / 2 + 6, cy - CELL / 2 + 6, CELL - 12, CELL - 12, { color: C.amber, a: ovA, lw: 1.5, fill: 0.08 });
                tag(g, cx - CELL / 2 + 6, cy - CELL / 2 + 5, 'SMALL', { bg: C.amber, fg: '#1a1205', a: ovA, size: 9, pad: 3 });
              } else {
                box(g, cx - CELL / 2 + 6, cy - CELL / 2 + 6, CELL - 12, CELL - 12, { color: C.coral, a: ovA, lw: 1.5, dash: [5, 4], fill: 0.1 });
              }
            }
            const frac = scanned / (COLS * ROWS);
            const weak = L === 0 && k === 0;
            const sumA = ovA * prog(frac, 0.45, 0.1) * (weak ? prog(t, this.cFlag - 0.15, 0.3) : 1);
            if (sumA > 0) summaries.push({ L, k, tx, ty, frac, weak, sumA });
            if (weak) {
              const pulse = env(t, this.cFlag, this.cFlag + 1.8, 0.15, 0.8) * (0.5 + 0.5 * Math.sin(t * 9));
              if (pulse > 0) { g.strokeStyle = rgba(C.coral, pulse * 0.85); g.lineWidth = 3; rrect(g, tx - 6, ty - 6, this.TW + 12, this.TH + 12, 14); g.stroke(); }
            }
          }
        });
        // gantry: beam across both lanes, scan band, camera heads above each lane
        const sb = g.createLinearGradient(GX - 4, 0, GX + 70, 0);
        sb.addColorStop(0, rgba(C.accent, 0.3)); sb.addColorStop(1, rgba(C.accent, 0));
        g.fillStyle = sb; g.fillRect(GX - 4, FEEDN.y, 74, FEEDN.h);
        g.fillStyle = rgba(C.accent, 0.9); g.fillRect(GX + 4, FEEDN.y, 2, FEEDN.h);
        const bm = g.createLinearGradient(GX - 26, 0, GX, 0);
        bm.addColorStop(0, '#2a2f35'); bm.addColorStop(0.5, '#6b737b'); bm.addColorStop(1, '#23272c');
        g.fillStyle = bm; g.fillRect(GX - 26, FEEDN.y, 26, FEEDN.h);
        LANES.forEach((ly) => {
          const cy = ly - this.TH / 2 - 16;
          g.fillStyle = '#0d0f12'; g.strokeStyle = C.accent; g.lineWidth = 2;
          rrect(g, GX - 38, cy - 20, 50, 40, 8); g.fill(); g.stroke();
          g.fillStyle = C.accent; g.beginPath(); g.arc(GX - 13, cy, 6, 0, Math.PI * 2); g.fill();
        });
        // tray summaries on top
        summaries.forEach(({ L, k, tx, ty, frac, weak, sumA }) => {
          const tt = this.tot(L, k);
          const lab = `TRAY 04${12 + k * 2 + L}  ·  ${tt.ok + tt.sm} / ${COLS * ROWS} ALIVE  ·  ${tt.sm} SMALL  ·  ${tt.em} EMPTY`;
          const r1 = tag(g, tx, ty - 10, lab, { bg: '#0b0d10', fg: '#f3f3ef', a: sumA, size: 11.5, stroke: 'rgba(255,255,255,0.18)', hgt: 26, pad: 9 });
          if (r1) tag(g, tx + r1.w + 6, ty - 10, weak ? 'EARLY INTERVENTION' : (frac > 0.99 ? '✓ READY' : 'SCANNING'), { bg: weak ? C.coral : frac > 0.99 ? C.accent : 'rgba(255,255,255,0.14)', fg: weak ? '#1d0905' : '#fff', a: sumA, size: 11.5, hgt: 26, pad: 9 });
        });
      }, { a: fade, label: grow > 0.9 ? 'GANTRY CAM · BENCH 4' : null, t: t + 12.4 });
    }
    // audit column
    this.panel.set(0, fmt(4318 + counts.ok + counts.sm));
    this.panel.set(1, fmt(57 + counts.sm));
    this.panel.set(2, fmt(21 + counts.em));
    this.panel.set(3, t > this.cFlag + 0.1 ? '1' : '0');
    const hg = clamp((t - this.cCount) / 1.5);
    this.histBars.forEach((b, i) => { const base = i < 3 ? 0.25 + 0.12 * i : Math.exp(-((i - 8.5) ** 2) / 9); b.style.height = `${(6 + base * 60 * hg * (0.92 + 0.08 * Math.sin(t * 3 + i))).toFixed(1)}px`; });
    const colA = (at) => env(t, at, this.dockAt - 0.3, 0.45, 0.6) * (1 - prog(t, this.times[0] - 0.8, 0.6) * 0.0);
    this.panel.show(t, this.cCount - 0.1, this.dockAt - 0.3);
    put(this.flagCard, { x: (1 - prog(t, this.cFlag + 0.1, 0.5, E.outCubic)) * 30, o: colA(this.cFlag + 0.1) });

    // ---------------- outcome → formula → dock
    this.outcome.render(t, this.cOut - 0.1, this.times[0] - 0.55);
    this.eq.render(t, {
      times: this.times,
      dockAt: this.dockAt,
      dock: this.dock,
      from: { 0: () => ({ x: 1430 + 170, y: 118 + 56 + 22, w: 300 }) },
    });
    exitLine(g, t, D);
  },
});
