// Close — the hand-off line becomes the value chain again: six problems (coral) → six results (the ledger:
// what the grower gains at each station, each station turning violet as its row lands) → one season; the
// ledger rows fly onto the logo's three E strokes, the Eagerworks AI Studio lockup builds, "Impact you can
// see, from seed to shelf." and the CTA.
import { addScene, h, put, prog, E, clamp, lerp, env, makeCanvas, rgba, C, W, H } from '../engine.js';
import { words, revealWords } from '../lib/ui.js';
import { seg } from '../lib/vo.js';
import { makeLockup } from '../lib/logo.js';
import { STROKES, VIEWBOX, ICON_VIEWBOX } from '../lib/logo-data.js';
import { CHAIN, BIG, drawLine, makeValueChain } from '../lib/chain.js';
import { STATIONS, GAINS, statText } from '../lib/impact-data.js';
import { icon } from '../lib/icons.js';
import '../lib/impact-theme.js';

const ROW_H = 66, ROW_W = 1320, LEDGER_Y = 330;

addScene({
  id: 'impact-close',
  pre: 0.2,
  post: 0.2,
  setup(ctx) {
    const R = ctx.root;
    this.cv = makeCanvas(R);
    this.g = this.cv.ctx;
    this.cSix = seg(ctx, 'z1', 0); this.cResults = seg(ctx, 'z1', 1); this.cOne = seg(ctx, 'z1', 2);
    this.cWorth = seg(ctx, 'z2', 0); this.cMeasure = seg(ctx, 'z2', 1);
    this.cName = seg(ctx, 'z3', 0); this.cCta = seg(ctx, 'z4', 0);
    this.chain = makeValueChain(R);
    // ledger rows
    this.rows = STATIONS.map((st, i) => {
      const gn = GAINS[st.id];
      const f = h('div', { style: { display: 'flex', alignItems: 'center', gap: '22px', flex: '1', minWidth: '0', fontFamily: 'var(--font-ui)', whiteSpace: 'nowrap' } },
        h('span', { style: { width: '230px', flex: 'none', fontWeight: '700', fontSize: '14px', letterSpacing: '0.2em', textTransform: 'uppercase', color: '#c9b4ff' } }, gn.kicker),
        h('span', { style: { fontWeight: '600', fontSize: '23px', color: '#f3f3ef' } }, gn.headline),
        gn.stat ? h('span', { class: 'tnum', style: { marginLeft: 'auto', fontFamily: 'var(--font-display)', fontStretch: '118%', fontWeight: '600', fontSize: '26px', color: '#d9caff' } }, statText(gn.stat) + (gn.stat.note ? '*' : '')) : null);
      const el = h('div', { class: 'abs', style: { left: `${(1920 - ROW_W) / 2}px`, top: `${LEDGER_Y + i * (ROW_H + 10)}px`, width: `${ROW_W}px`, height: `${ROW_H}px`, display: 'flex', alignItems: 'center', gap: '22px', padding: '0 26px 0 14px', borderRadius: '16px', background: 'rgba(15,17,21,0.92)', border: '1px solid rgba(255,255,255,0.12)', boxShadow: '0 20px 50px -24px rgba(0,0,0,0.9)', transformOrigin: '50% 50%' } },
        h('span', { style: { width: '42px', height: '42px', borderRadius: '50%', background: 'rgba(130,52,254,0.2)', border: '1px solid rgba(130,52,254,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#e6dcff', flex: 'none' } }, icon(st.icon, { size: 24 })),
        h('span', { class: 'kicker', style: { width: '138px', color: 'var(--text2)', fontSize: '13px', flex: 'none' } }, `${String(i + 1).padStart(2, '0')} ${st.label}`),
        f);
      R.append(el);
      return el;
    });
    this.sum = h('div', { class: 'abs', style: { left: '0', width: '1920px', top: `${LEDGER_Y + 6 * (ROW_H + 10) + 18}px`, textAlign: 'center' } },
      h('span', { class: 'ix-kicker', style: { fontSize: '16px', letterSpacing: '0.3em' } }, 'One season · six results'),
      h('div', { class: 'kicker', style: { marginTop: '12px', fontSize: '11px', color: 'var(--text3)' } }, '* Illustrative estimates'));
    R.append(this.sum);
    // strokes canvas (rows collapse into the E strokes)
    this.lock = makeLockup({ height: 92 });
    this.lock.el.style.position = 'relative';
    this.lockWrap = h('div', { class: 'abs', style: { left: '0', top: '0' } }, this.lock.el);
    R.append(this.lockWrap);
    this.tagline = h('div', { class: 'abs', style: { left: '0', width: '1920px', top: '642px', textAlign: 'center', fontSize: '46px', fontWeight: '450', letterSpacing: '-0.015em', color: 'var(--text)' } });
    this.tagSpans = words(this.tagline, 'Impact you can see, from seed to shelf.');
    R.append(this.tagline);
    this.cta = h('div', { class: 'abs', style: { left: '0', width: '1920px', top: '760px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '18px' } });
    this.ctaBtn = h('div', { style: { display: 'flex', alignItems: 'center', gap: '16px', height: '66px', padding: '0 34px', borderRadius: '999px', background: 'var(--accent-grad)', color: '#ffffff', fontSize: '25px', fontWeight: '600', letterSpacing: '-0.005em', boxShadow: '0 0 40px rgba(130,52,254,0.35)' } }, 'Let’s build what’s next', h('span', { style: { fontSize: '26px' } }, '→'));
    this.url = h('div', { class: 'kicker', style: { color: 'var(--text2)', fontSize: '15px', letterSpacing: '0.22em' } }, 'eagerworks.com');
    this.cta.append(this.ctaBtn, this.url);
    R.append(this.cta);
    this.black = h('div', { class: 'layer', style: { background: '#000', zIndex: '60' } });
    R.append(this.black);
  },

  render(t, ctx) {
    const g = this.g;
    g.clearRect(0, 0, W, H);
    const D = ctx.dur;

    // ---------------- the line → the value chain → moves up as the ledger lands
    if (t >= 0) drawLine(g, CHAIN.x0, CHAIN.x1, CHAIN.y, { a: 1 - prog(t, 0.2, 0.5) });
    const up = prog(t, this.cResults - 0.15, 0.7, E.inOutCubic);
    const fold = prog(t, this.cMeasure + 0.5, 0.8, E.inOutCubic);
    const s = lerp(1, 0.78, up);
    const cy = lerp(BIG.y, 196, up);
    const rowAt = (i) => this.cResults + 0.45 + i * 0.14;
    this.chain.set({
      draw: prog(t, 0.05, 0.6, E.inOutCubic),
      prog: prog(t, this.cOne - 0.1, 0.6, E.inOutCubic),
      node: (i) => prog(t, this.cSix - 0.25 + i * 0.07, 0.4),
      lit: (i) => prog(t, rowAt(i) + 0.15, 0.3),
      labels: 1,
      a: 1 - fold,
      x: 960 - 960 * s, y: cy - BIG.y * s, s,
    });

    // ---------------- ledger: six results, then they fly onto the logo's E strokes
    const lh = this.lock.height, sc = lh / VIEWBOX[3];
    const iconW = lh * (ICON_VIEWBOX[2] / VIEWBOX[3]);
    if (!this.lockW) { const r = this.lock.el.getBoundingClientRect(); if (r.width > 10) this.lockW = r.width; }
    const lw = this.lockW || 1500;
    const lx = (1920 - lw) / 2, ly = 520 - lh / 2 - 60;
    const slide = prog(t, this.cName + 0.2, 1.1, E.inOutCubic);
    const iconShift = (lw / 2 - iconW / 2) * (1 - slide);
    const stroke = (k, u) => { const st = STROKES[k]; return { x: lx + iconShift + (lerp(st.x1, st.x2, u) - VIEWBOX[0]) * sc, y: ly + (lerp(st.y1, st.y2, u) - VIEWBOX[1]) * sc }; };
    const collapse = prog(t, this.cName - 1.25, 0.95, E.inOutCubic);
    this.rows.forEach((el, i) => {
      const q = prog(t, rowAt(i), 0.45, E.outCubic);
      const pulse = env(t, this.cOne + i * 0.07, this.cOne + 0.5 + i * 0.07, 0.1, 0.3);
      const k = i % 3, u = (Math.floor(i / 3) + 0.5) / 2;
      const target = stroke(k, u);
      const cp = clamp(collapse * 1.35 - (i / 6) * 0.35);
      const e = E.inOutCubic(cp);
      const x0 = 0, y0 = (1 - q) * 18;
      const cx0 = 960, cy0 = LEDGER_Y + i * (ROW_H + 10) + ROW_H / 2;
      const x = lerp(x0, target.x - cx0, e), y = lerp(y0, target.y - cy0, e);
      const sx = lerp(1, 0.05, e), sy = lerp(1, 0.06, e);
      el.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) rotate(${lerp(0, -31, e).toFixed(2)}deg) scale(${sx.toFixed(4)}, ${sy.toFixed(4)})`;
      el.style.opacity = (q * (1 - clamp((cp - 0.75) / 0.25))).toFixed(3);
      el.style.borderColor = pulse > 0.05 || cp > 0.3 ? `rgba(130,52,254,${Math.max(pulse, cp).toFixed(3)})` : 'rgba(255,255,255,0.12)';
      el.style.boxShadow = pulse > 0.05 ? `0 0 ${(30 * pulse).toFixed(1)}px rgba(130,52,254,0.45)` : '0 20px 50px -24px rgba(0,0,0,0.9)';
      el.style.filter = cp > 0.4 ? `brightness(${(1 + cp * 2).toFixed(2)})` : 'none';
    });
    put(this.sum, { o: prog(t, this.cOne + 0.3, 0.5) * (1 - prog(t, this.cName - 1.4, 0.4)), y: (1 - prog(t, this.cOne + 0.3, 0.5, E.outCubic)) * 10 });

    // ---------------- lockup, tagline, CTA
    const la = prog(t, this.cName - 0.45, 0.2);
    put(this.lockWrap, { x: lx + iconShift, y: ly, o: la * (1 - prog(t, D - 0.8, 0.5)) });
    this.lock.set({
      strokes: prog(t, this.cName - 0.45, 0.4),
      outline: prog(t, this.cName - 0.25, 0.7),
      fill: prog(t, this.cName + 0.35, 0.55),
      letters: prog(t, this.cName + 0.45, 0.9),
      studio: prog(t, this.cName + 1.05, 0.7),
      glow: env(t, this.cName + 0.4, this.cName + 2.4, 0.3, 1.2),
    });
    const tagAt = (this.cName + 1.6 + this.cCta) / 2 - 0.4;
    revealWords(this.tagSpans, prog(t, tagAt, 1.2, E.linear), { rise: 10, soft: 2.5, blur: 4 });
    put(this.tagline, { o: 1 - prog(t, D - 0.8, 0.5) });
    const ca = prog(t, this.cCta - 0.1, 0.55, E.outBack);
    put(this.ctaBtn, { s: lerp(0.8, 1, Math.min(1.05, ca)), o: clamp(ca * 2) * (1 - prog(t, D - 0.8, 0.5)) });
    put(this.url, { o: prog(t, this.cCta + 0.5, 0.5) * (1 - prog(t, D - 0.8, 0.5)) });
    this.black.style.opacity = prog(t, D - 0.6, 0.6, E.inOutSine).toFixed(3);
    const sw = prog(t, tagAt + 1.2, 0.6, E.inOutCubic);
    if (sw > 0 && t < D - 0.4) {
      g.save(); g.globalAlpha = 1 - prog(t, D - 0.8, 0.5);
      g.fillStyle = C.accent; g.shadowColor = 'rgba(130,52,254,0.7)'; g.shadowBlur = 14;
      g.fillRect(960 - 60 * sw, 722, 120 * sw, 3);
      g.restore();
    }
  },
});
