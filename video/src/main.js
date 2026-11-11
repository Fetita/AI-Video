import { addGlobal, mount, seek, FPS, TIMELINE, h } from './engine.js';
import { makeCaptions } from './lib/captions.js';
import { makeAtmosphere, makeSweep } from './lib/atmosphere.js';

// Scene order comes from the timeline, so an alternate cut (?cut=…) can drop or reorder scenes.
const SCENES = TIMELINE.scenes.map((s) => s.id);

// ---- global background: lit, drifting atmosphere behind every scene (lib/atmosphere.js)
addGlobal({
  setup(stage) { this.update = makeAtmosphere(stage); },
  render(t) { this.update(t); },
});

// ---- a band of light crosses the frame on every scene change
addGlobal({
  setup(stage) { this.update = makeSweep(stage); },
  render(t) { this.update(t); },
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
    '400 20px Manrope', '500 20px Manrope', '600 20px Manrope', '700 20px Manrope',
    '500 20px Archivo', '600 20px Archivo', '700 20px Archivo',
    '400 20px "JetBrains Mono"', '500 20px "JetBrains Mono"', '600 20px "JetBrains Mono"',
    '400 20px Fraunces', '600 20px Fraunces',
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
