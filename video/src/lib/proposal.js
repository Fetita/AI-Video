// "Need | Solution" proposal card in the look of Eagerworks' proposal slides (black, blue corner
// glow, wide display titles, Manrope body with highlighted phrases, logo top right), anonymized.
// It opens out of the standard hand-off line and dissolves into the live system.
import { h, svg, prog, E, clamp, lerp } from '../engine.js';
import { CHAIN } from './chain.js';
import './impact-theme.js';

/**
 * makeProposalCard(parent, {need, solution, photo, caption, w, h})
 * need / solution: HTML strings (use <b> for the highlighted phrase).
 * Returns {el, solutionRect, render(t, {open, need, sol, out})}, each phase a 0..1 progress.
 */
export function makeProposalCard(parent, { need, solution, photo = null, caption = '', marks = [], photoSize = [707, 391], markLabel = 'Missed', w = 1500, h: hh = 640 } = {}) {
  const x = (1920 - w) / 2, y = CHAIN.y - hh / 2;
  const card = h('div', { class: 'ix-card', style: { left: `${x}px`, top: `${y}px`, width: `${w}px`, height: `${hh}px`, transformOrigin: '50% 50%' } });
  card.append(h('div', { class: 'glow' }));
  const pad = 78, colW = (w - pad * 2 - 100) / 2;
  const top = h('div', { class: 'abs', style: { left: `${pad}px`, right: `${pad}px`, top: '54px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' } },
    h('div', { class: 'lbl' }, 'Proposal · Need & Solution'),
    h('img', { src: 'assets/logo/eagerworks-logo.svg', style: { height: '24px', display: 'block', opacity: '0.95' } }));
  const divider = h('div', { class: 'abs', style: { left: `${w / 2}px`, top: '150px', width: '1px', height: `${hh - 210}px`, background: 'rgba(120,150,220,0.28)', transformOrigin: '50% 0' } });
  const col = (left, title, html) => {
    const c = h('div', { class: 'abs', style: { left: `${left}px`, top: '150px', width: `${colW}px` } });
    const t = h('h3', {}, title);
    const p = h('p', { style: { marginTop: '34px' } });
    p.innerHTML = html;
    c.append(t, p);
    card.append(c);
    return { c, t, p };
  };
  const L = col(pad, 'Need', need);
  const R = col(w / 2 + 50, 'Solution', solution);
  let ph = null;
  if (photo) {
    ph = h('div', { class: 'abs', style: { left: `${pad}px`, top: `${hh - 78 - 300}px`, width: `${colW}px`, height: '300px', borderRadius: '12px', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.14)', background: '#000' } },
      h('img', { src: photo, style: { width: '100%', height: '100%', objectFit: 'cover', display: 'block', filter: 'saturate(0.85) contrast(1.05)' } }),
      h('div', { style: { position: 'absolute', left: '0', right: '0', bottom: '0', height: '64px', background: 'linear-gradient(180deg, transparent, rgba(0,0,0,0.8))' } }),
      h('div', { class: 'lbl', style: { position: 'absolute', left: '16px', bottom: '14px', color: '#e8ecf5', fontSize: '12px' } }, caption));
    card.append(ph);
    // optional overlay: rings on what the off-the-shelf model missed (image coordinates, same crop as the photo)
    if (marks.length) {
      const ov = svg('svg', { viewBox: `0 0 ${photoSize[0]} ${photoSize[1]}`, preserveAspectRatio: 'xMidYMid slice', style: 'position:absolute;inset:0;width:100%;height:100%;overflow:visible' });
      ph.rings = marks.map((m) => { const c = svg('circle', { cx: m.x, cy: m.y, r: m.r, fill: 'none', stroke: '#ff6b57', 'stroke-width': 2.4, 'stroke-dasharray': '5 4' }); ov.append(c); return c; });
      ph.insertBefore(ov, ph.children[1]);
      ph.badge = h('div', { class: 'lbl', style: { position: 'absolute', right: '14px', top: '14px', color: '#1d0905', background: '#ff6b57', padding: '6px 10px', borderRadius: '6px', fontSize: '12px', opacity: '0' } }, markLabel);
      ph.append(ph.badge);
    }
  }
  card.append(top, divider);
  const line = h('div', { class: 'abs', style: { left: `${CHAIN.x0}px`, top: `${CHAIN.y - 1.5}px`, width: `${CHAIN.x1 - CHAIN.x0}px`, height: '3px', background: 'var(--accent)', boxShadow: '0 0 18px rgba(130,52,254,0.75)', transformOrigin: '50% 50%' } });
  parent.append(card, line);
  const wipe = (el, p) => {
    const v = (p * 130 - 15).toFixed(1);
    const m = `linear-gradient(180deg, #000 ${v}%, transparent ${(+v + 15).toFixed(1)}%)`;
    el.style.webkitMaskImage = m; el.style.maskImage = m;
    el.style.opacity = p > 0 ? '1' : '0';
  };
  return {
    el: card,
    /** Screen rect of the solution column (where the live system grows from). */
    solutionRect: () => ({ x: x + w / 2 + 50, y: y + 140, w: colW, h: hh - 200 }),
    render(t, { open = 0, need: pn = 0, sol: ps = 0, out = 0, marks: pm = 0 } = {}) {
      const vis = open > 0.001 && out < 0.999;
      card.style.display = vis ? 'block' : 'none';
      // the hand-off line is on screen from the cut (t >= 0) until the card has opened out of it
      line.style.display = t >= 0 && open < 1 ? 'block' : 'none';
      // the hand-off line contracts to the card width as the card opens out of it
      const lw = lerp(1, w / (CHAIN.x1 - CHAIN.x0), E.inOutCubic(clamp(open * 1.6)));
      line.style.transform = `scaleX(${lw.toFixed(4)})`;
      line.style.opacity = (1 - prog(open, 0.6, 0.4)).toFixed(3);
      if (!vis) return;
      const o = E.inOutCubic(clamp((open - 0.25) / 0.75));
      const inset = (1 - o) * 50;
      card.style.clipPath = `inset(${inset.toFixed(2)}% 0 ${inset.toFixed(2)}% 0 round 22px)`;
      const outE = E.inCubic(out);
      card.style.opacity = (1 - outE).toFixed(3);
      card.style.transform = `scale(${lerp(1, 1.06, outE).toFixed(4)})`;
      card.style.filter = out > 0.02 ? `blur(${(outE * 8).toFixed(2)}px)` : 'none';
      top.style.opacity = prog(open, 0.7, 0.3).toFixed(3);
      divider.style.transform = `scaleY(${prog(open, 0.6, 0.4, E.outCubic).toFixed(3)})`;
      L.t.style.opacity = clamp(pn * 3).toFixed(3);
      L.t.style.transform = `translateY(${((1 - clamp(pn * 3)) * 14).toFixed(2)}px)`;
      wipe(L.p, clamp((pn - 0.15) / 0.85));
      if (ph) {
        ph.style.opacity = clamp((pn - 0.5) * 3).toFixed(3);
        ph.style.transform = `translateY(${((1 - clamp((pn - 0.5) * 3)) * 16).toFixed(2)}px)`;
        if (ph.rings) {
          ph.rings.forEach((c, i) => { const q = clamp(pm * (ph.rings.length + 2) - i); c.setAttribute('opacity', q.toFixed(3)); c.setAttribute('stroke-width', (2.4 + (1 - q) * 4).toFixed(2)); });
          ph.badge.style.opacity = clamp(pm * 3).toFixed(3);
          ph.style.borderColor = pm > 0 ? `rgba(255,107,87,${(0.14 + 0.6 * clamp(pm * 2)).toFixed(3)})` : 'rgba(255,255,255,0.14)';
        }
      }
      R.t.style.opacity = clamp(ps * 3).toFixed(3);
      R.t.style.transform = `translateY(${((1 - clamp(ps * 3)) * 14).toFixed(2)}px)`;
      wipe(R.p, clamp((ps - 0.15) / 0.85));
    },
  };
}
