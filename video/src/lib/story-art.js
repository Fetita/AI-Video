// Original, fictional story-kit art: wooden pieces and the storybook illustration.

/** Wooden disc piece (top-down). kind: fox | lantern | moon | forest. Returns SVG string (viewBox -100 -100 200 200). */
export function piece(kind, id = kind) {
  const glyph = {
    fox: `
      <path d="M-46 -30 L-34 -64 L-14 -38 Z" fill="#d9652a"/><path d="M-38 -38 L-33 -54 L-22 -40 Z" fill="#3b2418"/>
      <path d="M46 -30 L34 -64 L14 -38 Z" fill="#d9652a"/><path d="M38 -38 L33 -54 L22 -40 Z" fill="#3b2418"/>
      <path d="M-50 -34 Q0 -52 50 -34 Q46 8 0 44 Q-46 8 -50 -34Z" fill="#e8772f"/>
      <path d="M-50 -30 Q-30 -4 -2 6 Q-6 30 0 44 Q-40 14 -50 -30Z" fill="#fff1e0"/>
      <path d="M50 -30 Q30 -4 2 6 Q6 30 0 44 Q40 14 50 -30Z" fill="#fff1e0"/>
      <ellipse cx="-17" cy="-12" rx="5" ry="6.5" fill="#2a1a12"/><ellipse cx="17" cy="-12" rx="5" ry="6.5" fill="#2a1a12"/>
      <circle cx="-15.5" cy="-14" r="1.6" fill="#fff"/><circle cx="18.5" cy="-14" r="1.6" fill="#fff"/>
      <path d="M-7 34 Q0 29 7 34 Q4 42 0 43 Q-4 42 -7 34Z" fill="#2a1a12"/>`,
    lantern: `
      <circle cx="0" cy="6" r="44" fill="url(#${id}glow)"/>
      <path d="M-14 -52 Q0 -66 14 -52" stroke="#2c2622" stroke-width="5" fill="none"/>
      <rect x="-22" y="-50" width="44" height="10" rx="3" fill="#2c2622"/>
      <path d="M-26 -40 H26 L22 30 H-22 Z" fill="#ffd27a"/>
      <path d="M-26 -40 H26 L22 30 H-22 Z" fill="none" stroke="#2c2622" stroke-width="5"/>
      <path d="M0 -40 V30 M-24 -5 H24" stroke="#2c2622" stroke-width="3.5"/>
      <path d="M-8 6 Q0 -16 8 6 Q6 16 0 18 Q-6 16 -8 6Z" fill="#fff6d8"/>
      <rect x="-28" y="30" width="56" height="10" rx="3" fill="#2c2622"/>`,
    moon: `
      <circle cx="0" cy="0" r="58" fill="#1f2a4d"/>
      <circle cx="-30" cy="-34" r="2.4" fill="#fff6d8"/><circle cx="36" cy="-26" r="1.8" fill="#fff6d8"/><circle cx="30" cy="36" r="2" fill="#fff6d8"/><circle cx="-38" cy="28" r="1.5" fill="#fff6d8"/>
      <path d="M12 -38 A40 40 0 1 0 12 38 A30 30 0 1 1 12 -38Z" fill="#ffe6a3"/>`,
    forest: `
      <path d="M-18 44 L-18 30" stroke="#5b3a22" stroke-width="7"/><path d="M-18 -56 L-48 -6 H-34 L-56 30 H20 L-2 -6 H12 Z" fill="#2f6b43"/>
      <path d="M-18 -56 L-48 -6 H-34 L-56 30 H-18 Z" fill="#3b8052"/>
      <path d="M24 44 L24 34" stroke="#5b3a22" stroke-width="6"/><path d="M24 -30 L2 6 H12 L-4 34 H52 L36 6 H46 Z" fill="#24573a"/>
      <path d="M24 -30 L2 6 H12 L-4 34 H24 Z" fill="#2f6b43"/>`,
  }[kind];
  return `<svg viewBox="-100 -100 200 200" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="${id}wood" cx="0.38" cy="0.32" r="0.8"><stop offset="0" stop-color="#e8bd84"/><stop offset="0.6" stop-color="#cf9a5c"/><stop offset="1" stop-color="#a8733f"/></radialGradient>
    <radialGradient id="${id}glow" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#ffd27a" stop-opacity="0.75"/><stop offset="1" stop-color="#ffd27a" stop-opacity="0"/></radialGradient>
    <radialGradient id="${id}face" cx="0.5" cy="0.45" r="0.55"><stop offset="0" stop-color="#f6e6cf"/><stop offset="1" stop-color="#e9d2b0"/></radialGradient>
  </defs>
  <circle cx="0" cy="0" r="96" fill="#7a4e28"/>
  <circle cx="0" cy="-3" r="94" fill="url(#${id}wood)"/>
  <circle cx="0" cy="-3" r="80" fill="none" stroke="rgba(120,72,30,0.35)" stroke-width="1.5"/>
  <circle cx="0" cy="-3" r="88" fill="none" stroke="rgba(255,240,210,0.25)" stroke-width="1"/>
  <circle cx="0" cy="-3" r="74" fill="url(#${id}face)"/>
  <circle cx="0" cy="-3" r="74" fill="none" stroke="rgba(90,50,20,0.25)" stroke-width="2"/>
  <g transform="translate(0,-3) scale(0.92)">${glyph}</g>
  <path d="M-70 -50 A86 86 0 0 1 40 -80" stroke="rgba(255,255,255,0.35)" stroke-width="3" fill="none" stroke-linecap="round"/>
</svg>`;
}

