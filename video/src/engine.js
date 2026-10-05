// Deterministic motion engine: every frame is a pure function of time t.
// The renderer calls window.__seek(t); nothing animates on its own.
import TL from './timeline.js';

export const W = 1920;
export const H = 1080;
export const FPS = TL.fps;
export const TIMELINE = TL;

// ---------------------------------------------------------------- math
export const clamp = (x, a = 0, b = 1) => (x < a ? a : x > b ? b : x);
export const lerp = (a, b, t) => a + (b - a) * t;
export const invlerp = (a, b, x) => clamp((x - a) / (b - a));
export const remap = (x, a, b, c, d) => lerp(c, d, invlerp(a, b, x));
export const smooth = (t) => t * t * (3 - 2 * t);
export const fract = (x) => x - Math.floor(x);
export const TAU = Math.PI * 2;

export const E = {
  linear: (t) => t,
  inQuad: (t) => t * t,
  outQuad: (t) => 1 - (1 - t) * (1 - t),
  inOutQuad: (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2),
  inCubic: (t) => t * t * t,
  outCubic: (t) => 1 - Math.pow(1 - t, 3),
  inOutCubic: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
  inQuart: (t) => t * t * t * t,
  outQuart: (t) => 1 - Math.pow(1 - t, 4),
  inOutQuart: (t) => (t < 0.5 ? 8 * t * t * t * t : 1 - Math.pow(-2 * t + 2, 4) / 2),
  outQuint: (t) => 1 - Math.pow(1 - t, 5),
  inOutQuint: (t) => (t < 0.5 ? 16 * t ** 5 : 1 - Math.pow(-2 * t + 2, 5) / 2),
  inExpo: (t) => (t === 0 ? 0 : Math.pow(2, 10 * t - 10)),
  outExpo: (t) => (t === 1 ? 1 : 1 - Math.pow(2, -10 * t)),
  inOutExpo: (t) => (t === 0 ? 0 : t === 1 ? 1 : t < 0.5 ? Math.pow(2, 20 * t - 10) / 2 : (2 - Math.pow(2, -20 * t + 10)) / 2),
  inOutSine: (t) => -(Math.cos(Math.PI * t) - 1) / 2,
  outSine: (t) => Math.sin((t * Math.PI) / 2),
  inSine: (t) => 1 - Math.cos((t * Math.PI) / 2),
  outBack: (t, s = 1.4) => 1 + (s + 1) * Math.pow(t - 1, 3) + s * Math.pow(t - 1, 2),
  // Critically-damped-ish settle with a single soft overshoot.
  spring: (t) => 1 - Math.exp(-7 * t) * Math.cos(9 * t * 0.9),
};

/** Eased progress of t through [start, start + dur]. */
export const prog = (t, start, dur, ease = E.inOutCubic) => ease(clamp((t - start) / dur));
/** 0→1 fade in over [a, a+fi], hold, 1→0 over [b-fo, b]. */
export const env = (t, a, b, fi = 0.3, fo = 0.3, ease = E.inOutSine) => {
  if (t < a || t > b) return 0;
  const i = fi > 0 ? ease(clamp((t - a) / fi)) : 1;
  const o = fo > 0 ? ease(clamp((b - t) / fo)) : 1;
  return Math.min(i, o);
};
/** Keyframe interpolation: keys = [[t, value], ...] (numbers or arrays). */
export function keys(t, ks, ease = E.inOutCubic) {
  if (t <= ks[0][0]) return ks[0][1];
  for (let i = 1; i < ks.length; i++) {
    if (t <= ks[i][0]) {
      const [t0, v0] = ks[i - 1];
      const [t1, v1, e] = ks[i];
      const p = (e || ease)((t - t0) / (t1 - t0));
      return Array.isArray(v0) ? v0.map((v, j) => lerp(v, v1[j], p)) : lerp(v0, v1, p);
    }
  }
  return ks[ks.length - 1][1];
}

// ---------------------------------------------------------------- random & noise
export function rng(seed = 1) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
export function hash(...n) {
  let h = 2166136261;
  for (const v of n) {
    h ^= Math.floor(v * 1000) | 0;
    h = Math.imul(h, 16777619);
  }
  h ^= h >>> 13;
  h = Math.imul(h, 0x5bd1e995);
  h ^= h >>> 15;
  return (h >>> 0) / 4294967296;
}

