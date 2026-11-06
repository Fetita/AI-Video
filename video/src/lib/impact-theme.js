// Styles for the impact film, injected as a <style> element on import (applies before frame 0,
// unlike a <link>, which loads asynchronously). The base film stylesheet stays untouched.
const CSS = `
.ix-kicker { font-family: var(--font-ui); font-weight: 600; font-size: 16px; letter-spacing: 0.26em; text-transform: uppercase; color: #c9b4ff; white-space: nowrap; }
.gx-card { position: absolute; left: 0; top: 0; display: inline-flex; flex-direction: column; align-items: center; transform-origin: 0 0; white-space: nowrap; }
.gx-kicker { display: inline-flex; align-items: center; gap: 12px; font-family: var(--font-ui); font-weight: 700; font-size: 17px; letter-spacing: 0.26em; text-transform: uppercase; color: #c9b4ff; }
.gx-ico { width: 40px; height: 40px; border-radius: 50%; background: rgba(130,52,254,0.22); border: 1px solid rgba(130,52,254,0.6); display: flex; align-items: center; justify-content: center; color: #e6dcff; }
.gx-head { position: relative; margin-top: 26px; font-family: var(--font-display); font-stretch: 118%; font-weight: 600; font-size: 74px; letter-spacing: -0.015em; line-height: 1.05; color: #f3f3ef; transform-origin: 50% 50%; }
.gx-under { position: absolute; left: 0; right: 0; bottom: -16px; height: 4px; border-radius: 2px; background: var(--accent-grad); box-shadow: 0 0 16px rgba(130,52,254,0.7); transform-origin: 0 50%; transform: scaleX(0); display: block; }
.gx-chips { display: flex; justify-content: center; align-items: center; gap: 16px; margin-top: 52px; }
.gx-chip { display: flex; align-items: center; gap: 12px; height: 60px; padding: 0 26px 0 18px; border-radius: 999px; background: rgba(14,12,22,0.9); border: 1px solid rgba(130,52,254,0.55);
  color: #e6dcff; font-family: var(--font-ui); font-weight: 600; font-size: 24px; letter-spacing: -0.005em; white-space: nowrap; transform-origin: 50% 50%;
  box-shadow: 0 20px 50px -20px rgba(0,0,0,0.9), 0 0 24px rgba(130,52,254,0.18); }
.gx-arrow { width: 34px; height: 34px; border-radius: 50%; background: rgba(130,52,254,0.28); display: flex; align-items: center; justify-content: center; color: #cdb8ff; }
.gx-stat { display: flex; align-items: center; gap: 28px; margin-top: 40px; padding: 18px 34px 18px 30px; border-radius: 22px; transform-origin: 50% 50%;
  background: linear-gradient(180deg, rgba(130,52,254,0.16), rgba(130,52,254,0.05)), #0f0d16; border: 1px solid rgba(130,52,254,0.45);
  box-shadow: 0 0 40px rgba(130,52,254,0.16), 0 24px 60px -24px rgba(0,0,0,0.85); }
.gx-stat-v { font-family: var(--font-display); font-stretch: 118%; font-weight: 600; font-size: 76px; line-height: 1; letter-spacing: -0.02em; color: #d9caff; text-align: center; }
.gx-stat-k { display: flex; flex-direction: column; gap: 8px; max-width: 470px; white-space: normal; text-align: left; }
.gx-stat-k > span:first-child { font-family: var(--font-ui); font-weight: 500; font-size: 23px; line-height: 1.3; color: var(--text2); }
.gx-note { font-family: var(--font-ui); font-weight: 600; font-size: 12px; letter-spacing: 0.18em; text-transform: uppercase; color: var(--text3); }
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
