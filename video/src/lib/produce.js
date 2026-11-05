// Procedural produce sprites for the impact film (seedlings and trays, onions, foliage,
// crates of lettuce, pumpkin defects). Built once in setup: no text is ever drawn into a sprite.
import { makeCanvas, rng, hash } from '../engine.js';

// ------------------------------------------------------------ nursery
/** Top-down seedling rosette. vigor ~0.35 (tiny) … 1.25 (big). */
export function seedlingSprite(seed, size = 72, vigor = 1) {
  const { c, ctx: g } = makeCanvas(null, size, size, '');
  const r = rng(seed);
  const cx = size / 2, cy = size / 2, S = size * 0.46 * vigor;
  g.fillStyle = 'rgba(0,0,0,0.35)';
  g.beginPath(); g.ellipse(cx + 2, cy + 3, S * 0.75, S * 0.6, 0, 0, Math.PI * 2); g.fill();
  const leaf = (a, L, W, c0, c1) => {
    g.save(); g.translate(cx, cy); g.rotate(a);
    const gr = g.createLinearGradient(0, 0, L, 0);
    gr.addColorStop(0, c0); gr.addColorStop(1, c1);
    g.fillStyle = gr;
    g.beginPath(); g.ellipse(L * 0.55, 0, L * 0.55, W, 0, 0, Math.PI * 2); g.fill();
    g.strokeStyle = 'rgba(235,255,210,0.35)'; g.lineWidth = Math.max(0.8, size / 90);
    g.beginPath(); g.moveTo(L * 0.12, 0); g.lineTo(L * 0.92, 0); g.stroke();
    g.restore();
  };
  const a0 = r() * Math.PI * 2;
  // cotyledons
  leaf(a0, S * 0.8, S * 0.28, '#b8e07c', '#7fb64e');
  leaf(a0 + Math.PI + (r() - 0.5) * 0.3, S * 0.78, S * 0.27, '#b8e07c', '#7fb64e');
  // true leaves (more with vigor)
  const n = vigor > 0.8 ? 3 : vigor > 0.55 ? 2 : 0;
  for (let i = 0; i < n; i++) leaf(a0 + Math.PI / 2 + i * 2.1 + (r() - 0.5) * 0.4, S * (0.9 + r() * 0.2), S * 0.42, '#9fd468', '#5d9a3c');
  g.fillStyle = '#d8f3a6'; g.beginPath(); g.arc(cx, cy, Math.max(1.2, S * 0.08), 0, Math.PI * 2); g.fill();
  return c;
}

/** Tray base (frame + peat-filled cells), cols × rows cells of `cell` px. */
export function traySprite(cols, rows, cell, seed = 3) {
  const m = 18;
  const w = cols * cell + m * 2, hh = rows * cell + m * 2;
  const { c, ctx: g } = makeCanvas(null, w, hh, '');
  const r = rng(seed);
  // plastic frame
  const fr = g.createLinearGradient(0, 0, 0, hh);
  fr.addColorStop(0, '#d9ddd9'); fr.addColorStop(1, '#b5bab6');
  g.fillStyle = fr;
  g.beginPath(); g.roundRect(0, 0, w, hh, 10); g.fill();
  g.strokeStyle = 'rgba(255,255,255,0.6)'; g.lineWidth = 2; g.beginPath(); g.roundRect(1.5, 1.5, w - 3, hh - 3, 9); g.stroke();
  for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++) {
    const x = m + i * cell, y = m + j * cell;
    g.fillStyle = '#c4c8c4'; g.fillRect(x, y, cell, cell);
    const pg = g.createRadialGradient(x + cell / 2, y + cell / 2, 2, x + cell / 2, y + cell / 2, cell * 0.62);
    pg.addColorStop(0, '#3a2c20'); pg.addColorStop(1, '#22180f');
    g.fillStyle = pg; g.fillRect(x + 3, y + 3, cell - 6, cell - 6);
    for (let k = 0; k < 16; k++) {
      g.fillStyle = r() < 0.5 ? `rgba(120,95,70,${0.25 + r() * 0.3})` : `rgba(10,6,3,${0.3 + r() * 0.3})`;
      g.fillRect(x + 4 + r() * (cell - 9), y + 4 + r() * (cell - 9), 1.5 + r() * 2, 1.5 + r() * 2);
    }
  }
  return { c, m, w, h: hh };
}

