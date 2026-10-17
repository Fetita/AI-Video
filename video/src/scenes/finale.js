// Finale — the whole studio in one wall, "One team. Design · Build · Ship.",
// every tile collapses into the logo's E strokes → lockup → tagline → CTA.
import { addScene, h, put, prog, E, clamp, lerp, env, makeCanvas, rgba, C, W, H } from '../engine.js';
import { makeLockup } from '../lib/logo.js';
import { STROKES, VIEWBOX, ICON_VIEWBOX } from '../lib/logo-data.js';
import { words, revealWords } from '../lib/ui.js';

const TILES = [
  ['hands', 'Hand tracking'], ['faces', 'Face detection'], ['tracking3d', '3D tracking'], ['dataset', 'Custom datasets'], ['benchmark', 'Model benchmarking'],
  ['robot', 'Robotics data'], ['field', 'Field analytics'], ['conveyor', 'Object tracking'], ['parse', 'LLM parsing'], ['search', 'Search'],
  ['recommend', 'Recommendation'], ['physical', 'Physical → digital'], ['generative', 'Generative AI'], ['documents', 'Document intelligence'], ['readiness', 'Audit readiness'],
];
const COLS = 5, TW = 330, TH = 186, GAP = 16;
const GW = COLS * TW + (COLS - 1) * GAP, GH = 3 * TH + 2 * GAP;

