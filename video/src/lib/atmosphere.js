// The film's "air": a deep graphite stage lit by two slow brand-coloured lights, with dust drifting
// through it at different depths and a faint engineering grid. Everything is a pure function of time.
// A fine temporal dither is laid over the gradients so they survive 8-bit capture without banding.
import { h, makeCanvas, rng, W, H, TAU, clamp, lerp, FPS, TIMELINE, hash, smooth } from '../engine.js';

const LIGHTS = [
  // colour, base position, drift radius, radius, strength, speed, phase
  { c: [130, 52, 254], x: 0.24, y: 0.18, dx: 0.10, dy: 0.07, r: 0.62, a: 0.165, w: 0.11, ph: 0.0 },
  { c: [102, 134, 246], x: 0.80, y: 0.74, dx: 0.09, dy: 0.08, r: 0.66, a: 0.125, w: 0.083, ph: 2.1 },
  { c: [150, 96, 255], x: 0.52, y: 1.06, dx: 0.16, dy: 0.03, r: 0.50, a: 0.11, w: 0.067, ph: 4.0 },
];

function sprite(size, soft) {
  const { c, ctx } = makeCanvas(null, size, size, '');
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, 'rgba(214,204,255,1)');
  g.addColorStop(soft, 'rgba(200,188,255,0.55)');
  g.addColorStop(1, 'rgba(190,176,255,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  return c;
}

