// Animatable Eagerworks lockup: constructed icon (for the build) + traced artwork (for the final state).
import { h, svg, clamp, lerp, E, prog } from '../engine.js';
import { VIEWBOX, ICON_PATH, LETTER_PATHS, LETTER_BBOXES, HEX, STROKES } from './logo-data.js';

export function hexPath({ cx, cy, R, corner }) {
  const V = Array.from({ length: 6 }, (_, i) => { const a = ((-90 + i * 60) * Math.PI) / 180; return [cx + R * Math.cos(a), cy + R * Math.sin(a)]; });
  const d = corner / Math.tan(Math.PI / 3);
  let p = '';
  for (let i = 0; i < 6; i++) {
    const [x, y] = V[i], [px, py] = V[(i + 5) % 6], [nx, ny] = V[(i + 1) % 6];
    const l1 = Math.hypot(px - x, py - y), l2 = Math.hypot(nx - x, ny - y);
    const a = [x + ((px - x) / l1) * d, y + ((py - y) / l1) * d];
    const b = [x + ((nx - x) / l2) * d, y + ((ny - y) / l2) * d];
    p += `${i === 0 ? 'M' : 'L'}${a[0].toFixed(1)},${a[1].toFixed(1)} A${corner},${corner} 0 0 1 ${b[0].toFixed(1)},${b[1].toFixed(1)} `;
  }
  return `${p}Z`;
}

/** Build the lockup. height = rendered height of the icon row in px. Returns {el, width, update(p)} parts. */
export function makeLockup({ height = 140, studio = true, bg = '#07080a' } = {}) {
  const [vx, vy, vw, vh] = VIEWBOX;
  const scale = height / vh;
  const width = vw * scale;
  const root = h('div', { class: 'abs', style: { left: '0', top: '0', height: `${height}px`, display: 'flex', alignItems: 'flex-start', whiteSpace: 'nowrap' } });
  const s = svg('svg', { viewBox: VIEWBOX.join(' '), width: width.toFixed(1), height: height.toFixed(1), style: 'overflow:visible;display:block' });
  const hp = hexPath(HEX);
  const hexFill = svg('path', { d: hp, fill: '#ffffff', 'fill-opacity': 0 });
  const hexOutline = svg('path', { d: hp, fill: 'none', stroke: '#ffffff', 'stroke-width': 26, 'stroke-linejoin': 'round' });
  const outlineLen = 6 * (HEX.R - 2 * (HEX.corner / Math.tan(Math.PI / 3))) + 6 * (HEX.corner * Math.PI / 3);
  hexOutline.setAttribute('stroke-dasharray', `${outlineLen.toFixed(1)}`);
  const strokes = STROKES.map((st) => {
    const l = svg('line', { x1: st.x1, y1: st.y1, x2: st.x2, y2: st.y2, stroke: '#d4ff5a', 'stroke-width': st.w + 8, 'stroke-linecap': 'butt' });
    const len = Math.hypot(st.x2 - st.x1, st.y2 - st.y1);
    l.setAttribute('stroke-dasharray', `${len.toFixed(1)}`);
    return { l, len };
  });
  const traced = svg('path', { d: ICON_PATH, fill: '#ffffff', 'fill-rule': 'evenodd', opacity: 0 });
  const letters = LETTER_PATHS.map((d) => svg('path', { d, fill: '#ffffff' }));
  const gLetters = svg('g', {});
  letters.forEach((l) => gLetters.append(l));
  s.append(hexFill, hexOutline, ...strokes.map((x) => x.l), traced, gLetters);
  root.append(s);
  let divider = null, studioEl = null;
  if (studio) {
    // align "AI Studio" to the wordmark: cap height ≈ wordmark ascender, shared baseline
    const baseline = (674 - vy) * scale;
    const fs = height * 0.52;
    divider = h('div', { style: { width: '2px', height: `${(height * 0.5).toFixed(1)}px`, background: 'rgba(255,255,255,0.28)', marginLeft: `${(height * 0.32).toFixed(1)}px`, marginTop: `${(baseline - height * 0.5).toFixed(1)}px` } });
    studioEl = h('div', { class: 'display', style: { fontSize: `${fs.toFixed(1)}px`, fontWeight: 500, fontStretch: '112%', letterSpacing: '-0.01em', color: '#ffffff', lineHeight: '1', marginLeft: `${(height * 0.3).toFixed(1)}px`, marginTop: `${(baseline - fs * 0.9).toFixed(1)}px` } }, 'AI Studio');
    root.append(divider, studioEl);
  }
  return {
    el: root, width, height, strokes, hexOutline, hexFill, traced, letters, divider, studioEl, outlineLen,
    /** Drive the build: p.strokes, p.outline, p.fill, p.letters, p.studio (each 0..1). */
    set({ strokes: ps = 1, outline: po = 1, fill: pf = 1, letters: pl = 1, studio: pst = 1, glow = 0 } = {}) {
      strokes.forEach((st, i) => {
        const q = E.outCubic(clamp(ps * 1.6 - i * 0.3));
        st.l.setAttribute('stroke-dashoffset', ((1 - q) * st.len).toFixed(1));
        st.l.setAttribute('opacity', (q > 0 ? 1 - clamp((pf - 0.55) / 0.3) : 0).toFixed(3));
        st.l.setAttribute('stroke', pf > 0.25 ? bg : '#d4ff5a');
      });
      hexOutline.setAttribute('stroke-dashoffset', ((1 - E.inOutCubic(po)) * outlineLen).toFixed(1));
      hexOutline.setAttribute('opacity', (po > 0 ? 1 - clamp((pf - 0.6) / 0.3) : 0).toFixed(3));
      hexFill.setAttribute('fill-opacity', (E.inOutSine(clamp(pf / 0.5)) * (1 - clamp((pf - 0.7) / 0.3))).toFixed(3));
      traced.setAttribute('opacity', clamp((pf - 0.55) / 0.35).toFixed(3));
      letters.forEach((l, i) => {
        const q = E.outCubic(clamp(pl * 2.2 - i * 0.12));
        l.setAttribute('opacity', q.toFixed(3));
        l.setAttribute('transform', `translate(${((1 - q) * -60).toFixed(1)} 0)`);
      });
      if (divider) {
        const q = E.outCubic(clamp(pst * 2));
        divider.style.transform = `scaleY(${q.toFixed(3)})`;
        const q2 = E.outCubic(clamp(pst * 2 - 0.4));
        studioEl.style.opacity = q2.toFixed(3);
        studioEl.style.transform = `translateX(${((1 - q2) * -24).toFixed(1)}px)`;
      }
      s.style.filter = glow > 0.01 ? `drop-shadow(0 0 ${(24 * glow).toFixed(1)}px rgba(212,255,90,${(0.35 * glow).toFixed(3)}))` : 'none';
    },
  };
}