// ------------------------------------------------------------ onions
/** Onion lying on its side: golden papery bulb, dry neck and wispy roots. */
export function onionSprite(seed, size = 110) {
  const { c, ctx: g } = makeCanvas(null, size, size, '');
  const r = rng(seed);
  const cx = size / 2, cy = size / 2, R = size * 0.3 * (0.9 + r() * 0.2);
  const tone = r();
  const pal = tone < 0.7 ? ['#f4dc9c', '#d6a24f', '#8e5d26'] : tone < 0.9 ? ['#f0d6a4', '#c98f4a', '#7f4f22'] : ['#f6ead0', '#dcc49a', '#9a8460'];
  g.fillStyle = 'rgba(0,0,0,0.45)'; g.beginPath(); g.ellipse(cx + 4, cy + 6, R * 1.05, R * 0.9, 0, 0, Math.PI * 2); g.fill();
  // roots (left)
  g.strokeStyle = 'rgba(224,210,176,0.7)'; g.lineWidth = 1;
  for (let i = 0; i < 9; i++) { const a = Math.PI + (r() - 0.5) * 1.3; g.beginPath(); g.moveTo(cx - R * 0.9, cy); g.quadraticCurveTo(cx - R * 1.2, cy + (r() - 0.5) * R, cx - R * 0.9 + Math.cos(a) * R * (0.5 + r() * 0.5), cy + Math.sin(a) * R * (0.5 + r() * 0.6)); g.stroke(); }
  // neck (right)
  g.fillStyle = '#a5824c';
  g.beginPath(); g.moveTo(cx + R * 0.7, cy - R * 0.22); g.quadraticCurveTo(cx + R * 1.5, cy - R * 0.1, cx + R * 1.75, cy + (r() - 0.5) * R * 0.3); g.quadraticCurveTo(cx + R * 1.5, cy + R * 0.12, cx + R * 0.7, cy + R * 0.22); g.closePath(); g.fill();
  // bulb
  const gr = g.createRadialGradient(cx - R * 0.3, cy - R * 0.35, R * 0.1, cx, cy, R * 1.05);
  gr.addColorStop(0, pal[0]); gr.addColorStop(0.55, pal[1]); gr.addColorStop(1, pal[2]);
  g.fillStyle = gr;
  g.beginPath(); g.moveTo(cx - R * 0.95, cy);
  g.bezierCurveTo(cx - R * 0.95, cy - R * 0.85, cx + R * 0.45, cy - R * 0.95, cx + R * 0.95, cy - R * 0.12);
  g.quadraticCurveTo(cx + R * 1.05, cy, cx + R * 0.95, cy + R * 0.12);
  g.bezierCurveTo(cx + R * 0.45, cy + R * 0.95, cx - R * 0.95, cy + R * 0.85, cx - R * 0.95, cy);
  g.fill();
  // papery skin lines
  g.strokeStyle = 'rgba(110,70,25,0.35)'; g.lineWidth = 1;
  for (let i = -2; i <= 2; i++) { g.beginPath(); g.moveTo(cx - R * 0.85, cy + i * R * 0.12); g.quadraticCurveTo(cx, cy + i * R * 0.42, cx + R * 0.9, cy + i * R * 0.06); g.stroke(); }
  g.fillStyle = 'rgba(255,248,225,0.3)'; g.beginPath(); g.ellipse(cx - R * 0.25, cy - R * 0.4, R * 0.45, R * 0.18, -0.2, 0, Math.PI * 2); g.fill();
  return c;
}

/** Tangle of onion tops (dressing on the windrower belt). */
export function foliageSprite(seed, w = 220, hh = 160) {
  const { c, ctx: g } = makeCanvas(null, w, hh, '');
  const r = rng(seed);
  for (let i = 0; i < 9; i++) {
    const x0 = w * 0.5 + (r() - 0.5) * w * 0.2, y0 = hh * 0.5 + (r() - 0.5) * hh * 0.2;
    const a = r() * Math.PI * 2, L = w * (0.3 + r() * 0.35);
    const x1 = x0 + Math.cos(a) * L, y1 = y0 + Math.sin(a) * L * 0.7;
    const col = r() < 0.6 ? `rgba(${110 + r() * 40},${150 + r() * 30},${60 + r() * 20},0.9)` : `rgba(${170 + r() * 30},${165 + r() * 25},${90 + r() * 20},0.85)`;
    g.strokeStyle = col; g.lineCap = 'round';
    g.lineWidth = 3 + r() * 3;
    g.beginPath(); g.moveTo(x0, y0); g.quadraticCurveTo((x0 + x1) / 2 + (r() - 0.5) * 40, (y0 + y1) / 2 + (r() - 0.5) * 40, x1, y1); g.stroke();
  }
  return c;
}