// Simplex noise (2D/3D), seeded.
const GRAD3 = [[1, 1, 0], [-1, 1, 0], [1, -1, 0], [-1, -1, 0], [1, 0, 1], [-1, 0, 1], [1, 0, -1], [-1, 0, -1], [0, 1, 1], [0, -1, 1], [0, 1, -1], [0, -1, -1]];
export function makeNoise(seed = 7) {
  const r = rng(seed);
  const p = new Uint8Array(256).map((_, i) => i);
  for (let i = 255; i > 0; i--) {
    const j = Math.floor(r() * (i + 1));
    [p[i], p[j]] = [p[j], p[i]];
  }
  const perm = new Uint8Array(512);
  for (let i = 0; i < 512; i++) perm[i] = p[i & 255];
  const F2 = 0.5 * (Math.sqrt(3) - 1), G2 = (3 - Math.sqrt(3)) / 6;
  function n2(xin, yin) {
    const s = (xin + yin) * F2;
    const i = Math.floor(xin + s), j = Math.floor(yin + s);
    const t = (i + j) * G2;
    const x0 = xin - (i - t), y0 = yin - (j - t);
    const i1 = x0 > y0 ? 1 : 0, j1 = x0 > y0 ? 0 : 1;
    const x1 = x0 - i1 + G2, y1 = y0 - j1 + G2, x2 = x0 - 1 + 2 * G2, y2 = y0 - 1 + 2 * G2;
    const ii = i & 255, jj = j & 255;
    let n = 0;
    let t0 = 0.5 - x0 * x0 - y0 * y0;
    if (t0 > 0) { const g = GRAD3[perm[ii + perm[jj]] % 12]; t0 *= t0; n += t0 * t0 * (g[0] * x0 + g[1] * y0); }
    let t1 = 0.5 - x1 * x1 - y1 * y1;
    if (t1 > 0) { const g = GRAD3[perm[ii + i1 + perm[jj + j1]] % 12]; t1 *= t1; n += t1 * t1 * (g[0] * x1 + g[1] * y1); }
    let t2 = 0.5 - x2 * x2 - y2 * y2;
    if (t2 > 0) { const g = GRAD3[perm[ii + 1 + perm[jj + 1]] % 12]; t2 *= t2; n += t2 * t2 * (g[0] * x2 + g[1] * y2); }
    return 70 * n;
  }
  function fbm(x, y, oct = 4, lac = 2, gain = 0.5) {
    let a = 1, f = 1, s = 0, norm = 0;
    for (let o = 0; o < oct; o++) { s += a * n2(x * f, y * f); norm += a; a *= gain; f *= lac; }
    return s / norm;
  }
  return { n2, fbm };
}

// ---------------------------------------------------------------- DOM helpers
export function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (k === 'class') el.className = v;
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (k === 'html') el.innerHTML = v;
    else el.setAttribute(k, v);
  }
  for (const c of children.flat()) if (c != null) el.append(c.nodeType ? c : document.createTextNode(String(c)));
  return el;
}
export function svg(tag, attrs = {}, ...children) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  for (const c of children.flat()) if (c) el.append(c);
  return el;
}
/** Set transform/opacity/etc. Numbers for x/y/s/r are composed into a transform. */
export function put(el, o) {
  const st = el.style;
  if ('x' in o || 'y' in o || 's' in o || 'r' in o || 'sx' in o || 'sy' in o || 'z' in o || 'rx' in o || 'ry' in o) {
    const x = o.x || 0, y = o.y || 0, z = o.z || 0;
    let tr = `translate3d(${x.toFixed(2)}px, ${y.toFixed(2)}px, ${z.toFixed(2)}px)`;
    if (o.rx) tr += ` rotateX(${o.rx.toFixed(3)}deg)`;
    if (o.ry) tr += ` rotateY(${o.ry.toFixed(3)}deg)`;
    if (o.r) tr += ` rotate(${o.r.toFixed(3)}deg)`;
    const s = o.s ?? 1;
    const sx = (o.sx ?? 1) * s, sy = (o.sy ?? 1) * s;
    if (sx !== 1 || sy !== 1) tr += ` scale(${sx.toFixed(4)}, ${sy.toFixed(4)})`;
    st.transform = tr;
  }
  if ('o' in o) {
    // Opacity only: toggling `visibility` here would override a hidden parent container.
    st.opacity = clamp(o.o).toFixed(3);
  }
  if ('blur' in o) st.filter = o.blur > 0.05 ? `blur(${o.blur.toFixed(2)}px)` : 'none';
  if ('w' in o) st.width = `${o.w}px`;
  if ('hgt' in o) st.height = `${o.hgt}px`;
  if ('clip' in o) st.clipPath = o.clip;
  return el;
}
export const px = (v) => `${v}px`;

