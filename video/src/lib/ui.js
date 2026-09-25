// Shared film UI: chapter label, pipeline stepper, text effects, detection overlays.
import { h, put, prog, E, clamp, lerp, env, rgba, C, hash, rrect } from '../engine.js';

// ------------------------------------------------------------------ chapter + stepper HUD
/**
 * Chapter label (top-left) and pipeline stepper (bottom-center).
 * steps: [{label, at}] — `at` is the scene-relative time the step becomes active.
 */
export function makeHud(ctx, { num, title, steps = [], stepY = 58 }) {
  const chapter = h('div', { class: 'hud-chapter' },
    h('span', { class: 'num' }, num), h('span', { class: 'bar' }), h('span', { class: 'ttl' }, title));
  const stepper = h('div', { class: 'stepper', style: { bottom: `${stepY}px` } });
  const parts = steps.map((s, i) => {
    const link = i > 0 ? h('div', { class: 'link' }, h('i')) : null;
    const dot = h('span', { class: 'dot' });
    const label = h('span', { class: 'lbl' }, s.label);
    const step = h('div', { class: 'step' }, dot, label);
    if (link) stepper.append(link);
    stepper.append(step);
    return { link, dot, label, step, at: s.at };
  });
  const wrap = h('div', { class: 'layer', style: { zIndex: 50 } }, chapter, stepper);
  if (new URLSearchParams(location.search).has('nohud')) wrap.style.display = 'none';
  ctx.root.append(wrap);
  const clipIn = (p) => `inset(0 ${(100 - p * 100).toFixed(2)}% 0 0)`;
  return function update(t, { hideSteps = false } = {}) {
    const a = prog(t, 0.15, 0.7, E.outCubic) * (1 - prog(t, ctx.dur - 0.45, 0.45, E.inCubic));
    chapter.style.clipPath = clipIn(prog(t, 0.15, 0.8, E.outQuart));
    put(chapter, { o: a });
    const sa = prog(t, 0.5, 0.6, E.outCubic) * (1 - prog(t, ctx.dur - 0.45, 0.45, E.inCubic)) * (hideSteps ? 0 : 1);
    put(stepper, { x: 0, y: (1 - sa) * 14, o: sa });
    stepper.style.transform = `translateX(-50%) translateY(${((1 - sa) * 14).toFixed(2)}px)`;
    parts.forEach((p, i) => {
      const on = clamp((t - p.at) / 0.35);
      const next = parts[i + 1];
      const done = next ? clamp((t - next.at) / 0.35) : 0;
      const active = on * (1 - done * 0.55);
      p.label.style.color = on > 0 ? `rgba(${lerp(108, 243, active)|0},${lerp(113, 243, active)|0},${lerp(121, 239, active)|0},1)` : '';
      p.dot.style.background = on > 0 ? rgba(C.accent, on) : 'transparent';
      p.dot.style.borderColor = on > 0 ? C.accent : '';
      p.dot.style.boxShadow = active > 0.5 && !done ? `0 0 0 ${(4 * active).toFixed(1)}px rgba(212,255,90,${(0.18 * active).toFixed(3)})` : 'none';
      if (p.link) p.link.firstChild.style.width = `${(E.inOutCubic(on) * 100).toFixed(1)}%`;
    });
  };
}

// ------------------------------------------------------------------ text effects
const GLYPHS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<>/_#*+=';
/** Scramble-decode from `from` into `to` as p goes 0→1 (left-to-right resolve). */
export function decode(from, to, p, seed = 1, frame = 0) {
  const n = Math.max(from.length, to.length);
  let out = '';
  for (let i = 0; i < n; i++) {
    const local = clamp(p * 1.6 - (i / n) * 0.6);
    if (local >= 1) out += to[i] ?? '';
    else if (local <= 0) out += from[i] ?? '';
    else {
      const ch = (to[i] ?? from[i] ?? ' ');
      out += ch === ' ' ? ' ' : GLYPHS[Math.floor(hash(seed, i, Math.floor(frame / 2)) * GLYPHS.length)];
    }
  }
  return out.replace(/\s+$/, '');
}

