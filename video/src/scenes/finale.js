// Finale — the whole studio in one wall, "One team. Design · Build · Ship.", every tile collapses into three
// strokes of violet light, which are the light tubes of the 3D logo (a Blender plate, scripts/render_logo.py):
// the camera pulls back off them, the black-glass icon turns white-hot and lands as the flat lockup → tagline → CTA.
import { addScene, h, put, prog, E, clamp, lerp, env, makeCanvas, rgba, C, W, H } from '../engine.js';
import { makeLockup } from '../lib/logo.js';
import { VIEWBOX, ICON_VIEWBOX } from '../lib/logo-data.js';
import { words, revealWords } from '../lib/ui.js';
import { makeClip } from '../lib/clip.js';

// mirrored in scripts/render_logo.py
const LOGO3D = { frames: 90, fps: 30, move: 2.5, endHeight: 300 };
// where the three light tubes sit in the plate's first frames (screen px): the tiles collapse onto them
const TUBES = [[700, 470, 1090, 50], [670, 670, 940, 390], [620, 960, 1010, 560]];
const LOCK_H = 132;

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
    // the 3D logo plate (transparent frames, composited over the film's atmosphere)
    this.plate = h('div', { class: 'abs', style: { left: '0', top: '0', width: '1920px', height: '1080px', opacity: 0 } });
    this.logo3d = makeClip(this.plate, { name: 'logo', frames: LOGO3D.frames, fps: LOGO3D.fps, ext: 'png' });
    R.append(this.plate);
    // lockup (scaled about the icon's centre while it takes over from the plate)
    this.lock = makeLockup({ height: LOCK_H });
    this.lock.el.style.position = 'relative';
    const iconW = LOCK_H * (ICON_VIEWBOX[2] / VIEWBOX[3]);
    this.lockWrap = h('div', { class: 'abs', style: { left: '0', top: '0', transformOrigin: `${(iconW / 2).toFixed(1)}px ${LOCK_H / 2}px` } }, this.lock.el);
    R.append(this.lockWrap);
    this.tagline = h('div', { class: 'abs', style: { left: '0', width: '1920px', top: '606px', textAlign: 'center', fontSize: '58px', fontWeight: 450, letterSpacing: '-0.015em', color: 'var(--text)' } });
    this.tagSpans = words(this.tagline, 'From AI ideas to real-world products.');
    R.append(this.tagline);
    this.cta = h('div', { class: 'abs', style: { left: '0', width: '1920px', top: '762px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '18px' } });
    this.ctaBtn = h('div', { style: { display: 'flex', alignItems: 'center', gap: '18px', height: '80px', padding: '0 42px', borderRadius: '999px', background: 'var(--accent-grad)', color: '#ffffff', fontSize: '30px', fontWeight: 600, letterSpacing: '-0.005em', boxShadow: '0 0 40px rgba(130,52,254,0.35)' } }, 'Let’s build what’s next', h('span', { style: { fontSize: '31px' } }, '→'));
    this.url = h('div', { class: 'kicker', style: { color: 'var(--text2)', fontSize: '19px', letterSpacing: '0.22em' } }, 'eagerworks.com');
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
    const t3d = cName - (LOGO3D.move - 0.05);        // first frame of the 3D plate
    const tau = t - t3d;
    const tCol = t3d - 0.8;                          // the wall starts collapsing
    const collapse = prog(t, tCol, 0.95, E.inOutCubic);
    const fadeOut = 1 - prog(t, D - 0.8, 0.5);

    // ---------- the wall assembles, pulses through every capability, then dims under the statement
    const tilt = lerp(9, 4, prog(t, 0, tCol, E.linear));
    this.inner.style.transform = `rotateX(${tilt.toFixed(2)}deg) rotateY(${(-tilt * 0.6).toFixed(2)}deg) scale(${lerp(1.06, 0.98, prog(t, 0, tCol, E.linear)).toFixed(4)})`;
    this.tiles.forEach((tl, i) => {
      const d = Math.hypot(tl.c - 2, tl.r - 1);
      const inP = prog(t, -0.15 + d * 0.08, 0.7, E.outCubic);
      const pulse = env(t, cDiff - 0.1 + i * 0.075, cDiff + 0.35 + i * 0.075, 0.08, 0.25);
      tl.hl.style.opacity = pulse.toFixed(3);
      // collapse: each tile flies onto one of the three light tubes and becomes a stroke of light
      const k = i % 3, u = (Math.floor(i / 3) + 0.5) / 5;
      const [x1, y1, x2, y2] = TUBES[k];
      const cp = clamp(collapse * 1.35 - (i / TILES.length) * 0.35);
      const e = E.inOutCubic(cp);
      const x = lerp(tl.x, lerp(x1, x2, u) - TW / 2, e), y = lerp(tl.y, lerp(y1, y2, u) - TH / 2, e);
      const len = Math.hypot(x2 - x1, y2 - y1) / 5;
      const sx = lerp(lerp(0.7, 1, inP), (len * 1.04) / TW, e), sy = lerp(lerp(0.7, 1, inP), 0.045, e);
      const rot = lerp(0, (Math.atan2(y2 - y1, x2 - x1) * 180) / Math.PI, e);
      tl.el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, ${((1 - inP) * -300).toFixed(1)}px) rotate(${rot.toFixed(2)}deg) scale(${sx.toFixed(4)}, ${sy.toFixed(4)})`;
      tl.el.style.opacity = (inP * (1 - prog(t, t3d + 0.05, 0.3))).toFixed(3);
      // the picture drains away and the tile becomes a bar of violet light
      const lit = clamp((cp - 0.3) / 0.4);
      tl.el.style.filter = cp > 0.2 ? `brightness(${(1 + cp * 0.22).toFixed(2)})` : 'none';
      tl.el.style.borderColor = lit > 0 ? 'rgba(184,156,255,0.95)' : 'rgba(255,255,255,0.14)';
      tl.el.style.background = lit > 0 ? '#8f4bff' : '#0b0d10';
      tl.el.style.boxShadow = lit > 0 ? `0 0 ${(60 * lit).toFixed(0)}px ${(14 * lit).toFixed(0)}px rgba(130,52,254,${(0.85 * lit).toFixed(3)})` : '0 24px 60px -20px rgba(0,0,0,0.8)';
      for (const child of tl.el.children) if (child !== tl.hl) child.style.opacity = (1 - lit).toFixed(3);
    });
    const dimA = env(t, cOne - 0.3, tCol + 0.35, 0.4, 0.45);
    this.dim.style.opacity = dimA.toFixed(3);
    put(this.one, { y: (1 - prog(t, cOne - 0.05, 0.5, E.outCubic)) * 24, o: prog(t, cOne - 0.05, 0.4) * (1 - prog(t, tCol - 0.2, 0.3)) });
    const wordAt = [cOne + 0.75, cBuild, cBuild + 0.55];
    this.dbsWords.forEach((w, i) => {
      const q = prog(t, wordAt[i] - 0.05, 0.35, E.outCubic);
      w.style.color = q > 0.5 ? '#ffffff' : 'var(--text3)';
      w.style.textShadow = q > 0.5 ? '0 0 30px rgba(130,52,254,0.35)' : 'none';
    });
    put(this.dbs, { o: prog(t, cOne + 0.3, 0.4) * (1 - prog(t, tCol - 0.2, 0.3)) });

    // ---------- the 3D logo: aura, plate, and a ring of light as the glass turns white
    const in3d = prog(t, t3d, 0.3, E.inOutSine);
    const handover = prog(t, cName + 0.02, 0.3, E.inOutSine);   // plate → flat lockup
    let pending;
    this.plate.style.opacity = (in3d * (1 - handover)).toFixed(3);
    if (in3d > 0 && handover < 1) pending = this.logo3d.show(Math.max(0, tau));
    if (in3d > 0 && t < cName + 2.2) {
      const ignite = prog(t, t3d + 0.1, 0.9, E.outCubic), white = prog(t, t3d + 1.5, 0.95, E.inOutSine);
      const a = (0.34 * ignite * (1 - white * 0.4)) * (1 - prog(t, cName + 0.9, 1.3)) * in3d;
      const r = lerp(760, 520, prog(t, t3d, LOGO3D.move, E.inOutSine));
      const gr = g.createRadialGradient(960, 540, 0, 960, 540, r);
      gr.addColorStop(0, `rgba(130,52,254,${a.toFixed(4)})`);
      gr.addColorStop(0.45, `rgba(112,90,250,${(a * 0.42).toFixed(4)})`);
      gr.addColorStop(1, 'rgba(102,134,246,0)');
      g.fillStyle = gr; g.fillRect(0, 0, W, H);
      const ring = prog(t, t3d + 2.05, 1.1, E.outCubic);
      if (ring > 0 && ring < 1) {
        g.save();
        g.strokeStyle = `rgba(184,156,255,${(0.75 * (1 - ring) ** 1.5).toFixed(4)})`;
        g.lineWidth = lerp(5, 1, ring);
        g.shadowColor = 'rgba(130,52,254,0.9)'; g.shadowBlur = 24;
        g.beginPath(); g.arc(960, 540, lerp(150, 980, ring), 0, Math.PI * 2); g.stroke();
        g.restore();
      }
    }

    // ---------- the flat lockup takes over from the plate's last frame, then settles into place
    const lh = LOCK_H;
    const iconW = lh * (ICON_VIEWBOX[2] / VIEWBOX[3]);
    if (!this.lockW) { const r = this.lock.el.getBoundingClientRect(); if (r.width > 10) this.lockW = r.width / (this.lockS || 1); }
    const lw = this.lockW || 1500;
    const lx = (1920 - lw) / 2, ly = 448 - lh / 2;
    const settle = prog(t, cName + 0.22, 1.05, E.inOutCubic);
    const sc = lerp(LOGO3D.endHeight / lh, 1, settle);
    this.lockS = sc;
    const cx = lerp(960, lx + iconW / 2, settle), cy = lerp(540, ly + lh / 2, settle);
    put(this.lockWrap, { x: cx - iconW / 2, y: cy - lh / 2, s: sc, o: handover * fadeOut });
    this.lock.set({ strokes: 1, outline: 1, fill: 1, letters: prog(t, cName + 0.62, 0.9), studio: prog(t, cName + 1.2, 0.7), glow: env(t, cName, cName + 2.6, 0.3, 1.4) });
    revealWords(this.tagSpans, prog(t, cTag - 0.05, 1.7, E.linear), { rise: 10, soft: 2.5, blur: 4 });
    put(this.tagline, { o: fadeOut });
    const ca = prog(t, cCta - 0.1, 0.55, E.outBack);
    put(this.ctaBtn, { s: lerp(0.8, 1, Math.min(1.05, ca)), o: clamp(ca * 2) * fadeOut });
    put(this.url, { o: prog(t, cCta + 0.5, 0.5) * fadeOut });
    // final fade to black
    this.black.style.opacity = prog(t, D - 0.6, 0.6, E.inOutSine).toFixed(3);
    // accent sweep under the tagline when it completes
    const sw = prog(t, cTag + 1.6, 0.6, E.inOutCubic);
    if (sw > 0 && t < D - 0.4) {
      g.save(); g.globalAlpha = fadeOut;
      g.fillStyle = C.accent; g.shadowColor = 'rgba(130,52,254,0.7)'; g.shadowBlur = 14;
      g.fillRect(960 - 70 * sw, 706, 140 * sw, 3);
      g.restore();
    }
    return pending;
  },
});
