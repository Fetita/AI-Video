// Brand table. A cut picks its brand with "brand" in its vo_script (copied into the timeline);
// the engine exposes the chosen entry as BRAND, C (hex palette) and P (palette as "r,g,b" triplets).
// Every scene colours itself from these tokens, so a brand re-colours the film without touching the scenes.
// The CSS side lives in styles.css (Eagerworks defaults) and brands/<id>.css (overrides).

export const BRANDS = {
  eagerworks: {
    id: 'eagerworks',
    name: 'Eagerworks AI Studio',
    url: 'eagerworks.com',
    fonts: { ui: 'Manrope', display: 'Archivo' },
    recap: 'assets/recap',
    C: {
      bg: '#07080a', bg2: '#0b0d10', panel: '#0f1115', text: '#f3f3ef', text2: '#a8acb3', text3: '#6c7179',
      accent: '#8234fe', accent2: '#6686f6', accentText: '#b89cff', coral: '#ff6b57', amber: '#ffc45c', sky: '#3ed6b8', violet: '#ff8fc8', paper: '#f5efe3',
      okBg: '#1e1538', badBg: '#2a1411', chipText: '#e4d8ff', lime: '#e9ffb3',
    },
    P: { bg: '7,8,10', acc: '130,52,254', acc2: '102,134,246', coral: '255,107,87', amber: '255,196,92', sky: '62,214,184' },
    copy: {
      disciplines: ['Product strategy', 'UX / UI design', 'Software engineering', 'Cloud & data'],
      disciplineSep: null,
      introHead: 'Designers & engineers.',
      introSub: 'We build digital products, from the first idea to launch.',
      pillars: [
        ['Listen', 'Your people, your users, and the problem behind the request.'],
        ['Adapt', 'Flexible and agile, as your needs change.'],
        ['Stay', 'Side by side, until it really works.'],
      ],
    },
  },

  // FS Studio (brand book, Oct 2019): charcoal #2F2F2F statement pages, pink #FF059F → purple #8154B1,
  // cyan #39DAE0, the "+" grid, and one geometric typeface (Europa; Figtree stands in, see docs/fsstudio-treatment.md).
  fsstudio: {
    id: 'fsstudio',
    name: 'FS Studio',
    url: 'fsstudio.com',
    fonts: { ui: 'Figtree', display: 'Figtree' },
    recap: 'assets/recap-fsstudio',
    captionBg: 'rgba(30,30,30,0.86)',
    partner: true, // closing credit: "In partnership with" + the Eagerworks logo, small and muted
    C: {
      bg: '#262626', bg2: '#2b2b2b', panel: '#303030', text: '#f2f2f2', text2: '#bcbcbc', text3: '#8e8e8e',
      accent: '#ff059f', accent2: '#8154b1', accentText: '#ff80c8', coral: '#ff3b30', amber: '#ffc543', sky: '#39dae0', violet: '#ff9a43', paper: '#f5efe3',
      okBg: '#3d1530', badBg: '#3d1716', chipText: '#ffd6ee', lime: '#e3f0a0',
      cyan: '#39dae0', orange: '#ff9a43',
    },
    P: { bg: '38,38,38', acc: '255,5,159', acc2: '129,84,177', coral: '255,59,48', amber: '255,197,67', sky: '57,218,224' },
    copy: {
      disciplines: ['Innovative tech', 'Solid code', 'Creative vision', 'Strategic capability'],
      disciplineSep: '+',
      introHead: 'Technologists & designers.',
      introSub: 'We solve product and R&D challenges, from idea to launch.',
      pillars: [
        ['Ask', 'The right questions: your people, your users, the problem behind the request.'],
        ['Adapt', 'Agile and flexible, as your needs change.'],
        ['Stay', 'Side by side, until it really works.'],
      ],
    },
  },
};
