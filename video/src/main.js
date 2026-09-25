import { addGlobal, mount, seek, makeCanvas, W, H, FPS, TIMELINE, h } from './engine.js';

const SCENES = ['hook', 'search', 'story', 'vision', 'agri', 'docs', 'finale'];

// ---- global background: deep graphite with a soft top light and a faint engineering grid
addGlobal({
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

// ---- vignette on top of everything (film grain is added in the delivery encode)
addGlobal({
  setup(stage) {
    stage.append(h('div', {
      class: 'layer',
      style: { zIndex: 900, background: 'radial-gradient(ellipse 85% 80% at 50% 50%, transparent 55%, rgba(0,0,0,0.42) 100%)' },
    }));
  },
});

async function boot() {
  const params = new URLSearchParams(location.search);
  const only = params.get('only')?.split(',');
  const list = only ? SCENES.filter((s) => only.includes(s)) : SCENES;
  for (const name of list) await import(`./scenes/${name}.js`);
  const stage = document.getElementById('stage');
  mount(stage);
  await document.fonts.ready;
  // Force-load every face we use so the first frame is never a fallback.
  await Promise.all([
    '400 20px Inter', '500 20px Inter', '600 20px Inter', '700 20px Inter',
    '500 20px Archivo', '600 20px Archivo', '700 20px Archivo',
    '400 20px "JetBrains Mono"', '500 20px "JetBrains Mono"', '600 20px "JetBrains Mono"',
    '400 20px Fraunces', 'italic 400 20px Fraunces', '600 20px Fraunces',
  ].map((f) => document.fonts.load(f)));
  await Promise.all([...document.images].map((im) => im.decode().catch(() => {})));
  window.__seek = (t) => seek(t);
  window.__duration = TIMELINE.duration;
  window.__fps = FPS;
  seek(0);
  window.__ready = true;
}

boot().catch((e) => {
  window.__error = String(e && e.stack ? e.stack : e);
  console.error(e);
});
