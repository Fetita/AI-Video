// Line icons for the impact film (original artwork, 24-unit grid, round caps).
// The same paths render as inline SVG (DOM) and on canvas through Path2D, so both match.
import { svg } from '../engine.js';

export const ICONS = {
  seedling: ['M12 21v-7.5', 'M12 13.5c0-4.2 3.1-6.5 7.2-6.5 0 4.2-3.1 6.5-7.2 6.5z', 'M12 15.5c0-3.4-2.5-5.3-5.8-5.3 0 3.4 2.5 5.3 5.8 5.3z', 'M7.5 21h9'],
  tray: ['M3 7h18v10H3z', 'M9 7v10', 'M15 7v10', 'M3 12h18'],
  lettuce: ['M12 20.5c-4.6 0-8-3.2-8-7.2 0-4.2 3.6-8.3 8-8.3s8 4.1 8 8.3c0 4-3.4 7.2-8 7.2z', 'M12 20.5V9.5', 'M12 13.5l-3.2-2.6', 'M12 16l3.4-2.9'],
  onion: ['M12 6.5c4 2.4 6.2 5.4 6.2 8.4a6.2 6.2 0 0 1-12.4 0c0-3 2.2-6 6.2-8.4z', 'M12 6.5V2.5', 'M10.3 3.4L12 6.5l1.7-3.1', 'M10.4 21.2l-.8 1.3', 'M12 21.2v1.5', 'M13.6 21.2l.8 1.3'],
  pumpkin: ['M12 7.5c-4.6 0-8 2.8-8 6.3S7.4 20 12 20s8-2.7 8-6.2-3.4-6.3-8-6.3z', 'M12 7.5c-2.2 2.1-2.2 10.4 0 12.5', 'M12 7.5c2.2 2.1 2.2 10.4 0 12.5', 'M12 7.5c0-2 1-3.3 2.6-3.8'],
  crate: ['M3 9.5h18V19H3z', 'M3 9.5L5 5.5h14l2 4', 'M3 13.5h18', 'M9.5 16.3h5'],
  dashboard: ['M3 4.5h18v13H3z', 'M7 14v-3', 'M11 14V8', 'M15 14v-5', 'M8.5 21h7'],
  box: ['M12 3l8 4.5v9L12 21l-8-4.5v-9z', 'M4 7.5l8 4.5 8-4.5', 'M12 12v9'],
  coins: ['M5 7.5c0-1.7 3.1-3 7-3s7 1.3 7 3-3.1 3-7 3-7-1.3-7-3z', 'M5 7.5v4.2c0 1.7 3.1 3 7 3s7-1.3 7-3V7.5', 'M5 11.7v4.3c0 1.7 3.1 3 7 3s7-1.3 7-3v-4.3'],
  truck: ['M2.5 6.5h11v9.5h-11z', 'M13.5 10h4l3 3.2V16h-7', 'M6.5 19a1.6 1.6 0 1 0 0-3.2 1.6 1.6 0 0 0 0 3.2z', 'M16.5 19a1.6 1.6 0 1 0 0-3.2 1.6 1.6 0 0 0 0 3.2z'],
  ticket: ['M3.5 7h17v3a2 2 0 0 0 0 4v3h-17v-3a2 2 0 0 0 0-4z', 'M12 9.6v3.2', 'M12 15v.01'],
  clock: ['M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16z', 'M12 8v4.2l2.8 1.8'],
  scale: ['M12 4v15.5', 'M6.5 19.5h11', 'M5 7.5h14', 'M5 7.5l-2.6 5.2a2.6 2.6 0 0 0 5.2 0z', 'M19 7.5l-2.6 5.2a2.6 2.6 0 0 0 5.2 0z'],
  tag: ['M3.5 12.2L12 3.7h8.3V12l-8.5 8.5z', 'M16.2 8.2v.01'],
  shield: ['M12 3l7 3v5.2c0 4.4-3 8.1-7 9.8-4-1.7-7-5.4-7-9.8V6z', 'M9 12l2.2 2.2L15.3 10'],
  leaf: ['M5 19c0-8 5-13.2 14-14-.8 9-6 14-14 14z', 'M5 19l7.2-7.2'],
  report: ['M6 3h9l4 4v14H6z', 'M15 3v4h4', 'M9 12h7', 'M9 16h4.5'],
  camera: ['M3 8h4l2-3h6l2 3h4v11H3z', 'M12 17a3.4 3.4 0 1 0 0-6.8 3.4 3.4 0 0 0 0 6.8z'],
  alert: ['M12 4l9 16H3z', 'M12 10v4', 'M12 17v.01'],
  chat: ['M4 5h16v11H9.5L4 20z'],
  check: ['M5 12.5l4.2 4.2L19 7'],
  database: ['M5 6c0-1.7 3.1-3 7-3s7 1.3 7 3-3.1 3-7 3-7-1.3-7-3z', 'M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6', 'M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3'],
};

/** Inline SVG icon element. */
export function icon(name, { size = 24, color = 'currentColor', stroke = 1.8 } = {}) {
  const el = svg('svg', { viewBox: '0 0 24 24', width: size, height: size, fill: 'none', stroke: color, 'stroke-width': stroke, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', style: 'display:block;flex:none;overflow:visible' });
  for (const d of ICONS[name] || []) el.append(svg('path', { d }));
  return el;
}

const P2D = new Map();
/** Draw an icon on canvas, centered at (x, y), `size` px wide. */
export function drawIcon(g, name, x, y, size, { color = '#fff', a = 1, lw = 1.8 } = {}) {
  if (a <= 0.001) return;
  if (!P2D.has(name)) P2D.set(name, (ICONS[name] || []).map((d) => new Path2D(d)));
  const s = size / 24;
  g.save();
  g.globalAlpha *= a;
  g.translate(x - size / 2, y - size / 2);
  g.scale(s, s);
  g.strokeStyle = color; g.lineWidth = lw; g.lineCap = 'round'; g.lineJoin = 'round';
  for (const p of P2D.get(name)) g.stroke(p);
  g.restore();
}
