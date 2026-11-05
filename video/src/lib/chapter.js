// Shared chapter furniture for the impact film: the outcome chips (what changes for the grower),
// the live-feed frame, the panel/stat helpers and the standard exit into the hand-off line.
import { h, svg, put, prog, E, clamp, lerp, env, rrect, rgba, C } from '../engine.js';
import { recHud } from './ui.js';
import { drawLine, CHAIN } from './chain.js';
import './impact-theme.js';

export const FEED = { x: 150, y: 118, w: 1620, h: 826 };

const arrowSvg = (up) => {
  const s = svg('svg', { viewBox: '0 0 24 24', width: 22, height: 22, fill: 'none', stroke: 'currentColor', 'stroke-width': 2.4, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', style: 'display:block;flex:none' });
  s.append(svg('path', { d: up ? 'M12 19V5' : 'M12 5v14' }), svg('path', { d: up ? 'M6 11l6-6 6 6' : 'M6 13l6 6 6-6' }));
  return s;
};

/**
 * Outcome chips: [{text, dir: 'up'|'down'}]. A row centered at y (kept above the caption box).
 * render(t, at, out): chips pop in from `at`, staggered; fade at `out`.
 */
export function makeOutcome(parent, items, { y = 806 } = {}) {
  const row = h('div', { class: 'abs', style: { left: '0', width: '1920px', top: `${y - 30}px`, display: 'flex', justifyContent: 'center', gap: '16px', zIndex: '30' } });
  const chips = items.map((it) => {
    const el = h('div', { style: { display: 'flex', alignItems: 'center', gap: '12px', height: '60px', padding: '0 26px 0 18px', borderRadius: '999px', background: 'rgba(14,12,22,0.9)', border: '1px solid rgba(130,52,254,0.55)', color: '#e6dcff', fontFamily: 'var(--font-ui)', fontWeight: '600', fontSize: '24px', letterSpacing: '-0.005em', whiteSpace: 'nowrap', boxShadow: '0 20px 50px -20px rgba(0,0,0,0.9), 0 0 24px rgba(130,52,254,0.18)' } },
      h('span', { style: { width: '34px', height: '34px', borderRadius: '50%', background: 'rgba(130,52,254,0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#cdb8ff' } }, arrowSvg(it.dir !== 'down')),
      h('span', {}, it.text));
    row.append(el);
    return el;
  });
  parent.append(row);
  return {
    el: row,
    render(t, at, out) {
      const a = 1 - prog(t, out, 0.4, E.inCubic);
      row.style.display = t > at - 0.2 && a > 0.001 ? 'flex' : 'none';
      chips.forEach((el, i) => {
        const q = prog(t, at + i * 0.22, 0.45, E.outCubic);
        const b = lerp(0.85, 1, Math.min(1.04, E.outBack(clamp((t - at - i * 0.22) / 0.5), 1.8)));
        el.style.opacity = (q * a).toFixed(3);
        el.style.transform = `translateY(${((1 - q) * 16).toFixed(2)}px) scale(${b.toFixed(4)})`;
      });
    },
  };
}

/** Clip a canvas drawing to a rounded rect (the camera feed), run fn, then stroke the border. */
export function withFeed(g, rect, fn, { a = 1, label = null, t = 0, radius = 18 } = {}) {
  if (a <= 0.001) return;
  g.save();
  g.globalAlpha *= a;
  rrect(g, rect.x, rect.y, rect.w, rect.h, radius);
  g.save(); g.clip();
  fn();
  g.restore();
  g.strokeStyle = 'rgba(255,255,255,0.16)'; g.lineWidth = 1;
  rrect(g, rect.x + 0.5, rect.y + 0.5, rect.w, rect.h, radius); g.stroke();
  if (label) recHud(g, rect.x + 28, rect.y + 24, label, t);
  g.restore();
}

/** Lerp between two rects. */
export const lerpRect = (a, b, p) => ({ x: lerp(a.x, b.x, p), y: lerp(a.y, b.y, p), w: lerp(a.w, b.w, p), h: lerp(a.h, b.h, p) });

/** Standard exit: the violet hand-off line draws from the centre in the last ~0.6 s (only before the cut). */
export function exitLine(g, t, D) {
  if (t >= D) return;
  const p = prog(t, D - 0.65, 0.55, E.inOutCubic);
  if (p <= 0) return;
  const w = (CHAIN.x1 - CHAIN.x0) * p;
  drawLine(g, 960 - w / 2, 960 + w / 2, CHAIN.y);
}

/** Standard entry: the hand-off line is on screen from the cut and leaves as `p` goes 0 → 1. */
export function entryLine(g, t, p) {
  if (t < 0 || p >= 1) return;
  const w = (CHAIN.x1 - CHAIN.x0) * (1 - E.inOutCubic(clamp(p)));
  drawLine(g, 960 - w / 2, 960 + w / 2, CHAIN.y, { a: 1 - clamp(p - 0.6) * 2.5 });
}

/** Dark stat panel (like the AI Studio film's live audit). rows: [[key, value, colour?]]. */
export function makeStatPanel(parent, { title, x, y, w = 360, rows = [], live = true }) {
  const el = h('div', { class: 'panel', style: { left: `${x}px`, top: `${y}px`, width: `${w}px`, padding: '18px 22px 16px', background: 'rgba(12,14,17,0.9)', zIndex: '20' } });
  el.append(h('div', { style: { display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' } },
    live ? h('span', { style: { width: '8px', height: '8px', borderRadius: '50%', background: 'var(--coral)' } }) : null,
    h('span', { style: { fontSize: '17px', fontWeight: '600' } }, title)));
  const vals = rows.map(([k, v, col], i) => {
    const val = h('span', { class: 'tnum', style: { color: col || 'var(--text)', fontSize: '22px' } }, v);
    el.append(h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', height: '44px', borderBottom: i < rows.length - 1 ? '1px solid var(--line)' : 'none' } }, h('span', { class: 'kicker', style: { fontSize: '11px' } }, k), val));
    return val;
  });
  parent.append(el);
  const last = vals.map(() => '');
  return {
    el,
    set(i, text) { if (last[i] !== text) { vals[i].textContent = text; last[i] = text; } },
    show(t, at, out, dx = 30) { put(el, { x: (1 - prog(t, at, 0.5, E.outCubic)) * dx, o: env(t, at, out, 0.4, 0.4) }); },
  };
}

export const fmt = (n) => Math.round(n).toLocaleString('en-US');
export { rgba, C };
