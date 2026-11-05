import { addGlobal, mount, seek, makeCanvas, W, H, FPS, TIMELINE, h, BRAND } from './engine.js';
import { makeCaptions } from './lib/captions.js';

// Scene order comes from the timeline, so an alternate cut (?cut=…) can drop or reorder scenes.
const SCENES = TIMELINE.scenes.map((s) => s.id);

// ---- global background: deep graphite with a soft top light and a faint engineering grid
// (FS Studio: brand charcoal, the brand's "+" grid and a slow emotional-layer glow; see plusGrid below)
if (BRAND.id === 'fsstudio') addGlobal(plusGrid());
else addGlobal({
  setup(stage) {
    const bg = h('div', { class: 'layer', style: { zIndex: 0 } });
    const { c, ctx } = makeCanvas(bg);
    const g = ctx.createRadialGradient(W * 0.5, H * 0.18, 0, W * 0.5, H * 0.35, W * 0.75);
    g.addColorStop(0, '#15181d');
    g.addColorStop(0.45, '#0c0e11');
    g.addColorStop(1, '#060708');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    stage.prepend(bg);
    this.grid = h('div', {
      class: 'layer',
      style: {
        zIndex: 0,
        backgroundImage: 'linear-gradient(rgba(255,255,255,0.028) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.028) 1px, transparent 1px)',
        backgroundSize: '48px 48px',
        maskImage: 'radial-gradient(ellipse 70% 60% at 50% 45%, #000 20%, transparent 80%)',
        webkitMaskImage: 'radial-gradient(ellipse 70% 60% at 50% 45%, #000 20%, transparent 80%)',
      },
    });
    bg.after(this.grid);
  },
  render(t) {
    this.grid.style.backgroundPosition = `${(t * 6) % 48}px ${(t * 3) % 48}px`;
  },
});

// ---- burned-in captions (only for cuts that ask for them)
if (TIMELINE.captions) {
  addGlobal({
    setup(stage) { this.update = makeCaptions(stage); },
    render(t) { this.update(t); },
  });
}

// ---- vignette on top of everything (film grain is added in the delivery encode)
addGlobal({
  setup(stage) {
    stage.append(h('div', {
      class: 'layer',
      style: { zIndex: 900, background: 'radial-gradient(ellipse 85% 80% at 50% 50%, transparent 55%, rgba(0,0,0,0.42) 100%)' },
    }));
  },
});

/** FS Studio's background: #2F2F2F charcoal, a drifting "+" grid tinted pink → orange (the brand book's
 *  technical layer) and two soft, slow colour fields (its emotional layer), kept faint so interfaces stay legible. */
function plusGrid() {
  const STEP = 64, ARM = 5;
  return {
    setup(stage) {
      const bg = h('div', { class: 'layer', style: { zIndex: 0 } });
      const { ctx } = makeCanvas(bg);
      const g = ctx.createRadialGradient(W * 0.5, H * 0.2, 0, W * 0.5, H * 0.4, W * 0.75);
      g.addColorStop(0, '#363636');
      g.addColorStop(0.5, '#2a2a2a');
      g.addColorStop(1, '#1e1e1e');
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, W, H);
      stage.prepend(bg);
      // emotional layer: two blurred colour fields that drift slowly
      this.fields = [['255,5,159', 0.11], ['57,218,224', 0.08]].map(([rgb, a]) => {
        const el = h('div', { class: 'layer', style: { zIndex: 0, background: `radial-gradient(circle at 50% 50%, rgba(${rgb},${a}), transparent 60%)`, width: '1400px', height: '1400px', left: '-700px', top: '-700px' } });
        bg.after(el);
        return el;
      });
      // technical layer: the "+" grid, drawn once with room to drift by one cell
      const grid = h('div', { class: 'layer', style: { zIndex: 0, maskImage: 'radial-gradient(ellipse 72% 64% at 50% 46%, #000 15%, transparent 82%)', webkitMaskImage: 'radial-gradient(ellipse 72% 64% at 50% 46%, #000 15%, transparent 82%)' } });
      const { c, ctx: q } = makeCanvas(grid, W + STEP, H + STEP);
      c.style.width = `${W + STEP}px`; c.style.height = `${H + STEP}px`;
      const tint = q.createLinearGradient(W + STEP, 0, 0, H + STEP);
      tint.addColorStop(0, 'rgba(255,5,159,0.26)');
      tint.addColorStop(1, 'rgba(255,154,67,0.22)');
      q.strokeStyle = tint;
      q.lineWidth = 1.5;
      q.beginPath();
      for (let y = STEP / 2; y < H + STEP; y += STEP) for (let x = STEP / 2; x < W + STEP; x += STEP) {
        q.moveTo(x - ARM, y); q.lineTo(x + ARM, y); q.moveTo(x, y - ARM); q.lineTo(x, y + ARM);
      }
      q.stroke();
      this.gridCanvas = c;
      this.fields[this.fields.length - 1].after(grid);
    },
    render(t) {
      this.gridCanvas.style.transform = `translate(${(-((t * 6) % STEP)).toFixed(2)}px, ${(-((t * 3) % STEP)).toFixed(2)}px)`;
      const p = [[0.22 + 0.06 * Math.sin(t * 0.11), 0.25 + 0.08 * Math.cos(t * 0.09)], [0.8 + 0.05 * Math.cos(t * 0.1), 0.78 + 0.06 * Math.sin(t * 0.13)]];
      this.fields.forEach((el, i) => { el.style.transform = `translate(${(p[i][0] * W).toFixed(1)}px, ${(p[i][1] * H).toFixed(1)}px)`; });
    },
  };
}

/** Apply the cut's brand: data-brand on <html> (for brands/<id>.css) and the brand stylesheet itself. */
async function applyBrand() {
  if (BRAND.id === 'eagerworks') return;
  document.documentElement.dataset.brand = BRAND.id;
  document.title = `${BRAND.name} — film`;
  const link = h('link', { rel: 'stylesheet', href: `src/brands/${BRAND.id}.css` });
  const loaded = new Promise((res) => { link.onload = res; link.onerror = res; });
  document.head.append(link);
  await loaded;
}

async function boot() {
  await applyBrand();
  const params = new URLSearchParams(location.search);
  const only = params.get('only')?.split(',');
  const list = only ? SCENES.filter((s) => only.includes(s)) : SCENES;
  for (const name of list) await import(`./scenes/${name}.js`);
  const stage = document.getElementById('stage');
  mount(stage);
  await document.fonts.ready;
  // Force-load every face we use so the first frame is never a fallback.
  await Promise.all([
    '400 20px Manrope', '500 20px Manrope', '600 20px Manrope', '700 20px Manrope',
    '500 20px Archivo', '600 20px Archivo', '700 20px Archivo',
    '400 20px "JetBrains Mono"', '500 20px "JetBrains Mono"', '600 20px "JetBrains Mono"',
    '400 20px Fraunces', '600 20px Fraunces',
    ...(BRAND.fonts.ui === 'Manrope' ? [] : [300, 400, 500, 600, 700, 800].map((w) => `${w} 20px ${BRAND.fonts.ui}`)),
  ].map((f) => document.fonts.load(f)));
  await Promise.all([...document.images].map((im) => im.decode().catch(() => {})));
  window.__seek = (t) => seek(t);
  window.__duration = TIMELINE.duration;
  window.__fps = FPS;
  await seek(0);
  window.__ready = true;
}

boot().catch((e) => {
  window.__error = String(e && e.stack ? e.stack : e);
  console.error(e);
});
