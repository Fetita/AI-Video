// 02 — Real-world AI · Detection · Tracking
// Tractor camera → live crop feed (detect · count · measure · map) → packing line (ID · track · count).
import { addScene, h, put, prog, E, clamp, lerp, env, makeCanvas, rng, rgba, C, hash, rrect, keys, TIMELINE } from '../engine.js';
import { makeHud, box, tag, recHud, brackets, FONT_UI } from '../lib/ui.js';

import { FRAME, ROWS, ROW_X0, ROW_DX, PITCH, SPEED, plantAt } from '../lib/field.js';
import { PLATES, makePlate, shotAt } from '../lib/shot.js';
import TRACTOR from '../shots/tractor.js';
import PACKLINE from '../shots/packline.js';
import { PACK } from '../lib/pack.js';
const COUNT_Y = FRAME.y + FRAME.h * 0.64;
const ROW_COLORS = ['#ffb35c', '#ff7b6b', '#5fe0c2', '#ff8fc8', '#ffd76b', '#c8e86b'];
const fmt = (n) => n.toLocaleString('en-US');

// The tractor and the crop feed are Blender plates (scripts/render_field.py): the tractor shot exports its boom
// camera's lens and ground footprint per frame (shots/tractor.js); the feed is orthographic at the film's own
// pixel scale and built from plantAt(), so the feed's overlays below land on the rendered plants unchanged.

