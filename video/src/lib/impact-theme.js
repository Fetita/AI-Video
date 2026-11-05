// Styles for the impact film, injected as a <style> element on import (applies before frame 0,
// unlike a <link>, which loads asynchronously). The base film stylesheet stays untouched.
const CSS = `
.ix-kicker { font-family: var(--font-ui); font-weight: 600; font-size: 16px; letter-spacing: 0.26em; text-transform: uppercase; color: #c9b4ff; white-space: nowrap; }
.ix-row { position: absolute; left: 0; top: 0; display: inline-flex; align-items: center; gap: 18px; transform-origin: 0 0; white-space: nowrap; }
.ix-token { display: inline-flex; align-items: center; gap: 14px; height: 72px; padding: 0 28px 0 22px; border-radius: 18px;
  border: 1px solid rgba(255,255,255,0.16); background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0) 60%), #101216;
  box-shadow: 0 24px 60px -24px rgba(0,0,0,0.85), inset 0 1px 0 rgba(255,255,255,0.06);
  font-family: var(--font-ui); font-weight: 600; font-size: 28px; letter-spacing: -0.005em; color: var(--text); transform-origin: 50% 50%; }
.ix-token.ai { border-color: rgba(130,52,254,0.62); background: linear-gradient(180deg, rgba(130,52,254,0.22), rgba(130,52,254,0.07)), #110f1a;
  box-shadow: 0 0 34px rgba(130,52,254,0.2), 0 24px 60px -24px rgba(0,0,0,0.85), inset 0 1px 0 rgba(255,255,255,0.08); }
.ix-token.ai svg { color: #c4adff; }
.ix-token.base svg { color: var(--text2); }
.ix-token.leak { border-color: rgba(255,107,87,0.6); background: linear-gradient(180deg, rgba(255,107,87,0.18), rgba(255,107,87,0.05)), #17100f; }
.ix-token.leak svg { color: var(--coral); }
.ix-op { width: 40px; height: 40px; transform-origin: 50% 50%; }
.ix-paren { font-family: var(--font-display); font-weight: 200; font-size: 104px; line-height: 1; color: var(--text3); margin-top: -10px; transform-origin: 50% 50%; }
.ix-eq { width: 40px; height: 40px; transform-origin: 50% 50%; }
.ix-result { display: inline-flex; align-items: center; gap: 14px; height: 78px; padding: 0 36px 0 38px; border-radius: 999px; background: var(--accent-grad);
  font-family: var(--font-display); font-stretch: 118%; font-weight: 600; font-size: 30px; letter-spacing: 0.08em; text-transform: uppercase; color: #fff;
  box-shadow: 0 0 54px rgba(130,52,254,0.45), inset 0 1px 0 rgba(255,255,255,0.25); position: relative; overflow: hidden; transform-origin: 50% 50%; }
.ix-result .sweep { position: absolute; top: 0; bottom: 0; width: 120px; left: -160px; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.45), transparent); transform: skewX(-18deg); }
.ix-card { position: absolute; overflow: hidden; border-radius: 22px; background: #020304; border: 1px solid rgba(255,255,255,0.09);
  box-shadow: 0 50px 120px -40px rgba(0,0,0,0.9); }
.ix-card .glow { position: absolute; right: -260px; bottom: -320px; width: 1100px; height: 900px; border-radius: 50%;
  background: radial-gradient(closest-side, rgba(82,128,214,0.55), rgba(64,108,196,0.22) 45%, rgba(40,70,140,0) 100%); }
.ix-card h3 { font-family: var(--font-display); font-stretch: 125%; font-weight: 600; font-size: 62px; letter-spacing: -0.01em; line-height: 1; color: #f2f4f8; }
.ix-card p { font-family: var(--font-ui); font-weight: 300; font-size: 27px; line-height: 1.45; color: #b8bdc8; }
.ix-card p b { font-weight: 600; color: #93b2ff; }
.ix-card .lbl { font-family: var(--font-ui); font-weight: 700; font-size: 13px; letter-spacing: 0.22em; text-transform: uppercase; color: #7f9cf5; }
.ix-chip { display: inline-flex; align-items: center; gap: 8px; height: 30px; padding: 0 12px; border-radius: 8px; font-family: var(--font-ui); font-weight: 600;
  font-size: 13px; letter-spacing: 0.12em; text-transform: uppercase; white-space: nowrap; }
.ix-paper { position: absolute; overflow: hidden; border-radius: 18px; background: #f4f1e8; color: #1c1d19; font-family: var(--font-ui);
  box-shadow: 0 60px 140px -40px rgba(0,0,0,0.95), 0 0 0 1px rgba(255,255,255,0.08); }
.ix-paper .k { font-weight: 700; font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase; color: #8a8c80; }
.ix-paper .v { font-weight: 700; font-size: 30px; letter-spacing: -0.01em; color: #1c1d19; font-variant-numeric: tabular-nums; }
.ix-paper .h { font-weight: 700; font-size: 17px; color: #1c1d19; }
.ix-paper .s { font-weight: 500; font-size: 12px; color: #8a8c80; }
.ix-map { position: absolute; display: block; }
.ix-map .lbl { font-family: var(--font-ui); font-weight: 600; font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase; white-space: nowrap; }
`;

if (!document.getElementById('ix-theme')) {
  const st = document.createElement('style');
  st.id = 'ix-theme';
  st.textContent = CSS;
  document.head.append(st);
}

// Size-band colours for onion grading (blue → green → amber → orange) and the paper dashboard ink.
export const BANDS = [
  { label: '< 45 mm', col: '#7f9fd8' },
  { label: '45–60', col: '#5fb07e' },
  { label: '60–75', col: '#e3b34f' },
  { label: '75 mm +', col: '#e0804a' },
];
export const PAPER = { bg: '#f4f1e8', ink: '#1c1d19', mute: '#8a8c80', line: 'rgba(28,29,25,0.12)', grid: 'rgba(28,29,25,0.06)' };