// ---------------------------------------------------------------- canvas helpers
export function makeCanvas(parent, w = W, h = H, cls = 'fill') {
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  c.className = cls;
  if (parent) parent.append(c);
  const ctx = c.getContext('2d');
  return { c, ctx };
}
export function rrect(ctx, x, y, w, hgt, r) {
  const rr = Math.min(r, w / 2, hgt / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + hgt, rr);
  ctx.arcTo(x + w, y + hgt, x, y + hgt, rr);
  ctx.arcTo(x, y + hgt, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}
export function rgba(hex, a = 1) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}
export const C = {
  bg: '#07080a', panel: '#0f1115', text: '#f3f3ef', text2: '#a8acb3', text3: '#6c7179',
  accent: '#8234fe', accent2: '#6686f6', accentText: '#b89cff', coral: '#ff6b57', amber: '#ffc45c', sky: '#3ed6b8', violet: '#ff8fc8', paper: '#f5efe3',
};

// ---------------------------------------------------------------- scene runtime
const scenes = [];
const globals = [];

export function lineInfo(id, sceneStart = 0) {
  const l = TL.lines[id];
  if (!l) throw new Error(`unknown VO line ${id}`);
  return {
    start: l.start - sceneStart,
    end: l.end - sceneStart,
    segs: l.segs.map(([a, b]) => [a - sceneStart, b - sceneStart]),
  };
}

/** Register a scene module. def: {id, pre, post, z, setup(ctx), render(t, ctx)} */
export function addScene(def) {
  const info = TL.scenes.find((s) => s.id === def.id);
  if (!info) throw new Error(`scene ${def.id} not in timeline`);
  const root = h('div', { class: 'scene', 'data-scene': def.id });
  const ctx = {
    id: def.id,
    root,
    start: info.start,
    end: info.end,
    dur: info.end - info.start,
    line: (id) => lineInfo(id, info.start),
    /** Scene-relative start (or end) time of a VO clause. */
    cue: (id, seg = 0, which = 0) => lineInfo(id, info.start).segs[seg][which],
  };
  scenes.push({ def, ctx, pre: def.pre ?? 0.8, post: def.post ?? 0.8, z: def.z ?? scenes.length });
  return ctx;
}
export function addGlobal(def) { globals.push(def); }

export function mount(stage) {
  const sorted = [...scenes].sort((a, b) => a.z - b.z);
  for (const s of sorted) {
    stage.append(s.ctx.root);
    s.def.setup?.(s.ctx);
    s.ctx.root.style.display = 'none';
  }
  for (const g of globals) g.setup?.(stage);
}

/** Render time t. A scene's render may return a promise (e.g. a video frame decoding);
 *  seek then resolves once every such frame is ready, so the renderer never captures a stale frame. */
export function seek(t) {
  const pending = [];
  for (const s of scenes) {
    const active = t >= s.ctx.start - s.pre && t < s.ctx.end + s.post;
    if (active) {
      if (s.ctx.root.style.display !== 'block') s.ctx.root.style.display = 'block';
      const r = s.def.render(t - s.ctx.start, s.ctx, t);
      if (r && typeof r.then === 'function') pending.push(r);
    } else if (s.ctx.root.style.display !== 'none') {
      s.ctx.root.style.display = 'none';
    }
  }
  for (const g of globals) g.render?.(t);
  return pending.length ? Promise.all(pending) : undefined;
}