/** Storybook illustration layers for the left page (viewBox 0 0 600 640). Returns {defs, layers:{sky, stars, moon, hills, trees, fox, lantern, fireflies}}. */
export function storyIllustration(id = 'si') {
  const stars = [];
  const rnd = (s) => { const x = Math.sin(s * 127.1) * 43758.5453; return x - Math.floor(x); };
  for (let i = 0; i < 46; i++) stars.push(`<circle class="star" data-i="${i}" cx="${(rnd(i) * 600).toFixed(1)}" cy="${(rnd(i + 99) * 330).toFixed(1)}" r="${(0.8 + rnd(i + 7) * 1.8).toFixed(2)}" fill="#fff6d8"/>`);
  const flies = [];
  for (let i = 0; i < 14; i++) flies.push(`<circle class="fly" data-i="${i}" cx="0" cy="0" r="${(2 + rnd(i + 31) * 2).toFixed(1)}" fill="#ffe28a"/>`);
  return {
    defs: `
      <linearGradient id="${id}sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#141b3a"/><stop offset="0.55" stop-color="#2d3a72"/><stop offset="1" stop-color="#5a5f9a"/></linearGradient>
      <radialGradient id="${id}moonglow" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#fff1c4" stop-opacity="0.55"/><stop offset="1" stop-color="#fff1c4" stop-opacity="0"/></radialGradient>
      <radialGradient id="${id}lglow" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#ffd27a" stop-opacity="0.85"/><stop offset="0.4" stop-color="#ffb84a" stop-opacity="0.35"/><stop offset="1" stop-color="#ffb84a" stop-opacity="0"/></radialGradient>
      <radialGradient id="${id}fglow" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#ffe28a" stop-opacity="0.9"/><stop offset="1" stop-color="#ffe28a" stop-opacity="0"/></radialGradient>`,
    layers: {
      sky: `<rect width="600" height="640" fill="url(#${id}sky)"/>`,
      stars: stars.join(''),
      moon: `<circle cx="430" cy="150" r="130" fill="url(#${id}moonglow)"/><circle cx="430" cy="150" r="62" fill="#fff1c4"/><circle cx="410" cy="136" r="10" fill="#f2dea6"/><circle cx="446" cy="170" r="7" fill="#f2dea6"/><circle cx="452" cy="126" r="5" fill="#f2dea6"/>`,
      hills: `<path d="M0 470 Q150 400 300 440 T600 420 V640 H0Z" fill="#1e2a52"/><path d="M0 540 Q170 470 340 520 T600 500 V640 H0Z" fill="#172142"/>`,
      trees: [[70, 470, 1.25], [140, 500, 0.9], [520, 460, 1.2], [470, 505, 0.85], [560, 520, 0.7]].map(([x, y, s]) =>
        `<g transform="translate(${x},${y}) scale(${s})"><rect x="-5" y="-6" width="10" height="26" fill="#101833"/><path d="M0 -150 L-44 -70 H-26 L-56 -10 H56 L26 -70 H44 Z" fill="#0f1a36"/></g>`).join(''),
      fox: `
        <g transform="translate(270,520)">
          <path d="M40 30 Q120 20 110 -40 Q104 -70 80 -60 Q96 -20 40 0Z" fill="#e8772f"/><path d="M110 -40 Q104 -70 80 -60 Q92 -48 96 -30Z" fill="#fff1e0"/>
          <path d="M-40 34 Q-52 -30 -20 -70 L20 -70 Q52 -30 40 34Z" fill="#e8772f"/>
          <path d="M-18 34 Q-24 -10 0 -34 Q24 -10 18 34Z" fill="#fff1e0"/>
          <path d="M-34 -96 L-26 -134 L-8 -104Z" fill="#d9652a"/><path d="M34 -96 L26 -134 L8 -104Z" fill="#d9652a"/>
          <path d="M-40 -100 Q0 -118 40 -100 Q36 -64 0 -44 Q-36 -64 -40 -100Z" fill="#e8772f"/>
          <path d="M-40 -98 Q-20 -78 -2 -74 Q-2 -56 0 -44 Q-30 -60 -40 -98Z" fill="#fff1e0"/><path d="M40 -98 Q20 -78 2 -74 Q2 -56 0 -44 Q30 -60 40 -98Z" fill="#fff1e0"/>
          <ellipse cx="-14" cy="-88" rx="4" ry="5" fill="#2a1a12"/><ellipse cx="14" cy="-88" rx="4" ry="5" fill="#2a1a12"/>
          <path d="M-5 -52 Q0 -56 5 -52 Q3 -46 0 -45 Q-3 -46 -5 -52Z" fill="#2a1a12"/>
          <path d="M-40 34 Q-44 44 -30 44 H-12 Q-4 44 -8 34Z M40 34 Q44 44 30 44 H12 Q4 44 8 34Z" fill="#c95e27"/>
        </g>`,
      lantern: `
        <g transform="translate(214,470)">
          <circle cx="0" cy="16" r="120" fill="url(#${id}lglow)" class="lglow"/>
          <path d="M30 -60 Q10 -40 0 -26" stroke="#c95e27" stroke-width="8" stroke-linecap="round" fill="none"/>
          <path d="M-8 -26 Q0 -34 8 -26" stroke="#2c2622" stroke-width="3" fill="none"/>
          <rect x="-12" y="-26" width="24" height="6" rx="2" fill="#2c2622"/>
          <path d="M-15 -20 H15 L13 20 H-13Z" fill="#ffd27a" stroke="#2c2622" stroke-width="3"/>
          <path d="M0 -20 V20" stroke="#2c2622" stroke-width="2"/>
          <rect x="-16" y="20" width="32" height="6" rx="2" fill="#2c2622"/>
        </g>`,
      fireflies: flies.join(''),
    },
  };
}
