// Story-kit art: wooden character pieces and the storybook illustration, both built around the
// supplied character artwork (assets/characters/*.png, cut from the sheets by extract_characters.mjs).
import { h, svg } from '../engine.js';

const CH = 'assets/characters/';

/** How each character sits on a piece's face: image width/left/top in % of the face circle. */
const FACE = {
  sloth: { src: 'sloth-lotus.png', w: 92, x: 4, y: 9 },
  scout: { src: 'scout.png', w: 124, x: -4, y: 8 },
  wizard: { src: 'wizard.png', w: 112, x: -6, y: 4 },
  samurai: { src: 'samurai.png', w: 122, x: -6, y: 6 },
};
export const PIECE_KINDS = Object.keys(FACE);

/** Wooden disc piece (top-down) with a character on its face. Returns an element that fills its parent. */
export function piece(kind, id = kind) {
  const f = FACE[kind];
  const root = h('div', { style: { position: 'absolute', inset: '0' } });
  const base = svg('svg', { viewBox: '-100 -100 200 200', style: 'position:absolute;inset:0;width:100%;height:100%;display:block;overflow:visible' });
  base.innerHTML = `
  <defs>
    <radialGradient id="${id}wood" cx="0.38" cy="0.32" r="0.8"><stop offset="0" stop-color="#e8bd84"/><stop offset="0.6" stop-color="#cf9a5c"/><stop offset="1" stop-color="#a8733f"/></radialGradient>
    <radialGradient id="${id}face" cx="0.5" cy="0.4" r="0.6"><stop offset="0" stop-color="#fff4e2"/><stop offset="1" stop-color="#f1d9b5"/></radialGradient>
  </defs>
  <circle cx="0" cy="0" r="96" fill="#7a4e28"/>
  <circle cx="0" cy="-3" r="94" fill="url(#${id}wood)"/>
  <circle cx="0" cy="-3" r="80" fill="none" stroke="rgba(120,72,30,0.35)" stroke-width="1.5"/>
  <circle cx="0" cy="-3" r="88" fill="none" stroke="rgba(255,240,210,0.25)" stroke-width="1"/>
  <circle cx="0" cy="-3" r="74" fill="url(#${id}face)"/>`;
  // the face: a printed character inset into the wood
  const face = h('div', { style: { position: 'absolute', left: '13%', top: '11.5%', width: '74%', height: '74%', borderRadius: '50%', overflow: 'hidden' } },
    h('img', { src: CH + f.src, style: { position: 'absolute', left: `${f.x}%`, top: `${f.y}%`, width: `${f.w}%`, display: 'block' } }));
  const top = svg('svg', { viewBox: '-100 -100 200 200', style: 'position:absolute;inset:0;width:100%;height:100%;display:block;overflow:visible' });
  top.innerHTML = `
  <circle cx="0" cy="-3" r="74" fill="none" stroke="rgba(90,50,20,0.35)" stroke-width="2.5"/>
  <circle cx="0" cy="-3" r="71" fill="none" stroke="rgba(0,0,0,0.08)" stroke-width="4"/>
  <path d="M-70 -50 A86 86 0 0 1 40 -80" stroke="rgba(255,255,255,0.35)" stroke-width="3" fill="none" stroke-linecap="round"/>`;
  root.append(base, face, top);
  return root;
}

/**
 * Storybook illustration (the left page, 582×672 px): a sunrise forest path where Mo the sloth
 * leads Pip, Wren and Kai. Returns {el, layers, sparkEls}; each layer can be faded in on its own.
 */
