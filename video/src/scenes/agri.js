// 04 — Real-world AI · Detection · Tracking
// Tractor camera → live crop feed (detect · count · measure · map) → packing line (ID · track · count).
import { addScene, h, put, prog, E, clamp, lerp, env, makeCanvas, rng, rgba, C, hash, rrect, keys } from '../engine.js';
import { makeHud, box, tag, recHud, brackets, FONT_MONO, FONT_UI } from '../lib/ui.js';

import { FRAME, ROWS, ROW_X0, ROW_DX, PITCH, SPEED, plantSprite, pumpkinSprite, soilTile, plantAt } from '../lib/field.js';
const COUNT_Y = FRAME.y + FRAME.h * 0.64;
const ROW_COLORS = ['#ffb35c', '#ff7b6b', '#5fe0c2', '#ff8fc8', '#ffd76b', '#c8e86b'];
const fmt = (n) => n.toLocaleString('en-US');

// ------------------------------------------------------------ tractor (line art, side view)
function drawTractor(g, t, ox, oy, S, camPulse, a) {
  g.save(); g.globalAlpha = a; g.translate(ox, oy); g.scale(S, S);
  g.lineJoin = 'round'; g.lineCap = 'round';
  const ink = 'rgba(243,243,239,0.9)', fill = '#0f1216';
  // boom + camera + FOV
  g.strokeStyle = ink; g.lineWidth = 3;
  g.beginPath(); g.moveTo(300, -40); g.lineTo(430, -120); g.lineTo(520, -120); g.stroke();
  const fov = g.createLinearGradient(0, -110, 0, 95);
  fov.addColorStop(0, `rgba(130,52,254,${0.35 + camPulse * 0.25})`); fov.addColorStop(1, 'rgba(130,52,254,0.04)');
  g.fillStyle = fov; g.beginPath(); g.moveTo(520, -108); g.lineTo(420, 95); g.lineTo(650, 95); g.closePath(); g.fill();
  g.strokeStyle = rgba(C.accent, 0.55); g.lineWidth = 1.5; g.beginPath(); g.moveTo(520, -108); g.lineTo(420, 95); g.moveTo(520, -108); g.lineTo(650, 95); g.stroke();
  g.fillStyle = fill; g.strokeStyle = C.accent; g.lineWidth = 3; rrect(g, 500, -134, 42, 28, 6); g.fill(); g.stroke();
  g.fillStyle = C.accent; g.beginPath(); g.arc(521, -106, 5, 0, Math.PI * 2); g.fill();
  if (camPulse > 0) { g.strokeStyle = rgba(C.accent, camPulse); g.lineWidth = 2; g.beginPath(); g.arc(521, -120, 30 + (1 - camPulse) * 30, 0, Math.PI * 2); g.stroke(); }
  // body
  g.fillStyle = fill; g.strokeStyle = ink; g.lineWidth = 3;
  g.beginPath(); g.moveTo(40, -40); g.lineTo(310, -52); g.quadraticCurveTo(334, -50, 336, -26); g.lineTo(336, 8); g.lineTo(40, 14); g.closePath(); g.fill(); g.stroke();
  for (let i = 0; i < 4; i++) { g.beginPath(); g.moveTo(318, -40 + i * 11); g.lineTo(334, -40 + i * 11); g.stroke(); }
  g.beginPath(); g.moveTo(180, -48); g.lineTo(180, -118); g.stroke();
  // cabin
  g.beginPath(); g.moveTo(-70, -40); g.lineTo(-58, -222); g.lineTo(96, -222); g.lineTo(118, -40); g.closePath(); g.fill(); g.stroke();
  g.strokeStyle = 'rgba(243,243,239,0.35)'; g.lineWidth = 2; rrect(g, -44, -206, 128, 120, 8); g.stroke();
  g.strokeStyle = ink; g.lineWidth = 3;
  g.beginPath(); g.moveTo(-80, -226); g.lineTo(106, -226); g.stroke();
  // wheels
  const wheel = (x, y, R) => {
    g.fillStyle = '#0b0d10'; g.beginPath(); g.arc(x, y, R, 0, Math.PI * 2); g.fill();
    g.strokeStyle = ink; g.lineWidth = 3; g.stroke();
    g.strokeStyle = 'rgba(243,243,239,0.5)'; g.lineWidth = 2; g.beginPath(); g.arc(x, y, R * 0.58, 0, Math.PI * 2); g.stroke();
    const rot = -t * (SPEED * 0.9 / R);
    for (let i = 0; i < 14; i++) { const an = rot + (i / 14) * Math.PI * 2; g.beginPath(); g.moveTo(x + Math.cos(an) * R * 0.78, y + Math.sin(an) * R * 0.78); g.lineTo(x + Math.cos(an) * R * 0.97, y + Math.sin(an) * R * 0.97); g.stroke(); }
    g.fillStyle = ink; g.beginPath(); g.arc(x, y, R * 0.12, 0, Math.PI * 2); g.fill();
  };
  wheel(0, 0, 95);
  wheel(262, 40, 55);
  g.restore();
}