/** Split text into word spans for per-word animation. Returns span list. */
export function words(el, text, cls = 'w') {
  el.textContent = '';
  const spans = [];
  text.split(/(\s+)/).forEach((tok) => {
    if (/^\s+$/.test(tok)) el.append(document.createTextNode(tok));
    else if (tok) {
      const s = h('span', { class: cls, style: { display: 'inline-block', whiteSpace: 'pre' } }, tok);
      el.append(s);
      spans.push(s);
    }
  });
  return spans;
}

/** Reveal words: opacity + slight rise, driven by progress p (0..1). */
export function revealWords(spans, p, { rise = 10, soft = 2.5, blur = 0 } = {}) {
  const n = spans.length;
  spans.forEach((s, i) => {
    const q = clamp(p * (n + soft) - i, 0, soft) / soft;
    const e = E.outCubic(q);
    s.style.opacity = e.toFixed(3);
    s.style.transform = `translateY(${((1 - e) * rise).toFixed(2)}px)`;
    if (blur) s.style.filter = e < 0.99 ? `blur(${((1 - e) * blur).toFixed(2)}px)` : 'none';
  });
}

/** Park an absolutely-positioned caret right after the last revealed word span. */
export function placeCaret(caret, spans, { dx = 5, dy = 0 } = {}) {
  let last = null;
  for (const sp of spans) { if (parseFloat(sp.style.opacity || '0') > 0.35) last = sp; else break; }
  caret.style.position = 'absolute';
  const ref = last || spans[0];
  if (!ref) return;
  caret.style.left = `${last ? ref.offsetLeft + ref.offsetWidth + dx : ref.offsetLeft}px`;
  caret.style.top = `${ref.offsetTop + dy}px`;
}

/** Typewriter: returns substring for progress p. */
export const typed = (text, p) => text.slice(0, Math.round(clamp(p) * text.length));

// ------------------------------------------------------------------ canvas overlays
export const FONT_MONO = '"JetBrains Mono", monospace';
export const FONT_UI = 'Inter, sans-serif';

/** Detection box in the film's style: hairline + bright corners + faint fill. */
export function box(g, x, y, w, hh, { color = C.accent, a = 1, lw = 1.5, corner = 0.22, fill = 0.06, dash = null, glow = 0 } = {}) {
  if (a <= 0.001) return;
  g.save();
  g.globalAlpha = a;
  if (fill) { g.fillStyle = rgba(color, fill); g.fillRect(x, y, w, hh); }
  g.strokeStyle = rgba(color, 0.55);
  g.lineWidth = lw;
  if (dash) g.setLineDash(dash);
  g.strokeRect(x + 0.5, y + 0.5, w, hh);
  g.setLineDash([]);
  const cl = Math.max(6, Math.min(w, hh) * corner);
  g.strokeStyle = color;
  g.lineWidth = lw * 2;
  if (glow) { g.shadowColor = rgba(color, 0.6); g.shadowBlur = glow; }
  g.beginPath();
  g.moveTo(x, y + cl); g.lineTo(x, y); g.lineTo(x + cl, y);
  g.moveTo(x + w - cl, y); g.lineTo(x + w, y); g.lineTo(x + w, y + cl);
  g.moveTo(x + w, y + hh - cl); g.lineTo(x + w, y + hh); g.lineTo(x + w - cl, y + hh);
  g.moveTo(x + cl, y + hh); g.lineTo(x, y + hh); g.lineTo(x, y + hh - cl);
  g.stroke();
  g.restore();
}