export function makeAtmosphere(stage) {
  const layer = h('div', { class: 'layer', style: { zIndex: 0 } });
  const { c, ctx: g } = makeCanvas(layer);
  stage.prepend(layer);

  // static base: soft top light on graphite
  const base = makeCanvas(null, W, H, '');
  {
    const b = base.ctx;
    const grad = b.createRadialGradient(W * 0.5, H * 0.16, 0, W * 0.5, H * 0.36, W * 0.78);
    grad.addColorStop(0, '#14161d');
    grad.addColorStop(0.45, '#0b0c11');
    grad.addColorStop(1, '#050508');
    b.fillStyle = grad;
    b.fillRect(0, 0, W, H);
  }
  // dither tile
  const noise = makeCanvas(null, 256, 256, '');
  {
    const r = rng(99);
    const im = noise.ctx.createImageData(256, 256);
    for (let i = 0; i < im.data.length; i += 4) { const v = Math.floor(r() * 256); im.data[i] = v; im.data[i + 1] = v; im.data[i + 2] = v; im.data[i + 3] = 255; }
    noise.ctx.putImageData(im, 0, 0);
  }
  const pattern = g.createPattern(noise.c, 'repeat');

  // dust: far = small and crisp, near = large, soft and faint
  const r = rng(2024);
  const far = sprite(32, 0.35), near = sprite(96, 0.5);
  const dust = Array.from({ length: 84 }, () => {
    const z = 0.12 + r() * 0.88;
    return { x: r(), y: r(), z, vx: (0.006 + r() * 0.01) / (0.35 + z), vy: -(0.004 + r() * 0.008) / (0.35 + z), ph: r() * TAU, w: 0.4 + r() * 0.9, wob: r() * TAU };
  });

  const grid = h('div', {
    class: 'layer',
    style: {
      zIndex: 0,
      backgroundImage: 'linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)',
      backgroundSize: '48px 48px',
      maskImage: 'radial-gradient(ellipse 70% 60% at 50% 45%, #000 15%, transparent 78%)',
      webkitMaskImage: 'radial-gradient(ellipse 70% 60% at 50% 45%, #000 15%, transparent 78%)',
    },
  });
  layer.after(grid);

  // the lights swell for a moment whenever the film moves to a new scene
  const cuts = TIMELINE.scenes.slice(1).map((s) => s.start);
  const D = TIMELINE.duration;

  return (t) => {
    g.globalCompositeOperation = 'source-over';
    g.globalAlpha = 1;
    g.drawImage(base.c, 0, 0);
    let swell = 0;
    for (const ct of cuts) { const d = t - ct; if (d > -0.5 && d < 1.6) swell = Math.max(swell, d < 0 ? smooth(1 + d / 0.5) : 1 - smooth(d / 1.6)); }
    const life = lerp(0.45, 1, smooth(clamp(t / 1.4))) * (1 - smooth(clamp((t - (D - 1.4)) / 1.2)));
    g.globalCompositeOperation = 'lighter';
    for (const L of LIGHTS) {
      const x = (L.x + Math.sin(t * L.w + L.ph) * L.dx) * W;
      const y = (L.y + Math.cos(t * L.w * 0.8 + L.ph * 1.7) * L.dy) * H;
      const rad = L.r * W * (1 + 0.06 * Math.sin(t * L.w * 1.9 + L.ph));
      const a = L.a * life * (1 + 0.55 * swell) * (0.9 + 0.1 * Math.sin(t * 0.5 + L.ph));
      const gr = g.createRadialGradient(x, y, 0, x, y, rad);
      const [cr, cg, cb] = L.c;
      gr.addColorStop(0, `rgba(${cr},${cg},${cb},${a.toFixed(4)})`);
      gr.addColorStop(0.35, `rgba(${cr},${cg},${cb},${(a * 0.48).toFixed(4)})`);
      gr.addColorStop(0.7, `rgba(${cr},${cg},${cb},${(a * 0.12).toFixed(4)})`);
      gr.addColorStop(1, `rgba(${cr},${cg},${cb},0)`);
      g.fillStyle = gr;
      g.fillRect(0, 0, W, H);
    }
    for (const p of dust) {
      const depth = 1 - p.z;                       // 0 far … 1 near
      const x = ((((p.x + p.vx * t + Math.sin(t * 0.21 * p.w + p.wob) * 0.008) % 1) + 1) % 1) * (W + 240) - 120;
      const y = ((((p.y + p.vy * t + Math.cos(t * 0.17 * p.w + p.wob) * 0.008) % 1) + 1) % 1) * (H + 240) - 120;
      const size = lerp(2.6, 54, depth * depth);
      const tw = 0.62 + 0.38 * Math.sin(t * p.w + p.ph);
      g.globalAlpha = lerp(0.42, 0.035, Math.sqrt(depth)) * tw * life;
      g.drawImage(depth > 0.45 ? near : far, x - size / 2, y - size / 2, size, size);
    }
    // dither (one pattern offset per output frame, so motion-blur sub-frames don't average it away)
    const f = Math.floor(t * FPS + 1e-4);
    g.globalAlpha = 0.016;
    g.save();
    g.translate(Math.floor(hash(f, 1) * 256), Math.floor(hash(f, 2) * 256));
    g.fillStyle = pattern;
    g.fillRect(-256, -256, W + 512, H + 512);
    g.restore();
    g.globalAlpha = 1;
    g.globalCompositeOperation = 'source-over';
    grid.style.backgroundPosition = `${((t * 6) % 48).toFixed(2)}px ${((t * 3) % 48).toFixed(2)}px`;
  };
}

/** A soft band of light that crosses the frame at every scene change (screened over the picture). */
export function makeSweep(stage) {
  const band = h('div', {
    class: 'layer',
    style: {
      zIndex: 700, left: '-1920px', width: '5760px', mixBlendMode: 'screen', willChange: 'transform, opacity',
      background: 'linear-gradient(104deg, transparent 38%, rgba(102,134,246,0.10) 44%, rgba(130,52,254,0.30) 48.5%, rgba(214,200,255,0.50) 50%, rgba(130,52,254,0.30) 51.5%, rgba(102,134,246,0.10) 56%, transparent 62%)',
    },
  });
  stage.append(band);
  const cuts = TIMELINE.scenes.slice(1).map((s) => s.start);
  return (t) => {
    let p = -1;
    for (const ct of cuts) { const q = (t - (ct - 0.3)) / 0.75; if (q > 0 && q < 1) p = q; }
    if (p < 0) { band.style.opacity = '0'; return; }
    const e = p * p * (3 - 2 * p);
    band.style.transform = `translate3d(${lerp(-1700, 1700, e).toFixed(1)}px, 0, 0)`;
    band.style.opacity = (Math.sin(Math.PI * p) ** 0.8 * 0.85).toFixed(3);
  };
}