// ------------------------------------------------------------ dispatch
/** Top-down crate of lettuce (kind: 'iceberg' | 'romaine'), with a blank label panel on the right. */
export function crateSprite(kind, seed, w = 300, hh = 196) {
  const { c, ctx: g } = makeCanvas(null, w, hh, '');
  const r = rng(seed);
  g.fillStyle = 'rgba(0,0,0,0.5)'; g.beginPath(); g.roundRect(6, 9, w - 6, hh - 6, 14); g.fill();
  const rim = g.createLinearGradient(0, 0, 0, hh);
  rim.addColorStop(0, '#3a4554'); rim.addColorStop(1, '#262e39');
  g.fillStyle = rim; g.beginPath(); g.roundRect(0, 0, w - 6, hh - 6, 14); g.fill();
  g.strokeStyle = 'rgba(255,255,255,0.14)'; g.lineWidth = 2; g.beginPath(); g.roundRect(1.5, 1.5, w - 9, hh - 9, 13); g.stroke();
  // ribs on the rim
  g.fillStyle = 'rgba(0,0,0,0.25)';
  for (let x = 24; x < w - 30; x += 22) { g.fillRect(x, 3, 6, 10); g.fillRect(x, hh - 19, 6, 10); }
  // inner floor
  g.fillStyle = '#161b22'; g.beginPath(); g.roundRect(16, 16, w - 38, hh - 38, 8); g.fill();
  const heads = kind === 'romaine' ? [[0, 0], [1, 0], [2, 0], [0, 1], [1, 1], [2, 1]] : [[0, 0], [1, 0], [2, 0], [3, 0], [0, 1], [1, 1], [2, 1], [3, 1]];
  const cols = kind === 'romaine' ? 3 : 4;
  const cw = (w - 46) / cols, ch = (hh - 46) / 2;
  heads.forEach(([i, j]) => {
    const x = 22 + cw * (i + 0.5) + (r() - 0.5) * 4, y = 22 + ch * (j + 0.5) + (r() - 0.5) * 4;
    if (kind === 'romaine') {
      g.save(); g.translate(x, y); g.rotate((r() - 0.5) * 0.2);
      const gr = g.createLinearGradient(-cw * 0.4, 0, cw * 0.4, 0);
      gr.addColorStop(0, '#4f8f36'); gr.addColorStop(0.5, '#93cd62'); gr.addColorStop(1, '#4f8f36');
      g.fillStyle = gr; g.beginPath(); g.ellipse(0, 0, cw * 0.42, ch * 0.4, 0, 0, Math.PI * 2); g.fill();
      g.strokeStyle = 'rgba(225,250,190,0.55)'; g.lineWidth = 1.4;
      for (let k = -1; k <= 1; k++) { g.beginPath(); g.moveTo(-cw * 0.36, k * ch * 0.12); g.quadraticCurveTo(0, k * ch * 0.2, cw * 0.36, k * ch * 0.1); g.stroke(); }
      g.restore();
    } else {
      const R = Math.min(cw, ch) * 0.46;
      const gr = g.createRadialGradient(x - R * 0.3, y - R * 0.3, R * 0.1, x, y, R);
      gr.addColorStop(0, '#e9f6c8'); gr.addColorStop(0.6, '#b9dc86'); gr.addColorStop(1, '#6ea446');
      g.fillStyle = gr; g.beginPath(); g.arc(x, y, R, 0, Math.PI * 2); g.fill();
      g.strokeStyle = 'rgba(80,130,50,0.45)'; g.lineWidth = 1.2;
      for (let k = 0; k < 4; k++) { const a = r() * Math.PI * 2; g.beginPath(); g.arc(x, y, R * (0.45 + k * 0.13), a, a + 1.6); g.stroke(); }
    }
  });
  // label panel (blank; the label is drawn live)
  g.fillStyle = 'rgba(255,255,255,0.05)'; g.fillRect(w - 26, 40, 14, hh - 86);
  return c;
}

// ------------------------------------------------------------ packhouse
/** Surface defect on a pumpkin drawn at (x, y) with radius R. kind: 'scar' | 'color'. */
export function drawDefect(g, x, y, R, kind, rot = 0, a = 1) {
  g.save(); g.globalAlpha *= a; g.translate(x, y); g.rotate(rot);
  if (kind === 'scar') {
    g.strokeStyle = 'rgba(70,40,20,0.85)'; g.lineWidth = R * 0.09; g.lineCap = 'round';
    g.beginPath(); g.moveTo(-R * 0.45, -R * 0.15); g.bezierCurveTo(-R * 0.15, -R * 0.35, R * 0.1, R * 0.05, R * 0.42, -R * 0.1); g.stroke();
    g.strokeStyle = 'rgba(235,200,150,0.5)'; g.lineWidth = R * 0.03;
    g.beginPath(); g.moveTo(-R * 0.42, -R * 0.1); g.bezierCurveTo(-R * 0.12, -R * 0.28, R * 0.1, R * 0.1, R * 0.4, -R * 0.04); g.stroke();
  } else {
    const gr = g.createRadialGradient(R * 0.2, R * 0.15, 0, R * 0.2, R * 0.15, R * 0.6);
    gr.addColorStop(0, 'rgba(110,130,70,0.85)'); gr.addColorStop(1, 'rgba(110,130,70,0)');
    g.fillStyle = gr; g.beginPath(); g.arc(R * 0.2, R * 0.15, R * 0.6, 0, Math.PI * 2); g.fill();
  }
  g.restore();
}

/** Deterministic pick helper. */
export const pick = (arr, ...k) => arr[Math.floor(hash(...k) * arr.length) % arr.length];