addScene({
  id: 'agri',
  pre: 0.3,
  post: 0.6,
  setup(ctx) {
    const R = ctx.root;
    this.hud = makeHud(ctx, {
      num: '02', title: 'Real-world AI · Detection · Tracking', badge: 'Client project',
      steps: [
        { label: 'Detect', at: ctx.cue('a2', 0) + 0.9 },
        { label: 'Count', at: ctx.cue('a2', 1) },
        { label: 'Measure', at: ctx.cue('a2', 1) + 0.8 },
        { label: 'Map', at: ctx.cue('a2', 2) },
        { label: 'Track', at: ctx.cue('a3', 1) },
      ],
    });
    this.tractor = makePlate(R, 'tractor');
    this.feed = makePlate(R, 'feed', { x: FRAME.x, y: FRAME.y, w: FRAME.w, h: FRAME.h, radius: 18 });
    this.feed.el.style.transformOrigin = `${960 - FRAME.x}px ${531 - FRAME.y}px`;
    this.packPlate = makePlate(R, 'packline', { x: FRAME.x, y: FRAME.y, w: FRAME.w, h: FRAME.h, radius: 18 });
    for (const p of [this.packPlate, this.feed, this.tractor]) R.prepend(p.el);
    const cv = makeCanvas(R);
    this.g = cv.ctx;
    // telemetry card (tractor shot)
    this.tele = h('div', { class: 'panel', style: { left: '1290px', top: '190px', width: '440px', padding: '22px 26px' } });
    this.teleRows = [['Plants detected', '0'], ['Row', '14 of 38'], ['Position', '41.12341, −98.45672'], ['Feed', 'Live']].map(([k, v]) => {
      const val = h('span', { class: 'tnum', style: { color: 'var(--text)', fontSize: '17px' } }, v);
      const row = h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', height: '44px', borderBottom: '1px solid var(--line)' } }, h('span', { class: 'kicker' }, k), val);
      return { row, val };
    });
    this.tele.append(h('div', { style: { display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' } }, h('span', { style: { width: '9px', height: '9px', borderRadius: '50%', background: 'var(--coral)' } }), h('span', { style: { fontSize: '18px', fontWeight: 600 } }, 'Tractor camera · live')), ...this.teleRows.map((r) => r.row));
    this.teleRows[3].row.style.borderBottom = 'none';
    R.append(this.tele);
    // live audit panel (field feed)
    this.audit = h('div', { class: 'panel', style: { left: '1370px', top: '150px', width: '370px', padding: '20px 24px', background: 'rgba(12,14,17,0.88)' } });
    const stat = (k, cls) => { const v = h('div', { class: 'tnum', style: { fontSize: '26px', color: cls || 'var(--text)', marginTop: '2px' } }, '0'); return { el: h('div', { style: { padding: '10px 0', borderBottom: '1px solid var(--line)' } }, h('div', { class: 'kicker', style: { fontSize: '11px' } }, k), v), v }; };
    this.sPlants = stat('Plants counted', 'var(--accent)');
    this.sSpacing = stat('Avg spacing');
    this.sGaps = stat('Gaps', 'var(--coral)');
    this.sOff = stat('Off-row', 'var(--coral)');
    this.hist = h('div', { style: { display: 'flex', alignItems: 'flex-end', gap: '4px', height: '56px', marginTop: '14px' } });
    this.histBars = Array.from({ length: 14 }, (_, i) => { const b = h('i', { style: { display: 'block', flex: 1, background: i > 3 && i < 11 ? 'var(--accent)' : 'rgba(130,52,254,0.35)', borderRadius: '2px 2px 0 0' } }); this.hist.append(b); return b; });
    this.audit.append(h('div', { style: { fontSize: '17px', fontWeight: 600, marginBottom: '6px' } }, 'Live field audit'), this.sPlants.el, this.sSpacing.el, this.sGaps.el, this.sOff.el,
      h('div', { class: 'kicker', style: { fontSize: '11px', marginTop: '12px' } }, 'Plant size distribution'), this.hist);
    R.append(this.audit);
    // packing-line panel
    this.pack = h('div', { class: 'panel', style: { left: '190px', top: '806px', display: 'flex', alignItems: 'center', gap: '44px', padding: '14px 30px', background: 'rgba(12,14,17,0.9)' } });
    const pstat = (k, col) => { const v = h('span', { class: 'tnum', style: { fontSize: '24px', color: col || 'var(--text)' } }, '0'); return { el: h('div', { style: { display: 'flex', flexDirection: 'column', gap: '4px' } }, h('span', { class: 'kicker', style: { fontSize: '11px' } }, k), v), v }; };
    this.pCount = pstat('Counted', 'var(--accent)');
    this.pView = pstat('Tracked in view');
    this.pSize = pstat('Avg diameter');
    this.pack.append(h('div', { style: { fontSize: '16px', fontWeight: 600, width: '130px', lineHeight: 1.3 } }, 'Packing line', h('br'), h('span', { class: 'kicker', style: { fontSize: '10.5px', color: 'var(--coral)' } }, '● Live')), this.pCount.el, this.pView.el, this.pSize.el);
    R.append(this.pack);
    // hand-off line into the search scene's brief card (same position as the hook/intro line)
    this.handoff = h('div', { class: 'abs', style: { left: '460px', top: '483px', width: '1000px', height: '2px', background: 'var(--accent)', transformOrigin: '50% 50%', boxShadow: '0 0 16px rgba(130,52,254,0.6)' } });
    this.handoff.style.display = 'none'; // scene changes are camera moves now (engine.js sceneCamera)
    R.append(this.handoff);
    const scenes = TIMELINE.scenes.map((s) => s.id);
    this.handsOff = scenes[scenes.indexOf('agri') + 1] === 'search'; // other cuts end without it
  },

  render(t, ctx) {
    const g = this.g;
    g.clearRect(0, 0, 1920, 1080);
    this.hud(t);
    const D = ctx.dur;
    const cCam = ctx.cue('a1', 1), cData = ctx.cue('a1', 2), cTr = ctx.cue('a2', 0), cCount = ctx.cue('a2', 1), cMap = ctx.cue('a2', 2), cPack = ctx.cue('a3', 0), cID = ctx.cue('a3', 1), cKeep = ctx.cue('a3', 2);

    // ================= A: tractor establishing shot (Blender plate; overlays at the boom camera from its export)
    const pending = [];
    const trA = env(t, -0.3, cTr + 0.95, 0.5, 0.35);
    this.tractor.el.style.opacity = trA.toFixed(3);
    this.tractor.el.style.display = trA > 0.001 ? 'block' : 'none';
    if (trA > 0.001) {
      const t0 = PLATES.tractor.t0();
      pending.push(this.tractor.show(t, t0));
      const S = shotAt(TRACTOR, 'tractor', t, t0);
      const lens = S.pt('lens'), foot = S.pt('foot');
      const push = prog(t, cTr + 0.1, 0.9, E.inCubic);
      const camPulse = env(t, cCam - 0.1, cCam + 1.2, 0.2, 0.8) * (1 - push);
      g.save(); g.globalAlpha = trA * (1 - push);
      // the camera's field of view, down to its footprint on the rows
      const lx = lens[0], ly = lens[1];
      const fov = g.createLinearGradient(lx, ly, lx, Math.max(...foot.map((q) => q[1])));
      fov.addColorStop(0, `rgba(130,52,254,${(0.28 + camPulse * 0.25).toFixed(3)})`); fov.addColorStop(1, 'rgba(130,52,254,0.05)');
      g.fillStyle = fov;
      g.beginPath(); g.moveTo(foot[0][0], foot[0][1]); foot.forEach((q) => g.lineTo(q[0], q[1])); g.closePath(); g.fill();
      g.strokeStyle = rgba(C.accent, 0.5); g.lineWidth = 1.5;
      g.beginPath(); foot.forEach((q) => { g.moveTo(lx, ly); g.lineTo(q[0], q[1]); }); g.stroke();
      g.beginPath(); g.moveTo(foot[0][0], foot[0][1]); foot.forEach((q) => g.lineTo(q[0], q[1])); g.closePath(); g.stroke();
      if (camPulse > 0) { g.strokeStyle = rgba(C.accent, camPulse); g.lineWidth = 2; g.beginPath(); g.arc(lx, ly, 26 + (1 - camPulse) * 30, 0, Math.PI * 2); g.stroke(); }
      g.restore();
      if (t > cCam && push < 0.5) tag(g, lx + 34, ly - 30, 'CAMERA', { a: trA * prog(t, cCam, 0.4) * (1 - push * 2), size: 12 });
      // data packets streaming from the camera to the telemetry card
      if (t > cData - 0.2 && push < 1) {
        for (let i = 0; i < 16; i++) {
          const u = ((t - cData) * 0.9 + i / 16) % 1;
          if (t - cData + i / 16 < 0) continue;
          const x = lerp(lx, 1290, E.inOutSine(u)), y = lerp(ly, 260, E.inOutSine(u)) - Math.sin(u * Math.PI) * 120;
          g.fillStyle = rgba(C.accent, trA * Math.sin(u * Math.PI) * (1 - push));
          g.fillRect(x - 3, y - 3, 6, 6);
        }
      }
    }
    const teleA = env(t, cData - 0.1, cTr + 0.5, 0.4, 0.35);
    put(this.tele, { x: (1 - prog(t, cData - 0.1, 0.5, E.outCubic)) * 30, o: teleA });
    this.teleRows[0].val.textContent = fmt(Math.floor(clamp((t - cData) / 3) * 146));
    this.teleRows[2].val.textContent = `41.${String(12341 + Math.floor(Math.max(0, t - cData) * 17)).padStart(5, '0')}, −98.45672`;

    // ================= B: live crop feed from the tractor camera
    const feedA = env(t, cTr + 0.7, cMap + 0.9, 0.35, 0.5);
    this.feed.el.style.display = feedA > 0.001 ? 'block' : 'none';
    // the overlays follow the plate's own frame (the plate holds each frame for 1/30 s)
    const tF = PLATES.feed.t0({ cTr }) + Math.floor((t - PLATES.feed.t0({ cTr })) * 30 + 1e-6) / 30;
    const scroll = (feedA > 0.001 ? tF : t) * SPEED;
    if (feedA > 0.001) {
      pending.push(this.feed.show(t, PLATES.feed.t0({ cTr })));
      put(this.feed.el, { s: 1 + (1 - prog(t, cTr + 0.7, 0.8, E.outCubic)) * 0.25, o: feedA });
    }
    const crossedAt = (row, k) => (k * PITCH + plantAt(row, k).jy + FRAME.y - COUNT_Y) / SPEED; // time when plant k crosses the count line
    let counted = 0, gaps = 0, offs = 0;
    if (feedA > 0.001) {
      g.save(); g.globalAlpha = feedA;
      const zoomIn = 1 + (1 - prog(t, cTr + 0.7, 0.8, E.outCubic)) * 0.25;
      g.translate(960, 531); g.scale(zoomIn, zoomIn); g.translate(-960, -531);
      rrect(g, FRAME.x, FRAME.y, FRAME.w, FRAME.h, 18); g.clip();
      const ovA = prog(t, cTr + 1.0, 0.6, E.outCubic);
      const measureA = prog(t, cCount + 0.7, 0.6);
      // row lines (fitted)
      for (let r = 0; r < ROWS; r++) {
        const x = ROW_X0 + r * ROW_DX;
        g.strokeStyle = rgba(ROW_COLORS[r], 0.55 * ovA); g.lineWidth = 2;
        g.beginPath(); g.moveTo(x, FRAME.y); g.lineTo(x, FRAME.y + FRAME.h); g.stroke();
      }
      // plants
      const kMin = Math.floor((scroll - 200) / PITCH), kMax = Math.ceil((scroll + FRAME.h + 200) / PITCH);
      for (let r = 0; r < ROWS; r++) {
        let prev = null;
        for (let k = kMin; k <= kMax; k++) {
          const p = plantAt(r, k);
          const x = ROW_X0 + r * ROW_DX + p.jx;
          // field position k·PITCH scrolls from the top of the feed to the bottom as the tractor advances
          const py = FRAME.y + FRAME.h + 120 - (k * PITCH - scroll + p.jy);
          if (py < FRAME.y - 80 || py > FRAME.y + FRAME.h + 80) { prev = p.missing ? prev : { x, y: py }; continue; }
          const sz = 116 * p.s;
          if (ovA > 0) {
            const vis = clamp((py - FRAME.y - 30) / 60);
            const a = ovA * vis;
            const passed = py > COUNT_Y;
            if (p.missing) {
              box(g, x - 46, py - 46, 92, 92, { color: C.coral, a: a * 0.9, dash: [6, 5], fill: 0.05 });
              tag(g, x - 46, py - 50, 'GAP', { bg: C.coral, a, size: 11 });
            } else {
              const col = p.off ? C.coral : C.accent;
              const bw = sz * 0.8;
              const flash = passed ? clamp(1 - (py - COUNT_Y) / 60) : 0;
              box(g, x - bw / 2, py - bw / 2, bw, bw, { color: col, a, lw: 1.4 + flash * 1.5, fill: 0.04 + flash * 0.15 });
              tag(g, x - bw / 2, py - bw / 2 - 3, p.off ? 'OFF-ROW' : `#${p.id}`, { bg: p.off ? C.coral : rgba(C.accent, 0.9), a: a * (p.off ? 1 : 0.85), size: 10, pad: 4 });
              if (p.off && a > 0) { g.strokeStyle = rgba(C.coral, a); g.lineWidth = 2; g.setLineDash([4, 4]); g.beginPath(); g.moveTo(x, py); g.lineTo(ROW_X0 + r * ROW_DX, py); g.stroke(); g.setLineDash([]); tag(g, (x + ROW_X0 + r * ROW_DX) / 2, py + 16, `${Math.round(Math.abs(p.off) / 7)} cm`, { bg: '#0b0d10', fg: C.coral, a, size: 10, anchor: 'c' }); }
              // measurement: diameter on rows 1 and 4
              if (measureA > 0 && (r === 1 || r === 4) && k % 2 === 0) {
                const ang = 0.6 + p.v * 0.3, rr = sz * 0.36;
                g.strokeStyle = rgba('#ffffff', a * measureA); g.lineWidth = 2;
                g.beginPath(); g.moveTo(x - Math.cos(ang) * rr, py - Math.sin(ang) * rr); g.lineTo(x + Math.cos(ang) * rr, py + Math.sin(ang) * rr); g.stroke();
                g.fillStyle = rgba('#ffffff', a * measureA);
                [-1, 1].forEach((sg) => { g.beginPath(); g.arc(x + sg * Math.cos(ang) * rr, py + sg * Math.sin(ang) * rr, 3.5, 0, Math.PI * 2); g.fill(); });
                tag(g, x + bw / 2 + 4, py + 6, `Ø ${Math.round(11 + p.s * 5)} cm`, { bg: '#0b0d10', fg: '#fff', a: a * measureA, size: 11, anchor: 'bl', stroke: 'rgba(255,255,255,0.3)' });
              }
              // spacing ticks on row 2
              if (measureA > 0 && r === 2 && prev) {
                g.strokeStyle = rgba(C.sky, a * measureA); g.lineWidth = 1.5;
                const x2 = ROW_X0 + r * ROW_DX + 70;
                g.beginPath(); g.moveTo(x2, prev.y); g.lineTo(x2, py); g.moveTo(x2 - 6, prev.y); g.lineTo(x2 + 6, prev.y); g.moveTo(x2 - 6, py); g.lineTo(x2 + 6, py); g.stroke();
                tag(g, x2 + 10, (prev.y + py) / 2 + 9, `${Math.round((prev.y - py) / 5)} cm`, { bg: '#0b0d10', fg: C.sky, a: a * measureA, size: 10, anchor: 'bl' });
              }
              // GPS pin as it's counted
              if (passed && py - COUNT_Y < 90 && t > cMap - 0.3) {
                const ga = clamp(1 - (py - COUNT_Y) / 90) * ovA;
                tag(g, x + 30, py - 30, `${(41.12 + p.id * 0.000013).toFixed(5)}, −98.4${(5600 + p.id % 97).toString()}`, { bg: '#0b0d10', fg: C.accentText, a: ga, size: 10, stroke: rgba(C.accent, 0.4) });
              }
            }
          }
          if (!p.missing) prev = { x, y: py };
        }
      }
      // count line
      g.strokeStyle = `rgba(255,255,255,${(0.75 * prog(t, cCount - 0.2, 0.4)).toFixed(3)})`; g.lineWidth = 2;
      g.beginPath(); g.moveTo(FRAME.x, COUNT_Y); g.lineTo(FRAME.x + FRAME.w, COUNT_Y); g.stroke();
      tag(g, FRAME.x + 24, COUNT_Y - 8, 'COUNT LINE', { bg: null, fg: 'rgba(255,255,255,0.75)', a: prog(t, cCount - 0.2, 0.4), size: 11, anchor: 'bl', pad: 0 });
      g.restore();
      g.save(); g.globalAlpha = feedA;
      recHud(g, FRAME.x + 28, FRAME.y + 24, 'TRACTOR CAM · ROW 14', t + 3.1);
      g.strokeStyle = 'rgba(255,255,255,0.14)'; g.lineWidth = 1; rrect(g, FRAME.x + 0.5, FRAME.y + 0.5, FRAME.w, FRAME.h, 18); g.stroke();
      g.restore();
    }
    // audit numbers: plants whose crossing time has passed since counting started
    {
      const tc = Math.max(0, t - cCount);
      counted = 1284 + Math.floor(tc * SPEED / PITCH * ROWS * 0.96);
      gaps = 12 + Math.floor(tc * 0.9);
      offs = 7 + Math.floor(tc * 0.5);
    }
    const auditA = env(t, cCount - 0.1, cMap + 3.1, 0.4, 0.4);
    put(this.audit, { x: (1 - prog(t, cCount - 0.1, 0.5, E.outCubic)) * 30, o: auditA });
    this.sPlants.v.textContent = fmt(counted);
    this.sSpacing.v.textContent = `${(29.4 + Math.sin(t * 1.3) * 0.3).toFixed(1)} cm`;
    this.sGaps.v.textContent = String(gaps);
    this.sOff.v.textContent = String(offs);
    this.histBars.forEach((b, i) => { const base = Math.exp(-((i - 7) ** 2) / 10); b.style.height = `${(8 + base * 46 * clamp((t - cCount) / 1.5) * (0.9 + 0.1 * Math.sin(t * 3 + i))).toFixed(1)}px`; });

    // ================= C: map — every counted plant has a position
    const mapA = env(t, cMap + 0.35, cPack + 0.25, 0.6, 0.4);
    if (mapA > 0.001) {
      g.save(); g.globalAlpha = mapA;
      const zin = prog(t, cMap + 0.35, 1.4, E.outCubic);
      const S = lerp(2.2, 1, zin);
      g.translate(700, 540); g.scale(S, S); g.translate(-700, -540);
      const poly = [[260, 240], [1150, 200], [1210, 860], [300, 900]];
      g.fillStyle = '#10150f'; g.strokeStyle = 'rgba(255,255,255,0.3)'; g.lineWidth = 2 / S;
      g.beginPath(); poly.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y))); g.closePath(); g.fill(); g.stroke();
      g.save(); g.clip();
      const nRows = 38;
      const covered = 14 + clamp((t - cMap - 0.4) / 2) * 3;
      for (let rI = 0; rI < nRows; rI++) {
        const u = (rI + 0.5) / nRows;
        const x0 = lerp(260, 1150, u), x1 = lerp(300, 1210, u);
        if (rI < covered) {
          for (let k = 0; k < 90; k++) {
            const v = k / 90;
            if (rI > covered - 1 && v > (covered % 1)) break;
            const x = lerp(x0, x1, v), y = lerp(lerp(240, 200, u), lerp(900, 860, u), v);
            const bad = hash(rI, k, 3) < 0.03;
            g.fillStyle = bad ? C.coral : rgba(C.accent, 0.8);
            g.fillRect(x - 2, y - 2, bad ? 5 : 3.2, bad ? 5 : 3.2);
          }
        } else {
          g.strokeStyle = 'rgba(255,255,255,0.05)'; g.lineWidth = 1;
          g.beginPath(); g.moveTo(x0, lerp(240, 200, u)); g.lineTo(x1, lerp(900, 860, u)); g.stroke();
        }
      }
      g.restore();
      // tractor marker
      const u = (covered - 0.5) / nRows, v = covered % 1;
      const mx = lerp(lerp(260, 1150, u), lerp(300, 1210, u), v), my = lerp(lerp(240, 200, u), lerp(900, 860, u), v);
      g.fillStyle = C.accent; g.beginPath(); g.arc(mx, my, 7 / S, 0, Math.PI * 2); g.fill();
      g.strokeStyle = rgba(C.accent, 0.5); g.lineWidth = 2 / S; g.beginPath(); g.arc(mx, my, (16 + Math.sin(t * 5) * 3) / S, 0, Math.PI * 2); g.stroke();
      g.restore();
      // callout: a single plant, geo-located
      const ca = prog(t, cMap + 1.3, 0.5, E.outCubic) * mapA;
      if (ca > 0) {
        const px = 520, py = 520;
        g.save(); g.globalAlpha = ca;
        g.strokeStyle = C.accent; g.lineWidth = 2; g.beginPath(); g.arc(px, py, 12, 0, Math.PI * 2); g.stroke();
        g.beginPath(); g.moveTo(px + 12, py - 8); g.lineTo(px + 90, py - 70); g.lineTo(px + 150, py - 70); g.stroke();
        g.restore();
        tag(g, px + 150, py - 70 + 13, 'PLANT #04812 · 41.12417, −98.45691 · Ø 14 cm', { a: ca, bg: '#0b0d10', fg: C.accentText, stroke: rgba(C.accent, 0.6), size: 12, anchor: 'bl', hgt: 26 });
      }
      tag(g, 260, 180, 'FIELD MAP · EVERY PLANT GEO-LOCATED', { a: mapA * prog(t, cMap + 0.6, 0.5), font: FONT_UI, track: 0.16, bg: null, fg: 'rgba(255,255,255,0.7)', size: 13, anchor: 'bl', pad: 0 });
    }

    // ================= D: packing line — ID, track, count (Blender plate; overlays follow each pumpkin's export)
    const out = ctx.last ? prog(t, D - 0.8, 0.5, E.inCubic) : prog(t, D - 0.32, 0.32, E.inCubic); // leaves with the camera's fly-out
    const packA = env(t, cPack - 0.1, D + 1, 0.45, 0.01) * (1 - out);
    const LINE_X = PACK.LINE_X, by0 = PACK.by0, bh = PACK.bh;
    let packCount = 1038, inView = 0;
    this.packPlate.el.style.display = packA > 0.001 ? 'block' : 'none';
    if (packA > 0.001) {
      const t0p = PLATES.packline.t0({ cPack });
      pending.push(this.packPlate.show(t, t0p));
      put(this.packPlate.el, { o: packA });
      const S = shotAt(PACKLINE, 'packline', t, t0p);
      const tq = t0p + S.i / 30;
      // the running count: every pumpkin past the line so far (the same model the plate was built from)
      for (let k = 0; k < PACK.N; k++) if (FRAME.x - 110 + (tq - cPack - PACK.spawn(k)) * PACK.BV > LINE_X) packCount++;
      const at = (i, k) => { const r = PACKLINE.pts.pumpkin[i]; const q = r && r[k]; return q ? { x: q[0] + FRAME.x, y: q[1] + FRAME.y, R: q[2] } : null; };
      const items = Object.keys(S.pt('pumpkin') || {}).map((k) => ({ k: +k, ...at(S.i, k) }));
      g.save(); g.globalAlpha = packA;
      rrect(g, FRAME.x, FRAME.y, FRAME.w, FRAME.h, 18); g.clip();
      const ovA = prog(t, cID - 0.2, 0.5);
      // count line (once the camera has settled overhead)
      g.strokeStyle = `rgba(255,255,255,${(0.8 * ovA).toFixed(3)})`; g.lineWidth = 2; g.setLineDash([10, 8]);
      g.beginPath(); g.moveTo(LINE_X, by0 - 40); g.lineTo(LINE_X, by0 + bh + 40); g.stroke(); g.setLineDash([]);
      tag(g, LINE_X + 10, by0 - 50, 'COUNT LINE', { bg: null, fg: 'rgba(255,255,255,0.8)', a: ovA, size: 11, anchor: 'bl', pad: 0 });
      items.forEach((it) => {
        const seen = clamp((it.x - FRAME.x - 20) / 60) * ovA;
        if (seen <= 0) return;
        inView += it.x < FRAME.x + FRAME.w ? 1 : 0;
        // trail: where the plate showed this pumpkin over the last 1.2 s
        g.strokeStyle = rgba(C.sky, 0.8 * seen); g.lineWidth = 2.5; g.beginPath();
        for (let s2 = 0; s2 <= 20; s2++) { const q = at(S.i - Math.round(s2 * 1.8), String(it.k)); if (!q || q.x < FRAME.x) break; s2 ? g.lineTo(q.x, q.y) : g.moveTo(q.x, q.y); }
        g.stroke();
        const counted2 = it.x > LINE_X;
        const flash = counted2 ? clamp(1 - (it.x - LINE_X) / 90) : 0;
        const col = counted2 ? C.accent : C.sky;
        box(g, it.x - it.R, it.y - it.R, it.R * 2, it.R * 2, { color: col, a: seen, lw: 1.6 + flash * 1.5, fill: 0.03 + flash * 0.18 });
        tag(g, it.x - it.R, it.y - it.R - 4, `ID ${1040 + it.k}${counted2 ? '  ✓ COUNTED' : ''}`, { bg: col, a: seen, size: 11 });
        g.fillStyle = rgba('#ffffff', seen); g.beginPath(); g.arc(it.x, it.y, 3.5, 0, Math.PI * 2); g.fill();
        const md = prog(t, cID + 0.8, 0.5) * seen;
        if (md > 0) {
          const an = 0.45;
          g.strokeStyle = rgba('#ffffff', md * 0.9); g.lineWidth = 1.6;
          g.beginPath(); g.moveTo(it.x - Math.cos(an) * it.R * 0.84, it.y + Math.sin(an) * it.R * 0.84); g.lineTo(it.x + Math.cos(an) * it.R * 0.84, it.y - Math.sin(an) * it.R * 0.84); g.stroke();
          tag(g, it.x - it.R, it.y + it.R + 22, `Ø ${Math.round(it.R / 3.1)} cm`, { bg: '#0b0d10', fg: '#fff', a: md, size: 10.5, anchor: 'bl', stroke: 'rgba(255,255,255,0.25)' });
        }
      });
      g.restore();
      g.save(); g.globalAlpha = packA;
      recHud(g, FRAME.x + 28, FRAME.y + 24, 'LINE CAM 02', t + 40);
      g.strokeStyle = 'rgba(255,255,255,0.14)'; g.lineWidth = 1; rrect(g, FRAME.x + 0.5, FRAME.y + 0.5, FRAME.w, FRAME.h, 18); g.stroke();
      g.restore();
    }
    const packPanelA = env(t, cID - 0.1, D + 1, 0.4, 0.01) * (1 - out);
    put(this.pack, { y: (1 - prog(t, cID - 0.1, 0.5, E.outCubic)) * 20, o: packPanelA });
    this.pCount.v.textContent = fmt(packCount);
    this.pView.v.textContent = String(inView);
    this.pSize.v.textContent = `${(26.8 + Math.sin(t) * 0.4).toFixed(1)} cm`;
    // hand-off: a violet line draws where the next scene's brief card opens
    const hp = this.handsOff ? prog(t, D - 0.55, 0.5, E.inOutCubic) : 0;
    put(this.handoff, { sx: hp, o: hp > 0 ? 1 : 0 });
    return pending.length ? Promise.all(pending) : undefined;
  },
});
