// The impact equation: each chapter's hero moment. Tokens appear as the VO names them
// (or fly in out of the scene), "= IMPACT" lands at the end of the line, then the whole
// formula docks into its station on the chain map.
import { h, svg, prog, E, clamp, lerp, env, TIMELINE } from '../engine.js';
import { icon } from './icons.js';
import { findPhrase, charTime } from './vo.js';
import './impact-theme.js';

/** Scene-relative appearance time of every token, from the phrases they're tied to. */
export function eqTimes(ctx, def) {
  const id = def.line;
  const l = ctx.line(id);
  const times = [];
  let cursor = 0, prev = l.start;
  def.tokens.forEach((k) => {
    let t = null;
    if (k.say) {
      const idx = findPhrase(id, k.say, cursor);
      if (idx >= 0) { t = charTime(ctx, id, idx); cursor = idx + 1; }
    }
    if (k.t === 'close') t = Math.max(t ?? prev, prev) + 0.32;
    if (k.t === 'eq') t = prev + 0.34;
    if (k.t === 'result') t = Math.max(prev + 0.3, l.end - 0.12);
    if (t == null) t = prev + 0.25;
    t = Math.max(t, prev + (k.t === 'term' ? 0.12 : 0.08));
    times.push(t);
    prev = t;
  });
  return times;
}

/** Absolute time the formula of `def` docks (shared with the chain map so the dot fills in sync). */
export const DOCK_DELAY = 0.75, DOCK_DUR = 0.8;
export function dockStart(def) {
  const l = TIMELINE.lines[def.line];
  return l ? l.end + DOCK_DELAY : Infinity;
}

// Operators as strokes (crisp at any scale, independent of font coverage).
const OPS = { '×': ['M12 12L28 28', 'M28 12L12 28'], '+': ['M20 9v22', 'M9 20h22'], '=': ['M10 15h20', 'M10 25h20'] };
const opSvg = (sym, color) => {
  const s = svg('svg', { viewBox: '0 0 40 40', width: 40, height: 40, fill: 'none', stroke: color, 'stroke-width': 3, 'stroke-linecap': 'round', style: 'display:block' });
  for (const d of OPS[sym]) s.append(svg('path', { d }));
  return s;
};

