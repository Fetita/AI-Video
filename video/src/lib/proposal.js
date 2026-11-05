// Need → Solution, in the film's own look: two matte panels that unfold out of the hand-off line,
// joined by a violet connector. NEED carries a coral chip, SOLUTION a violet one. No slide layout,
// proposal label, logo or corner glow: the content of the proposal, not a picture of it. An optional
// photo (the onion proof of concept) sits inside the NEED panel as a small monitor.
import { h, svg, prog, E, clamp, lerp } from '../engine.js';
import { CHAIN } from './chain.js';
import { icon } from './icons.js';
import './impact-theme.js';

const PW = 700, GAP = 120;

/**
 * makeProposalCard(parent, {need, solution, photo, caption, marks, photoSize, markLabel, h})
 * need / solution: HTML strings (use <b> for the highlighted phrase).
 * Returns {el, solutionRect, render(t, {open, need, sol, out, marks})}, each phase a 0..1 progress.
 */
export function makeProposalCard(parent, { need, solution, photo = null, caption = '', marks = [], photoSize = [707, 391], markLabel = 'Missed', h: hh = 300, solH = hh } = {}) {
  const x0 = (1920 - (PW * 2 + GAP)) / 2, x1 = x0 + PW + GAP;
  const y = CHAIN.y - hh / 2;
  const wrap = h('div', { class: 'abs', style: { left: '0', top: '0', width: '1920px', height: '1080px' } });
  const panel = (x, kind, html, ph_ = hh) => {
    const coral = kind === 'need';
    const el = h('div', { class: 'abs', style: { left: `${x}px`, top: `${CHAIN.y - ph_ / 2}px`, width: `${PW}px`, height: `${ph_}px`, borderRadius: '18px', overflow: 'hidden', background: 'linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0) 45%), #0f1115', border: `1px solid ${coral ? 'rgba(255,107,87,0.32)' : 'rgba(130,52,254,0.45)'}`, boxShadow: '0 40px 90px -30px rgba(0,0,0,0.8), inset 0 1px 0 rgba(255,255,255,0.05)', padding: '30px 32px' } });
    const head = h('div', { style: { display: 'flex', alignItems: 'center', gap: '14px' } },
      h('span', { style: { width: '42px', height: '42px', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', background: coral ? 'rgba(255,107,87,0.14)' : 'rgba(130,52,254,0.18)', color: coral ? '#ff8a78' : '#c4adff', flex: 'none' } }, icon(coral ? 'alert' : 'camera', { size: 24, stroke: 1.9 })),
      h('span', { class: 'ix-chip', style: { background: coral ? 'rgba(255,107,87,0.16)' : 'rgba(130,52,254,0.2)', color: coral ? '#ffb3a8' : '#d9caff', border: `1px solid ${coral ? 'rgba(255,107,87,0.45)' : 'rgba(130,52,254,0.55)'}`, fontSize: '13px', letterSpacing: '0.2em' } }, coral ? 'Need' : 'Solution'));
    const p = h('div', { style: { marginTop: '22px', fontFamily: 'var(--font-ui)', fontWeight: '500', fontSize: '30px', lineHeight: '1.38', letterSpacing: '-0.005em', color: '#f3f3ef' } });
    p.innerHTML = html.replace(/<b>/g, `<b style="font-weight:700;color:${coral ? '#ffb3a8' : '#cdb8ff'}">`);
    el.append(head, p);
    wrap.append(el);
    return { el, p };
  };
  const N = panel(x0, 'need', need);
  const S = panel(x1, 'solution', solution, solH);
  let ph = null;
  if (photo) {
    const pw = PW - 64, phh = Math.round(pw * 0.44);
    ph = h('div', { style: { position: 'absolute', left: '32px', bottom: '30px', width: `${pw}px`, height: `${phh}px`, borderRadius: '12px', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.14)', background: '#000' } },
      h('img', { src: photo, style: { width: '100%', height: '100%', objectFit: 'cover', display: 'block', filter: 'saturate(0.8) contrast(1.05)' } }),
      h('div', { style: { position: 'absolute', left: '0', right: '0', bottom: '0', height: '56px', background: 'linear-gradient(180deg, transparent, rgba(0,0,0,0.78))' } }),
      h('div', { style: { position: 'absolute', left: '16px', bottom: '14px', display: 'flex', alignItems: 'center', gap: '9px', fontFamily: 'var(--font-ui)', fontWeight: '600', fontSize: '12px', letterSpacing: '0.18em', textTransform: 'uppercase', color: '#e8ecf5' } },
        h('i', { style: { width: '8px', height: '8px', borderRadius: '50%', background: 'var(--coral)', display: 'block' } }), caption));
    if (marks.length) {
      const ov = svg('svg', { viewBox: `0 0 ${photoSize[0]} ${photoSize[1]}`, preserveAspectRatio: 'xMidYMid slice', style: 'position:absolute;inset:0;width:100%;height:100%;overflow:visible' });
      ph.rings = marks.map((m) => { const c = svg('circle', { cx: m.x, cy: m.y, r: m.r, fill: 'none', stroke: '#ff6b57', 'stroke-width': 2.4, 'stroke-dasharray': '5 4' }); ov.append(c); return c; });
      ph.insertBefore(ov, ph.children[1]);
      ph.badge = h('div', { style: { position: 'absolute', right: '12px', top: '12px', fontFamily: 'var(--font-ui)', fontWeight: '700', fontSize: '12px', letterSpacing: '0.18em', textTransform: 'uppercase', color: '#1d0905', background: '#ff6b57', padding: '6px 10px', borderRadius: '6px', opacity: '0' } }, markLabel);
      ph.append(ph.badge);
    }
    N.el.append(ph);
  }
  // the hand-off line contracts into the connector between the two panels; a pulse runs need → solution
  const line = h('div', { class: 'abs', style: { left: `${CHAIN.x0}px`, top: `${CHAIN.y - 1.5}px`, width: `${CHAIN.x1 - CHAIN.x0}px`, height: '3px', background: 'var(--accent)', boxShadow: '0 0 18px rgba(130,52,254,0.75)', transformOrigin: '0 50%' } });
  const pulse = h('i', { class: 'abs', style: { left: '0', top: `${CHAIN.y - 5}px`, width: '10px', height: '10px', borderRadius: '50%', background: '#fff', boxShadow: '0 0 14px rgba(160,120,255,0.95)', display: 'block', opacity: '0' } });
  const chev = svg('svg', { viewBox: '0 0 24 24', width: 26, height: 26, fill: 'none', stroke: '#b89cff', 'stroke-width': 2.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', style: `position:absolute;left:${x1 - GAP / 2 - 13}px;top:${CHAIN.y - 13}px;opacity:0` });
  chev.append(svg('path', { d: 'M9 6l6 6-6 6' }));
  wrap.append(line, pulse, chev);
  parent.append(wrap);
  const wipe = (el, p) => {
    const v = (p * 130 - 15).toFixed(1);
    const m = `linear-gradient(180deg, #000 ${v}%, transparent ${(+v + 15).toFixed(1)}%)`;
    el.style.webkitMaskImage = m; el.style.maskImage = m;
    el.style.opacity = p > 0 ? '1' : '0';
  };
  const unfold = (el, p) => {
    const q = E.inOutCubic(clamp(p));
    const inset = (1 - q) * 50;
    el.style.clipPath = `inset(${inset.toFixed(2)}% 0 ${inset.toFixed(2)}% 0 round 18px)`;
    el.style.display = q > 0.001 ? 'block' : 'none';
  };
  return {
    el: wrap,
    /** Screen rect of the solution panel (where the live system grows from). */
    solutionRect: () => ({ x: x1, y: CHAIN.y - solH / 2, w: PW, h: solH }),
    render(t, { open = 0, need: pn = 0, sol: ps = 0, out = 0, marks: pm = 0 } = {}) {
      const vis = (t >= 0 || open > 0) && out < 0.999;
      wrap.style.display = vis ? 'block' : 'none';
      if (!vis) return;
      const outE = E.inCubic(out);
      // line: full width at the cut → the connector between the panels
      const c = E.inOutCubic(clamp(open * 1.4));
      const lx0 = lerp(CHAIN.x0, x0 + PW, c), lx1 = lerp(CHAIN.x1, x1, c);
      line.style.transform = `translateX(${(lx0 - CHAIN.x0).toFixed(2)}px) scaleX(${((lx1 - lx0) / (CHAIN.x1 - CHAIN.x0)).toFixed(4)})`;
      line.style.opacity = (1 - outE).toFixed(3);
      chev.style.opacity = (clamp(ps * 3) * (1 - outE)).toFixed(3);
      const pp = ((t * 0.9) % 1 + 1) % 1;
      pulse.style.transform = `translateX(${lerp(x0 + PW - 4, x1 - 6, pp).toFixed(1)}px)`;
      pulse.style.opacity = (clamp(ps * 3) * Math.sin(pp * Math.PI) * (1 - outE)).toFixed(3);
      // NEED unfolds with the open, SOLUTION when its line starts
      unfold(N.el, clamp((open - 0.3) / 0.7));
      unfold(S.el, clamp(ps / 0.35));
      N.el.style.opacity = (1 - outE).toFixed(3);
      N.el.style.transform = `translateX(${(-outE * 60).toFixed(1)}px)`;
      S.el.style.opacity = (1 - clamp(out * 1.4)).toFixed(3);
      wipe(N.p, clamp((pn - 0.1) / 0.9));
      wipe(S.p, clamp((ps - 0.25) / 0.75));
      if (ph) {
        const q = clamp((pn - 0.45) * 2.5);
        ph.style.opacity = q.toFixed(3);
        ph.style.transform = `translateY(${((1 - q) * 14).toFixed(2)}px)`;
        if (ph.rings) {
          ph.rings.forEach((r, i) => { const qq = clamp(pm * (ph.rings.length + 2) - i); r.setAttribute('opacity', qq.toFixed(3)); r.setAttribute('stroke-width', (2.4 + (1 - qq) * 4).toFixed(2)); });
          ph.badge.style.opacity = clamp(pm * 3).toFixed(3);
          ph.style.borderColor = pm > 0 ? `rgba(255,107,87,${(0.14 + 0.6 * clamp(pm * 2)).toFixed(3)})` : 'rgba(255,255,255,0.14)';
        }
      }
    },
  };
}
