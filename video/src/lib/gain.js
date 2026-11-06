// The gain card: each chapter's closing beat, what the grower gains. The kicker and headline land as the
// gain line starts, the chips pop as the VO names them (or fly in out of the scene), an optional stat
// counts up, an underline sweeps under the headline, then the whole card docks into its station on the
// chain map.
import { h, svg, prog, E, clamp, lerp, env, TIMELINE } from '../engine.js';
import { icon } from './icons.js';
import { findPhrase, charTime } from './vo.js';
import { statText } from './impact-data.js';
import './impact-theme.js';

const STAT_DUR = 1.0;   // stat count-up
/** Scene-relative appearance time of every item: [headline, ...chips, stat?]. Mirrored in audio/sfx.py. */
export function gainTimes(ctx, def) {
  const id = def.line;
  const l = ctx.line(id);
  const times = [l.start - 0.2];
  let cursor = 0, prev = times[0];
  const at = (say, fallback) => {
    let t = null;
    if (say) {
      const idx = findPhrase(id, say, cursor);
      if (idx >= 0) { t = charTime(ctx, id, idx); cursor = idx + 1; }
    }
    if (t == null) t = prev + fallback;
    t = Math.max(t, prev + 0.2);
    times.push(t);
    prev = t;
  };
  def.chips.forEach((c) => at(c.say, 0.35));
  if (def.stat) at(def.stat.say, 0.45);
  return times;
}
/** Time the card is complete (underline + chime), from gainTimes. */
export const doneTime = (def, times) => times[times.length - 1] + (def.stat ? STAT_DUR - 0.1 : 0.35);

/** Absolute time the card of `def` docks (shared with the chain map so the dot fills in sync). */
export const DOCK_DELAY = 1.2, DOCK_DUR = 0.8;
export function dockStart(def) {
  const l = TIMELINE.lines[def.line];
  return l ? l.end + DOCK_DELAY : Infinity;
}

const arrowSvg = (up) => {
  const s = svg('svg', { viewBox: '0 0 24 24', width: 22, height: 22, fill: 'none', stroke: 'currentColor', 'stroke-width': 2.4, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', style: 'display:block;flex:none' });
  s.append(svg('path', { d: up ? 'M12 19V5' : 'M12 5v14' }), svg('path', { d: up ? 'M6 11l6-6 6 6' : 'M6 13l6 6 6-6' }));
  return s;
};

/**
 * makeGain(parent, def, {y, fit}) → {el, layout(), level(), render(t, {times, from, dock, dockAt, outAt})}
 * `from[i](t)` (optional; i indexes [headline, ...chips, stat]) returns the screen rect {x, y, w}
 * (center, width) an item flies out of.
 */
export function makeGain(parent, def, { y = 530, fit = 1640 } = {}) {
  const wrap = h('div', { class: 'abs', style: { left: '0', top: '0', width: '1920px', height: '1080px', zIndex: '40' } });
  const veil = h('div', { class: 'layer', style: { background: 'radial-gradient(ellipse 70% 60% at 50% 50%, rgba(7,8,10,0.94), rgba(7,8,10,0.82) 62%, rgba(7,8,10,0.64))', opacity: '0' } });
  const col = h('div', { class: 'gx-card', style: { opacity: '0' } });
  const kick = h('div', { class: 'gx-kicker' }, h('span', { class: 'gx-ico' }, icon(def.icon, { size: 22, stroke: 2 })), h('span', {}, def.kicker));
  const under = h('i', { class: 'gx-under' });
  const head = h('div', { class: 'gx-head' }, h('span', {}, def.headline), under);
  const chipRow = h('div', { class: 'gx-chips' });
  const chips = def.chips.map((c) => {
    const el = h('div', { class: 'gx-chip' }, h('span', { class: 'gx-arrow' }, arrowSvg(c.dir !== 'down')), h('span', {}, c.text));
    chipRow.append(el);
    return el;
  });
  col.append(kick, head, chipRow);
  let statVal = null, statEl = null;
  if (def.stat) {
    statVal = h('div', { class: 'gx-stat-v tnum' }, statText(def.stat, 1));
    statEl = h('div', { class: 'gx-stat' }, statVal,
      h('div', { class: 'gx-stat-k' }, h('span', {}, def.stat.label), def.stat.note ? h('span', { class: 'gx-note' }, def.stat.note) : null));
    col.append(statEl);
  }
  const items = [head, ...chips, ...(statEl ? [statEl] : [])].map((el) => { el.style.opacity = '0'; return { el }; });
  wrap.append(veil, col);
  parent.append(wrap);

  let L = null;
  function layout() {
    if (L) return L;
    const W = col.offsetWidth, H = col.offsetHeight;
    if (W < 10) return null; // hidden: try again next frame
    if (statVal) statVal.style.minWidth = `${statVal.offsetWidth}px`; // the count-up never reflows the card
    const s = Math.min(1, fit / W);
    const x0 = 960 - (W * s) / 2, y0 = y - (H * s) / 2;
    const slots = items.map(({ el }) => {
      const ox = el.offsetLeft + (el.parentElement === chipRow ? chipRow.offsetLeft : 0);
      const oy = el.offsetTop + (el.parentElement === chipRow ? chipRow.offsetTop : 0);
      return { x: x0 + (ox + el.offsetWidth / 2) * s, y: y0 + (oy + el.offsetHeight / 2) * s, w: el.offsetWidth * s, h: el.offsetHeight * s };
    });
    L = { W, H, s, x0, y0, slots };
    return L;
  }

  return {
    el: wrap,
    items,
    layout,
    /** Card-wide visibility envelope (0..1), e.g. to dim the scene or hide the stepper. */
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
      // card placement: centered on (960, y); docking shrinks it into the chain-map dot
      const m = lerp(1, 0.03, dp);
      const cx = dock ? lerp(960, dock.x, dp) : 960, cy = dock ? lerp(y, dock.y, dp) : y;
      col.style.transform = `translate(${(cx - (W * s * m) / 2).toFixed(2)}px, ${(cy - (H * s * m) / 2).toFixed(2)}px) scale(${(s * m).toFixed(4)})`;
      col.style.opacity = ((1 - prog(t, dockAt + DOCK_DUR * 0.62, DOCK_DUR * 0.38)) * (1 - out)).toFixed(3);
      col.style.filter = dp > 0.02 ? `brightness(${(1 + dp * 1.6).toFixed(2)})` : 'none';
      const kq = prog(t, t0 - 0.25, 0.45, E.outCubic);
      kick.style.opacity = kq.toFixed(3);
      kick.style.transform = `translateY(${((1 - kq) * 10).toFixed(2)}px)`;
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
        const b = lerp(0.86, 1, E.outBack(q, 1.6));
        el.style.opacity = q.toFixed(3);
        el.style.transform = `translateY(${((1 - q) * 16).toFixed(2)}px) scale(${b.toFixed(4)})`;
        el.style.filter = q < 0.98 ? `blur(${((1 - q) * 6).toFixed(2)}px)` : 'none';
      });
      if (statVal) statVal.firstChild.textContent = statText(def.stat, E.outCubic(prog(t, times[times.length - 1], STAT_DUR, E.linear)));
      under.style.transform = `scaleX(${prog(t, doneTime(def, times), 0.65, E.inOutCubic).toFixed(4)})`;
    },
  };
}