const arrow = () => {
  const s = svg('svg', { viewBox: '0 0 24 24', width: 26, height: 26, fill: 'none', stroke: '#fff', 'stroke-width': 2.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', style: 'display:block' });
  s.append(svg('path', { d: 'M7 17L17 7' }), svg('path', { d: 'M9 7h8v8' }));
  return s;
};

/**
 * makeEquation(parent, def, {y, fit, kicker}) → {el, layout(), render(t, {times, from, dock, dockAt, outAt})}
 * `from[i](t)` (optional) returns the screen rect {x, y, w} (center, width) a token flies out of.
 */
export function makeEquation(parent, def, { y = 540, fit = 1660, kicker = 'Measured impact' } = {}) {
  const wrap = h('div', { class: 'abs', style: { left: '0', top: '0', width: '1920px', height: '1080px', zIndex: '40' } });
  const veil = h('div', { class: 'layer', style: { background: 'radial-gradient(ellipse 70% 56% at 50% 50%, rgba(7,8,10,0.93), rgba(7,8,10,0.8) 62%, rgba(7,8,10,0.62))', opacity: '0' } });
  const kick = h('div', { class: 'abs ix-kicker', style: { left: '0', width: '1920px', textAlign: 'center', top: `${y - 112}px`, opacity: '0' } }, kicker);
  const row = h('div', { class: 'ix-row', style: { opacity: '0' } });
  const items = def.tokens.map((k) => {
    let el;
    if (k.t === 'term') el = h('div', { class: `ix-token ${k.tone || 'base'}` }, icon(k.icon, { size: 32, stroke: 1.9 }), h('span', {}, k.label));
    else if (k.t === 'op') el = h('div', { class: 'ix-op' }, opSvg(k.sym, '#a8acb3'));
    else if (k.t === 'open') el = h('div', { class: 'ix-paren' }, '(');
    else if (k.t === 'close') el = h('div', { class: 'ix-paren' }, ')');
    else if (k.t === 'eq') el = h('div', { class: 'ix-eq' }, opSvg('=', '#ffffff'));
    else el = h('div', { class: 'ix-result' }, h('span', {}, 'Impact'), arrow(), h('i', { class: 'sweep' }));
    el.style.opacity = '0';
    row.append(el);
    return { k, el, sweep: k.t === 'result' ? el.lastChild : null };
  });
  wrap.append(veil, kick, row);
  parent.append(wrap);

  let L = null;
  function layout() {
    if (L) return L;
    const W = row.offsetWidth, H = row.offsetHeight;
    if (W < 10) return null; // hidden: try again next frame
    const s = Math.min(1.2, fit / W); // short formulas grow a little, long ones shrink to fit
    const x0 = 960 - (W * s) / 2, y0 = y - (H * s) / 2;
    const slots = items.map(({ el }) => ({
      x: x0 + (el.offsetLeft + el.offsetWidth / 2) * s,
      y: y0 + (el.offsetTop + el.offsetHeight / 2) * s,
      w: el.offsetWidth * s, h: el.offsetHeight * s,
    }));
    L = { W, H, s, x0, y0, slots };
    return L;
  }

  return {
    el: wrap,
    items,
    layout,
    /** Equation-wide visibility envelope (0..1), e.g. to dim the scene or hide the stepper. */
    level(t, { times, dockAt = Infinity, outAt = Infinity } = {}) {
      const end = Math.min(dockAt + DOCK_DUR * 0.6, outAt);
      return env(t, times[0] - 0.7, end + 0.45, 0.55, 0.45);
    },
    render(t, { times, from = {}, dock = null, dockAt = Infinity, outAt = Infinity }) {
      const lay = layout();
      if (!lay) return;
      const t0 = times[0];
      const live = t > t0 - 1.0 && t < Math.min(dockAt + DOCK_DUR + 0.2, outAt + 0.6);
      wrap.style.display = live ? 'block' : 'none';
      if (!live) return;
      const { W, H, s, slots } = lay;
      const dp = dock ? prog(t, dockAt, DOCK_DUR, E.inOutCubic) : 0;
      const out = prog(t, outAt, 0.45, E.inCubic);
      veil.style.opacity = (env(t, t0 - 0.7, Math.min(dockAt + DOCK_DUR * 0.55, outAt + 0.3), 0.55, 0.4)).toFixed(3);
      kick.style.opacity = (prog(t, t0 - 0.45, 0.4) * (1 - prog(t, dockAt - 0.1, 0.3)) * (1 - out)).toFixed(3);
      // row placement: centered on (960, y); docking shrinks it into the chain-map dot
      const m = lerp(1, 0.035, dp);
      const cx = dock ? lerp(960, dock.x, dp) : 960, cy = dock ? lerp(y, dock.y, dp) : y;
      row.style.transform = `translate(${(cx - (W * s * m) / 2).toFixed(2)}px, ${(cy - (H * s * m) / 2).toFixed(2)}px) scale(${(s * m).toFixed(4)})`;
      row.style.opacity = ((1 - prog(t, dockAt + DOCK_DUR * 0.62, DOCK_DUR * 0.38)) * (1 - out)).toFixed(3);
      row.style.filter = dp > 0.02 ? `brightness(${(1 + dp * 1.6).toFixed(2)})` : 'none';
      items.forEach((it, i) => {
        const ti = times[i];
        const el = it.el;
        const f = from[i];
        if (f && t < ti + 0.15) {
          // fly out of the scene into the slot
          const p = prog(t, ti - 0.5, 0.6, E.inOutCubic);
          if (p <= 0) { el.style.opacity = '0'; return; }
          const src = f(t);
          const sl = slots[i];
          const k = lerp(Math.max(0.2, src.w / sl.w), 1, p);
          const dx = (lerp(src.x, sl.x, p) - sl.x) / s, dy = (lerp(src.y, sl.y, p) - sl.y) / s;
          el.style.opacity = clamp(p * 3).toFixed(3);
          el.style.transform = `translate(${dx.toFixed(2)}px, ${dy.toFixed(2)}px) scale(${k.toFixed(4)})`;
          el.style.filter = 'none';
          return;
        }
        const q = prog(t, ti - 0.06, 0.42, E.outCubic);
        const b = it.k.t === 'result' ? Math.min(1.06, E.outBack(clamp((t - ti + 0.06) / 0.5), 2.0)) : lerp(0.84, 1, E.outBack(q, 1.6));
        el.style.opacity = q.toFixed(3);
        el.style.transform = `translateY(${((1 - q) * 18).toFixed(2)}px) scale(${b.toFixed(4)})`;
        el.style.filter = q < 0.98 ? `blur(${((1 - q) * 6).toFixed(2)}px)` : 'none';
        if (it.sweep) it.sweep.style.transform = `translateX(${(prog(t, ti + 0.25, 0.7, E.inOutSine) * 520).toFixed(1)}px) skewX(-18deg)`;
      });
    },
  };
}
