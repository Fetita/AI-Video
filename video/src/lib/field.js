// Procedural crop-field and produce sprites (shared by the agriculture scene, hook and recap).
import { makeCanvas, rng, hash } from '../engine.js';

export const FRAME = { x: 150, y: 118, w: 1620, h: 826 };
export const ROWS = 6, ROW_X0 = FRAME.x + 200, ROW_DX = 244, PITCH = 150, SPEED = 230;

// ------------------------------------------------------------ sprites
export function plantSprite(seed, size = 128) {
  const { c, ctx: g } = makeCanvas(null, size, size, '');
  const r = rng(seed);
  const cx = size / 2, cy = size / 2;
  g.fillStyle = 'rgba(20,12,6,0.35)';
  g.beginPath(); g.ellipse(cx + 5, cy + 7, size * 0.36, size * 0.33, 0, 0, Math.PI * 2); g.fill();
  const leaves = 7 + Math.floor(r() * 3);
  const rot0 = r() * Math.PI * 2;
  for (let layer = 0; layer < 2; layer++) {
    for (let i = 0; i < leaves; i++) {
      const a = rot0 + (i / leaves) * Math.PI * 2 + layer * 0.35 + (r() - 0.5) * 0.3;
      const L = size * (layer ? 0.24 : 0.36) * (0.85 + r() * 0.25), Wd = L * (0.55 + r() * 0.15);
      g.save();
      g.translate(cx, cy); g.rotate(a);
      const gr = g.createLinearGradient(0, 0, L, 0);
      gr.addColorStop(0, layer ? '#b7e38a' : '#8fc66a'); gr.addColorStop(0.7, layer ? '#7dbb58' : '#5a9a45'); gr.addColorStop(1, layer ? '#5f9e45' : '#3e7433');
      g.fillStyle = gr;
      g.beginPath(); g.ellipse(L * 0.55, 0, L * 0.55, Wd * 0.5, 0, 0, Math.PI * 2); g.fill();
      g.strokeStyle = 'rgba(230,255,200,0.35)'; g.lineWidth = 1.2;
      g.beginPath(); g.moveTo(L * 0.1, 0); g.lineTo(L * 0.95, 0); g.stroke();
      g.restore();
    }
  }
  g.fillStyle = '#d5f2a8'; g.beginPath(); g.arc(cx, cy, size * 0.05, 0, Math.PI * 2); g.fill();
  return c;
}
export function pumpkinSprite(kind, seed, size = 200) {
  const { c, ctx: g } = makeCanvas(null, size, size, '');
  const r = rng(seed);
  const cx = size / 2, cy = size / 2, R = size * 0.42;
  const pal = { orange: ['#ffb05a', '#e8792b', '#a8471a'], deep: ['#f59a45', '#d25f1c', '#8f3a12'], pale: ['#f6ecd8', '#dccbb0', '#9f8e74'], green: ['#8fb37a', '#5f8a4c', '#34532b'] }[kind];
  g.fillStyle = 'rgba(0,0,0,0.45)'; g.beginPath(); g.ellipse(cx + 8, cy + 10, R, R * 0.95, 0, 0, Math.PI * 2); g.fill();
  const lobes = 9 + Math.floor(r() * 3);
  const rot = r() * 6;
  for (let i = 0; i < lobes; i++) {
    const a = rot + (i / lobes) * Math.PI * 2;
    g.save(); g.translate(cx, cy); g.rotate(a);
    const gr = g.createRadialGradient(R * 0.35, -R * 0.1, 2, R * 0.45, 0, R * 0.75);
    gr.addColorStop(0, pal[0]); gr.addColorStop(0.6, pal[1]); gr.addColorStop(1, pal[2]);
    g.fillStyle = gr;
    g.beginPath(); g.ellipse(R * 0.5, 0, R * 0.52, R * 0.36, 0, 0, Math.PI * 2); g.fill();
    g.restore();
  }
  const hl = g.createRadialGradient(cx - R * 0.35, cy - R * 0.4, 0, cx - R * 0.2, cy - R * 0.2, R * 0.9);
  hl.addColorStop(0, 'rgba(255,255,255,0.28)'); hl.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = hl; g.beginPath(); g.arc(cx, cy, R, 0, Math.PI * 2); g.fill();
  g.fillStyle = '#5a4526'; g.beginPath(); g.ellipse(cx, cy, R * 0.13, R * 0.1, rot, 0, Math.PI * 2); g.fill();
  g.strokeStyle = '#4c6b2f'; g.lineWidth = size * 0.035; g.lineCap = 'round';
  g.beginPath(); g.moveTo(cx, cy); g.quadraticCurveTo(cx + R * 0.15, cy - R * 0.25, cx + R * 0.32, cy - R * 0.18); g.stroke();
  return c;
}
export function soilTile(w, hgt) {
  const { c, ctx: g } = makeCanvas(null, w, hgt, '');
  g.fillStyle = '#4a3a2c'; g.fillRect(0, 0, w, hgt);
  const r = rng(77);
  // raised beds under each row
  for (let i = 0; i < ROWS; i++) {
    const x = ROW_X0 - FRAME.x + i * ROW_DX;
    const gr = g.createLinearGradient(x - 110, 0, x + 110, 0);
    gr.addColorStop(0, 'rgba(30,22,16,0.5)'); gr.addColorStop(0.3, 'rgba(120,98,76,0.25)'); gr.addColorStop(0.5, 'rgba(140,116,90,0.3)'); gr.addColorStop(0.7, 'rgba(120,98,76,0.25)'); gr.addColorStop(1, 'rgba(30,22,16,0.5)');
    g.fillStyle = gr; g.fillRect(x - 122, 0, 244, hgt);
  }
  for (let i = 0; i < 5200; i++) {
    const x = r() * w, y = r() * hgt, s = 1 + r() * r() * 9;
    const v = r();
    g.fillStyle = v < 0.5 ? `rgba(30,20,12,${0.12 + r() * 0.25})` : `rgba(170,140,110,${0.06 + r() * 0.16})`;
    for (const dy of [-hgt, 0, hgt]) { g.beginPath(); g.ellipse(x, y + dy, s, s * (0.6 + r() * 0.4), r() * 3, 0, Math.PI * 2); g.fill(); }
  }
  return c;
}

// ------------------------------------------------------------ field model
export function plantAt(row, k) {
  const hsh = hash(row * 1.37 + 3, k * 0.713 + 11);
  const missing = hsh < 0.045;
  const off = !missing && hsh > 0.955 ? (hash(row, k, 2) < 0.5 ? -1 : 1) * (34 + hash(row, k, 5) * 18) : 0;
  return {
    missing, off,
    jx: (hash(row, k, 7) - 0.5) * 10 + off,
    jy: (hash(row, k, 9) - 0.5) * 26,
    s: 0.82 + hash(row, k, 13) * 0.36,
    v: Math.floor(hash(row, k, 17) * 10),
    id: 4000 + k * ROWS + row,
  };
}