export function storyIllustration(id = 'si') {
  const W = 582, H = 672;
  const rnd = (s) => { const x = Math.sin(s * 127.1) * 43758.5453; return x - Math.floor(x); };
  const el = h('div', { style: { position: 'absolute', left: '0', top: '0', width: `${W}px`, height: `${H}px`, overflow: 'hidden', borderRadius: '8px' } });
  const layer = (name, child) => { const L = h('div', { class: `L-${name}`, style: { position: 'absolute', inset: '0' } }, child); el.append(L); return L; };
  const art = (inner) => { const s = svg('svg', { viewBox: `0 0 ${W} ${H}`, width: W, height: H, style: 'position:absolute;inset:0;display:block' }); s.innerHTML = inner; return s; };
  const img = (src, x, y, w, flip = false) => h('img', { src: CH + src, style: { position: 'absolute', left: `${x}px`, top: `${y}px`, width: `${w}px`, display: 'block', transform: flip ? 'scaleX(-1)' : 'none' } });

  const layers = {};
  layers.sky = layer('sky', art(`
    <defs>
      <linearGradient id="${id}sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7d6fc2"/><stop offset="0.42" stop-color="#d79bb5"/><stop offset="0.75" stop-color="#ffc9a0"/><stop offset="1" stop-color="#ffe2b8"/></linearGradient>
    </defs>
    <rect width="${W}" height="${H}" fill="url(#${id}sky)"/>
    ${[[70, 92, 1], [210, 60, 0.8], [470, 110, 1.1]].map(([x, y, s]) => `<g transform="translate(${x},${y}) scale(${s})" fill="#fff1e6" opacity="0.55"><ellipse cx="0" cy="0" rx="46" ry="14"/><ellipse cx="22" cy="-8" rx="26" ry="14"/><ellipse cx="-18" cy="-6" rx="22" ry="11"/></g>`).join('')}`));
  layers.sun = layer('sun', art(`
    <defs><radialGradient id="${id}sun" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#fff3cf" stop-opacity="0.95"/><stop offset="0.35" stop-color="#ffd59a" stop-opacity="0.55"/><stop offset="1" stop-color="#ffb98a" stop-opacity="0"/></radialGradient></defs>
    <circle class="sunglow" cx="372" cy="292" r="190" fill="url(#${id}sun)"/>
    <circle cx="372" cy="292" r="54" fill="#fff0c8"/>`));
  layers.hills = layer('hills', art(`
    <path d="M0 330 Q90 270 190 300 T390 286 T582 300 V672 H0Z" fill="#b48cb8" opacity="0.85"/>
    <path d="M0 372 Q120 320 250 352 T582 338 V672 H0Z" fill="#8fae8a"/>
    <path d="M0 420 Q160 380 300 408 T582 400 V672 H0Z" fill="#6f9e68"/>`));
  const tree = (x, y, s, c1, c2) => `<g transform="translate(${x},${y}) scale(${s})"><rect x="-6" y="-10" width="12" height="40" rx="3" fill="#6b4a33"/><circle cx="0" cy="-52" r="40" fill="${c1}"/><circle cx="-24" cy="-26" r="30" fill="${c1}"/><circle cx="24" cy="-28" r="30" fill="${c2}"/><circle cx="8" cy="-70" r="24" fill="${c2}"/></g>`;
  layers.trees = layer('trees', art(`
    ${tree(40, 420, 1.35, '#4f8a55', '#5f9c62')}${tree(118, 404, 0.85, '#5a945c', '#6aa66a')}${tree(520, 412, 1.25, '#4a8250', '#5a955e')}${tree(452, 396, 0.8, '#5a945c', '#6aa66a')}
    ${tree(250, 352, 0.55, '#6f9f74', '#7cab7c')}${tree(318, 348, 0.5, '#6f9f74', '#7cab7c')}`));
  layers.path = layer('path', art(`
    <path d="M150 672 C210 590 330 560 300 500 C280 460 300 430 330 412 L346 412 C330 432 322 462 344 500 C380 568 330 612 420 672Z" fill="#f1d9a6"/>
    <path d="M150 672 C210 590 330 560 300 500 C280 460 300 430 330 412" fill="none" stroke="#d9b97f" stroke-width="3"/>
    <path d="M0 560 Q110 540 190 600 T300 672 H0Z" fill="#5c9157"/><path d="M582 548 Q470 560 430 620 T420 672 H582Z" fill="#5c9157"/>
    ${Array.from({ length: 22 }, (_, i) => { const x = rnd(i) * W, y = 470 + rnd(i + 40) * 190; return `<path d="M${x.toFixed(1)} ${y.toFixed(1)} q3 -12 6 0 q3 -10 6 0" fill="none" stroke="#4b7f48" stroke-width="2.2" stroke-linecap="round"/>`; }).join('')}`));
  // the three heroes walk up the path behind their guide
  layers.heroes = layer('heroes', h('div', { style: { position: 'absolute', inset: '0' } },
    img('samurai.png', 52, 368, 132),
    img('wizard.png', 150, 392, 138),
    img('scout.png', 22, 440, 168)));
  layers.sloth = layer('sloth', img('sloth-lunge.png', 300, 400, 250));
  const sparks = Array.from({ length: 16 }, (_, i) => `<circle class="spark" cx="0" cy="0" r="${(2 + rnd(i + 31) * 2.2).toFixed(1)}" fill="#fff1c4"/>`).join('');
  layers.sparkles = layer('sparkles', art(sparks));
  return { el, layers, sparkEls: [...el.querySelectorAll('.spark')], sunGlow: el.querySelector('.sunglow') };
}
