// Animatable FS Studio lockup. Same interface as logo.js (el, height, set({...})) so the hook and the
// finale drive either brand with the same timing. The build draws the icon as ONE continuous pink line
// (the film's signal line becoming the mark), then swaps to the supplied artwork, slides the FSSTUDIO
// wordmark in letter by letter, and adds "Applied AI" with the brand's cyan "+" (after "Applied Imagination+").
import { h, svg, clamp, E } from '../engine.js';
import { VIEWBOX, ICON_PATH, CENTRE_PATH, CENTRE_LENGTH, STROKE_W, LETTER_PATHS, WORDMARK } from './logo-data-fsstudio.js';

const PINK = '#ff059f';

/** height = rendered height of the lockup's viewBox (icon height) in px. */
export function makeLockup({ height = 176, studio = true } = {}) {
  const [vx, vy, vw, vh] = VIEWBOX;
  const scale = height / vh;
  const width = vw * scale;
  const root = h('div', { class: 'abs', style: { left: '0', top: '0', height: `${height}px`, display: 'flex', alignItems: 'flex-start', whiteSpace: 'nowrap' } });
  const s = svg('svg', { viewBox: VIEWBOX.join(' '), width: width.toFixed(1), height: height.toFixed(1), style: 'overflow:visible;display:block' });
  // the line that draws itself, and the artwork it resolves into
  const line = svg('path', { d: CENTRE_PATH, fill: 'none', stroke: PINK, 'stroke-width': STROKE_W, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-dasharray': `${CENTRE_LENGTH + 2}` });
  const head = svg('circle', { r: STROKE_W * 0.9, fill: '#ffffff', opacity: 0 }); // bright tip that leads the line
  const traced = svg('path', { d: ICON_PATH, fill: PINK, opacity: 0 });
  const letters = LETTER_PATHS.map((d) => svg('path', { d, fill: '#f2f2f2' }));
  const gLetters = svg('g', {});
  letters.forEach((l) => gLetters.append(l));
  s.append(line, traced, head, gLetters);
  root.append(s);
  let divider = null, studioEl = null, plus = null;
  if (studio) {
    // "Applied AI" shares the wordmark's baseline; its cap height matches the wordmark's
    const baseline = (WORDMARK.baseline - vy) * scale;
    const cap = (WORDMARK.baseline - WORDMARK.top) * scale;
    const fs = cap / 0.7;
    divider = h('div', { style: { width: '2px', height: `${(cap * 1.25).toFixed(1)}px`, background: 'rgba(255,255,255,0.3)', marginLeft: `${(cap * 0.62).toFixed(1)}px`, marginTop: `${(baseline - cap * 1.12).toFixed(1)}px`, transformOrigin: '50% 100%' } });
    plus = h('span', { style: { color: '#39dae0', fontWeight: 700, fontSize: `${(fs * 0.62).toFixed(1)}px`, position: 'relative', top: `${(-fs * 0.42).toFixed(1)}px`, marginLeft: `${(fs * 0.04).toFixed(1)}px`, display: 'inline-block' } }, '+');
    studioEl = h('div', { style: { fontFamily: 'var(--font-display)', fontSize: `${fs.toFixed(1)}px`, fontWeight: 600, letterSpacing: '-0.01em', color: '#ffffff', lineHeight: '1', marginLeft: `${(cap * 0.6).toFixed(1)}px`, marginTop: `${(baseline - fs * 0.93).toFixed(1)}px` } }, 'Applied AI', plus);
    root.append(divider, studioEl);
  }
  return {
    el: root, width, height, letters, divider, studioEl,
    /** p.strokes + p.outline draw the line, p.fill resolves it into the artwork, p.letters, p.studio (each 0..1). */
    set({ strokes: ps = 1, outline: po = 1, fill: pf = 1, letters: pl = 1, studio: pst = 1, glow = 0 } = {}) {
      const draw = clamp(0.3 * E.outCubic(clamp(ps)) + 0.7 * E.inOutCubic(clamp(po)));
      line.setAttribute('stroke-dashoffset', ((1 - draw) * (CENTRE_LENGTH + 2)).toFixed(1));
      const swap = clamp((pf - 0.35) / 0.4);
      line.setAttribute('opacity', (draw > 0 ? 1 - swap : 0).toFixed(3));
      traced.setAttribute('opacity', swap.toFixed(3));
      if (draw > 0 && draw < 1) {
        const p = line.getPointAtLength(draw * CENTRE_LENGTH);
        head.setAttribute('cx', p.x.toFixed(2)); head.setAttribute('cy', p.y.toFixed(2));
        head.setAttribute('opacity', (0.85 * Math.sin(Math.PI * draw)).toFixed(3));
      } else head.setAttribute('opacity', '0');
      letters.forEach((l, i) => {
        const q = E.outCubic(clamp(pl * 2.2 - i * 0.12));
        l.setAttribute('opacity', q.toFixed(3));
        l.setAttribute('transform', `translate(${((1 - q) * -40).toFixed(2)} 0)`);
      });
      if (divider) {
        const q = E.outCubic(clamp(pst * 2));
        divider.style.transform = `scaleY(${q.toFixed(3)})`;
        const q2 = E.outCubic(clamp(pst * 2 - 0.4));
        studioEl.style.opacity = q2.toFixed(3);
        studioEl.style.transform = `translateX(${((1 - q2) * -24).toFixed(1)}px)`;
        const q3 = E.outBack(clamp(pst * 2 - 1));
        plus.style.transform = `scale(${q3.toFixed(3)}) rotate(${((1 - clamp(q3)) * 90).toFixed(1)}deg)`;
      }
      const g = glow + 0.6 * Math.sin(Math.PI * clamp(pf));
      s.style.filter = g > 0.01 ? `drop-shadow(0 0 ${(26 * g).toFixed(1)}px rgba(255,5,159,${(0.4 * Math.min(g, 1)).toFixed(3)}))` : 'none';
    },
  };
}