addScene({
  id: 'agri',
  pre: 0.3,
  post: 0.6,
  setup(ctx) {
    const R = ctx.root;
    this.hud = makeHud(ctx, {
      num: '04', title: 'Real-world AI · Detection · Tracking', badge: 'Client project',
      steps: [
        { label: 'Detect', at: ctx.cue('a2', 0) + 0.9 },
        { label: 'Count', at: ctx.cue('a2', 1) },
        { label: 'Measure', at: ctx.cue('a2', 1) + 0.8 },
        { label: 'Map', at: ctx.cue('a2', 2) },
        { label: 'Track', at: ctx.cue('a3', 1) },
      ],
    });
    const cv = makeCanvas(R);
    this.g = cv.ctx;
    this.plants = Array.from({ length: 10 }, (_, i) => plantSprite(900 + i));
    this.pumpkins = [['orange', 1], ['deep', 2], ['orange', 3], ['pale', 4], ['orange', 5], ['green', 6], ['deep', 7], ['orange', 8]].map(([k, s]) => pumpkinSprite(k, s));
    this.soil = soilTile(FRAME.w, 1200);
    // conveyor belt texture
    const belt = makeCanvas(null, 480, 420, '');
    const bg = belt.ctx;
    bg.fillStyle = '#1d2024'; bg.fillRect(0, 0, 480, 420);
    const br = rng(8);
    for (let i = 0; i < 900; i++) { bg.fillStyle = `rgba(255,255,255,${br() * 0.035})`; bg.fillRect(br() * 480, br() * 420, 2, 2); }
    for (let x = 0; x < 480; x += 120) { bg.fillStyle = 'rgba(0,0,0,0.35)'; bg.fillRect(x, 0, 6, 420); bg.fillStyle = 'rgba(255,255,255,0.05)'; bg.fillRect(x + 6, 0, 2, 420); }
    this.belt = belt.c;
    // telemetry card (tractor shot)
    this.tele = h('div', { class: 'panel', style: { left: '1290px', top: '190px', width: '440px', padding: '22px 26px' } });
    this.teleRows = [['Plants detected', '0'], ['Row', '14 of 38'], ['Position', '41.12341, −98.45672'], ['Feed', 'Live']].map(([k, v]) => {
      const val = h('span', { class: 'mono', style: { color: 'var(--text)', fontSize: '17px' } }, v);
      const row = h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', height: '44px', borderBottom: '1px solid var(--line)' } }, h('span', { class: 'kicker' }, k), val);
      return { row, val };
    });
    this.tele.append(h('div', { style: { display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' } }, h('span', { style: { width: '9px', height: '9px', borderRadius: '50%', background: 'var(--coral)' } }), h('span', { style: { fontSize: '18px', fontWeight: 600 } }, 'Tractor camera · live')), ...this.teleRows.map((r) => r.row));
    this.teleRows[3].row.style.borderBottom = 'none';
    R.append(this.tele);
    // live audit panel (field feed)
    this.audit = h('div', { class: 'panel', style: { left: '1370px', top: '150px', width: '370px', padding: '20px 24px', background: 'rgba(12,14,17,0.88)' } });
    const stat = (k, cls) => { const v = h('div', { class: 'mono', style: { fontSize: '26px', color: cls || 'var(--text)', marginTop: '2px' } }, '0'); return { el: h('div', { style: { padding: '10px 0', borderBottom: '1px solid var(--line)' } }, h('div', { class: 'kicker', style: { fontSize: '11px' } }, k), v), v }; };
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
    const pstat = (k, col) => { const v = h('span', { class: 'mono', style: { fontSize: '24px', color: col || 'var(--text)' } }, '0'); return { el: h('div', { style: { display: 'flex', flexDirection: 'column', gap: '4px' } }, h('span', { class: 'kicker', style: { fontSize: '11px' } }, k), v), v }; };
    this.pCount = pstat('Counted', 'var(--accent)');
    this.pView = pstat('Tracked in view');
    this.pSize = pstat('Avg diameter');
    this.pack.append(h('div', { style: { fontSize: '16px', fontWeight: 600, width: '130px', lineHeight: 1.3 } }, 'Packing line', h('br'), h('span', { class: 'kicker', style: { fontSize: '10.5px', color: 'var(--coral)' } }, '● Live')), this.pCount.el, this.pView.el, this.pSize.el);
    R.append(this.pack);
    // report page (hands off to the documents scene)
    this.page = h('div', { class: 'abs', style: { left: '760px', top: '280px', width: '400px', height: '520px', borderRadius: '10px', background: '#f4f3ef', boxShadow: '0 40px 80px rgba(0,0,0,0.6)', padding: '34px', transformOrigin: '50% 50%' } },
      h('div', { style: { fontFamily: 'var(--font-mono)', fontSize: '11px', letterSpacing: '0.16em', color: '#6b6f76', marginBottom: '12px' } }, 'DAILY OPERATIONS REPORT'),
      h('div', { style: { fontSize: '22px', fontWeight: 650, color: '#15171a', marginBottom: '22px' } }, 'Packing line · shift summary'),
      ...Array.from({ length: 11 }, (_, i) => h('div', { style: { height: '9px', borderRadius: '3px', background: i % 4 === 0 ? '#c9ccd1' : '#e2e4e7', width: `${[92, 80, 86, 60, 90, 76, 84, 58, 88, 70, 64][i]}%`, marginBottom: '14px' } })));
    R.append(this.page);
  },

  render(t, ctx) {
    const g = this.g;
    g.clearRect(0, 0, 1920, 1080);
    this.hud(t);
    const D = ctx.dur;
    const cCam = ctx.cue('a1', 1), cData = ctx.cue('a1', 2), cTr = ctx.cue('a2', 0), cCount = ctx.cue('a2', 1), cMap = ctx.cue('a2', 2), cPack = ctx.cue('a3', 0), cID = ctx.cue('a3', 1), cKeep = ctx.cue('a3', 2);

    // ================= A: tractor establishing shot
    const trA = env(t, -0.3, cTr + 0.95, 0.5, 0.35);
    if (trA > 0.001) {
      const push = prog(t, cTr + 0.1, 0.9, E.inCubic);
      const S = lerp(1.25, 3.6, push), ox = lerp(560, 960 - 535 * 3.6, push), oy = lerp(640, 540 - 95 * 3.6, push);
      // horizon + ground + passing crop rows
      g.save(); g.globalAlpha = trA;
      const gy = oy + 95 * S;
      const sky = g.createLinearGradient(0, 200, 0, gy);
      sky.addColorStop(0, 'rgba(20,24,30,0)'); sky.addColorStop(1, 'rgba(40,46,52,0.35)');
      g.fillStyle = sky; g.fillRect(0, 200, 1920, gy - 200);
      g.strokeStyle = 'rgba(255,255,255,0.18)'; g.lineWidth = 1.5; g.beginPath(); g.moveTo(0, gy); g.lineTo(1920, gy); g.stroke();
      g.fillStyle = '#0c0e10'; g.fillRect(0, gy, 1920, 1080 - gy);
      // crop rows receding toward the viewer (perspective)
      g.lineWidth = 1;
      for (let i = -14; i <= 14; i++) {
        const xv = 960 + i * 90 * S;
        const grd = g.createLinearGradient(0, gy, 0, 1080);
        grd.addColorStop(0, 'rgba(111,174,85,0.0)'); grd.addColorStop(1, 'rgba(111,174,85,0.16)');
        g.strokeStyle = grd;
        g.beginPath(); g.moveTo(960 + i * 20, gy); g.lineTo(xv, 1080 + 200); g.stroke();
      }
      for (let i = 0; i < 70; i++) {
        const x = ((i * 64 - t * SPEED * 0.9 * (S / 1.25)) % (70 * 64) + 70 * 64) % (70 * 64) - 200;
        const hh = 12 * S;
        g.fillStyle = '#4f8a3f'; g.beginPath(); g.ellipse(x, gy - hh * 0.35, hh * 0.9, hh * 0.45, 0, Math.PI, Math.PI * 2); g.fill();
        g.fillStyle = '#6fae55'; g.beginPath(); g.ellipse(x - hh * 0.3, gy - hh * 0.4, hh * 0.35, hh * 0.3, -0.5, 0, Math.PI * 2); g.fill();
      }
      g.restore();
      drawTractor(g, t, ox, oy, S, env(t, cCam - 0.1, cCam + 1.2, 0.2, 0.8) * (1 - push), trA);
      if (t > cCam && push < 0.5) tag(g, ox + 560 * S, oy - 150 * S, 'CAMERA', { a: trA * prog(t, cCam, 0.4) * (1 - push * 2), size: 12 });
      // data packets streaming from the camera to the telemetry card
      if (t > cData - 0.2 && push < 1) {
        const cxp = ox + 521 * S, cyp = oy - 120 * S;
        for (let i = 0; i < 16; i++) {
          const u = ((t - cData) * 0.9 + i / 16) % 1;
          if (t - cData + i / 16 < 0) continue;
          const x = lerp(cxp, 1290, E.inOutSine(u)), y = lerp(cyp, 260, E.inOutSine(u)) - Math.sin(u * Math.PI) * 120;
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
    const scroll = t * SPEED;
    const crossedAt = (row, k) => (k * PITCH + plantAt(row, k).jy + FRAME.y - COUNT_Y) / SPEED; // time when plant k crosses the count line
    let counted = 0, gaps = 0, offs = 0;
    if (feedA > 0.001) {
      g.save(); g.globalAlpha = feedA;
      const zoomIn = 1 + (1 - prog(t, cTr + 0.7, 0.8, E.outCubic)) * 0.25;
      g.translate(960, 531); g.scale(zoomIn, zoomIn); g.translate(-960, -531);
      rrect(g, FRAME.x, FRAME.y, FRAME.w, FRAME.h, 18); g.clip();
      const sh = this.soil.height, oy = ((scroll % sh) + sh) % sh;
      g.drawImage(this.soil, FRAME.x, FRAME.y + oy - sh);
      g.drawImage(this.soil, FRAME.x, FRAME.y + oy);
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
          if (!p.missing) g.drawImage(this.plants[p.v], x - sz / 2, py - sz / 2, sz, sz);
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
      tag(g, 260, 180, 'FIELD MAP · EVERY PLANT GEO-LOCATED', { a: mapA * prog(t, cMap + 0.6, 0.5), bg: null, fg: 'rgba(255,255,255,0.7)', size: 13, anchor: 'bl', pad: 0 });
    }

    // ================= D: packing line — ID, track, count
    const packA = env(t, cPack - 0.1, D + 1, 0.45, 0.01) * (1 - prog(t, D - 0.8, 0.5, E.inCubic));
    const BV = 250, LINE_X = FRAME.x + 1080;
    let packCount = 1038, inView = 0;
    if (packA > 0.001) {
      g.save(); g.globalAlpha = packA;
      rrect(g, FRAME.x, FRAME.y, FRAME.w, FRAME.h, 18); g.clip();
      g.fillStyle = '#121417'; g.fillRect(FRAME.x, FRAME.y, FRAME.w, FRAME.h);
      const by0 = FRAME.y + 200, bh = 420;
      const off = ((t * BV) % 480 + 480) % 480;
      for (let x = FRAME.x - 480 + off; x < FRAME.x + FRAME.w; x += 480) g.drawImage(this.belt, x, by0, 480, bh);
      // rails
      [by0 - 40, by0 + bh].forEach((ry) => {
        const rg = g.createLinearGradient(0, ry, 0, ry + 40);
        rg.addColorStop(0, '#6c737b'); rg.addColorStop(0.5, '#9aa2aa'); rg.addColorStop(1, '#4c5259');
        g.fillStyle = rg; g.fillRect(FRAME.x, ry, FRAME.w, 40);
        for (let x = FRAME.x + 40; x < FRAME.x + FRAME.w; x += 160) { g.fillStyle = '#3a3f45'; g.beginPath(); g.arc(x, ry + 20, 5, 0, Math.PI * 2); g.fill(); }
      });
      g.fillStyle = 'rgba(0,0,0,0.35)'; g.fillRect(FRAME.x, by0, FRAME.w, 16);
      // pumpkins
      const spawn = (k) => cPack - 2.6 + k * 0.62 + (hash(k, 4) - 0.5) * 0.2;
      const items = [];
      for (let k = 0; k < 40; k++) {
        const t0 = spawn(k);
        const x = FRAME.x - 110 + (t - t0) * BV;
        if (x < FRAME.x - 140 || x > FRAME.x + FRAME.w + 140) { if (x > LINE_X) packCount++; continue; }
        const y = by0 + 90 + hash(k, 8) * (bh - 180) + Math.sin((t - t0) * 1.7 + k) * 6;
        const R = 70 + hash(k, 11) * 26;
        const rot = hash(k, 5) * 6 + (t - t0) * 0.15;
        items.push({ k, x, y, R, rot, spr: this.pumpkins[k % this.pumpkins.length], t0 });
        if (x > LINE_X) packCount++;
      }
      items.forEach((it) => { g.save(); g.translate(it.x, it.y); g.rotate(it.rot); g.drawImage(it.spr, -it.R * 1.19, -it.R * 1.19, it.R * 2.38, it.R * 2.38); g.restore(); });
      // count line
      g.strokeStyle = 'rgba(255,255,255,0.8)'; g.lineWidth = 2; g.setLineDash([10, 8]);
      g.beginPath(); g.moveTo(LINE_X, by0 - 40); g.lineTo(LINE_X, by0 + bh + 40); g.stroke(); g.setLineDash([]);
      tag(g, LINE_X + 10, by0 - 50, 'COUNT LINE', { bg: null, fg: 'rgba(255,255,255,0.8)', size: 11, anchor: 'bl', pad: 0 });
      const ovA = prog(t, cID - 0.2, 0.5);
      items.forEach((it) => {
        const seen = clamp((it.x - FRAME.x - 20) / 60) * ovA;
        if (seen <= 0) return;
        inView += it.x < FRAME.x + FRAME.w ? 1 : 0;
        // trail
        g.strokeStyle = rgba(C.sky, 0.8 * seen); g.lineWidth = 2.5; g.beginPath();
        for (let s = 0; s <= 20; s++) { const tt = t - s * 0.06; const xx = FRAME.x - 110 + (tt - it.t0) * BV; const yy = by0 + 90 + hash(it.k, 8) * (bh - 180) + Math.sin((tt - it.t0) * 1.7 + it.k) * 6; if (xx < FRAME.x) break; s ? g.lineTo(xx, yy) : g.moveTo(xx, yy); }
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
    const packPanelA = env(t, cID - 0.1, D + 1, 0.4, 0.01) * (1 - prog(t, D - 1.0, 0.5));
    put(this.pack, { y: (1 - prog(t, cID - 0.1, 0.5, E.outCubic)) * 20, o: packPanelA });
    this.pCount.v.textContent = fmt(packCount);
    this.pView.v.textContent = String(inView);
    this.pSize.v.textContent = `${(26.8 + Math.sin(t) * 0.4).toFixed(1)} cm`;
    // handoff: the shift summary report
    const pg = prog(t, D - 0.9, 0.8, E.outCubic);
    put(this.page, { y: (1 - pg) * 80, s: lerp(0.85, 1, pg), r: lerp(-6, -3, pg), o: pg * (t < D ? 1 : 0) });
  },
});