addScene({
  id: 'finale',
  pre: 0.2,
  post: 0.2,
  setup(ctx) {
    const R = ctx.root;
    this.wall = h('div', { class: 'abs', style: { left: '0', top: '0', width: '1920px', height: '1080px', perspective: '1800px' } });
    this.inner = h('div', { class: 'abs', style: { left: '0', top: '0', width: '1920px', height: '1080px', transformOrigin: '960px 540px', transformStyle: 'preserve-3d' } });
    this.wall.append(this.inner);
    this.tiles = TILES.map(([img, label], i) => {
      const el = h('div', { class: 'abs', style: { left: '0', top: '0', width: `${TW}px`, height: `${TH}px`, borderRadius: '12px', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.14)', boxShadow: '0 24px 60px -20px rgba(0,0,0,0.8)', transformOrigin: '50% 50%', background: '#0b0d10' } },
        h('img', { src: `assets/recap/${img}.jpg`, style: { width: '100%', height: '100%', objectFit: 'cover', display: 'block' } }),
        h('div', { style: { position: 'absolute', left: '0', right: '0', bottom: '0', height: '60px', background: 'linear-gradient(180deg, transparent, rgba(0,0,0,0.75))' } }),
        h('div', { class: 'kicker', style: { position: 'absolute', left: '14px', bottom: '12px', color: '#f3f3ef', fontSize: '11.5px', letterSpacing: '0.16em' } }, label));
      const hl = h('div', { style: { position: 'absolute', inset: '0', borderRadius: '12px', boxShadow: 'inset 0 0 0 2px rgba(130,52,254,0.9)', opacity: 0 } });
      el.append(hl);
      this.inner.append(el);
      const c = i % COLS, r = Math.floor(i / COLS);
      return { el, hl, x: (1920 - GW) / 2 + c * (TW + GAP), y: (1080 - GH) / 2 + r * (TH + GAP), c, r };
    });
    R.append(this.wall);
    this.dim = h('div', { class: 'layer', style: { background: 'radial-gradient(ellipse 60% 55% at 50% 50%, rgba(7,8,10,0.92), rgba(7,8,10,0.75))' } });
    R.append(this.dim);
    // statement
    this.one = h('div', { class: 'abs display', style: { left: '0', width: '1920px', top: '392px', textAlign: 'center', fontSize: '118px', fontWeight: 600, letterSpacing: '-0.02em', lineHeight: 1 } }, 'One team.');
    this.dbs = h('div', { class: 'abs', style: { left: '0', width: '1920px', top: '560px', display: 'flex', justifyContent: 'center', gap: '34px', alignItems: 'center' } });
    this.dbsWords = ['Design', 'Build', 'Ship'].map((w, i) => {
      const el = h('span', { class: 'display', style: { fontSize: '64px', fontWeight: 500, letterSpacing: '-0.01em', color: 'var(--text3)' } }, w);
      if (i) this.dbs.append(h('i', { style: { width: '10px', height: '10px', borderRadius: '50%', background: 'var(--accent)', display: 'block' } }));
      this.dbs.append(el);
      return el;
    });
    R.append(this.one, this.dbs);
    // collapse strokes (canvas)
    const cv = makeCanvas(R);
    this.g = cv.ctx;
    // lockup
    this.lock = makeLockup({ height: 92 });
    this.lock.el.style.position = 'relative';
    this.lockWrap = h('div', { class: 'abs', style: { left: '0', top: '0' } }, this.lock.el);
    R.append(this.lockWrap);
    this.tagline = h('div', { class: 'abs', style: { left: '0', width: '1920px', top: '642px', textAlign: 'center', fontSize: '46px', fontWeight: 450, letterSpacing: '-0.015em', color: 'var(--text)' } });
    this.tagSpans = words(this.tagline, 'From AI ideas to real-world products.');
    R.append(this.tagline);
    this.cta = h('div', { class: 'abs', style: { left: '0', width: '1920px', top: '760px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '18px' } });
    this.ctaBtn = h('div', { style: { display: 'flex', alignItems: 'center', gap: '16px', height: '66px', padding: '0 34px', borderRadius: '999px', background: 'var(--accent-grad)', color: '#ffffff', fontSize: '25px', fontWeight: 600, letterSpacing: '-0.005em', boxShadow: '0 0 40px rgba(130,52,254,0.35)' } }, 'Let’s build what’s next', h('span', { style: { fontSize: '26px' } }, '→'));
    this.url = h('div', { class: 'kicker', style: { color: 'var(--text2)', fontSize: '15px', letterSpacing: '0.22em' } }, 'eagerworks.com');
    this.cta.append(this.ctaBtn, this.url);
    R.append(this.cta);
    this.black = h('div', { class: 'layer', style: { background: '#000', zIndex: 60 } });
    R.append(this.black);
  },

  render(t, ctx) {
    const g = this.g;
    g.clearRect(0, 0, W, H);
    const D = ctx.dur;
    const cDiff = ctx.cue('f1', 0), cOne = ctx.cue('f1', 1), cBuild = ctx.cue('f1', 2), cName = ctx.cue('f2', 0), cTag = ctx.cue('f3', 0), cCta = ctx.cue('f4', 0);
    const collapse = prog(t, cName - 1.25, 0.95, E.inOutCubic);

    // ---------- the wall assembles, pulses through every capability, then dims under the statement
    const tilt = lerp(9, 4, prog(t, 0, cName, E.linear));
    this.inner.style.transform = `rotateX(${tilt.toFixed(2)}deg) rotateY(${(-tilt * 0.6).toFixed(2)}deg) scale(${lerp(1.06, 0.98, prog(t, 0, cName, E.linear)).toFixed(4)})`;
    // icon position (centered build) → stroke targets on screen
    const lh = this.lock.height, sc = lh / VIEWBOX[3];
    const iconW = lh * (ICON_VIEWBOX[2] / VIEWBOX[3]);
    if (!this.lockW) { const r = this.lock.el.getBoundingClientRect(); if (r.width > 10) this.lockW = r.width; }
    const lw = this.lockW || 1500;
    const lx = (1920 - lw) / 2, ly = 520 - lh / 2 - 60;
    const slide = prog(t, cName + 0.2, 1.1, E.inOutCubic);
    const iconShift = (lw / 2 - iconW / 2) * (1 - slide);
    const stroke = (k, u) => { const s = STROKES[k]; return { x: lx + iconShift + (lerp(s.x1, s.x2, u) - VIEWBOX[0]) * sc, y: ly + (lerp(s.y1, s.y2, u) - VIEWBOX[1]) * sc }; };
    this.tiles.forEach((tl, i) => {
      const d = Math.hypot(tl.c - 2, tl.r - 1);
      const inP = prog(t, -0.15 + d * 0.08, 0.7, E.outCubic);
      const pulse = env(t, cDiff - 0.1 + i * 0.075, cDiff + 0.35 + i * 0.075, 0.08, 0.25);
      tl.hl.style.opacity = pulse.toFixed(3);
      // collapse: each tile flies onto one of the three E strokes and becomes a line
      const k = i % 3, u = (Math.floor(i / 3) + 0.5) / 5;
      const target = stroke(k, u);
      const cp = clamp(collapse * 1.35 - (i / TILES.length) * 0.35);
      const e = E.inOutCubic(cp);
      const x = lerp(tl.x, target.x - TW / 2, e), y = lerp(tl.y, target.y - TH / 2, e);
      const sx = lerp(lerp(0.7, 1, inP), 0.16, e), sy = lerp(lerp(0.7, 1, inP), 0.03, e);
      const rot = lerp(0, -33, e);
      tl.el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, ${((1 - inP) * -300).toFixed(1)}px) rotate(${rot.toFixed(2)}deg) scale(${sx.toFixed(4)}, ${sy.toFixed(4)})`;
      tl.el.style.opacity = (inP * (1 - clamp((cp - 0.75) / 0.25))).toFixed(3);
      tl.el.style.filter = cp > 0.4 ? `brightness(${(1 + cp * 2).toFixed(2)}) saturate(0)` : 'none';
      tl.el.style.borderColor = cp > 0.3 ? 'rgba(130,52,254,0.9)' : 'rgba(255,255,255,0.14)';
    });
    const dimA = env(t, cOne - 0.3, cName - 0.9, 0.4, 0.45);
    this.dim.style.opacity = dimA.toFixed(3);
    put(this.one, { y: (1 - prog(t, cOne - 0.05, 0.5, E.outCubic)) * 24, o: prog(t, cOne - 0.05, 0.4) * (1 - prog(t, cName - 1.45, 0.3)) });
    const wordAt = [cOne + 0.75, cBuild, cBuild + 0.55];
    this.dbsWords.forEach((w, i) => {
      const q = prog(t, wordAt[i] - 0.05, 0.35, E.outCubic);
      w.style.color = q > 0.5 ? '#ffffff' : 'var(--text3)';
      w.style.textShadow = q > 0.5 ? '0 0 30px rgba(130,52,254,0.35)' : 'none';
    });
    put(this.dbs, { o: prog(t, cOne + 0.3, 0.4) * (1 - prog(t, cName - 1.45, 0.3)) });

    // ---------- lockup builds from the collapsed strokes
    const la = prog(t, cName - 0.45, 0.2);
    put(this.lockWrap, { x: lx + iconShift, y: ly, o: la * (1 - prog(t, D - 0.8, 0.5)) });
    this.lock.set({
      strokes: prog(t, cName - 0.45, 0.4),
      outline: prog(t, cName - 0.25, 0.7),
      fill: prog(t, cName + 0.35, 0.55),
      letters: prog(t, cName + 0.45, 0.9),
      studio: prog(t, cName + 1.05, 0.7),
      glow: env(t, cName + 0.4, cName + 2.4, 0.3, 1.2),
    });
    revealWords(this.tagSpans, prog(t, cTag - 0.05, 1.7, E.linear), { rise: 10, soft: 2.5, blur: 4 });
    put(this.tagline, { o: 1 - prog(t, D - 0.8, 0.5) });
    const ca = prog(t, cCta - 0.1, 0.55, E.outBack);
    put(this.ctaBtn, { s: lerp(0.8, 1, Math.min(1.05, ca)), o: clamp(ca * 2) * (1 - prog(t, D - 0.8, 0.5)) });
    put(this.url, { o: prog(t, cCta + 0.5, 0.5) * (1 - prog(t, D - 0.8, 0.5)) });
    // final fade to black
    this.black.style.opacity = prog(t, D - 0.6, 0.6, E.inOutSine).toFixed(3);
    // accent sweep under the tagline when it completes
    const sw = prog(t, cTag + 1.6, 0.6, E.inOutCubic);
    if (sw > 0 && t < D - 0.4) {
      g.save(); g.globalAlpha = 1 - prog(t, D - 0.8, 0.5);
      g.fillStyle = C.accent; g.shadowColor = 'rgba(130,52,254,0.7)'; g.shadowBlur = 14;
      g.fillRect(960 - 60 * sw, 722, 120 * sw, 3);
      g.restore();
    }
  },
});