/** Small label tag. anchor: 'tl' puts the tag above the point's left. */
export function tag(g, x, y, text, { bg = C.accent, fg = '#0a0c0e', size = 12, a = 1, pad = 6, hgt = null, font = FONT_MONO, weight = 600, anchor = 'bl', r = 3, stroke = null } = {}) {
  if (a <= 0.001) return;
  g.save();
  g.globalAlpha = a;
  g.font = `${weight} ${size}px ${font}`;
  const tw = g.measureText(text).width;
  const th = hgt || Math.round(size * 1.75);
  const w = tw + pad * 2;
  let tx = x, ty = y;
  if (anchor === 'bl') ty = y - th;
  if (anchor === 'c') { tx = x - w / 2; ty = y - th / 2; }
  if (anchor === 'br') { tx = x - w; ty = y - th; }
  if (anchor === 'tr') { tx = x - w; }
  if (bg) { g.fillStyle = bg; rrect(g, tx, ty, w, th, r); g.fill(); }
  if (stroke) { g.strokeStyle = stroke; g.lineWidth = 1; rrect(g, tx + 0.5, ty + 0.5, w - 1, th - 1, r); g.stroke(); }
  g.fillStyle = fg;
  g.textBaseline = 'middle';
  g.fillText(text, tx + pad, ty + th / 2 + 0.5);
  g.restore();
  return { x: tx, y: ty, w, h: th };
}

/** Crosshair / reticle ring used for recognition moments. */
export function reticle(g, x, y, r, { color = C.accent, a = 1, p = 1, spin = 0, lw = 2 } = {}) {
  if (a <= 0.001) return;
  g.save();
  g.globalAlpha = a;
  g.strokeStyle = color;
  g.lineWidth = lw;
  const segs = 4;
  for (let i = 0; i < segs; i++) {
    const a0 = spin + (i / segs) * Math.PI * 2 + 0.18;
    g.beginPath();
    g.arc(x, y, r, a0, a0 + (Math.PI * 2 / segs - 0.36) * p);
    g.stroke();
  }
  g.globalAlpha = a * 0.35;
  g.lineWidth = 1;
  g.beginPath();
  g.arc(x, y, r + 8, 0, Math.PI * 2 * p);
  g.stroke();
  g.restore();
}

/** Viewfinder corner brackets around a rectangle. */
export function brackets(g, x, y, w, hh, { color = 'rgba(255,255,255,0.7)', len = 28, lw = 2, a = 1 } = {}) {
  if (a <= 0.001) return;
  g.save();
  g.globalAlpha = a;
  g.strokeStyle = color;
  g.lineWidth = lw;
  g.beginPath();
  g.moveTo(x, y + len); g.lineTo(x, y); g.lineTo(x + len, y);
  g.moveTo(x + w - len, y); g.lineTo(x + w, y); g.lineTo(x + w, y + len);
  g.moveTo(x + w, y + hh - len); g.lineTo(x + w, y + hh); g.lineTo(x + w - len, y + hh);
  g.moveTo(x + len, y + hh); g.lineTo(x, y + hh); g.lineTo(x, y + hh - len);
  g.stroke();
  g.restore();
}

/** Blinking-free REC indicator + timecode text for camera feeds. */
export function recHud(g, x, y, label, t, { a = 1 } = {}) {
  if (a <= 0.001) return;
  g.save();
  g.globalAlpha = a;
  g.fillStyle = C.coral;
  g.beginPath(); g.arc(x + 6, y + 8, 5, 0, Math.PI * 2); g.fill();
  g.font = `500 13px ${FONT_MONO}`;
  g.fillStyle = 'rgba(255,255,255,0.8)';
  g.textBaseline = 'middle';
  const tc = (s) => { const f = Math.floor((s % 1) * 30); const ss = Math.floor(s) % 60; const mm = Math.floor(s / 60); return `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}:${String(f).padStart(2, '0')}`; };
  g.fillText(`${label}   ${tc(Math.max(0, t))}`, x + 20, y + 8.5);
  g.restore();
}

/** Ease a value toward target with a soft ping (0→1→settle) for UI emphasis. */
export const pop = (t, at, dur = 0.5) => {
  const p = clamp((t - at) / dur);
  return p <= 0 ? 0 : E.outBack(p, 2.2);
};
export { env };
