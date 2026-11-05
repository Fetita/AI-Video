// Conveyors for the impact film: the packing-line belt and rails (same look as the AI Studio
// film's packing line), the windrower's rod belt, and a roller conveyor for crates.
import { makeCanvas, rng } from '../engine.js';

/** Belt texture tile (480×420), as in the original packing line. */
export function beltTexture() {
  const belt = makeCanvas(null, 480, 420, '');
  const bg = belt.ctx;
  bg.fillStyle = '#1d2024'; bg.fillRect(0, 0, 480, 420);
  const br = rng(8);
  for (let i = 0; i < 900; i++) { bg.fillStyle = `rgba(255,255,255,${br() * 0.035})`; bg.fillRect(br() * 480, br() * 420, 2, 2); }
  for (let x = 0; x < 480; x += 120) { bg.fillStyle = 'rgba(0,0,0,0.35)'; bg.fillRect(x, 0, 6, 420); bg.fillStyle = 'rgba(255,255,255,0.05)'; bg.fillRect(x + 6, 0, 2, 420); }
  return belt.c;
}

/** Horizontal steel rail from x0 to x1 at y (40 px tall), with bolts. */
export function drawRail(g, x0, x1, y, hgt = 40) {
  const rg = g.createLinearGradient(0, y, 0, y + hgt);
  rg.addColorStop(0, '#6c737b'); rg.addColorStop(0.5, '#9aa2aa'); rg.addColorStop(1, '#4c5259');
  g.fillStyle = rg; g.fillRect(x0, y, x1 - x0, hgt);
  for (let x = x0 + 40; x < x1; x += 160) { g.fillStyle = '#3a3f45'; g.beginPath(); g.arc(x, y + hgt / 2, 5, 0, Math.PI * 2); g.fill(); }
}

/** Belt surface scrolling left → right inside [x0, x1] × [y, y + hgt]. */
export function drawBelt(g, tex, t, speed, x0, x1, y, hgt) {
  const off = ((t * speed) % 480 + 480) % 480;
  g.save();
  g.beginPath(); g.rect(x0, y, x1 - x0, hgt); g.clip();
  for (let x = x0 - 480 + off; x < x1; x += 480) g.drawImage(tex, x, y, 480, hgt);
  g.restore();
}

/**
 * Windrower rod belt seen from above: steel rods across the frame moving upward,
 * side chains, a centre chain and painted frame edges. rect = {x, y, w, h}.
 */
export function drawRodBelt(g, t, rect, speed = 160, pitch = 30) {
  const { x, y, w, h: hh } = rect;
  g.save();
  g.beginPath(); g.rect(x, y, w, hh); g.clip();
  const bg = g.createLinearGradient(0, y, 0, y + hh);
  bg.addColorStop(0, '#0d0f0e'); bg.addColorStop(1, '#171a17');
  g.fillStyle = bg; g.fillRect(x, y, w, hh);
  // soil glimpses below the rods
  g.fillStyle = 'rgba(70,52,36,0.35)';
  for (let i = 0; i < 40; i++) { const sx = x + ((i * 397) % w), sy = y + ((i * 211) % hh); g.fillRect(sx, sy, 40, 3); }
  const off = ((t * speed) % pitch + pitch) % pitch;
  for (let ry = y + hh + pitch - off; ry > y - pitch; ry -= pitch) {
    const rg = g.createLinearGradient(0, ry - 5, 0, ry + 5);
    rg.addColorStop(0, '#5b6168'); rg.addColorStop(0.45, '#b9c0c6'); rg.addColorStop(1, '#3a3f44');
    g.fillStyle = rg; g.fillRect(x, ry - 4.5, w, 9);
    g.fillStyle = 'rgba(0,0,0,0.35)'; g.fillRect(x, ry + 4.5, w, 3);
  }
  // chains: sides and centre
  [x + 26, x + w / 2, x + w - 26].forEach((cx) => {
    g.fillStyle = '#2b2f33'; g.fillRect(cx - 13, y, 26, hh);
    for (let ry = y + hh + pitch - off; ry > y - pitch; ry -= pitch) { g.fillStyle = '#4a5157'; g.fillRect(cx - 10, ry - 9, 20, 18); g.fillStyle = '#23272a'; g.fillRect(cx - 4, ry - 4, 8, 8); }
  });
  g.restore();
  // painted frame (lower edge + sides)
  g.fillStyle = '#b8932f'; g.fillRect(x - 18, y, 18, hh); g.fillRect(x + w, y, 18, hh);
  const fe = g.createLinearGradient(0, y + hh, 0, y + hh + 34);
  fe.addColorStop(0, '#d2ab3d'); fe.addColorStop(1, '#8a6c1f');
  g.fillStyle = fe; g.fillRect(x - 18, y + hh, w + 36, 34);
  g.fillStyle = 'rgba(0,0,0,0.3)'; g.fillRect(x - 18, y + hh, w + 36, 4);
}

/** Roller conveyor (flow left → right): vertical rollers between two side frames. */
export function drawRollers(g, t, x0, x1, y, hgt, { pitch = 38, speed = 150 } = {}) {
  g.save();
  g.fillStyle = '#0e1013'; g.fillRect(x0, y, x1 - x0, hgt);
  const spin = (t * speed * 0.15) % 1;
  for (let x = x0 + 6; x < x1; x += pitch) {
    const rg = g.createLinearGradient(x, 0, x + pitch - 10, 0);
    rg.addColorStop(0, '#30353b'); rg.addColorStop(0.35 + spin * 0.1, '#8a929a'); rg.addColorStop(1, '#2a2e33');
    g.fillStyle = rg; g.fillRect(x, y + 6, pitch - 10, hgt - 12);
  }
  g.restore();
  drawRail(g, x0, x1, y - 26, 26);
  drawRail(g, x0, x1, y + hgt, 26);
}
